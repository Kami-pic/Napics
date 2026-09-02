"""
路由模块：search_single — 单源搜索 + 单关键词搜索
从 routes/search.py 拆分
"""
import re
import logging
import concurrent.futures

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from shared import config_m, get_clients
import searcher, douban_client, bangumi_client
from bt_search_provider_factory import (
    LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES,
    get_direct_bt_provider_map,
)
from prowlarr_search_provider_factory import get_prowlarr_provider_map
from global_filter import GlobalFilter
from search_helpers import (
    enrich_result as _enrich_result,
    merge_bt_extra_sources as _merge_bt_extra_sources,
)
from provider_models import SearchCandidate, SearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _candidate_to_search_result(candidate: SearchCandidate) -> searcher.SearchResult:
    from quality_parser import parse_quality, get_quality_level
    quality = parse_quality(candidate.title)
    return searcher.SearchResult(
        title=candidate.title,
        size_gb=candidate.size_gb,
        indexer=candidate.indexer or candidate.provider_id,
        seeders=candidate.seeders,
        leechers=candidate.leechers,
        download_url=candidate.download_url,
        info_url=candidate.info_url,
        quality_tag=quality.display if quality.display else (candidate.raw_quality or "Unknown"),
        quality=quality,
        quality_rank=get_quality_level(quality).rank,
    )


@router.get("/api/search/source")
def search_single_source(
    source: str,
    keyword: str,
    fallback_keywords: str = "",
):
    """单源搜索端点：搜指定源，支持回退链。返回普通 JSON。"""
    from plugin_guard import is_bt_source_allowed
    if not is_bt_source_allowed(source):
        return {"error": f"搜索源 {source} 未安装对应插件", "results": [], "search_keywords": [], "hit_keyword": ""}
    kw_list = [keyword.strip()]
    if fallback_keywords:
        for fb in fallback_keywords.split(","):
            fb = fb.strip()
            if fb and fb.lower() not in {k.lower() for k in kw_list}:
                kw_list.append(fb)

    direct_providers = get_direct_bt_provider_map()
    source_getters = {"prowlarr": None, **direct_providers}

    try:
        from plugin_context import get_plugin_providers
        from search_service import _PluginScraperAdapter, _PluginSearchAdapter
        for pid, info in get_plugin_providers().items():
            if info["type"] == "scraper_search":
                source_getters[pid] = _PluginScraperAdapter(pid, info)
            elif info["type"] == "search":
                source_getters[pid] = _PluginSearchAdapter(pid, info)
    except Exception:
        pass

    if source not in source_getters:
        return {
            "error": f"搜索源 {source} 已安装，但运行时未注册对应 Provider",
            "error_code": "provider_not_registered",
            "results": [],
            "search_keywords": [],
            "hit_keyword": "",
        }

    searched = []
    hit_kw = ""
    all_results = []

    try:
        if source == "prowlarr":
            clients = get_clients()
            provider = get_prowlarr_provider_map(client_factory=lambda: clients["search"])["prowlarr"]
            for kw in kw_list:
                searched.append(kw)
                candidates = provider.search(SearchRequest(query=kw, limit=0))
                raw = [_candidate_to_search_result(candidate) for candidate in candidates]
                if raw:
                    if not hit_kw:
                        hit_kw = kw
                    seen = set()
                    for r in raw:
                        if r.download_url and r.download_url not in seen:
                            seen.add(r.download_url)
                            all_results.append(r)
                    break
        else:
            provider = source_getters[source]
            for kw in kw_list:
                searched.append(kw)
                candidates = provider.search(SearchRequest(query=kw, limit=40))
                if candidates:
                    if not hit_kw:
                        hit_kw = kw
                    all_results.extend(_candidate_to_search_result(candidate) for candidate in candidates)
                    break
    except Exception as e:
        return {
            "error": str(e), "results": [],
            "search_keywords": searched, "hit_keyword": hit_kw,
        }

    # 去重 + enrich
    deduped = []
    hashes = set()
    for r in all_results:
        h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
        if h:
            hu = h.group(1).upper()
            if hu in hashes:
                continue
            hashes.add(hu)
        deduped.append(r)

    match_names = list(dict.fromkeys([keyword] + kw_list + ([hit_kw] if hit_kw else [])))
    enrich_query = hit_kw or keyword
    enriched = [_enrich_result(r, enrich_query, match_names=match_names) for r in deduped]

    return {
        "source": source,
        "results": enriched,
        "count": len(enriched),
        "search_keywords": searched,
        "hit_keyword": hit_kw,
    }


