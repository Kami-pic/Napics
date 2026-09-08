"""qBittorrent 直连客户端（方案 A：监控进度 / 删种走 qB，不经 napics）。

登录逻辑照抄 napics downloader.py::QBittorrentClient._login：
表单 login → session cookie → 403 视作 session 过期，清登录态重试一次。
用 httpx（与 napics_client 统一）。
"""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx

logger = logging.getLogger("napics_mcp.qb")


class QbError(Exception):
    """qB 不可达 / 登录失败。工具层据此回 QB_UNAVAILABLE / AUTH_FAILED。"""

    def __init__(self, message: str, auth: bool = False):
        super().__init__(message)
        self.auth = auth


class QbClient:
    def __init__(self, url: str, username: str = "admin", password: str = "",
                 timeout: float = 15.0):
        self.url = (url or "").rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        # trust_env=False：不读 ALL_PROXY/HTTP(S)_PROXY —— qB 在回环/局域网，
        # 走 clash 代理只会失败。follow_redirects=False：登录/查询不该被重定向带偏。
        self._client = httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)
        self._logged_in = False

    def close(self) -> None:
        self._client.close()

    # ── 登录 ──

    def _login(self) -> bool:
        if self._logged_in:
            return True
        try:
            r = self._client.post(
                f"{self.url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                headers={"Referer": self.url},
            )
        except httpx.HTTPError as e:
            raise QbError(f"qB 不可达: {e}")
        # 旧版 200 + "Ok."，新版可能 204
        self._logged_in = (r.status_code == 200 and "ok" in r.text.lower()) or r.status_code == 204
        if not self._logged_in:
            raise QbError(f"qB 登录失败（状态 {r.status_code}）", auth=True)
        return True

    def _get(self, path: str, params: dict) -> httpx.Response:
        """带一次 403 重登的 GET。"""
        for attempt in range(2):
            self._login()
            try:
                r = self._client.get(f"{self.url}{path}", params=params)
            except httpx.HTTPError as e:
                raise QbError(f"qB 请求失败: {e}")
            if r.status_code == 403 and attempt == 0:
                self._logged_in = False
                continue
            return r
        return r  # type: ignore[return-value]

    def _post(self, path: str, data: dict) -> httpx.Response:
        for attempt in range(2):
            self._login()
            try:
                r = self._client.post(f"{self.url}{path}", data=data)
            except httpx.HTTPError as e:
                raise QbError(f"qB 请求失败: {e}")
            if r.status_code == 403 and attempt == 0:
                self._logged_in = False
                continue
            return r
        return r  # type: ignore[return-value]

    # ── 探活 ──

    def reachable(self) -> bool:
        try:
            return self._login()
        except QbError:
            return False

    # ── 查种子 ──

    def torrent_info(self, qb_hash: str) -> Optional[dict]:
        """GET /api/v2/torrents/info?hashes=<hash>。返回单条 dict 或 None。"""
        r = self._get("/api/v2/torrents/info", {"hashes": (qb_hash or "").lower()})
        if r.status_code != 200:
            raise QbError(f"查询种子失败（状态 {r.status_code}）")
        arr = r.json()
        if not isinstance(arr, list) or not arr:
            return None
        return arr[0]

    def list_hashes(self) -> List[str]:
        r = self._get("/api/v2/torrents/info", {})
        if r.status_code != 200:
            raise QbError(f"列出种子失败（状态 {r.status_code}）")
        arr = r.json()
        return [t.get("hash", "") for t in arr if isinstance(t, dict)]

    # ── 删种 ──

    def delete(self, qb_hash: str, delete_files: bool = False) -> bool:
        """POST /api/v2/torrents/delete。qB 对该端点即使 hash 不存在也回 200。"""
        r = self._post(
            "/api/v2/torrents/delete",
            {"hashes": (qb_hash or "").lower(), "deleteFiles": "true" if delete_files else "false"},
        )
        if r.status_code not in (200, 204):
            raise QbError(f"删种失败（状态 {r.status_code}）")
        return True
