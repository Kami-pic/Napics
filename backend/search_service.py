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

from core.source_registry import source_defaults
from search_keyword_mapper import (
    MultiLangKeywords, get_search_keywords_for_source,
    is_bare_year as _is_bare_year,
)
from search_helpers import enrich_result
from text_processing import split_by_language, normalize as text_normalize
from provider_models import SearchCandidate, SearchRequest
from searcher import SearchResult

logger = logging.getLogger(__name__)

# BT / 网盘源的默认配置从 core/source_registry.py 派生。
# 这两份表以前是手写的，和 DIRECT_BT_SOURCE_ORDER、SOURCE_LANG_PRIORITY、
# CN_SEASON_SOURCES、_no_seeder_info 等另外四处各自维护同一批源名 ——
# 加删一个源要六处同步，漏一处就是静默的错误行为。
BT_SOURCE_DEFAULTS = source_defaults("bt")
PAN_SOURCE_DEFAULTS = source_defaults("pan")


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
    year: str = "",
) -> MultiLangKeywords:
    """从搜索参数构造多语言搜索词集合。"""
    parts = split_by_language(query)
    kw_cn = cn_name.strip() or parts.get("cn", "") or ""
    kw_en = en_name.strip() or shadow_name.strip() or parts.get("en", "") or ""
    kw_original = original_name.strip() or ""

    # 「沙丘 2011」这种带空格的输入会被 split_by_language 拆成 cn="沙丘" en="2011"
    # ——它判断数字归中文还是英文只看紧邻的前后一个 token，而空格本身就是一个
    # token，把邻接关系切断了。而 prowlarr / bitsearch / yts / 1337x 的语言优先级
    # 第一位是 en，于是**第一个搜索词就是「2011」**，搜出一堆 2011 年的片子、
    # 命中即短路，真正的「沙丘」永远轮不到。
    #
    # 这里不动 split_by_language（compute_junk_flags、extract_variants 等一堆地方
    # 都在用它），只在搜索词这一层把纯年份的候选词摘掉、转成 year 信号。
    kw_year = (year or "").strip()
    if _is_bare_year(kw_en) and (kw_cn or kw_original):
        if not kw_year:
            kw_year = kw_en.strip()
        kw_en = ""
    if _is_bare_year(kw_cn) and (kw_en or kw_original):
        # 罕见但可能：全中文输入里年份被归进了 cn
        if not kw_year:
            kw_year = kw_cn.strip()
        kw_cn = ""

    if kw_cn:
        kw_cn = text_normalize(kw_cn)
    return MultiLangKeywords(
        cn=kw_cn, en=kw_en, original=kw_original,
        query=query, season_number=season_number,
        year=kw_year,
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
            if not _is_bare_year(t):
                terms.add(t)
            for w in t.split():
                # 纯年份不能当相关性词：标题里含 2011 的什么片都算"相关"
                if len(w) >= 3 and not _is_bare_year(w):
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
                seen = set()
                filtered_out = 0
                kept = []
                for r in raw:
                    if r.download_url and r.download_url not in seen:
                        seen.add(r.download_url)
                        if relevance_terms:
                            title_lower = (r.title or "").lower()
                            if not any(term in title_lower for term in relevance_terms):
                                filtered_out += 1
                                continue
                        kept.append(r)
                if filtered_out:
                    logger.info(f"[SearchService/Prowlarr] 过滤掉 {filtered_out} 条不相关结果")
                # 短路判断放在相关性过滤**之后**。原来是 `if raw: ... break`，
                # 一个坏关键词只要捞回任何东西就把回退链掐断了，哪怕全部不相关。
                if kept:
                    if not hit_kw:
                        hit_kw = kw
                    all_results.extend(kept)
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
    from quality_parser import parse_quality, get_quality_level
    quality = parse_quality(candidate.title)
    return SearchResult(
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


def _get_provider_list() -> List[Tuple[str, Any]]:
    """获取所有直搜源的 (name, SearchProvider) 列表。包含内置源和第三方插件注册的源。"""
    from bt_search_provider_factory import get_direct_bt_provider_map

    providers = get_direct_bt_provider_map()
    result = [(name, provider) for name, provider in providers.items()]
    registered_ids = set(providers)

    # 加载未被内置工厂接管的第三方插件搜索源
    try:
        from plugin_context import get_plugin_providers
        for pid, info in get_plugin_providers().items():
            if pid in registered_ids:
                continue
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
            if self.id in BT_SOURCE_DEFAULTS:
                proxy = get_source_proxy(self.id)
            else:
                try:
                    from shared import config_m
                    metadata = self._info.get("metadata")
                    proxy = (
                        config_m.config.http_proxy or None
                        if getattr(metadata, "supports_proxy", False)
                        else None
                    )
                except Exception:
                    proxy = None
            self._scraper = scraper_class(proxy=proxy)
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


def _no_source_reason(bt_overrides: dict, allowed_sources: Optional[set]) -> str:
    """诊断"一个搜索源都没有"的具体原因，用于回传给前端。

    区分三种情况，避免用户面对一个没有任何信息的空结果：
    1. 插件未安装 —— 守卫放行集合为空
    2. 插件装了但 provider 没注册成功 —— 守卫放行了，但工厂里没有对应实现
    3. 源被用户手动关掉了
    """
    if allowed_sources is not None and not allowed_sources:
        return "未安装搜索插件，请在插件中心安装搜索源"

    registered = {name for name, _ in _get_provider_list()}
    if not registered:
        return "搜索插件已安装但未注册任何搜索源，请查看后端日志中的插件加载错误"

    if allowed_sources is not None:
        usable = registered & allowed_sources
        if not usable:
            return (
                "已安装插件与可用搜索源不匹配（插件声明的源未注册成功），"
                "请在插件中心重新安装搜索插件"
            )
        return f"全部搜索源已被关闭（可用：{'、'.join(sorted(usable))}），请在设置中启用至少一个"

    return "全部搜索源已被关闭，请在设置中启用至少一个"


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

    # 一个源都没有：必须显式告诉前端原因，否则前端只收到 done、界面静默无反应
    if not all_source_names:
        reason = _no_source_reason(bt_overrides, allowed_sources)
        logger.warning(f"[Search] 无可用搜索源: {reason}")
        yield f"data: {json.dumps({'type': 'done', 'error': 'no_source', 'message': reason})}\n\n"
        return

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
                enriched = [enrich_result(r, query, match_names=match_names, target_year=keywords.year) for r in source_deduped]
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
                    enriched = [enrich_result(r, query, match_names=match_names, target_year=keywords.year) for r in deduped]
                    all_results.extend(enriched)
            except Exception as e:
                name = future_map.get(future, "unknown")
                logger.error(f"[SearchService] {name} 搜索失败: {e}")

    return all_results