@router.get("/search/single")
def search_single_keyword(
    keyword: str,
    media_type: str = "",
    skip_filter: bool = False,
    year: str = "",
):
    """单关键词搜索。

    skip_filter=False（默认）：含二次匹配+全局过滤
    skip_filter=True：Prowlarr 裸搜，不做任何过滤

    year 传了才参与：二次匹配的年份关卡 + 匹配加分。不传就是原来的行为。
    """
    from plugin_guard import get_allowed_bt_sources

    allowed_bt = get_allowed_bt_sources()
    if not allowed_bt:
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    clients = None
    raw_results = []
    if "prowlarr" in allowed_bt:
        clients = get_clients()
        prowlarr_provider = get_prowlarr_provider_map(
            client_factory=lambda: clients["search"]
        )["prowlarr"]
        try:
            candidates = prowlarr_provider.search(SearchRequest(query=keyword, limit=0))
            raw_results = [_candidate_to_search_result(candidate) for candidate in candidates]
        except Exception as e:
            logger.error(f"[Search/Single] Prowlarr error: {e}")

    if not raw_results and not skip_filter:
        raw_results = _merge_bt_extra_sources(
            keyword,
            [],
            allowed_sources=allowed_bt,
        )

    total_raw = len(raw_results)
    if not raw_results and not skip_filter:
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    # 去重
    seen = set()
    deduped = []
    for r in raw_results:
        if r.download_url and r.download_url not in seen:
            seen.add(r.download_url)
            deduped.append(r)

    # 裸搜模式
    if skip_filter:
        all_results = list(deduped)
        try:
            bt_overrides = config_m.config.bt_search_sources or {}
            direct_providers = get_direct_bt_provider_map()
            providers = [
                (name, direct_providers[name])
                for name in LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES
                if name in direct_providers and name in allowed_bt
            ]
            existing_hashes = set()
            for r in all_results:
                h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                if h:
                    existing_hashes.add(h.group(1).upper())

            def _search_source(name_provider):
                name, provider = name_provider
                if not bt_overrides.get(name, True):
                    return []
                try:
                    candidates = provider.search(SearchRequest(query=keyword, limit=20))
                    return [_candidate_to_search_result(candidate) for candidate in candidates]
                except:
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_search_source, sg): sg[0] for sg in providers}
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        results = future.result(timeout=5)
                        for r in results:
                            h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                            if h:
                                hash_upper = h.group(1).upper()
                                if hash_upper not in existing_hashes:
                                    existing_hashes.add(hash_upper)
                                    all_results.append(r)
                    except:
                        pass
        except Exception as e:
            logger.error(f"[Search/Single] 直搜源合并失败: {e}")

        return {
            "keyword": keyword,
            "bt_count": len(all_results),
            "bt_results": [_enrich_result(r, keyword, target_year=year) for r in all_results],
            "total_raw": total_raw,
            "total_filtered": len(all_results),
        }

    # 智能过滤模式
    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        from secondary_matcher import SecondaryMatcher

        if media_type:
            from plugin_guard import is_metadata_allowed

            resolver = AliasResolver(
                douban_client,
                bangumi_client,
                enable_douban=is_metadata_allowed("douban"),
                enable_bangumi=is_metadata_allowed("bangumi"),
            )
            aliases = resolver.resolve(keyword, "", media_type)
            target_titles = [keyword]
            if aliases:
                target_titles.extend(aliases.cn_names or [])
                target_titles.extend(aliases.en_names or [])
            target_titles = list(dict.fromkeys(t for t in target_titles if t))

            matcher = SecondaryMatcher()
            bt_titles = [r.title for r in deduped]
            passed = matcher.batch_filter(
                bt_titles=bt_titles,
                target_titles=target_titles,
                target_year=year,
                media_type=media_type,
            )
            # 年份过滤后一条不剩时退回不带年份：BT 标题的年份不完全可靠，
            # 宁可放宽也不要把本来能用的结果全过滤掉。
            if not passed and year:
                loose = matcher.batch_filter(
                    bt_titles=bt_titles,
                    target_titles=target_titles,
                    target_year="",
                    media_type=media_type,
                )
                if loose:
                    logger.info(f"[Search/Single] '{keyword}' 年份过滤后为空，退回不带年份")
                    passed = loose
            deduped = [deduped[i] for i in passed]

        if deduped:
            filter_passed = gf.apply([r.title for r in deduped])
            deduped = [deduped[i] for i in filter_passed]

        return {
            "keyword": keyword,
            "bt_count": len(deduped),
            "bt_results": [r.dict() for r in deduped],
            "total_raw": total_raw,
            "total_filtered": len(deduped),
        }
    except Exception as e:
        logger.error(f"[Search/Single] error: {e}")
        if clients is not None:
            raw = clients["search"].search(keyword)
        else:
            raw = deduped
        return {"keyword": keyword, "bt_count": len(raw), "bt_results": [r.dict() for r in raw], "total_raw": len(raw), "total_filtered": len(raw)}
