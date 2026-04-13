"""RSS 条目匹配引擎：质量过滤 + 关键词过滤 + 集数匹配 + 指纹去重。

职责：接收 RSSItem 列表和 Subscription，返回匹配的条目。
和源解耦，不关心条目从哪来。
"""

import re
from typing import List, Dict

from rss_source_base import RSSItem
from quality_parser import parse_quality, get_quality_level

# 分辨率最低要求映射
_QUALITY_MIN_RANK = {
    "720p": 2,
    "1080p": 3,
    "2160p": 6,
}


def match_items(items: List[RSSItem], subscription) -> List[RSSItem]:
    """对 RSS 条目列表执行匹配过滤，返回符合订阅要求的条目。

    过滤链：质量 → 包含/排除关键词 → 集数匹配 → 指纹去重
    """
    result = items

    # 1. 质量过滤
    result = _filter_quality(result, subscription.quality)

    # 2. 包含/排除关键词
    result = _filter_keywords(result, subscription.include, subscription.exclude)

    # 3. 集数匹配 + 指纹去重
    result = _filter_episodes(result, subscription)

    return result


def _filter_quality(items: List[RSSItem], min_quality: str) -> List[RSSItem]:
    """过滤不满足最低质量要求的条目"""
    min_rank = _QUALITY_MIN_RANK.get(min_quality, 0)
    if min_rank == 0:
        return items

    filtered = []
    for item in items:
        quality = parse_quality(item.title)
        level = get_quality_level(quality)
        if level.rank >= min_rank:
            filtered.append(item)
    return filtered


def _filter_keywords(items: List[RSSItem], include: str, exclude: str) -> List[RSSItem]:
    """包含/排除关键词过滤"""
    if not include and not exclude:
        return items

    include_words = [w.strip().lower() for w in include.split(",") if w.strip()] if include else []
    exclude_words = [w.strip().lower() for w in exclude.split(",") if w.strip()] if exclude else []

    filtered = []
    for item in items:
        title_lower = item.title.lower()
        # 排除词命中 → 跳过
        if any(w in title_lower for w in exclude_words):
            continue
        # 包含词全部命中才通过（AND 逻辑）
        if include_words and not all(w in title_lower for w in include_words):
            continue
        filtered.append(item)
    return filtered


def _filter_episodes(items: List[RSSItem], subscription) -> List[RSSItem]:
    """集数匹配 + 指纹去重。

    电影：只要没下载过就通过
    剧集：只保留缺失集（不在 downloaded_episodes 中的）
    """
    downloaded = subscription.downloaded_episodes or {}
    downloaded_hashes = {ep.info_hash for ep in downloaded.values() if hasattr(ep, 'info_hash') and ep.info_hash}
    # 兼容 dict 格式
    if downloaded and isinstance(list(downloaded.values())[0], dict):
        downloaded_hashes = {v.get("info_hash", "") for v in downloaded.values() if v.get("info_hash")}

    is_tv = subscription.type == "tv"
    target_season = subscription.season

    filtered = []
    for item in items:
        # 指纹去重：已下载的 hash 不再推送
        if item.info_hash and item.info_hash in downloaded_hashes:
            continue

        if is_tv:
            # 剧集：必须有集号，且该集未下载
            if item.episode is None:
                # 可能是整季包，保留
                if _looks_like_season_pack(item.title):
                    filtered.append(item)
                continue
            # 季号校验（如果订阅指定了季号）
            if target_season and item.season and item.season != target_season:
                continue
            # 该集已下载 → 跳过
            ep_key = str(item.episode)
            if ep_key in downloaded:
                continue
            filtered.append(item)
        else:
            # 电影：只要没下载过就通过
            if "0" not in downloaded:
                filtered.append(item)

    return filtered


def _looks_like_season_pack(title: str) -> bool:
    """判断标题是否像整季包"""
    upper = title.upper()
    # 包含 "S01" 但不包含 "E01" → 可能是整季
    has_season = bool(re.search(r"S\d{1,2}", upper))
    has_episode = bool(re.search(r"E\d{1,4}", upper))
    # 包含 "Complete" / "全集" / "Batch"
    has_complete = any(w in upper for w in ["COMPLETE", "全集", "BATCH", "合集"])
    return (has_season and not has_episode) or has_complete
