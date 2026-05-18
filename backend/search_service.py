"""搜索服务：统一搜索逻辑，供 SSE 端点、订阅调度器、手动搜索共用。

从 routes/search.py 的 _generate() 闭包中抽离核心逻辑：
- build_keywords()：构造多语言搜索词集合
- search_prowlarr()：Prowlarr 搜索 + 回退链 + 相关性过滤
- search_direct()：直搜源搜索 + 回退链
- search_all_sources_iter()：迭代器版本（SSE 用）
- search_all_sources()：同步版本（订阅调度器用）
"""

import re
import json
import logging
import concurrent.futures
import time
from typing import List, Dict, Optional, Iterator, Tuple, Any

from search_keyword_mapper import MultiLangKeywords, get_search_keywords_for_source
from search_helpers import enrich_result
from text_processing import split_by_language, normalize as text_normalize
from provider_models import SearchCandidate, SearchRequest
from searcher import SearchResult

logger = logging.getLogger(__name__)

# BT 源默认配置（从 routes/search.py 移入）
BT_SOURCE_DEFAULTS = {
    "prowlarr": {"label": "Prowlarr", "enabled": True, "type": "bt", "needs_proxy": False},
    "bitsearch": {"label": "Bitsearch", "enabled": True, "type": "bt", "needs_proxy": True},
    "cilixiong": {"label": "磁力熊", "enabled": True, "type": "bt", "needs_proxy": False},
    "xl720": {"label": "XL720", "enabled": True, "type": "bt", "needs_proxy": False},
    "nyaa": {"label": "Nyaa", "enabled": True, "type": "bt", "needs_proxy": True},
    "mikan": {"label": "蜜柑计划", "enabled": True, "type": "bt", "needs_proxy": True},
    "yts": {"label": "YTS", "enabled": True, "type": "bt", "needs_proxy": True},
    "limetorrents": {"label": "LimeTorrents", "enabled": False, "type": "bt", "needs_proxy": True},
    "acgrip": {"label": "ACG.RIP", "enabled": False, "type": "bt", "needs_proxy": True},
    "bangumi_moe": {"label": "Bangumi Moe", "enabled": True, "type": "bt", "needs_proxy": False},
    "eztv": {"label": "EZTV", "enabled": False, "type": "bt", "needs_proxy": True},
    "dmhy": {"label": "动漫花园", "enabled": True, "type": "bt", "needs_proxy": True},
    "1337x": {"label": "1337x", "enabled": True, "type": "bt", "needs_proxy": True},
}

# 网盘源默认配置
PAN_SOURCE_DEFAULTS = {
    "pansearch": {"label": "PanSearch", "enabled": True, "type": "pan"},
    "gogopanso": {"label": "狗狗盘搜", "enabled": True, "type": "pan"},
    "github": {"label": "GitHub", "enabled": True, "type": "pan"},
    "rrdynb": {"label": "人人电影", "enabled": True, "type": "pan"},
    "ddys": {"label": "低端影视", "enabled": True, "type": "pan"},
    "pansou": {"label": "PanSou", "enabled": False, "type": "pan"},
}


# infohash 提取正则
_INFOHASH_RE = re.compile(r"btih:([a-fA-F0-9]{40})", re.IGNORECASE)


def get_source_proxy(source_name: str, bt_overrides: Optional[dict] = None) -> Optional[str]:
    """获取指定源应该使用的代理地址。

    优先级：bt_search_sources 中源级别的 proxy 配置 > needs_proxy 默认值。
    bt_search_sources 支持两种格式：
    - 旧格式（布尔）：{"bitsearch": true} — 只控制启用，代理走默认
    - 新格式（字典）：{"bitsearch": {"enabled": true, "proxy": false}} — 独立控制代理
    """
    from shared import config_m
    global_proxy = getattr(config_m.config, "http_proxy", "") or ""

    default_info = BT_SOURCE_DEFAULTS.get(source_name, {})
    needs_proxy = default_info.get("needs_proxy", False)

    # 检查源级别的 proxy 覆盖
    if bt_overrides is None:
        bt_overrides = config_m.config.bt_search_sources or {}
    override = bt_overrides.get(source_name)
    if isinstance(override, dict):
        # 新格式：{"enabled": true, "proxy": false}
        if "proxy" in override:
            needs_proxy = override["proxy"]

    return global_proxy if (needs_proxy and global_proxy) else None


