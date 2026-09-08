"""Workflow —— Task 状态机（todo §4/§7/§8）。

铁律（§8/§78）：run() 必须 try/finally，cleanup 在 finally，绝不 if success 才 cleanup，
否则异常时容器一直占内存。cleanup best-effort。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from adapters.napics_client import NapicsClient, NapicsError
from adapters.qb_client import QbClient
from config import Config
from db import Db
from models import (
    Constraints,
    DownloadMovieInput,
    ErrorCode,
    QbState,
    Resource,
    Stage,
    TaskStatus,
)
from notifier import Notifier
from probe import Prober
from service_manager import ServiceManager, ServiceStartError

logger = logging.getLogger("nas_download_mcp.workflow")


def _res_matches(res: Resource, c: Optional[Constraints]) -> bool:
    """按约束筛候选（4k / <50g）。约束缺省即不限。"""
    if c is None:
        return True
    if c.max_size_gb is not None and res.size_gb is not None and res.size_gb > c.max_size_gb:
        return False
    if c.min_resolution:
        want = c.min_resolution.lower().replace("4k", "2160p")
        got = (res.resolution or "").lower()
        # 简单档位：要 2160p 就必须命中 2160/4k
        if "2160" in want and not ("2160" in got or "4k" in got):
            return False
    return True


class Workflow:
    def __init__(self, cfg: Config, db: Db):
        self.cfg = cfg
        self.db = db
        self.notifier = Notifier(cfg.notify_channel)

    def _event(self, task_id: str, kind: str, detail=None) -> None:
        self.db.add_event(task_id, kind, detail)

    def _set(self, task_id: str, status: TaskStatus, stage: Stage, **extra) -> None:
        self.db.update_task(task_id, status=status.value, current_stage=stage.value, **extra)

    async def run(self, task_id: str, inp: DownloadMovieInput) -> None:
        """完整下载 workflow。任何异常都经 finally cleanup。"""
        napics = NapicsClient(self.cfg.napics_api_base, self.cfg.napics_agent_token)
        qb = QbClient(self.cfg.qb_url, self.cfg.qb_username, self.cfg.qb_password)
        from adapters.docker_adapter import DockerAdapter

        svc = ServiceManager(self.cfg, DockerAdapter.from_config(self.cfg))
        selected_hash = ""
        try:
            # 1) 启动服务
            self._set(task_id, TaskStatus.STARTING, Stage.STARTING_SERVICES)
            self._event(task_id, "SERVICE_STARTING")
            try:
                await svc.ensure_started()
            except ServiceStartError as e:
                self._fail(task_id, ErrorCode(e.code) if e.code in ErrorCode._value2member_map_ else ErrorCode.SERVICE_START_FAILED, str(e))
                return
            self._set(task_id, TaskStatus.STARTING, Stage.SERVICES_READY)
            self._event(task_id, "SERVICE_HEALTHY")

            # 2) 搜索
            self._set(task_id, TaskStatus.SEARCHING, Stage.SEARCHING)
            self._event(task_id, "SEARCH_STARTED")
            queries = inp.queries or [f"{inp.original_title or inp.title} {inp.year or ''}".strip()]
            results: list[Resource] = []
            for q in queries:
                try:
                    hits = napics.search(
                        query=q, media_type=inp.media_type, title=inp.title,
                        year=inp.year, season=inp.season,
                    )
                except NapicsError as e:
                    self._fail(task_id, ErrorCode.SEARCH_FAILED, str(e))
                    return
                results.extend(hits)
                if hits:
                    break  # 首个有结果的 query 即止（回退链）
            # 去重（按 download_url）+ 约束筛选
            seen, uniq = set(), []
            for r in results:
                if r.download_url and r.download_url not in seen:
                    seen.add(r.download_url)
                    uniq.append(r)
            candidates = [r for r in uniq if _res_matches(r, inp.constraints)]
            self._event(task_id, "SEARCH_COMPLETED", {"total": len(uniq), "matched": len(candidates)})
            if not candidates:
                self._fail(task_id, ErrorCode.NO_RESULTS, "无匹配资源（4k/<50g）")
                return

            # 3) 测速探测
            self._set(task_id, TaskStatus.PROBING, Stage.PROBING_RESOURCES)
            self._event(task_id, "PROBE_STARTED")
            save_path = inp.save_path or ""
            prober = Prober(self.cfg, napics, qb)
            probe_res = await prober.run(candidates, inp.title, save_path, f"probe-{task_id}")
            if probe_res.exhausted or probe_res.selected is None:
                self._fail(task_id, ErrorCode.PROBE_EXHAUSTED, "所有资源探测失败/资源耗尽")
                return
            selected = probe_res.selected
            selected_hash = selected.qb_hash
            self.db.set_qb_hashes(task_id, [selected_hash])
            self.db.update_task(task_id, selected_qb_hash=selected_hash,
                                napics_task_id=selected.napics_task_id, save_path=save_path)
            self._event(task_id, "RESOURCE_SELECTED", {"title": selected.resource.title, "hash": selected_hash})

            # 4) 正式下载监控（不再用 10KB/120s 判失败）
            self._set(task_id, TaskStatus.DOWNLOADING, Stage.DOWNLOADING)
            self._event(task_id, "DOWNLOAD_STARTED")
            if not await self._wait_download(task_id, qb, selected_hash):
                self._fail(task_id, ErrorCode.DOWNLOAD_FAILED, "下载失败或超时")
                return
            self._event(task_id, "DOWNLOAD_COMPLETED")

            # 5) 后处理（刮削整理）
            self._set(task_id, TaskStatus.PROCESSING, Stage.PROCESSING)
            self._event(task_id, "PROCESSING_STARTED")
            try:
                proc = await asyncio.wait_for(
                    asyncio.to_thread(napics.process, selected.napics_task_id, save_path),
                    timeout=self.cfg.processing_timeout_seconds,
                )
            except asyncio.TimeoutError:
                self._fail(task_id, ErrorCode.PROCESS_FAILED, "后处理超时", status=TaskStatus.TIMEOUT)
                return
            except NapicsError as e:
                self._fail(task_id, ErrorCode.PROCESS_FAILED, str(e))
                return
            pstatus = proc.get("status")
            self._event(task_id, "PROCESSING_COMPLETED", proc)
            if pstatus == "failed":
                self._fail(task_id, ErrorCode.PROCESS_FAILED, "后处理失败")
                return

            # 6) 完成
            self._set(task_id, TaskStatus.COMPLETED, Stage.COMPLETED)
            msg = "已入库" if pstatus == "processed" else "已下载并整理（未配 TMDB，未刮削）"
            self._event(task_id, "TASK_COMPLETED", {"process": pstatus})
            self.notifier.notify(f"下载完成：{inp.title}", msg, event="success")

        except Exception as e:  # 兜底，任何未预期异常
            logger.exception("[workflow] 未预期异常")
            self._fail(task_id, ErrorCode.INTERNAL_ERROR, str(e))
        finally:
            # 铁律：无论成败都 cleanup 关容器（§8/§78）
            self._set_stage(task_id, Stage.CLEANING_UP)
            self._event(task_id, "CLEANUP_STARTED")
            try:
                cres = await svc.cleanup()
                self.db.update_task(task_id, cleanup_status="completed")
                self._event(task_id, "SERVICE_STOPPED", cres)
            except Exception as e:
                self.db.update_task(task_id, cleanup_status="failed")
                logger.error("[workflow] cleanup 异常: %s", e)
            napics.close()
            qb.close()
            self.db.release_lock()

    async def _wait_download(self, task_id: str, qb: QbClient, qb_hash: str) -> bool:
        """轮询 qB 直到完成。DOWNLOAD_TIMEOUT=0 表示无限等。"""
        start = time.time()
        limit = self.cfg.download_timeout_seconds
        while True:
            st = await asyncio.to_thread(qb.info, qb_hash)
            self.db.update_task(task_id, error_message="")  # 心跳
            if st.state == QbState.COMPLETED:
                return True
            if st.state == QbState.ERROR:
                return False
            if limit and (time.time() - start) > limit:
                return False
            await asyncio.sleep(5)

    def _set_stage(self, task_id: str, stage: Stage) -> None:
        self.db.update_task(task_id, current_stage=stage.value)

    def _fail(self, task_id: str, code: ErrorCode, message: str, status: TaskStatus = TaskStatus.FAILED) -> None:
        self.db.update_task(task_id, status=status.value, current_stage=Stage.FAILED.value,
                            error_code=code.value, error_message=message)
        self._event(task_id, "TASK_FAILED", {"code": code.value, "message": message})
        self.notifier.notify("下载失败", f"{message}", event="failure")
