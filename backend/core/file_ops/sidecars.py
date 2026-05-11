"""同名前缀关联文件操作。"""

import os
from typing import Callable, Iterable, Optional


SIDECAR_SUFFIXES = (
    ".nfo",
    "-poster.jpg",
    "-poster.png",
    "-fanart.jpg",
    "-clearlogo.png",
    "-thumb.jpg",
)


def move_sidecars(
    old_path: str,
    new_path: str,
    mover: Callable[[str, str], object],
    suffixes: Optional[Iterable[str]] = None,
) -> None:
    """移动或重命名同名前缀关联文件，单个失败不阻断主流程。"""
    old_base = os.path.splitext(old_path)[0]
    new_base = os.path.splitext(new_path)[0]
    for suffix in suffixes or SIDECAR_SUFFIXES:
        old_sidecar = old_base + suffix
        if not os.path.exists(old_sidecar):
            continue
        try:
            mover(old_sidecar, new_base + suffix)
        except Exception:
            pass


def copy_sidecars(
    old_path: str,
    new_path: str,
    copier: Callable[[str, str], object],
    suffixes: Optional[Iterable[str]] = None,
) -> None:
    """复制同名前缀关联文件，单个失败不阻断主流程。"""
    old_base = os.path.splitext(old_path)[0]
    new_base = os.path.splitext(new_path)[0]
    for suffix in suffixes or SIDECAR_SUFFIXES:
        old_sidecar = old_base + suffix
        if not os.path.exists(old_sidecar):
            continue
        try:
            copier(old_sidecar, new_base + suffix)
        except Exception:
            pass