def build_keywords(
    query: str,
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    shadow_name: str = "",
    season_number: int = 0,
) -> MultiLangKeywords:
    """从搜索参数构造多语言搜索词集合。"""
    parts = split_by_language(query)
    kw_cn = cn_name.strip() or parts.get("cn", "") or ""
    kw_en = en_name.strip() or shadow_name.strip() or parts.get("en", "") or ""
    kw_original = original_name.strip() or ""
    if kw_cn:
        kw_cn = text_normalize(kw_cn)
    return MultiLangKeywords(
        cn=kw_cn, en=kw_en, original=kw_original,
        query=query, season_number=season_number,
    )


def _build_match_names(keywords: MultiLangKeywords, query: str) -> List[str]:
    """构造匹配名称列表（传给 enrich_result 解决跨语言匹配）。"""
    return [n for n in [keywords.cn, keywords.en, keywords.original] if n and n != query]


def _build_relevance_terms(keywords: MultiLangKeywords) -> set:
    """构造相关性检查用的关键词集合。"""
    terms = set()
    for t in [keywords.cn, keywords.en, keywords.original, keywords.query]:
        t = t.strip().lower()
        if t and len(t) >= 2:
            terms.add(t)
            for w in t.split():
                if len(w) >= 3:
                    terms.add(w)
    return terms


def _dedup_by_infohash(results: list) -> list:
    """同源内按 infohash 去重。"""
    deduped = []
    seen = set()
    for r in results:
        m = _INFOHASH_RE.search(getattr(r, "download_url", "") if hasattr(r, "download_url") else r.get("download_url", ""))
        if m:
            h = m.group(1).upper()
            if h in seen:
                continue
            seen.add(h)
        deduped.append(r)
    return deduped


def search_prowlarr(
    search_client,
    keywords: MultiLangKeywords,
) -> Tuple[str, list, Optional[str], list, str]:
    """Prowlarr 搜索 + 回退链 + 基础相关性过滤。

    返回: (source_name, results, error, searched_keywords, hit_keyword)
    """
    try:
        provider = _prowlarr_client_to_provider(search_client)
        kw_list = get_search_keywords_for_source("prowlarr", keywords)
        searched = []
        hit_kw = ""
        all_results = []
        relevance_terms = _build_relevance_terms(keywords)

        for kw in kw_list:
            searched.append(kw)
            logger.info(f"[SearchService/Prowlarr] 搜索词: '{kw}'")
            t0 = time.time()
            candidates = provider.search(SearchRequest(query=kw, limit=0))
            raw = [_candidate_to_search_result(candidate) for candidate in candidates]
            elapsed = time.time() - t0
            logger.info(f"[SearchService/Prowlarr] '{kw}' 返回 {len(raw)} 条，耗时 {elapsed:.1f}s")
            if raw:
                if not hit_kw:
                    hit_kw = kw
                seen = set()
                filtered_out = 0
                for r in raw:
                    if r.download_url and r.download_url not in seen:
                        seen.add(r.download_url)
                        if relevance_terms:
                            title_lower = (r.title or "").lower()
                            if not any(term in title_lower for term in relevance_terms):
                                filtered_out += 1
                                continue
                        all_results.append(r)
                if filtered_out:
                    logger.info(f"[SearchService/Prowlarr] 过滤掉 {filtered_out} 条不相关结果")
                break
        return "prowlarr", all_results, None, searched, hit_kw
    except Exception as e:
        logger.info(f"[SearchService/Prowlarr] 异常: {e}")
        return "prowlarr", [], str(e), [], ""


def _prowlarr_client_to_provider(search_client):
    from prowlarr_search_provider_factory import get_prowlarr_provider_map

    providers = get_prowlarr_provider_map(client_factory=lambda: search_client)
    return providers["prowlarr"]


def search_direct(
    name: str,
    provider,
    keywords: MultiLangKeywords,
) -> Tuple[str, list, Optional[str], list, str]:
    """直搜源搜索 + 回退链。

    返回: (source_name, results, error, searched_keywords, hit_keyword)
    """
    try:
        kw_list = get_search_keywords_for_source(name, keywords)
        searched = []
        hit_kw = ""
        all_results = []
        for kw in kw_list:
            searched.append(kw)
            candidates = provider.search(SearchRequest(query=kw, limit=40))
            if candidates:
                if not hit_kw:
                    hit_kw = kw
                all_results.extend(_candidate_to_search_result(candidate) for candidate in candidates)
                break
        return name, all_results, None, searched, hit_kw
    except Exception as e:
        return name, [], str(e), [], ""


