"""
路由模块：search
"""
import json
import logging
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import (
    config_m, indexer_m,
    _get_pan_search_service,
    get_clients,
)
import searcher, douban_client, bangumi_client
from bt_search_provider_factory import (
    LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES,
    get_direct_bt_provider_map,
)
from global_filter import GlobalFilter
from search_helpers import enrich_result as _enrich_result, merge_bt_extra_sources as _merge_bt_extra_sources
from search_service import (
    build_keywords, search_all_sources_iter,
    BT_SOURCE_DEFAULTS as _BT_SOURCE_DEFAULTS,
    PAN_SOURCE_DEFAULTS as _PAN_SOURCE_DEFAULTS,
)
from provider_models import SearchCandidate, SearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def _candidate_to_search_result(candidate: SearchCandidate) -> searcher.SearchResult:
    return searcher.SearchResult(
        title=candidate.title,
        size_gb=candidate.size_gb,
        indexer=candidate.indexer or candidate.provider_id,
        seeders=candidate.seeders,
        leechers=candidate.leechers,
        download_url=candidate.download_url,
        info_url=candidate.info_url,
        quality_tag=candidate.raw_quality,
    )


@router.get("/api/search")
def search_resources(
    query: str,
    enhanced: bool = True,
    media_type: str = "",
    year: str = "",
    shadow_name: str = "",
    clean_name: str = "",
    season: int = 0,
    total_episodes: int = 0,
):
    """搜索资源。增强搜索：回退链 + 二次匹配 + 全局过滤 + 综合排序。"""
    clients = get_clients()
    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        resolver = AliasResolver(douban_client, bangumi_client)
        aliases = resolver.resolve(query, "", media_type)
        indexer_m.load()

        resp = searcher.enhanced_search(
            client=clients["search"],
            title=query,
            aliases=aliases,
            year="",
            media_type=media_type,
            indexer_manager=indexer_m,
            shadow_name=shadow_name,
            clean_name=clean_name,
            global_filter=gf,
        )

        bt_keyword = resp.hit_keyword or query
        bt_results_list = _merge_bt_extra_sources(bt_keyword, list(resp.results))

        return {
            "query": query,
            "bt_count": len(bt_results_list),
            "bt_results": [_enrich_result(r, query) for r in bt_results_list],
            "hit_keyword": resp.hit_keyword,
            "total_raw": resp.total_raw,
            "total_filtered": len(bt_results_list),
            "enhanced": True,
        }
    except Exception as e:
        logger.error(f"[Search] Enhanced search failed, fallback: {e}")

    bt_results = clients["search"].search(query)
    bt_results = _merge_bt_extra_sources(query, bt_results)

    return {
        "query": query,
        "bt_count": len(bt_results),
        "bt_results": [_enrich_result(r, query) for r in bt_results],
        "hit_keyword": query,
        "total_raw": len(bt_results),
        "total_filtered": len(bt_results),
        "enhanced": False,
    }


@router.get("/api/search/stream")
def search_resources_stream(
    query: str,
    media_type: str = "",
    shadow_name: str = "",
    clean_name: str = "",
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    season_number: int = 0,
):
    """SSE 流式搜索：所有源全部并行，每个源用最适合的语言搜索词 + 回退链。"""
    def _generate():
        keywords = build_keywords(
            query=query, cn_name=cn_name, en_name=en_name,
            original_name=original_name, shadow_name=shadow_name,
            season_number=season_number,
        )
        clients = get_clients()
        conf = config_m.config
        bt_overrides = conf.bt_search_sources or {}

        yield from search_all_sources_iter(
            keywords=keywords,
            query=query,
            bt_overrides=bt_overrides,
            search_client=clients["search"],
        )

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/api/search/source")
def search_single_source(
    source: str,
    keyword: str,
    fallback_keywords: str = "",
):
    """单源搜索端点：搜指定源，支持回退链。返回普通 JSON。

    参数：
    - source: 源名称（prowlarr/bitsearch/cilixiong/xl720/nyaa/mikan/yts/limetorrents/acgrip/bangumi_moe）
    - keyword: 主搜索词
    - fallback_keywords: 逗号分隔的回退词列表（可选，用户手动改词后不传）
    """
    # 构造搜索词列表
    kw_list = [keyword.strip()]
    if fallback_keywords:
        for fb in fallback_keywords.split(","):
            fb = fb.strip()
            if fb and fb.lower() not in {k.lower() for k in kw_list}:
                kw_list.append(fb)

    # 获取源的搜索函数
    direct_providers = get_direct_bt_provider_map()
    source_getters = {"prowlarr": None, **direct_providers}

    if source not in source_getters:
        return {"error": f"未知源: {source}", "results": [], "search_keywords": [], "hit_keyword": ""}

    searched = []
    hit_kw = ""
    all_results = []

    try:
        if source == "prowlarr":
            clients = get_clients()
            for kw in kw_list:
                searched.append(kw)
                raw = clients["search"].search(kw)
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
            provider = direct_providers[source]
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

    # 去重 + enrich（用命中的搜索词做匹配，构造 match_names）
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

    # 构造 match_names：搜索词 + 回退词 + 命中词
    match_names = list(dict.fromkeys([keyword] + kw_list + ([hit_kw] if hit_kw else [])))
    enrich_query = hit_kw or keyword  # 用命中的搜索词做主匹配
    enriched = [_enrich_result(r, enrich_query, match_names=match_names) for r in deduped]

    return {
        "source": source,
        "results": enriched,
        "count": len(enriched),
        "search_keywords": searched,
        "hit_keyword": hit_kw,
    }


