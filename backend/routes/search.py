"""
路由模块：search
"""
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import (
    config_m, indexer_m,
    _get_pan_search_service,
    get_clients,
)
import searcher, douban_client, bangumi_client
from prowlarr_search_provider_factory import get_prowlarr_provider_map
from storage_provider_factory import get_storage_provider_map
from global_filter import GlobalFilter
from search_helpers import enrich_result as _enrich_result, merge_bt_extra_sources as _merge_bt_extra_sources
from search_service import (
    build_keywords, search_all_sources_iter,
    BT_SOURCE_DEFAULTS as _BT_SOURCE_DEFAULTS,
    PAN_SOURCE_DEFAULTS as _PAN_SOURCE_DEFAULTS,
)
from provider_models import SearchCandidate, SearchRequest
from provider_runtime import allow_private_providers

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
    from plugin_guard import get_allowed_bt_sources
    allowed_bt = get_allowed_bt_sources()
    if not allowed_bt:
        return {"query": query, "bt_count": 0, "bt_results": [], "hit_keyword": "", "total_raw": 0, "total_filtered": 0, "enhanced": False}

    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )
    if "prowlarr" not in allowed_bt:
        bt_results = _merge_bt_extra_sources(query, [], allowed_sources=allowed_bt)
        passed = gf.apply([result.title for result in bt_results])
        bt_results = [bt_results[index] for index in passed]
        return {
            "query": query,
            "bt_count": len(bt_results),
            "bt_results": [_enrich_result(r, query) for r in bt_results],
            "hit_keyword": query,
            "total_raw": len(bt_results),
            "total_filtered": len(bt_results),
            "enhanced": False,
        }

    clients = get_clients()

    try:
        from alias_resolver import AliasResolver, AliasSet
        from plugin_guard import is_metadata_allowed

        resolver = AliasResolver(
            douban_client,
            bangumi_client,
            enable_douban=is_metadata_allowed("douban"),
            enable_bangumi=is_metadata_allowed("bangumi"),
        )
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
        bt_results_list = _merge_bt_extra_sources(
            bt_keyword,
            list(resp.results),
            allowed_sources=allowed_bt,
        )

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
    bt_results = _merge_bt_extra_sources(query, bt_results, allowed_sources=allowed_bt)

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
    from plugin_guard import get_allowed_bt_sources

    def _generate():
        allowed_bt = get_allowed_bt_sources()
        if not allowed_bt:
            # 无搜索插件安装：带 error 字段，前端据此显示原因而不是静默收起
            import json as _json
            yield f"data: {_json.dumps({'type': 'done', 'error': 'no_source', 'message': '未安装搜索插件，请在插件中心安装搜索源'})}\n\n"
            return

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
            allowed_sources=allowed_bt,
        )

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/search/pan")
def search_pan(keyword: str, media_type: str = ""):
    """网盘搜索聚合接口。"""
    from plugin_guard import is_pan_search_allowed
    if not is_pan_search_allowed():
        return {
            "results": [], "groups": {}, "source_statuses": [], "total": 0,
            "error": "no_source",
            "message": "未安装网盘搜索插件，请在插件中心安装网盘搜索源",
        }
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
    import plugin_guard

    if not plugin_guard.is_storage_allowed("openlist"):
        return {"mounts": [], "error": "plugin_not_installed"}
    try:
        provider = get_storage_provider_map().get("openlist_storage")
        if not provider:
            return {"mounts": [], "error": "OpenList 未配置"}
        mounts = provider.list_mounts()
        return {
            "mounts": [
                {
                    "pan_type": mount.pan_type,
                    "driver": mount.driver,
                    "mount_path": mount.mount_path,
                    "status": mount.status,
                }
                for mount in mounts
            ]
        }
    except Exception as e:
        return {"mounts": [], "error": str(e)}

@router.post("/alist/transfer")
def transfer_pan_resource(req: dict):
    """网盘资源转存接口。
    夸克链接 → 调用夸克转存 API 自动保存到自己的夸克网盘。
    其他网盘 → 返回提示让用户手动保存。
    """
    try:
        if not allow_private_providers():
            return {
                "success": False,
                "error_code": "private_disabled",
                "error_message": "自动转存属于私有 Provider 能力，公开核心默认禁用",
            }

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


# ── 搜索源管理（配置数据从 search_service 导入）──


@router.get("/search/sources")
def get_search_sources():
    """获取所有搜索源及启用状态和代理配置。仅返回已安装插件对应的源。"""
    from plugin_guard import get_allowed_bt_sources, is_pan_search_allowed

    conf = config_m.config
    bt_overrides = conf.bt_search_sources or {}
    pan_overrides = conf.pan_search_sources or {}
    allowed_bt = get_allowed_bt_sources()

    sources = []
    for name, info in _BT_SOURCE_DEFAULTS.items():
        if name not in allowed_bt:
            continue
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

    if is_pan_search_allowed():
        from plugin_guard import get_allowed_pan_sources
        allowed_pan = get_allowed_pan_sources()
        for name, info in _PAN_SOURCE_DEFAULTS.items():
            if name not in allowed_pan:
                continue
            sources.append({
                "name": name, "label": info["label"], "type": info["type"],
                "enabled": pan_overrides.get(name, info["enabled"]),
            })

    # 第三方插件注册的搜索源；内置元数据已列出的同 ID Provider 不重复追加
    listed_names = {source["name"] for source in sources}
    try:
        from plugin_context import get_plugin_providers
        for pid, info in get_plugin_providers().items():
            if (
                info["type"] in ("search", "scraper_search")
                and pid in allowed_bt
                and pid not in listed_names
            ):
                meta = info["metadata"]
                sources.append({
                    "name": pid, "label": meta.name, "type": "bt",
                    "enabled": True, "needs_proxy": meta.supports_proxy,
                    "proxy": False,
                })
                listed_names.add(pid)
            elif (
                info["type"] == "pan_search"
                and is_pan_search_allowed()
                and pid not in listed_names
            ):
                meta = info["metadata"]
                sources.append({
                    "name": pid, "label": meta.name, "type": "pan",
                    "enabled": True,
                })
                listed_names.add(pid)
    except Exception:
        pass

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
