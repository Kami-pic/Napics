"""qB 直连客户端（todo §6）。

qB 的能力在 napics 里散在两处，本模块参考真实实现重写为 httpx 版：
- login/add            ← backend/downloader.py::QBittorrentClient
- info/progress/state  ← backend/download_provider_adapter.py::_progress_qb / _format_qb_*
- delete               ← napics 侧不存在，本模块自己实现

监控/测速/删种全归上层直连 qB（napics 不碰这些）。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from models import DownloadStatus, QbState

logger = logging.getLogger("nas_download_mcp.qb")

# qB 原始 state → 统一枚举（todo §6）
_STATE_MAP = {
    "downloading": QbState.DOWNLOADING,
    "metaDL": QbState.DOWNLOADING,
    "forcedDL": QbState.DOWNLOADING,
    "stalledDL": QbState.STALLED,
    "queuedDL": QbState.STALLED,
    "checkingDL": QbState.DOWNLOADING,
    "allocating": QbState.DOWNLOADING,
    "pausedDL": QbState.PAUSED,
    "uploading": QbState.COMPLETED,
    "forcedUP": QbState.COMPLETED,
    "stalledUP": QbState.COMPLETED,
    "queuedUP": QbState.COMPLETED,
    "checkingUP": QbState.COMPLETED,
    "pausedUP": QbState.COMPLETED,
    "error": QbState.ERROR,
    "missingFiles": QbState.ERROR,
}


def _map_state(raw: str, progress: float) -> QbState:
    if progress >= 1.0:
        return QbState.COMPLETED
    return _STATE_MAP.get(raw, QbState.UNKNOWN)


class QbClient:
    """同步 httpx 客户端。qB Web API 是 cookie session，httpx.Client 自动持有 cookie。"""

    def __init__(self, url: str, username: str = "admin", password: str = "", timeout: float = 10.0):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._logged_in = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "QbClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── 登录（参考 downloader.py::_login）──
    def login(self) -> bool:
        if self._logged_in:
            return True
        try:
            r = self._client.post(
                f"{self.url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                headers={"Referer": self.url},
            )
            self._logged_in = (r.status_code == 200 and "ok" in r.text.lower()) or r.status_code == 204
            if not self._logged_in:
                logger.warning("[qB] login failed status=%s", r.status_code)
            return self._logged_in
        except Exception as e:
            logger.warning("[qB] login error: %s", e)
            return False

    def reachable(self) -> bool:
        """探活：能登录即视为可达。"""
        self._logged_in = False
        return self.login()

    def _post(self, path: str, data: dict) -> Optional[httpx.Response]:
        """带 403 重登的 POST。"""
        for attempt in range(2):
            if not self.login():
                return None
            r = self._client.post(f"{self.url}{path}", data=data, headers={"Referer": self.url})
            if r.status_code == 403 and attempt == 0:
                self._logged_in = False
                continue
            return r
        return None

    def _get(self, path: str, params: dict) -> Optional[httpx.Response]:
        for attempt in range(2):
            if not self.login():
                return None
            r = self._client.get(f"{self.url}{path}", params=params, headers={"Referer": self.url})
            if r.status_code == 403 and attempt == 0:
                self._logged_in = False
                continue
            return r
        return None

    # ── 加种（参考 downloader.py::add_torrent）──
    def add(self, torrent_url: str, save_path: str = "", category: str = "") -> bool:
        data = {"urls": torrent_url}
        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        r = self._post("/api/v2/torrents/add", data)
        if r is None:
            return False
        if r.status_code == 409:
            logger.info("[qB] torrent already exists (409)")
            return True  # 已存在也算加上了
        if r.status_code not in (200, 202):
            logger.error("[qB] add failed status=%s body=%s", r.status_code, r.text[:200])
            return False
        return True

    # ── 查进度（参考 download_provider_adapter.py::_progress_qb）──
    def info(self, torrent_hash: str) -> DownloadStatus:
        r = self._get("/api/v2/torrents/info", {"hashes": torrent_hash})
        if r is None or r.status_code != 200:
            return DownloadStatus(state=QbState.UNKNOWN)
        torrents = r.json()
        if not torrents:
            return DownloadStatus(state=QbState.UNKNOWN)
        item = torrents[0]
        progress = float(item.get("progress", 0) or 0)
        eta_raw = int(item.get("eta", 0) or 0)
        eta = None if (not eta_raw or eta_raw >= 8640000) else eta_raw
        return DownloadStatus(
            state=_map_state(str(item.get("state", "")), progress),
            percentage=round(progress * 100, 2),
            download_speed_bytes=int(item.get("dlspeed", 0) or 0),
            eta_seconds=eta,
        )

    def list_all(self) -> list[dict]:
        """全量种子列表（空 hash 回落匹配用，todo §2.2/§6）。返回原始 dict。"""
        r = self._get("/api/v2/torrents/info", {})
        if r is None or r.status_code != 200:
            return []
        data = r.json()
        return data if isinstance(data, list) else []

    def find_hash_by_name(self, media_name: str, save_path: str = "") -> Optional[str]:
        """空 hash 回落匹配（todo §2.2）：media_name 双向包含 + 可选 save_path 校验。

        参考 napics download.py::sync_from_qb 的双向包含。多结果撞名时优先 save_path 命中。
        """
        name_l = (media_name or "").strip().lower()
        if not name_l:
            return None
        candidates = []
        for t in self.list_all():
            qb_name = str(t.get("name", "")).lower()
            if not qb_name:
                continue
            if name_l in qb_name or qb_name in name_l:
                candidates.append(t)
        if not candidates:
            return None
        if save_path and len(candidates) > 1:
            sp = save_path.strip().lower()
            for t in candidates:
                if sp and sp in str(t.get("save_path", "")).lower():
                    return str(t.get("hash", "")) or None
        return str(candidates[0].get("hash", "")) or None

    # ── 删种（napics 没有，上层自实现；todo §6）──
    def delete(self, torrent_hash: str, delete_files: bool = False) -> bool:
        r = self._post(
            "/api/v2/torrents/delete",
            {"hashes": torrent_hash, "deleteFiles": "true" if delete_files else "false"},
        )
        if r is None:
            return False
        return r.status_code in (200, 202)
