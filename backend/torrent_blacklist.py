"""无效种子黑名单：TTL 缓存，24h 避免重复提交失败的种子。"""

import json
import os
import time
from typing import List

BLACKLIST_FILE = "torrent_blacklist.json"
TTL_SECONDS = 24 * 3600  # 24 小时


class TorrentBlacklist:
    """内存 + 文件持久化的种子黑名单。"""

    def __init__(self, path: str = BLACKLIST_FILE):
        self._path = path
        self._entries: dict = {}  # url → expire_ts
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                # 只加载未过期的
                self._entries = {k: v for k, v in data.items() if v > now}
            except Exception:
                self._entries = {}

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
        except Exception:
            pass

    def add(self, url: str, reason: str = ""):
        """将种子 URL 加入黑名单，24h 后自动过期。"""
        self._entries[url] = time.time() + TTL_SECONDS
        self._save()

    def is_blocked(self, url: str) -> bool:
        """检查种子是否在黑名单中（未过期）。"""
        expire = self._entries.get(url)
        if expire is None:
            return False
        if time.time() > expire:
            del self._entries[url]
            return False
        return True

    def remove(self, url: str):
        """手动移除黑名单条目。"""
        self._entries.pop(url, None)
        self._save()

    def cleanup(self) -> int:
        """清理所有过期条目，返回清理数量。"""
        now = time.time()
        expired = [k for k, v in self._entries.items() if v < now]
        for k in expired:
            del self._entries[k]
        if expired:
            self._save()
        return len(expired)

    def list_entries(self) -> List[dict]:
        """列出所有未过期的黑名单条目。"""
        now = time.time()
        return [
            {"url": k, "expires_at": v, "ttl_hours": round((v - now) / 3600, 1)}
            for k, v in self._entries.items()
            if v > now
        ]

    @property
    def count(self) -> int:
        return len([v for v in self._entries.values() if v > time.time()])
