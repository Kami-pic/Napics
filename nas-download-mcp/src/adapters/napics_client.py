"""napics 后端客户端（todo §2）。

上层直接 HTTP 调 napics 后端 :8001 的 agent 端点 + 下载管理。不经过下层 stdio MCP。
凭据（agent token）走本模块自己的 env，不读 napics config.json。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from models import Resource

logger = logging.getLogger("nas_download_mcp.napics")


class NapicsError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class NapicsClient:
    def __init__(self, api_base: str, agent_token: str = "", timeout: float = 15.0):
        self.api_base = api_base.rstrip("/")
        self.agent_token = agent_token
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict:
        h = {}
        if self.agent_token:
            h["X-Agent-Token"] = self.agent_token
        return h

    # ── §2.4 探活 ──
    def health(self) -> bool:
        try:
            r = self._client.get(f"{self.api_base}/api/agent/health")
            return r.status_code == 200 and bool(r.json().get("ok"))
        except Exception as e:
            logger.warning("[napics] health error: %s", e)
            return False

    # ── §2.1 搜索（返回展平 Resource）──
    # ── §2.1 搜索：消费 napics SSE 流式端点，按时间窗口收先到的源 ──
    #    /api/agent/search 是同步等所有源，境外慢源(重试3×15s)会拖到超时；
    #    /api/search/stream 是 as_completed 先搜到先吐，设收集窗口卡掉慢源。不改 napics。
    def search(
        self,
        query: str,
        media_type: str = "",
        title: str = "",
        year: Optional[int] = None,
        season: Optional[int] = None,
        limit: int = 30,
        deadline_seconds: float = 30.0,
        min_results: int = 5,
    ) -> list[Resource]:
        import json as _json
        import time as _time

        params = {"query": query}
        if title:
            params["cn_name"] = title
        if year:
            params["year"] = str(year)
        if season:
            params["season_number"] = season

        collected: list[dict] = []
        seen: set[str] = set()
        start = _time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(deadline_seconds * 2 + 15)) as sc:
                with sc.stream(
                    "GET", f"{self.api_base}/api/search/stream",
                    params=params, headers=self._headers(),
                ) as resp:
                    if resp.status_code != 200:
                        raise NapicsError(f"搜索返回 {resp.status_code}", retryable=resp.status_code >= 500)
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        try:
                            evt = _json.loads(line[6:])
                        except Exception:
                            continue
                        etype = evt.get("type")
                        if etype == "done" and evt.get("error") == "no_source":
                            raise NapicsError(evt.get("message", "未安装搜索插件"), retryable=False)
                        if etype == "source_done":
                            for r in evt.get("results", []) or []:
                                u = r.get("download_url", "")
                                if u and u not in seen:
                                    seen.add(u)
                                    collected.append(r)
                        if etype == "done":
                            break
                        elapsed = _time.monotonic() - start
                        if elapsed >= deadline_seconds and len(collected) >= min_results:
                            break
        except NapicsError:
            raise
        except Exception as e:
            if not collected:
                raise NapicsError(f"搜索失败: {e}", retryable=True)

        flattened = [self._flatten(r) for r in collected]
        flattened.sort(key=lambda x: x.score or 0, reverse=True)
        return flattened[:limit] if limit else flattened

    @staticmethod
    def _flatten(d: dict) -> Resource:
        """napics enrich 结果（quality 子对象）→ Resource，同 agent.py::_flatten_resource。"""
        q = d.get("quality") or {}
        if not isinstance(q, dict):
            q = getattr(q, "__dict__", {}) or {}
        return Resource(
            title=d.get("title", ""),
            source=q.get("source"),
            indexer=d.get("indexer"),
            download_url=d.get("download_url", ""),
            size_gb=d.get("size_gb"),
            seeders=d.get("seeders"),
            leechers=d.get("leechers"),
            resolution=q.get("resolution"),
            codec=q.get("video_codec"),
            release_group=q.get("release_group"),
            has_chinese_sub=q.get("has_chinese_sub"),
            score=(d.get("quality_score") or 0) + (d.get("match_score") or 0),
        )

    # ── §2.2 创建下载（返回 napics task_id + qb_hash，可能空）──
    def submit_download(
        self,
        download_url: str,
        media_name: str,
        save_path: str = "",
        idempotency_key: str = "",
        channel: str = "qb",
        is_season_pack: bool = False,
        season_number: int = 0,
    ) -> dict:
        """返回 {success, task_id, qb_hash, error}。qb_hash 来自 task.downloader_hash（可能空）。"""
        payload = {
            "media_name": media_name,
            "download_url": download_url,
            "save_path": save_path,
            "channel": channel,
            "is_season_pack": is_season_pack,
            "season_number": season_number,
            "idempotency_key": idempotency_key,
        }
        headers = self._headers()
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            r = self._client.post(
                f"{self.api_base}/download-manager/submit", json=payload, headers=headers
            )
        except Exception as e:
            raise NapicsError(f"创建下载请求失败: {e}", retryable=True)
        if r.status_code != 200:
            raise NapicsError(f"创建下载返回 {r.status_code}", retryable=r.status_code >= 500)
        body = r.json()
        task = body.get("task") or {}
        return {
            "success": bool(body.get("success")),
            "task_id": task.get("id", ""),
            "qb_hash": task.get("downloader_hash", "") or "",
            "error": task.get("error") or body.get("error") or "",
        }

    # ── §2.3 后处理（刮削+整理，只消费出参）──
    def process(self, task_id: str = "", path: str = "") -> dict:
        """返回 {status: processed|partial|failed, library_path, files}。"""
        params = {}
        if path:
            params["path"] = path
        if task_id:
            params["task_id"] = task_id
        try:
            r = self._client.post(
                f"{self.api_base}/api/agent/process", params=params, headers=self._headers()
            )
        except Exception as e:
            raise NapicsError(f"后处理请求失败: {e}", retryable=True)
        if r.status_code == 401:
            raise NapicsError("agent token 校验失败", retryable=False)
        if r.status_code != 200:
            raise NapicsError(f"后处理返回 {r.status_code}", retryable=r.status_code >= 500)
        return r.json()
