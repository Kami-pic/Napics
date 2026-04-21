"""
路由模块：search
"""
import json
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import (
    config_m, indexer_m,
    _get_pan_search_service,
    _get_bitsearch_scraper, _get_cilixiong_scraper, _get_xl720_scraper, _get_nyaa_scraper,
    _get_mikan_scraper, _get_yts_scraper, _get_limetorrents_scraper, _get_acgrip_scraper,
    _get_bangumi_moe_scraper,
    get_clients,
)
import searcher, douban_client, bangumi_client
from global_filter import GlobalFilter
from search_helpers import enrich_result as _enrich_result, merge_bt_extra_sources as _merge_bt_extra_sources

router = APIRouter()


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
        print(f"[Search] Enhanced search failed, fallback: {e}")

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
        import concurrent.futures
        from text_processing import split_by_language, normalize as _normalize
        from search_keyword_mapper import MultiLangKeywords, get_search_keywords_for_source

        # 构造多语言搜索词集合
        parts = split_by_language(query)
        kw_cn = cn_name.strip() or parts.get("cn", "") or ""
        kw_en = en_name.strip() or shadow_name.strip() or parts.get("en", "") or ""
        kw_original = original_name.strip() or ""
        # 清洗中文名
        if kw_cn:
            kw_cn = _normalize(kw_cn)

        keywords = MultiLangKeywords(
            cn=kw_cn, en=kw_en, original=kw_original,
            query=query, season_number=season_number,
        )

        clients = get_clients()
        conf = config_m.config
        bt_overrides = conf.bt_search_sources or {}

        def _search_prowlarr():
            """Prowlarr 搜索 + 回退链"""
            try:
                kw_list = get_search_keywords_for_source("prowlarr", keywords)
                searched = []
                hit_kw = ""
                all_results = []
                for kw in kw_list:
                    searched.append(kw)
                    print(f"[SSE/Prowlarr] 搜索词: '{kw}'")
                    import time as _t
                    t0 = _t.time()
                    raw = clients["search"].search(kw)
                    elapsed = _t.time() - t0
                    print(f"[SSE/Prowlarr] '{kw}' 返回 {len(raw)} 条，耗时 {elapsed:.1f}s")
                    if raw:
                        if not hit_kw:
                            hit_kw = kw
                        seen = set()
                        for r in raw:
                            if r.download_url and r.download_url not in seen:
                                seen.add(r.download_url)
                                all_results.append(r)
                        break  # 有结果就停止回退
                return "prowlarr", all_results, None, searched, hit_kw
            except Exception as e:
                print(f"[SSE/Prowlarr] 异常: {e}")
                return "prowlarr", [], str(e), [], ""

        def _search_direct(name, getter):
            """直搜源搜索 + 回退链"""
            try:
                s = getter()
                kw_list = get_search_keywords_for_source(name, keywords)
                searched = []
                hit_kw = ""
                all_results = []
                for kw in kw_list:
                    searched.append(kw)
                    results = s.search_as_search_results(kw, max_results=20)
                    if results:
                        if not hit_kw:
                            hit_kw = kw
                        all_results.extend(results)
                        break  # 有结果就停止回退
                return name, all_results, None, searched, hit_kw
            except Exception as e:
                return name, [], str(e), [], ""

        scrapers = [
            ("bitsearch", _get_bitsearch_scraper),
            ("cilixiong", _get_cilixiong_scraper),
            ("xl720", _get_xl720_scraper),
            ("nyaa", _get_nyaa_scraper),
            ("mikan", _get_mikan_scraper),
            ("yts", _get_yts_scraper),
            ("limetorrents", _get_limetorrents_scraper),
            ("acgrip", _get_acgrip_scraper),
            ("bangumi_moe", _get_bangumi_moe_scraper),
        ]

        # 推送所有源的 searching 状态
        all_sources = []
        if bt_overrides.get("prowlarr", _BT_SOURCE_DEFAULTS["prowlarr"]["enabled"]):
            all_sources.append("prowlarr")
        for name, _ in scrapers:
            default_enabled = _BT_SOURCE_DEFAULTS.get(name, {}).get("enabled", True)
            if bt_overrides.get(name, default_enabled):
                all_sources.append(name)
        for name in all_sources:
            yield f"data: {json.dumps({'type': 'status', 'source': name, 'status': 'searching'})}\n\n"

        # 全部并行提交，用 as_completed 逐个 yield
        with concurrent.futures.ThreadPoolExecutor(max_workers=11) as pool:
            future_map = {}
            if bt_overrides.get("prowlarr", _BT_SOURCE_DEFAULTS["prowlarr"]["enabled"]):
                f = pool.submit(_search_prowlarr)
                future_map[f] = "prowlarr"
            for name, getter in scrapers:
                default_enabled = _BT_SOURCE_DEFAULTS.get(name, {}).get("enabled", True)
                if bt_overrides.get(name, default_enabled):
                    f = pool.submit(_search_direct, name, getter)
                    future_map[f] = name

            completed_sources = set()
            try:
                for future in concurrent.futures.as_completed(future_map, timeout=65):
                    try:
                        name, results, err, searched, hit_kw = future.result(timeout=65)
                    except Exception as e:
                        name = future_map[future]
                        results, err, searched, hit_kw = [], str(e), [], ""
                    completed_sources.add(name)
                    # 同源内去重
                    source_deduped = []
                    source_hashes = set()
                    for r in results:
                        h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                        if h:
                            hu = h.group(1).upper()
                            if hu in source_hashes:
                                continue
                            source_hashes.add(hu)
                        source_deduped.append(r)
                    status = "done" if not err else "failed"
                    enriched = [_enrich_result(r, query) for r in source_deduped]
                    yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': status, 'count': len(results), 'added': len(source_deduped), 'error': err or '', 'search_keywords': searched, 'hit_keyword': hit_kw, 'results': enriched}, default=str)}\n\n"
            except concurrent.futures.TimeoutError:
                pass
            # 超时未完成的源推送 failed 状态
            for future, name in future_map.items():
                if name not in completed_sources:
                    yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': 'failed', 'count': 0, 'added': 0, 'error': '搜索超时', 'search_keywords': [], 'hit_keyword': '', 'results': []})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

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
    source_getters = {
        "prowlarr": None,  # 特殊处理
        "bitsearch": _get_bitsearch_scraper,
        "cilixiong": _get_cilixiong_scraper,
        "xl720": _get_xl720_scraper,
        "nyaa": _get_nyaa_scraper,
        "mikan": _get_mikan_scraper,
        "yts": _get_yts_scraper,
        "limetorrents": _get_limetorrents_scraper,
        "acgrip": _get_acgrip_scraper,
        "bangumi_moe": _get_bangumi_moe_scraper,
    }

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
            getter = source_getters[source]
            s = getter()
            for kw in kw_list:
                searched.append(kw)
                results = s.search_as_search_results(kw, max_results=20)
                if results:
                    if not hit_kw:
                        hit_kw = kw
                    all_results.extend(results)
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

    enriched = [_enrich_result(r, keyword) for r in deduped]

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
    """获取 Alist 已挂载网盘列表。"""
    try:
        clients = get_clients()
        alist = clients.get("alist")
        if not alist:
            return {"mounts": [], "error": "Alist 未配置"}
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
                return {"success": False, "error_code": "no_cookie", "error_message": "无法获取夸克 Cookie，请检查 Alist 夸克存储配置"}
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
        print(f"[Search/Single] Prowlarr error: {e}")
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
            from shared import _get_bitsearch_scraper, _get_cilixiong_scraper, _get_xl720_scraper, _get_nyaa_scraper, _get_mikan_scraper, _get_yts_scraper, _get_limetorrents_scraper, _get_acgrip_scraper, _get_bangumi_moe_scraper
            scrapers = [
                ("bitsearch", _get_bitsearch_scraper),
                ("cilixiong", _get_cilixiong_scraper),
                ("xl720", _get_xl720_scraper),
                ("nyaa", _get_nyaa_scraper),
                ("mikan", _get_mikan_scraper),
                ("yts", _get_yts_scraper),
                ("limetorrents", _get_limetorrents_scraper),
                ("acgrip", _get_acgrip_scraper),
                ("bangumi_moe", _get_bangumi_moe_scraper),
            ]
            existing_hashes = set()
            for r in all_results:
                h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                if h:
                    existing_hashes.add(h.group(1).upper())

            import concurrent.futures
            def _search_source(name_getter):
                name, getter = name_getter
                if not bt_overrides.get(name, True):
                    return []
                try:
                    scraper = getter()
                    return scraper.search_as_search_results(keyword, max_results=20)
                except:
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_search_source, sg): sg[0] for sg in scrapers}
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
            print(f"[Search/Single] 直搜源合并失败: {e}")

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
        print(f"[Search/Single] error: {e}")
        # fallback 到裸搜
        raw = clients["search"].search(keyword)
        return {"keyword": keyword, "bt_count": len(raw), "bt_results": [r.dict() for r in raw], "total_raw": len(raw), "total_filtered": len(raw)}


