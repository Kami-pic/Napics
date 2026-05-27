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

    过滤链：标题匹配 → 质量 → 包含/排除关键词 → 集数匹配（含 Quality Cutoff）→ 指纹去重
    """
    result = items

    # 0. 标题匹配（跨语言，用 L1+L2）
    result = _filter_title_match(result, subscription)

    # 1. 质量过滤
    result = _filter_quality(result, subscription.quality)

    # 2. 包含/排除关键词
    result = _filter_keywords(result, subscription.include, subscription.exclude)

    # 3. 集数匹配 + 指纹去重 + Quality Cutoff
    result = _filter_episodes(result, subscription)

    return result


def _filter_title_match(items: List[RSSItem], subscription) -> List[RSSItem]:
    """标题匹配过滤：用 L1 normalize + L2 match_chain 做跨语言匹配。

    从订阅的 aliases 构造候选名称列表，和 RSS 条目标题做匹配。
    match_score < 20 的条目过滤掉（明显不相关）。
    """
    if not items:
        return items

    # 构造候选名称
    aliases = getattr(subscription, "aliases", {}) or {}
    candidates = []
    if subscription.title:
        candidates.append(subscription.title)
    for key in ("cn", "en", "original"):
        for name in (aliases.get(key) or []):
            if name and name not in candidates:
                candidates.append(name)
    if subscription.search_keyword and subscription.search_keyword not in candidates:
        candidates.append(subscription.search_keyword)

    if not candidates:
        return items

    try:
        from match_scoring import match_chain
        from search_helpers import extract_bt_title_for_match

        filtered = []
        for item in items:
            bt_clean = extract_bt_title_for_match(item.title)
            targets = [bt_clean] if bt_clean else [item.title]
            score = match_chain(candidates, targets, [])
            if score >= 20:
                filtered.append(item)
        return filtered
    except Exception:
        # L1/L2 导入失败时不过滤，保持原有行为
        return items


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
    """集数匹配 + 指纹去重 + Quality Cutoff。

    电影：只要没下载过就通过
    剧集：只保留缺失集（不在 downloaded_episodes 中的）
    best_version 模式：不受"已下载"限制，但仍做指纹去重（同 hash 不重复推送）
    Quality Cutoff：已下载集质量达到 target_quality 时，该集不再搜索更好版本
    """
    downloaded = subscription.downloaded_episodes or {}
    downloaded_hashes = set()
    for v in downloaded.values():
        if hasattr(v, 'info_hash') and v.info_hash:
            downloaded_hashes.add(v.info_hash)
        elif isinstance(v, dict) and v.get("info_hash"):
            downloaded_hashes.add(v["info_hash"])

    is_tv = subscription.type == "tv"
    target_season = subscription.season
    best_version = getattr(subscription, "best_version", False)

    # Quality Cutoff：已达到目标质量的集号集合
    cutoff_episodes = set()
    target_quality = getattr(subscription, "target_quality", "") or ""
    if target_quality and downloaded:
        target_rank = _QUALITY_MIN_RANK.get(target_quality, 0)
        if target_rank > 0:
            for ep_key, ep_info in downloaded.items():
                qt = ""
                if hasattr(ep_info, "quality_tag"):
                    qt = ep_info.quality_tag
                elif isinstance(ep_info, dict):
                    qt = ep_info.get("quality_tag", "")
                if qt:
                    quality = parse_quality(qt)
                    level = get_quality_level(quality)
                    if level.rank >= target_rank:
                        cutoff_episodes.add(ep_key)

    filtered = []
    for item in items:
        # 指纹去重：完全相同的 hash 不再推送
        if item.info_hash and item.info_hash in downloaded_hashes:
            continue

        if best_version:
            # 洗版模式：不限制已下载集，但需要质量更高才有意义
            if is_tv:
                if item.episode is None:
                    if _looks_like_season_pack(item.title):
                        filtered.append(item)
                    continue
                if target_season and item.season and item.season != target_season:
                    continue
                # Quality Cutoff：该集已达到目标质量，不再洗版
                if str(item.episode) in cutoff_episodes:
                    continue
            filtered.append(item)
        else:
            # 正常模式
            if is_tv:
                if item.episode is None:
                    if _looks_like_season_pack(item.title):
                        filtered.append(item)
                    continue
                if target_season and item.season and item.season != target_season:
                    continue
                ep_key = str(item.episode)
                if ep_key in downloaded:
                    continue
                filtered.append(item)
            else:
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
