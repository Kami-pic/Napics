"""回收站：存放被替换的旧文件，支持恢复和定时清理。

核心设计：
- 元数据持久化到 recycle_bin.json（original_path 是恢复的唯一凭证）
- 文件名加 task_id 前缀防止回收站内部重名覆盖
- 过期清理按 retention_days 配置
"""

import os
import json
import shutil
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel


RECYCLE_META_FILE = "recycle_bin.json"


class RecycleBinEntry(BaseModel):
    """回收站条目"""
    id: str = ""
    original_path: str = ""      # 原始路径（恢复的唯一凭证）
    recycle_path: str = ""       # 回收站中的实际路径
    size_gb: float = 0.0
    moved_at: str = ""           # ISO datetime
    task_id: str = ""            # 关联的下载任务 ID
    expires_at: str = ""         # 过期时间


class RecycleBin:
    """回收站管理器。"""

    def __init__(self, recycle_dir: str, retention_days: int = 30):
        self.recycle_dir = recycle_dir
        self.retention_days = retention_days
        self.entries: List[RecycleBinEntry] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        """确保回收站目录存在。"""
        if self.recycle_dir:
            os.makedirs(self.recycle_dir, exist_ok=True)

    def move_to_bin(self, file_path: str, task_id: str = "") -> Optional[RecycleBinEntry]:
        """将文件移入回收站。

        文件名加 task_id 前缀防止重名覆盖：
        原始: Dune.2024.1080p.mkv
        回收站: {task_id}_{原始文件名}
        """
        if not os.path.exists(file_path):
            return None
        if not self.recycle_dir:
            return None

        entry_id = str(uuid.uuid4())[:8]
        original_name = os.path.basename(file_path)
        # 加 task_id 前缀防止重名
        prefix = f"{task_id}_" if task_id else f"{entry_id}_"
        recycle_name = f"{prefix}{original_name}"
        recycle_path = os.path.join(self.recycle_dir, recycle_name)

        # 如果回收站中已存在同名文件（极端情况），再加时间戳
        if os.path.exists(recycle_path):
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            recycle_name = f"{prefix}{ts}_{original_name}"
            recycle_path = os.path.join(self.recycle_dir, recycle_name)

        try:
            # 获取文件大小
            size_bytes = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
            size_gb = round(size_bytes / (1024 ** 3), 3)

            shutil.move(file_path, recycle_path)

            now = datetime.now()
            entry = RecycleBinEntry(
                id=entry_id,
                original_path=file_path,
                recycle_path=recycle_path,
                size_gb=size_gb,
                moved_at=now.isoformat(),
                task_id=task_id,
                expires_at=(now + timedelta(days=self.retention_days)).isoformat(),
            )
            self.entries.append(entry)
            self._save()
            return entry
        except Exception as e:
            print(f"[RecycleBin] 移入回收站失败: {file_path} → {e}")
            return None

    def restore(self, entry_id: str) -> bool:
        """从回收站恢复文件到原始路径。

        如果原始路径已被占用，返回 False。
        """
        entry = self._find_entry(entry_id)
        if not entry:
            return False

        if not os.path.exists(entry.recycle_path):
            # 回收站中文件已不存在，清理条目
            self.entries = [e for e in self.entries if e.id != entry_id]
            self._save()
            return False

        if os.path.exists(entry.original_path):
            # 原始路径已被占用
            return False

        try:
            # 确保原始路径的父目录存在
            parent = os.path.dirname(entry.original_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            shutil.move(entry.recycle_path, entry.original_path)
            self.entries = [e for e in self.entries if e.id != entry_id]
            self._save()
            return True
        except Exception as e:
            print(f"[RecycleBin] 恢复失败: {entry.recycle_path} → {e}")
            return False

    def cleanup_expired(self) -> int:
        """清理过期文件，返回清理数量。"""
        now = datetime.now()
        cleaned = 0
        remaining = []

        for entry in self.entries:
            try:
                expires = datetime.fromisoformat(entry.expires_at)
                if now > expires:
                    # 过期，删除文件
                    if os.path.exists(entry.recycle_path):
                        try:
                            os.remove(entry.recycle_path)
                            cleaned += 1
                        except Exception as e:
                            print(f"[RecycleBin] 删除过期文件失败: {entry.recycle_path} → {e}")
                            remaining.append(entry)  # 删除失败的保留
                            continue
                    cleaned += 1  # 文件已不存在也算清理
                else:
                    remaining.append(entry)
            except (ValueError, TypeError):
                remaining.append(entry)  # 无法解析过期时间的保留

        self.entries = remaining
        self._save()
        return cleaned

    def list_entries(self) -> List[RecycleBinEntry]:
        """列出回收站所有文件，按移入时间倒序。"""
        return sorted(self.entries, key=lambda e: e.moved_at or "", reverse=True)

    def _find_entry(self, entry_id: str) -> Optional[RecycleBinEntry]:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def _load(self):
        path = os.path.join(self.recycle_dir, RECYCLE_META_FILE) if self.recycle_dir else RECYCLE_META_FILE
        if not os.path.exists(path):
            self.entries = []
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [RecycleBinEntry(**item) for item in data]
        except Exception:
            self.entries = []

    def _save(self):
        path = os.path.join(self.recycle_dir, RECYCLE_META_FILE) if self.recycle_dir else RECYCLE_META_FILE
        try:
            data = [e.dict() for e in self.entries]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[RecycleBin] 保存元数据失败: {e}")