# ── 搜索源管理 ──

# BT 源默认配置
_BT_SOURCE_DEFAULTS = {
    "prowlarr": {"label": "Prowlarr", "enabled": True, "type": "bt"},
    "bitsearch": {"label": "Bitsearch", "enabled": True, "type": "bt"},
    "cilixiong": {"label": "磁力熊", "enabled": True, "type": "bt"},
    "xl720": {"label": "XL720", "enabled": True, "type": "bt"},
    "nyaa": {"label": "Nyaa", "enabled": True, "type": "bt"},
    "mikan": {"label": "蜜柑计划", "enabled": True, "type": "bt"},
    "yts": {"label": "YTS", "enabled": True, "type": "bt"},
    "limetorrents": {"label": "LimeTorrents", "enabled": False, "type": "bt"},  # 站点 CF 保护严格，暂不可用
    "acgrip": {"label": "ACG.RIP", "enabled": True, "type": "bt"},
    "bangumi_moe": {"label": "Bangumi Moe", "enabled": True, "type": "bt"},
}
# 网盘源默认配置
_PAN_SOURCE_DEFAULTS = {
    "pansearch": {"label": "PanSearch", "enabled": True, "type": "pan"},
    "gogopanso": {"label": "狗狗盘搜", "enabled": True, "type": "pan"},
    "github": {"label": "GitHub", "enabled": True, "type": "pan"},
    "rrdynb": {"label": "人人电影", "enabled": True, "type": "pan"},
    "ddys": {"label": "低端影视", "enabled": True, "type": "pan"},
    "pansou": {"label": "PanSou", "enabled": False, "type": "pan"},
}


