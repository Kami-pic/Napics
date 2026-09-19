"""测速探测 Probe（todo §6）。仅 qb 通道。

一批候选各经 napics submit 推进 qB → 拿 hash（空则按 media_name 回落匹配）→
每 PROBE_INTERVAL 查 dlspeed → 有效阈值内、稳定窗口取最快 → 选定一条、删其余。
整批失败进下一批；资源耗尽 → RETRY_EXHAUSTED。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from adapters.napics_client import NapicsClient, NapicsError
from adapters.qb_client import QbClient
from config import Config
from models import QbState, Resource

logger = logging.getLogger("nas_download_mcp.probe")


@dataclass
class ProbeCandidate:
    resource: Resource
    napics_task_id: str = ""
    qb_hash: str = ""
    last_speed: int = 0
    submitted: bool = False
    failed: bool = False


@dataclass
class ProbeResult:
    selected: Optional[ProbeCandidate] = None
    all_candidates: list[ProbeCandidate] = field(default_factory=list)
    exhausted: bool = False


class Prober:
    def __init__(self, cfg: Config, napics: NapicsClient, qb: QbClient):
        self.cfg = cfg
        self.napics = napics
        self.qb = qb

    def _submit_one(self, res: Resource, media_name: str, save_path: str, idem: str) -> ProbeCandidate:
        cand = ProbeCandidate(resource=res)
        try:
            r = self.napics.submit_download(
                download_url=res.download_url,
                media_name=media_name,
                save_path=save_path,
                idempotency_key=idem,
            )
        except NapicsError as e:
            logger.warning("[probe] submit 失败: %s", e)
            cand.failed = True
            return cand
        if not r["success"]:
            cand.failed = True
            return cand
        cand.submitted = True
        cand.napics_task_id = r["task_id"]
        cand.qb_hash = r["qb_hash"]
        # 空 hash 回落（§2.2）：优先 magnet 本可靠拿，非 magnet 空 hash 按名字匹配
        if not cand.qb_hash:
            fallback = self.qb.find_hash_by_name(media_name, save_path)
            if fallback:
                cand.qb_hash = fallback
            else:
                logger.warning("[probe] 候选拿不到 qb_hash，判失败: %s", res.title)
                cand.failed = True
        return cand

    async def probe_batch(
        self, resources: list[Resource], media_name: str, save_path: str, idem_prefix: str
    ) -> list[ProbeCandidate]:
        """对一批候选并发 submit + 测速，返回选定（selected）在前的候选列表。"""
        cands: list[ProbeCandidate] = []
        for i, res in enumerate(resources):
            # magnet 优先（更易拿到可靠 hash）——排序把 magnet 提前
            cand = self._submit_one(res, media_name, save_path, f"{idem_prefix}-{i}")
            cands.append(cand)

        alive = [c for c in cands if c.submitted and c.qb_hash and not c.failed]
        if not alive:
            return cands

        deadline = time.time() + self.cfg.probe_timeout_seconds
        min_speed = self.cfg.probe_min_speed_bytes
        first_valid_at: Optional[float] = None

        while time.time() < deadline:
            for c in alive:
                st = self.qb.info(c.qb_hash)
                c.last_speed = st.download_speed_bytes
                if st.state in (QbState.ERROR,):
                    c.failed = True
            alive = [c for c in alive if not c.failed]
            if not alive:
                break

            valid = [c for c in alive if c.last_speed > min_speed]
            if valid:
                # 稳定窗口：首个达标后再观察 STABILIZATION_WINDOW，取最快（§24）
                if first_valid_at is None:
                    first_valid_at = time.time()
                if time.time() - first_valid_at >= self.cfg.stabilization_window_seconds:
                    best = max(valid, key=lambda c: c.last_speed)
                    best_first = [best] + [c for c in cands if c is not best]
                    return best_first
            await asyncio.sleep(self.cfg.probe_interval_seconds)

        # 超时：若有达标的取最快，否则整批失败
        valid = [c for c in cands if c.submitted and c.qb_hash and c.last_speed > min_speed and not c.failed]
        if valid:
            best = max(valid, key=lambda c: c.last_speed)
            return [best] + [c for c in cands if c is not best]
        return cands

    def cleanup_batch(self, cands: list[ProbeCandidate], keep: Optional[ProbeCandidate]) -> None:
        """删掉同批未选中的 qB 种子（deleteFiles=True 删 probe 临时数据；禁删媒体库文件）。"""
        for c in cands:
            if keep is not None and c is keep:
                continue
            if c.qb_hash:
                try:
                    self.qb.delete(c.qb_hash, delete_files=True)
                except Exception as e:
                    logger.warning("[probe] 删种失败 %s: %s", c.qb_hash, e)

    async def run(
        self, all_resources: list[Resource], media_name: str, save_path: str, idem_prefix: str
    ) -> ProbeResult:
        """按 batch_size 分批探测，直到选出一条或资源耗尽。"""
        # magnet 候选优先（§6 拿 hash 更可靠）
        ordered = sorted(all_resources, key=lambda r: (0 if r.is_magnet() else 1))
        batch = self.cfg.probe_batch_size
        collected: list[ProbeCandidate] = []
        for start in range(0, len(ordered), batch):
            chunk = ordered[start : start + batch]
            cands = await self.probe_batch(chunk, media_name, save_path, f"{idem_prefix}-b{start}")
            collected.extend(cands)
            selected = cands[0] if cands and cands[0].submitted and cands[0].qb_hash and not cands[0].failed \
                and cands[0].last_speed > self.cfg.probe_min_speed_bytes else None
            if selected is not None:
                self.cleanup_batch(cands, keep=selected)
                return ProbeResult(selected=selected, all_candidates=collected)
            # 整批失败：清掉本批
            self.cleanup_batch(cands, keep=None)
        return ProbeResult(selected=None, all_candidates=collected, exhausted=True)