@router.get("/search/pan")
def search_pan(keyword: str, media_type: str = ""):
    """网盘搜索聚合接口。"""
    try:
        service = _get_pan_search_service()
        response = service.search_sync(keyword, media_type=media_type)
        return response.dict()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"results": [], "groups": {}, "source_statuses": [{"name": "error", "status": "failed", "count": 0, "error": str(e)}], "total": 0}

@router.get("/alist/mounts")
def get_alist_mounts():
    """获取 OpenList 已挂载网盘列表。"""
    try:
        clients = get_clients()
        alist = clients.get("alist")
        if not alist:
            return {"mounts": [], "error": "OpenList 未配置"}
        mounts = alist.get_mounts_list()
        return {"mounts": [m.dict() for m in mounts]}
    except Exception as e:
        return {"mounts": [], "error": str(e)}

@router.post("/alist/transfer")
def transfer_pan_resource(req: dict):
    """网盘资源转存接口。
    夸克链接 → 调用夸克转存 API 自动保存到自己的夸克网盘。
    其他网盘 → 返回提示让用户手动保存。
    """
    try:
        share_url = req.get("share_url", "")
        pan_type = req.get("pan_type", "")
        passcode = req.get("password", "")

        if not share_url:
            return {"success": False, "error_code": "missing_url", "error_message": "缺少分享链接"}

        # 夸克链接 → 自动转存
        if pan_type == "quark":
            from quark_transfer import QuarkTransfer
            conf = config_m.config
            qt = QuarkTransfer.from_alist(conf.alist_url, conf.alist_token)
            if not qt:
                return {"success": False, "error_code": "no_cookie", "error_message": "无法获取夸克 Cookie，请检查 OpenList 夸克存储配置"}
            result = qt.transfer(share_url, passcode)
            return result

        # 其他网盘 → 暂不支持自动转存
        return {"success": False, "error_code": "unsupported",
                "error_message": f"{pan_type} 暂不支持自动转存，请手动打开链接保存"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error_code": "server_error", "error_message": str(e)}

@router.get("/search/single")
def search_single_keyword(
    keyword: str,
    media_type: str = "",
    skip_filter: bool = False,
):
    """单关键词搜索。

    skip_filter=False（默认）：含二次匹配+全局过滤（不含年份匹配）
    skip_filter=True：Prowlarr 裸搜，不做任何过滤
    """
    clients = get_clients()

    # 搜索 Prowlarr
    try:
        raw_results = clients["search"].search(keyword)
    except Exception as e:
        logger.error(f"[Search/Single] Prowlarr error: {e}")
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    total_raw = len(raw_results)
    if not raw_results:
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    # 去重
    seen = set()
    deduped = []
    for r in raw_results:
        if r.download_url and r.download_url not in seen:
            seen.add(r.download_url)
            deduped.append(r)

    # 裸搜模式：跳过所有过滤，合并直搜源（后台线程，不阻塞返回）
    if skip_filter:
        # 先返回 Prowlarr 结果，直搜源结果通过 /api/search 接口获取
        all_results = list(deduped)
        # 尝试快速合并直搜源（有缓存时秒返回）
        try:
            bt_overrides = config_m.config.bt_search_sources or {}
            direct_providers = get_direct_bt_provider_map()
            providers = [
                (name, direct_providers[name])
                for name in LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES
                if name in direct_providers
            ]
            existing_hashes = set()
            for r in all_results:
                h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                if h:
                    existing_hashes.add(h.group(1).upper())

            import concurrent.futures
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
            "bt_results": [_enrich_result(r, keyword) for r in all_results],
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


        # 二次匹配（仅标题匹配，不含年份）
        if media_type:
            resolver = AliasResolver(douban_client, bangumi_client)
            aliases = resolver.resolve(keyword, "", media_type)
            target_titles = [keyword]
            if aliases:
                target_titles.extend(aliases.cn_names or [])
                target_titles.extend(aliases.en_names or [])
            target_titles = list(dict.fromkeys(t for t in target_titles if t))

            matcher = SecondaryMatcher()
            passed = matcher.batch_filter(
                bt_titles=[r.title for r in deduped],
                target_titles=target_titles,
                target_year="",
                media_type=media_type,
            )
            deduped = [deduped[i] for i in passed]

        # 全局过滤
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
        # fallback 到裸搜
        raw = clients["search"].search(keyword)
        return {"keyword": keyword, "bt_count": len(raw), "bt_results": [r.dict() for r in raw], "total_raw": len(raw), "total_filtered": len(raw)}


# ── 搜索源管理（配置数据从 search_service 导入）──


@router.get("/search/sources")
def get_search_sources():
    """获取所有搜索源及启用状态和代理配置。"""
    conf = config_m.config
    bt_overrides = conf.bt_search_sources or {}
    pan_overrides = conf.pan_search_sources or {}

    sources = []
    for name, info in _BT_SOURCE_DEFAULTS.items():
        override = bt_overrides.get(name)
        if isinstance(override, dict):
            enabled = override.get("enabled", info["enabled"])
            proxy = override.get("proxy", info.get("needs_proxy", False))
        elif isinstance(override, bool):
            enabled = override
            proxy = info.get("needs_proxy", False)
        else:
            enabled = info["enabled"]
            proxy = info.get("needs_proxy", False)
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": enabled, "needs_proxy": info.get("needs_proxy", False),
            "proxy": proxy,
        })
    for name, info in _PAN_SOURCE_DEFAULTS.items():
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": pan_overrides.get(name, info["enabled"]),
        })
    return {"sources": sources}


