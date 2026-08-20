"""扫描期为新条目填充检索名（清洗名）与标准名（影子名）。

扫描是这两个名字的**主要来源**。此前 /scan 只调 clean_from_filename(file_name)，
既不看 NFO 也不看文件夹名，导致：
- `爱情与灵药 (2010).mp4` 拿不到英文名（英文名在 NFO 和同级目录名里）
- 标准名只是清洗名 display，拿不到 `中文 English (年份)` 这种规范形态
于是每次清缓存重扫，用户已有的检索名/标准名就大面积丢失。

这里统一走：
- 检索名 → clean_name_system.build_search_index_name（NFO → 文件夹名 → 文件名）
- 标准名 → renamer.generate_shadow_name_from_nfo（严格取 NFO），拿不到时退回检索名

两个函数各自读一次 NFO，没有共用缓存：扫描的耗时被 ffprobe（子进程 + 读文件头）
主导，NFO 是同目录下的小 XML，多读一次的代价可以忽略，换来的是不必在此处
猜"该把哪个 NFO 传给谁"（视频级 NFO 与 tvshow.nfo 结构不同，传错会算出错误的季集号）。
"""

import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 文件名带 SxxExx 的按剧集处理，否则按电影处理
_EPISODE_RE = re.compile(r"S\d+E\d+", re.IGNORECASE)

# 填名算法版本。扫描时同尺寸文件走"复用"分支、直接沿用旧条目，
# 若不比对版本号，算法改好后老条目永远不会被重算——用户重扫看不到任何变化。
# 版本不一致的条目在下次扫描时补算一次，算完打上版本号，之后不再重复读 NFO。
# 取名逻辑有实质改动时 +1，触发全库一次性升级。
FILLER_VERSION = 2
_VERSION_FIELD = "names_filled_v"


def needs_refill(item: dict) -> bool:
    """复用的旧条目是否需要按当前算法重算名字"""
    return item.get(_VERSION_FIELD) != FILLER_VERSION


def fill_search_index_name(item: dict) -> Tuple[bool, str]:
    """填充检索名，返回 (是否写入, 用于兜底标准名的 display)。

    走 safe_update_clean_name，因此不会把已有的高优先级名字（manual/nfo）降级。
    """
    from clean_name_system import build_search_index_name, safe_update_clean_name

    file_path = item.get("file_path", "")
    file_name = item.get("file_name", "")
    if not file_path or not file_name:
        return False, ""

    try:
        result = build_search_index_name(file_path, file_name)
    except Exception as e:
        logger.debug(f"[scan_names] 检索名生成失败 {file_name}: {e}")
        return False, ""

    if not result or not result.display:
        return False, ""

    return safe_update_clean_name(item, result), result.display


def fill_standard_name(item: dict, fallback_display: str = "") -> bool:
    """填充标准名：优先 NFO，其次用检索名兜底。"""
    from renamer import generate_shadow_name_from_nfo
    from shadow_name_manager import apply_auto_fill

    file_path = item.get("file_path", "")
    file_name = item.get("file_name", "")
    if not file_path:
        return False

    folder = os.path.dirname(file_path)
    folder_type = "tv" if _EPISODE_RE.search(file_name) else "movie"

    shadow: Optional[str] = None
    try:
        shadow = generate_shadow_name_from_nfo(file_path, folder, folder_type)
    except Exception as e:
        logger.debug(f"[scan_names] NFO 标准名生成失败 {file_name}: {e}")

    source = "nfo"
    if not shadow:
        shadow, source = fallback_display, "parsed"
    if not shadow:
        return False

    return apply_auto_fill(item, shadow, source=source)


def fill_names_for_item(item: dict) -> Tuple[bool, bool]:
    """给单个扫描条目填充检索名与标准名，返回 (检索名已写, 标准名已写)。"""
    clean_filled, display = fill_search_index_name(item)
    shadow_filled = fill_standard_name(item, fallback_display=display)
    # 打上版本号：无论这次是否真的写入（可能被 manual 保护挡住），都算已按当前算法处理过，
    # 避免每次扫描都为同一批条目重复读 NFO
    item[_VERSION_FIELD] = FILLER_VERSION
    return clean_filled, shadow_filled