@router.get("/search/sources")
def get_search_sources():
    """获取所有搜索源及启用状态。"""
    conf = config_m.config
    bt_overrides = conf.bt_search_sources or {}
    pan_overrides = conf.pan_search_sources or {}

    sources = []
    for name, info in _BT_SOURCE_DEFAULTS.items():
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": bt_overrides.get(name, info["enabled"]),
        })
    for name, info in _PAN_SOURCE_DEFAULTS.items():
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": pan_overrides.get(name, info["enabled"]),
        })
    return {"sources": sources}


@router.put("/search/sources/{name}")
def toggle_search_source(name: str, req: dict):
    """切换搜索源启用/禁用。"""
    enabled = req.get("enabled", True)
    conf = config_m.config

    # 判断是 BT 源还是网盘源
    if name in _BT_SOURCE_DEFAULTS:
        if not conf.bt_search_sources:
            conf.bt_search_sources = {}
        conf.bt_search_sources[name] = enabled
    elif name in _PAN_SOURCE_DEFAULTS:
        if not conf.pan_search_sources:
            conf.pan_search_sources = {}
        conf.pan_search_sources[name] = enabled
    else:
        raise HTTPException(status_code=404, detail=f"未知搜索源: {name}")

    config_m.save(conf)
    return {"ok": True, "name": name, "enabled": enabled}
