"""napics Agent API 客户端（搜索 + 创建下载 + 后处理）。

对应 napics backend 的 §2 端点（对话 B 已落地）：
- GET  /api/agent/search       → 展平的 Resource 列表
- POST /download-manager/submit → 创建下载（带 Idempotency-Key）
- POST /api/agent/process       → 刮削整理归位
- GET  /api/agent/health        → napics 侧探活

写操作带 X-Agent-Token（config.napics_agent_token 非空时）。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger("napics_mcp.napics")


class NapicsError(Exception):
    """napics 不可达 / 返回错误。auth=True 表示 401。"""

    def __init__(self, message: str, auth: bool = False, not_found: bool = False):
        super().__init__(message)
        self.auth = auth
        self.not_found = not_found


class NapicsClient:
    def __init__(self, base: str, agent_token: str = "", timeout: float = 15.0):
        self.base = (base or "").rstrip("/")
        self.agent_token = agent_token
        self.timeout = timeout
        # trust_env=False：napics 在回环/局域网，不走 ALL_PROXY/HTTP(S)_PROXY。
        self._client = httpx.Client(timeout=timeout, trust_env=False)

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict:
        h = {}
        if self.agent_token:
            h["X-Agent-Token"] = self.agent_token
        return h

    def _raise_for_status(self, r: httpx.Response, ctx: str) -> None:
        if r.status_code == 401:
            raise NapicsError(f"{ctx}：Agent token 无效", auth=True)
        if r.status_code == 404:
            raise NapicsError(f"{ctx}：资源不存在", not_found=True)
        if r.status_code >= 400:
            raise NapicsError(f"{ctx}：napics 返回 {r.status_code} {r.text[:200]}")

    # ── 探活 ──

    def reachable(self) -> bool:
        try:
            r = self._client.get(f"{self.base}/api/agent/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    # ── §2.1 搜索 ──

    def search(self, query: str, media_type: str = "", title: str = "",
               year: Optional[int] = None, season: Optional[int] = None,
               limit: int = 30) -> dict:
        params = {"query": query, "limit": limit}
        if media_type:
            params["media_type"] = media_type
        if title:
            params["title"] = title
        if year:
            params["year"] = year
        if season:
            params["season"] = season
        try:
            r = self._client.get(f"{self.base}/api/agent/search",
                                 params=params, headers=self._headers())
        except httpx.HTTPError as e:
            raise NapicsError(f"napics 不可达: {e}")
        self._raise_for_status(r, "搜索")
        return r.json()

    # ── §2.2 创建下载 ──

    def submit(self, download_url: str, media_name: str, idempotency_key: str,
               save_path: Optional[str] = None, channel: str = "qb") -> dict:
        # napics DownloadSubmitRequest.save_path 是必填 str；省略时发空串，
        # 由 napics 落到默认沙盒。
        body = {
            "download_url": download_url,
            "media_name": media_name,
            "save_path": save_path or "",
            "channel": channel,
            "idempotency_key": idempotency_key,
        }
        headers = self._headers()
        headers["Idempotency-Key"] = idempotency_key
        try:
            r = self._client.post(f"{self.base}/download-manager/submit",
                                  json=body, headers=headers)
        except httpx.HTTPError as e:
            raise NapicsError(f"napics 不可达: {e}")
        self._raise_for_status(r, "创建下载")
        return r.json()

    # ── §2.4 后处理 ──

    def process(self, path: Optional[str] = None,
                task_id: Optional[str] = None) -> dict:
        params = {}
        if path:
            params["path"] = path
        if task_id:
            params["task_id"] = task_id
        try:
            r = self._client.post(f"{self.base}/api/agent/process",
                                  params=params, headers=self._headers())
        except httpx.HTTPError as e:
            raise NapicsError(f"napics 不可达: {e}")
        self._raise_for_status(r, "后处理")
        return r.json()
