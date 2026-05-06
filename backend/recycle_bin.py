"""回收站：存放被替换的旧文件，支持恢复和定时清理。

核心设计：
- 元数据集中持久化，避免多媒体库根时前端列表丢数据
- 文件实体默认跟随媒体库根落盘，避免跨盘搬回 backend 本地
- 文件名加 task_id 前缀防止回收站内部重名覆盖
- 过期清理按 retention_days 配置
"""

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)
RECYCLE_META_FILE = "recycle_bin.json"
DEFAULT_RECYCLE_PARENT_DIR_NAME = "#recycle"


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

    def __init__(
        self,
        recycle_dir: str = "",
        retention_days: int = 30,
        library_roots: Optional[List[str]] = None,
        meta_path: str = "",
    ):
        self.recycle_dir = os.path.normpath(recycle_dir) if recycle_dir else ""
        self.retention_days = retention_days
        self.library_roots = [os.path.normpath(root) for root in (library_roots or []) if root]
        self.meta_path = meta_path or (
            os.path.join(self.recycle_dir, RECYCLE_META_FILE) if self.recycle_dir else RECYCLE_META_FILE
        )
        self.entries: List[RecycleBinEntry] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        """确保元数据目录与显式回收站目录存在。"""
        if self.recycle_dir:
            os.makedirs(self.recycle_dir, exist_ok=True)
        meta_parent = os.path.dirname(self.meta_path)
        if meta_parent:
            os.makedirs(meta_parent, exist_ok=True)

    def move_to_bin(self, file_path: str, task_id: str = "") -> Optional[RecycleBinEntry]:
        """将文件或目录移入回收站，保留相对路径结构。"""
        if not os.path.exists(file_path):
            return None

        recycle_dir = self._resolve_recycle_dir(file_path)
        if not recycle_dir:
            return None

        # 计算相对路径：从共享文件夹根（recycle_dir 的父目录）到文件的相对路径
        # recycle_dir = share/#recycle，share_root = share/
        share_root = os.path.dirname(recycle_dir)
        norm_file = os.path.normpath(file_path)
        norm_share = os.path.normpath(share_root)
        try:
            rel_path = os.path.relpath(norm_file, norm_share)
        except ValueError:
            # 跨盘时 relpath 会报错，fallback 到只用文件名
            rel_path = os.path.basename(file_path.rstrip("\\/"))

        recycle_path = os.path.join(recycle_dir, rel_path)
        recycle_parent = os.path.dirname(recycle_path)
        os.makedirs(recycle_parent, exist_ok=True)

        # 同名冲突处理
        if os.path.exists(recycle_path):
            base, ext = os.path.splitext(recycle_path)
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            recycle_path = f"{base}_{ts}{ext}" if ext else f"{recycle_path}_{ts}"

        entry_id = str(uuid.uuid4())[:8]
        try:
            size_gb = self._calculate_size_gb(file_path)
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
            logger.error(f"[RecycleBin] 移入回收站失败: {file_path} → {e}")
            return None

    def restore(self, entry_id: str) -> bool:
        """从回收站恢复文件到原始路径。"""
        entry = self._find_entry(entry_id)
        if not entry:
            return False

        if not os.path.exists(entry.recycle_path):
            self.entries = [e for e in self.entries if e.id != entry_id]
            self._save()
            return False

        if os.path.exists(entry.original_path):
            return False

        try:
            parent = os.path.dirname(entry.original_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            shutil.move(entry.recycle_path, entry.original_path)
            self.entries = [e for e in self.entries if e.id != entry_id]
            self._save()
            return True
        except Exception as e:
            logger.error(f"[RecycleBin] 恢复失败: {entry.recycle_path} → {e}")
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
                    if os.path.exists(entry.recycle_path):
                        try:
                            self._remove_path(entry.recycle_path)
                        except Exception as e:
                            logger.error(f"[RecycleBin] 删除过期文件失败: {entry.recycle_path} → {e}")
                            remaining.append(entry)
                            continue
                    cleaned += 1
                else:
                    remaining.append(entry)
            except (ValueError, TypeError):
                remaining.append(entry)

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

    def _resolve_recycle_dir(self, file_path: str) -> str:
        if self.recycle_dir:
            return self.recycle_dir

        matched_root = self._match_library_root(file_path)
        if matched_root:
            return self._build_default_recycle_dir_from_root(matched_root)

        parent_dir = os.path.dirname(os.path.abspath(file_path))
        return os.path.join(parent_dir, DEFAULT_RECYCLE_PARENT_DIR_NAME) if parent_dir else ""

    def _match_library_root(self, file_path: str) -> str:
        abs_path = os.path.abspath(file_path)
        best_match = ""
        for root in self.library_roots:
            try:
                common = os.path.commonpath([abs_path, root])
            except ValueError:
                continue
            if os.path.normcase(common) != os.path.normcase(root):
                continue
            if len(root) > len(best_match):
                best_match = root
        return best_match

    def _build_default_recycle_dir_from_root(self, library_root: str) -> str:
        r"""回收站放在媒体库根的上级目录（共享文件夹根）下的 #recycle。
        如 媒体库 \\DS218play\share\视频 → 回收站 \\DS218play\share\#recycle
        """
        normalized_root = os.path.normpath(library_root)
        parent_dir = os.path.dirname(normalized_root.rstrip("\\/"))

        if parent_dir and os.path.normcase(parent_dir) != os.path.normcase(normalized_root.rstrip("\\/")):
            return os.path.join(parent_dir, DEFAULT_RECYCLE_PARENT_DIR_NAME)

        return os.path.join(normalized_root, DEFAULT_RECYCLE_PARENT_DIR_NAME)

    def _load(self):
        path = self.meta_path
        legacy_path = self._legacy_meta_path()
        if not os.path.exists(path) and legacy_path and os.path.exists(legacy_path):
            path = legacy_path
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
        try:
            data = [e.model_dump() for e in self.entries]
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[RecycleBin] 保存元数据失败: {e}")

    def _legacy_meta_path(self) -> str:
        if self.recycle_dir:
            return os.path.join(self.recycle_dir, RECYCLE_META_FILE)
        return ""

    @staticmethod
    def _remove_path(path: str):
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    @staticmethod
    def _calculate_size_gb(path: str) -> float:
        size_bytes = 0
        if os.path.isfile(path):
            size_bytes = os.path.getsize(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    if os.path.isfile(file_path):
                        size_bytes += os.path.getsize(file_path)
        return round(size_bytes / (1024 ** 3), 3)