@router.put("/search/sources/{name}")
def toggle_search_source(name: str, req: dict):
    """切换搜索源启用/禁用/代理。

    请求体支持：
    - {"enabled": true} — 只切换启用
    - {"enabled": true, "proxy": false} — 同时切换启用和代理
    - {"proxy": false} — 只切换代理
    """
    conf = config_m.config

    # 判断是 BT 源还是网盘源
    if name in _BT_SOURCE_DEFAULTS:
        if not conf.bt_search_sources:
            conf.bt_search_sources = {}

        has_proxy_field = "proxy" in req
        has_enabled_field = "enabled" in req

        if has_proxy_field:
            # 需要用字典格式存储
            current = conf.bt_search_sources.get(name)
            if isinstance(current, dict):
                new_val = dict(current)
            else:
                # 从旧格式迁移
                default_enabled = _BT_SOURCE_DEFAULTS[name]["enabled"]
                new_val = {"enabled": current if isinstance(current, bool) else default_enabled}
            if has_enabled_field:
                new_val["enabled"] = req["enabled"]
            new_val["proxy"] = req["proxy"]
            conf.bt_search_sources[name] = new_val
        else:
            # 只切换 enabled，保持原有格式
            current = conf.bt_search_sources.get(name)
            if isinstance(current, dict):
                current["enabled"] = req.get("enabled", True)
                conf.bt_search_sources[name] = current
            else:
                conf.bt_search_sources[name] = req.get("enabled", True)

    elif name in _PAN_SOURCE_DEFAULTS:
        if not conf.pan_search_sources:
            conf.pan_search_sources = {}
        conf.pan_search_sources[name] = req.get("enabled", True)
    else:
        raise HTTPException(status_code=404, detail=f"未知搜索源: {name}")

    config_m.save(conf)
    return {"ok": True, "name": name}