def _candidate_to_search_result(candidate: SearchCandidate) -> SearchResult:
    return SearchResult(
        title=candidate.title,
        size_gb=candidate.size_gb,
        indexer=candidate.indexer or candidate.provider_id,
        seeders=candidate.seeders,
        leechers=candidate.leechers,
        download_url=candidate.download_url,
        info_url=candidate.info_url,
        quality_tag=candidate.raw_quality,
    )


def _get_provider_list() -> List[Tuple[str, Any]]:
    """获取所有直搜源的 (name, SearchProvider) 列表。包含内置源和第三方插件注册的源。"""
    from bt_search_provider_factory import get_direct_bt_provider_map

    providers = get_direct_bt_provider_map()
    result = [(name, provider) for name, provider in providers.items()]

    # 加载第三方插件注册的搜索源
    try:
        from plugin_context import get_plugin_providers
        from provider_models import SearchRequest, SearchCandidate
        for pid, info in get_plugin_providers().items():
            if info["type"] == "scraper_search":
                # 基于 ScraperBase 的爬虫，包装为兼容接口
                result.append((pid, _PluginScraperAdapter(pid, info)))
            elif info["type"] == "search":
                # 函数式搜索源
                result.append((pid, _PluginSearchAdapter(pid, info)))
    except Exception:
        pass

    return result


class _PluginScraperAdapter:
    """将第三方插件的 ScraperBase 爬虫适配为搜索系统可用的接口"""

    def __init__(self, provider_id: str, info: dict):
        self.id = provider_id
        self._info = info
        self._scraper = None

    def _get_scraper(self):
        if self._scraper is None:
            scraper_class = self._info["scraper_class"]
            try:
                from shared import config_m
                proxy = config_m.config.http_proxy or ""
            except Exception:
                proxy = ""
            self._scraper = scraper_class(proxy=proxy if proxy else None)
        return self._scraper

    def metadata(self):
        return self._info["metadata"]

    def search(self, request):
        from provider_models import SearchCandidate
        scraper = self._get_scraper()
        results = scraper.search_as_search_results(request.query, max_results=request.limit or 40)
        candidates = []
        for r in results:
            candidates.append(SearchCandidate(
                title=r.title,
                downloadUrl=r.download_url,
                infoUrl=getattr(r, "info_url", ""),
                sizeGb=r.size_gb,
                seeders=r.seeders,
                leechers=r.leechers,
                rawQuality=getattr(r, "quality_tag", ""),
                providerId=self.id,
                indexer=getattr(r, "indexer", self.id),
                infoHash="",
            ))
        return candidates


class _PluginSearchAdapter:
    """将第三方插件的函数式搜索源适配为搜索系统可用的接口"""

    def __init__(self, provider_id: str, info: dict):
        self.id = provider_id
        self._info = info

    def metadata(self):
        return self._info["metadata"]

    def search(self, request):
        search_fn = self._info["search_fn"]
        return search_fn(request.query, request.limit or 40)


def _get_enabled_sources(bt_overrides: dict) -> Tuple[bool, List[Tuple[str, Any]]]:
    """根据配置返回启用的源。返回 (prowlarr_enabled, providers_list)。

    bt_overrides 支持两种格式：
    - 旧格式（布尔）：{"bitsearch": true}
    - 新格式（字典）：{"bitsearch": {"enabled": true, "proxy": false}}
    """
    def _is_enabled(name: str) -> bool:
        override = bt_overrides.get(name)
        if override is None:
            return BT_SOURCE_DEFAULTS.get(name, {}).get("enabled", True)
        if isinstance(override, dict):
            return override.get("enabled", True)
        return bool(override)

    prowlarr_enabled = _is_enabled("prowlarr")
    providers = _get_provider_list()
    enabled_providers = []
    for name, provider in providers:
        if _is_enabled(name):
            enabled_providers.append((name, provider))
    return prowlarr_enabled, enabled_providers


