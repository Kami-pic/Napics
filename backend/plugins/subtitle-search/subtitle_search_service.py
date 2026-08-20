"""字幕多源搜索编排。

职责：
- 管理三个源的客户端单例（配置变更时可重置）
- 为每个源生成各自的搜索词回退链（中文源 cn 优先，SubDL en 优先）
- 并发搜索、逐词回退、合并去重
- 按来源分派下载
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from assrt_client import AssrtClient
from subdl_client import SubdlClient
from subhd_client import SubhdClient
from subtitle_keywords import (
    base_names_for_source,
    build_keyword_tags,
    keywords_for_source,
)
from subtitle_matching import build_match_candidates, enrich_items
from subtitle_models import SubtitleSearchItem, SubtitleSourceStat

logger = logging.getLogger(__name__)

# 结果排序时的源优先级（中文源优先展示）
_SOURCE_ORDER = {"assrt": 0, "subhd": 1, "subdl": 2}

# 客户端单例
_assrt_client: Optional[AssrtClient] = None
_subdl_client: Optional[SubdlClient] = None
_subhd_client: Optional[SubhdClient] = None


def _config():
    """读取系统配置（插件不直接依赖 shared 之外的内部模块）"""
    from shared import config_m
    return config_m.config


def reset_clients() -> None:
    """配置变更后清空单例，下次请求按新配置重建"""
    global _assrt_client, _subdl_client, _subhd_client
    _assrt_client = None
    _subdl_client = None
    _subhd_client = None


def set_assrt_client(client: AssrtClient) -> None:
    global _assrt_client
    _assrt_client = client


def set_subdl_client(client: SubdlClient) -> None:
    global _subdl_client
    _subdl_client = client


def set_subhd_client(client: SubhdClient) -> None:
    global _subhd_client
    _subhd_client = client


def get_assrt_client() -> Optional[AssrtClient]:
    """assrt 需要 token，未配置时该源不可用"""
    global _assrt_client
    if _assrt_client is None:
        try:
            conf = _config()
            token = (conf.assrt_token or "").strip()
            if token:
                _assrt_client = AssrtClient(token=token, proxy=conf.http_proxy or "")
        except Exception as e:
            logger.warning(f"[subtitle] assrt 客户端初始化失败: {e}")
    return _assrt_client


def get_subdl_client() -> Optional[SubdlClient]:
    """SubDL 需要 api_key，未配置时该源不可用"""
    global _subdl_client
    if _subdl_client is None:
        try:
            conf = _config()
            api_key = (getattr(conf, "subdl_api_key", "") or "").strip()
            if api_key:
                _subdl_client = SubdlClient(api_key=api_key, proxy=conf.http_proxy or "")
        except Exception as e:
            logger.warning(f"[subtitle] SubDL 客户端初始化失败: {e}")
    return _subdl_client


def get_subhd_client() -> Optional[SubhdClient]:
    """SubHD 走页面解析，无需凭据"""
    global _subhd_client
    if _subhd_client is None:
        try:
            conf = _config()
            _subhd_client = SubhdClient(proxy=conf.http_proxy or "")
        except Exception as e:
            logger.warning(f"[subtitle] SubHD 客户端初始化失败: {e}")
    return _subhd_client


def search_all_sources(
    *,
    query: str = "",
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    folder_type: str = "",
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
    episode_tag: str = "",
    is_file: bool = False,
    no_muxer: bool = True,
    cnt: int = 15,
) -> Tuple[List[SubtitleSearchItem], List[SubtitleSourceStat], str]:
    """三源并发搜索，返回 (合并结果, 各源情况, 主搜索词)。"""
    # 没传 episode_tag 时，用季集号补一个（与前端搜索升级同格式）
    if not episode_tag and season_number and episode_number:
        episode_tag = f"S{str(season_number).zfill(2)}E{str(episode_number).zfill(2)}"

    tags = build_keyword_tags(
        cn_name=cn_name,
        en_name=en_name,
        original_name=original_name,
        query=query,
        folder_type=folder_type,
        season_number=season_number,
        episode_tag=episode_tag,
    )
    if not tags:
        return [], [], query

    primary_keyword = tags[0].keyword

    tasks = {
        "assrt": lambda: _search_assrt(tags, is_file=is_file, no_muxer=no_muxer, cnt=cnt),
        "subhd": lambda: _search_subhd(tags, cnt=cnt),
        "subdl": lambda: _search_subdl(
            tags,
            season_number=season_number or 0,
            episode_number=episode_number or 0,
            folder_type=folder_type,
            cnt=cnt,
        ),
    }

    stats: List[SubtitleSourceStat] = []
    merged: List[SubtitleSearchItem] = []

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            source = futures[future]
            try:
                items, stat = future.result()
                merged.extend(items)
                stats.append(stat)
            except Exception as e:
                logger.warning(f"[subtitle] {source} 搜索异常: {e}")
                stats.append(SubtitleSourceStat(source=source, error=str(e)))

    # 相关性打分（复用 L2 匹配链），供排序与智能过滤使用
    match_candidates = build_match_candidates(
        cn_name=cn_name, en_name=en_name, original_name=original_name, query=query,
    )
    enrich_items(merged, match_candidates)

    merged = _dedupe_and_sort(merged)
    stats.sort(key=lambda s: _SOURCE_ORDER.get(s.source, 99))
    return merged, stats, primary_keyword


def _search_assrt(tags, *, is_file: bool, no_muxer: bool, cnt: int):
    """assrt：中文优先，逐词回退直到命中"""
    stat = SubtitleSourceStat(source="assrt")
    client = get_assrt_client()
    if client is None:
        stat.error = "未配置 assrt_token"
        return [], stat

    for keyword in keywords_for_source("assrt", tags):
        stat.searched_keywords.append(keyword)
        items, _ = client.search(keyword, is_file=is_file, no_muxer=no_muxer, cnt=cnt)
        if items:
            stat.hit_keyword = keyword
            stat.count = len(items)
            return items, stat
    return [], stat


def _search_subhd(tags, *, cnt: int):
    """SubHD：中文站，中文词优先，逐词回退"""
    stat = SubtitleSourceStat(source="subhd")
    client = get_subhd_client()
    if client is None:
        stat.error = "SubHD 客户端不可用"
        return [], stat

    for keyword in keywords_for_source("subhd", tags):
        stat.searched_keywords.append(keyword)
        items, _ = client.search(keyword, limit=cnt)
        if items:
            stat.hit_keyword = keyword
            stat.count = len(items)
            return items, stat
    return [], stat


def _search_subdl(tags, *, season_number: int, episode_number: int, folder_type: str, cnt: int):
    """SubDL：英文优先；季集号走请求参数，搜索词只用基础片名"""
    stat = SubtitleSourceStat(source="subdl")
    client = get_subdl_client()
    if client is None:
        stat.error = "未配置 subdl_api_key"
        return [], stat

    media_type = ""
    if season_number > 0 or folder_type in ("tv", "series", "season"):
        media_type = "tv"
    elif folder_type == "movie":
        media_type = "movie"

    for keyword in base_names_for_source("subdl", tags):
        stat.searched_keywords.append(keyword)
        items, _ = client.search(
            keyword,
            media_type=media_type,
            season_number=season_number,
            episode_number=episode_number,
            limit=cnt,
        )
        if items:
            stat.hit_keyword = keyword
            stat.count = len(items)
            return items, stat
    return [], stat


def _dedupe_and_sort(items: List[SubtitleSearchItem]) -> List[SubtitleSearchItem]:
    """按 (来源, ID) 去重后按相关性排序。

    排序优先级：相关性分 > 非垃圾 > 中文源优先 > 用户评分。
    相关性优先是因为多源合并后，"哪个源" 远不如 "是不是这部片" 重要。
    """
    seen = set()
    unique: List[SubtitleSearchItem] = []
    for item in items:
        key = (item.source, item.id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    unique.sort(key=lambda i: (
        -(i.match_score or 0),
        i.is_junk,
        _SOURCE_ORDER.get(i.source, 99),
        -(i.vote_score or 0),
    ))
    return unique


def download_subtitle(
    *,
    source: str,
    subtitle_id: int,
    video_path: str,
    file_url: str = "",
    language_suffix: str = "",
    slug: str = "",
) -> Tuple[List[str], str]:
    """按来源分派下载，返回 (保存的文件列表, 错误信息)。"""
    if source == "subdl":
        client = get_subdl_client()
        if client is None:
            return [], "未配置 subdl_api_key"
        if not file_url:
            return [], "SubDL 结果缺少下载链接"
        return client.download_subtitle(file_url, video_path, language_suffix), ""

    if source == "subhd":
        client = get_subhd_client()
        if client is None:
            return [], "SubHD 客户端不可用"
        if not slug:
            return [], "SubHD 结果缺少标识，无法下载"
        saved = client.download_subtitle(slug, video_path, language_suffix)
        if not saved:
            return [], "SubHD 未返回可用下载链接（站点限流或需要登录）"
        return saved, ""

    # 默认 assrt：直链优先，否则查详情取文件列表
    client = get_assrt_client()
    if client is None:
        return [], "未配置 assrt_token"

    download_url = file_url
    if not download_url:
        detail = client.detail(subtitle_id)
        if detail is None:
            return [], "无法获取字幕详情"
        if detail.filelist:
            download_url = detail.filelist[0].url
        elif detail.url:
            download_url = detail.url
        else:
            return [], "字幕无下载链接"

    return client.download_subtitle(download_url, video_path, language_suffix), ""
