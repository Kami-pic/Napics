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


def list_subtitle_files(video_path: str) -> list:
    """列出视频的外挂字幕文件名。

    两级匹配：

    1. 同名前缀 —— 覆盖 `视频名.srt` 与 `视频名.chs.srt` / `视频名.简体.ass`。
    2. 若同名一个都没有，且**该目录只有这一个视频文件**，则把目录里的字幕
       都归给它。单片目录里字幕名与视频名不一致很常见（字幕留着发布组原名、
       视频已被重命名成中文），严格同名会漏掉。

    多视频目录（整季剧集）必须保持严格同名，否则播第 1 集会把 12 集的字幕
    全列出来。
    """
    from core.constants import SUBTITLE_EXTS, VIDEO_EXTS

    directory = os.path.dirname(video_path)
    if not directory or not os.path.isdir(directory):
        return []

    stem = os.path.splitext(os.path.basename(video_path))[0].lower()
    try:
        entries = sorted(os.listdir(directory))
    except OSError:
        return []

    subtitle_names = [
        name for name in entries
        if os.path.splitext(name)[1].lower() in SUBTITLE_EXTS
    ]
    if not subtitle_names:
        return []

    same_stem = [
        name for name in subtitle_names
        if (lambda b: b == stem or b.startswith(stem + "."))(
            os.path.splitext(name)[0].lower()
        )
    ]
    if same_stem:
        return same_stem

    video_count = sum(
        1 for name in entries
        if os.path.splitext(name)[1].lower() in VIDEO_EXTS
        and os.path.isfile(os.path.join(directory, name))
    )
    if video_count == 1:
        return subtitle_names
    return []