def search_all_sources_iter(
    keywords: MultiLangKeywords,
    query: str,
    bt_overrides: Optional[dict] = None,
    search_client=None,
    match_names: Optional[List[str]] = None,
    allowed_sources: Optional[set] = None,
) -> Iterator[str]:
    """迭代器版本：逐源返回 SSE 事件字符串。供 SSE 端点使用。

    和原 _generate() 行为完全一致：
    1. 推送所有源的 searching 状态
    2. 全部并行提交，as_completed 逐个 yield source_done 事件
    3. 超时未完成的源推送 failed
    4. 最后推送 done

    allowed_sources: 如果提供，只搜索在此集合中的源（插件守卫用）
    """
    if bt_overrides is None:
        bt_overrides = {}
    if match_names is None:
        match_names = _build_match_names(keywords, query)

    prowlarr_enabled, enabled_scrapers = _get_enabled_sources(bt_overrides)

    # 插件守卫：过滤掉未安装插件对应的源
    if allowed_sources is not None:
        prowlarr_enabled = prowlarr_enabled and ("prowlarr" in allowed_sources)
        enabled_scrapers = [(name, getter) for name, getter in enabled_scrapers if name in allowed_sources]

    # 推送所有源的 searching 状态
    all_source_names = []
    if prowlarr_enabled:
        all_source_names.append("prowlarr")
    all_source_names.extend(name for name, _ in enabled_scrapers)
    for name in all_source_names:
        yield f"data: {json.dumps({'type': 'status', 'source': name, 'status': 'searching'})}\n\n"

    # 全部并行提交
    with concurrent.futures.ThreadPoolExecutor(max_workers=14) as pool:
        future_map = {}
        if prowlarr_enabled and search_client:
            f = pool.submit(search_prowlarr, search_client, keywords)
            future_map[f] = "prowlarr"
        for name, getter in enabled_scrapers:
            f = pool.submit(search_direct, name, getter, keywords)
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
                source_deduped = _dedup_by_infohash(results)
                status = "done" if not err else "failed"
                enriched = [enrich_result(r, query, match_names=match_names) for r in source_deduped]
                logger.info("[SSE] %s: raw=%d deduped=%d enriched=%d err=%s", name, len(results), len(source_deduped), len(enriched), err or "none")
                yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': status, 'count': len(results), 'added': len(source_deduped), 'error': err or '', 'search_keywords': searched, 'hit_keyword': hit_kw, 'results': enriched}, default=str)}\n\n"
        except concurrent.futures.TimeoutError:
            pass
        for future, name in future_map.items():
            if name not in completed_sources:
                yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': 'failed', 'count': 0, 'added': 0, 'error': '搜索超时', 'search_keywords': [], 'hit_keyword': '', 'results': []})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def search_all_sources(
    keywords: MultiLangKeywords,
    query: str,
    sources: Optional[List[str]] = None,
    bt_overrides: Optional[dict] = None,
    search_client=None,
    match_names: Optional[List[str]] = None,
    timeout: int = 60,
) -> List[dict]:
    """同步版本：搜索所有指定源，返回 enrich 后的结果列表。供订阅调度器使用。

    参数:
        sources: 指定源列表（如 ["prowlarr", "nyaa"]），None=全部启用的源
        bt_overrides: BT 源启用覆盖配置
        search_client: Prowlarr 搜索客户端
        match_names: 匹配名称列表
        timeout: 总超时秒数
    """
    if bt_overrides is None:
        bt_overrides = {}
    if match_names is None:
        match_names = _build_match_names(keywords, query)

    prowlarr_enabled, enabled_scrapers = _get_enabled_sources(bt_overrides)

    # 如果指定了源列表，过滤
    if sources:
        source_set = set(sources)
        prowlarr_enabled = prowlarr_enabled and "prowlarr" in source_set
        enabled_scrapers = [(n, g) for n, g in enabled_scrapers if n in source_set]

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=14) as pool:
        future_map = {}
        if prowlarr_enabled and search_client:
            f = pool.submit(search_prowlarr, search_client, keywords)
            future_map[f] = "prowlarr"
        for name, getter in enabled_scrapers:
            f = pool.submit(search_direct, name, getter, keywords)
            future_map[f] = name

        for future in concurrent.futures.as_completed(future_map, timeout=timeout):
            try:
                name, results, err, searched, hit_kw = future.result(timeout=timeout)
                if not err:
                    deduped = _dedup_by_infohash(results)
                    enriched = [enrich_result(r, query, match_names=match_names) for r in deduped]
                    all_results.extend(enriched)
            except Exception as e:
                name = future_map.get(future, "unknown")
                logger.error(f"[SearchService] {name} 搜索失败: {e}")

    return all_results
