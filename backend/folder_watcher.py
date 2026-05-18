"""文件夹监控器 — Core 能力，不依赖任何下载器。

监控指定目录，发现新文件/文件夹后创建下载任务（status=completed），
触发归位替换流程。

用于无下载器插件时的兜底方案：用户自己下载文件到监控目录，系统自动整理。
"""

import logging
import os
import time
import threading
from typing import List, Set

logger = logging.getLogger(__name__)

# 视频文件扩展名
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".ts", ".m4v", ".wmv", ".rmvb", ".flv", ".mov"}

# 忽略的文件/目录名
IGNORE_NAMES = {".DS_Store", "Thumbs.db", "@eaDir", "#recycle", ".recycle_bins"}


class FolderWatcher:
    """下载目录监控器"""

    def __init__(self, watch_dirs: List[str], scan_interval: int = 60):
        self._watch_dirs = [d for d in watch_dirs if d.strip()]
        self._scan_interval = scan_interval
        self._known_items: Set[str] = set()
        self._initialized = False
        self._lock = threading.Lock()

    @property
    def watch_dirs(self) -> List[str]:
        return list(self._watch_dirs)

    def update_dirs(self, dirs: List[str]) -> None:
        """更新监控目录列表"""
        with self._lock:
            self._watch_dirs = [d for d in dirs if d.strip()]
            # 重置已知文件，下次扫描会重新初始化
            self._known_items.clear()
            self._initialized = False

    def scan(self) -> List[str]:
        """扫描监控目录，返回新增的文件/文件夹路径。

        首次扫描只记录现有文件（不触发整理），后续扫描才返回新增项。
        只返回包含视频文件的目录或视频文件本身。
        """
        with self._lock:
            current_items: Set[str] = set()

            for dir_path in self._watch_dirs:
                if not os.path.isdir(dir_path):
                    continue
                try:
                    for item in os.listdir(dir_path):
                        if item in IGNORE_NAMES:
                            continue
                        full_path = os.path.join(dir_path, item)
                        # 只关注视频文件或包含视频的目录
                        if os.path.isfile(full_path):
                            ext = os.path.splitext(item)[1].lower()
                            if ext in VIDEO_EXTS:
                                current_items.add(full_path)
                        elif os.path.isdir(full_path):
                            if self._has_video(full_path):
                                current_items.add(full_path)
                except Exception as e:
                    logger.error(f"[FolderWatcher] 扫描目录失败 {dir_path}: {e}")

            # 首次扫描：只记录，不返回
            if not self._initialized:
                self._known_items = current_items
                self._initialized = True
                logger.info(f"[FolderWatcher] 初始化完成，已知 {len(current_items)} 项")
                return []

            # 后续扫描：返回新增项
            new_items = current_items - self._known_items
            self._known_items = current_items

            if new_items:
                logger.info(f"[FolderWatcher] 检测到 {len(new_items)} 个新项")

            return sorted(new_items)

    @staticmethod
    def _has_video(dir_path: str) -> bool:
        """检查目录中是否包含视频文件（只检查一层）"""
        try:
            for item in os.listdir(dir_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in VIDEO_EXTS:
                    return True
                # 检查子目录（两层深度）
                sub_path = os.path.join(dir_path, item)
                if os.path.isdir(sub_path):
                    for sub_item in os.listdir(sub_path):
                        if os.path.splitext(sub_item)[1].lower() in VIDEO_EXTS:
                            return True
        except Exception:
            pass
        return False
