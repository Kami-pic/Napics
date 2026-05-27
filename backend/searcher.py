import requests
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel
from quality_parser import QualityTag, parse_quality, get_quality_level
from search_query_builder import SearchQueryBuilder
from alias_resolver import AliasSet
from indexer_priority_manager import IndexerPriorityManager
from text_processing import normalize
from match_scoring import match_chain
from secondary_matcher import SecondaryMatcher
from global_filter import GlobalFilter

logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    title: str
    size_gb: float
    indexer: str
    seeders: int
    leechers: int
    download_url: str
    info_url: Optional[str] = None
    quality_tag: str  # e.g., "Bluray-2160p-x265-DTS-中字"
    quality: Optional[QualityTag] = None  # 结构化质量信息
    quality_rank: int = 0  # 质量等级排名


class EnhancedSearchResponse(BaseModel):
    """增强搜索的返回结构"""
    results: List[SearchResult] = []
    hit_keyword: str = ""        # 实际命中的搜索关键词
    total_raw: int = 0           # Prowlarr 原始结果总数（所有关键词累计）
    total_filtered: int = 0      # 经二次匹配+全局过滤后的结果数

class ProwlarrClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._indexer_priorities: Optional[Dict[str, int]] = None

    def get_indexer_priorities(self) -> Dict[str, int]:
        """从 Prowlarr API 读取索引器优先级（只读不改）。
        
        返回 {indexer_name: priority}，priority 越小越优先。
        缓存结果，避免每次搜索都请求。
        """
        if self._indexer_priorities is not None:
            return self._indexer_priorities
        try:
            url = f"{self.api_url}/api/v1/indexer"
            r = requests.get(url, params={"apikey": self.api_key}, timeout=5,
                           proxies={"http": None, "https": None})
            if r.status_code == 200:
                self._indexer_priorities = {
                    item["name"]: item.get("priority", 25)
                    for item in r.json()
                    if item.get("enable", True)
                }
                return self._indexer_priorities
        except Exception:
            pass
        return {}

    def search(self, query: str) -> List[SearchResult]:
        """通过 Prowlarr API 搜索资源"""
        try:
            url = f"{self.api_url}/api/v1/search"
            params = {
                "query": query,
                "type": "search",
                "apikey": self.api_key
            }
            response = requests.get(url, params=params, timeout=60,
                                    proxies={"http": None, "https": None})
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data:
                size = item.get("size", 0)
                title = item.get("title", "")
                quality = parse_quality(title)
                quality_level = get_quality_level(quality)
                # 下载链接优先级：infoHash 构造磁力 > 真正的磁力链接 > Prowlarr 代理链接
                info_hash = item.get("infoHash", "")
                mag_url = item.get("magnetUrl", "")
                dl_url = item.get("downloadUrl", "")
                if info_hash:
                    download_url = f"magnet:?xt=urn:btih:{info_hash}&dn={requests.utils.quote(title)}"
                elif mag_url and mag_url.startswith("magnet:"):
                    download_url = mag_url
                else:
                    download_url = mag_url or dl_url
                results.append(SearchResult(
                    title=title,
                    size_gb=round(size / (1024**3), 2),
                    indexer=item.get("indexer", "Unknown"),
                    seeders=item.get("seeders", 0),
                    leechers=item.get("leechers", 0),
                    download_url=download_url,
                    info_url=item.get("infoUrl", ""),
                    quality_tag=quality.display if quality.display else "Unknown",
                    quality=quality,
                    quality_rank=quality_level.rank,
                ))
            # 按做种数降序排列
            results.sort(key=lambda r: r.seeders, reverse=True)
            return results
        except Exception as e:
            logger.error(f"Prowlarr search error: {e}")
            return []

def enhanced_search(
    client: ProwlarrClient,
    title: str,
    aliases: AliasSet,
    year: str = "",
    media_type: str = "",
    indexer_manager: Optional[IndexerPriorityManager] = None,
    shadow_name: str = "",
    clean_name: str = "",
    global_filter: Optional[GlobalFilter] = None,
    season_years: Optional[Dict] = None,
) -> EnhancedSearchResponse:
    """增强版 Prowlarr 搜索 — 回退链 + 二次匹配 + 全局过滤 + 综合排序。

    搜索回退链（短路返回：首个有效结果处停止）：
    1. shadow_name（影子名）— 最精准的搜索词
    2. clean_name（清洗名）— 去标签后的文件夹名
    3. aliases.en_names[0]（英文原名）— BT 站英文为主
    4. title（TMDB 中文标题）— 兜底

    每个关键词搜索后执行三层漏斗：
    - Prowlarr 原始搜索 → SecondaryMatcher 二次匹配 → GlobalFilter 全局过滤
    - 过滤后有效结果 >= 1 → 短路返回，不再尝试后续关键词
    """
    # 构建回退链（去重去空，保持优先级顺序）
    fallback_chain: List[str] = []
    seen_kw: set = set()

    def _add_kw(kw: str):
        kw = kw.strip()
        if kw and kw not in seen_kw:
            seen_kw.add(kw)
            fallback_chain.append(kw)

    if shadow_name:
        _add_kw(shadow_name)
    if clean_name:
        _add_kw(clean_name)
    if aliases and aliases.en_names:
        _add_kw(aliases.en_names[0])
    _add_kw(title)

    # 构建目标标题列表（供二次匹配使用）
    target_titles: List[str] = [title]
    if aliases:
        target_titles.extend(aliases.cn_names or [])
        target_titles.extend(aliases.en_names or [])
        target_titles.extend(aliases.jp_names or [])
    # 去重去空
    target_titles = list(dict.fromkeys(t for t in target_titles if t))

    # 初始化组件
    matcher = SecondaryMatcher()
    if global_filter is None:
        global_filter = GlobalFilter()  # 使用默认排除列表

    # 索引器优先级：从 Prowlarr API 读取（只读不改）
    indexer_weights: Dict[str, int] = client.get_indexer_priorities()

    query_norm = normalize(title)
    total_raw = 0

    # 回退链搜索（短路返回）
    for keyword in fallback_chain:
        # 第一层：Prowlarr 原始搜索
        try:
            raw_results = client.search(keyword)
        except Exception:
            continue

        total_raw += len(raw_results)
        if not raw_results:
            continue

        # 去重
        seen_urls: set = set()
        deduped: List[SearchResult] = []
        for r in raw_results:
            if r.download_url and r.download_url not in seen_urls:
                seen_urls.add(r.download_url)
                deduped.append(r)

        # 第二层：SecondaryMatcher 二次匹配（不传年份）
        passed_indices = matcher.batch_filter(
            bt_titles=[r.title for r in deduped],
            target_titles=target_titles,
            target_year="",
            media_type=media_type,
        )
        matched = [deduped[i] for i in passed_indices]

        if not matched:
            continue

        # 第三层：GlobalFilter 全局过滤
        filter_indices = global_filter.apply([r.title for r in matched])
        filtered = [matched[i] for i in filter_indices]

        if not filtered:
            continue

        # 有效结果 >= 1，短路返回
        # 综合评分排序
        filtered.sort(
            key=lambda r: _composite_score(r, query_norm, indexer_weights),
            reverse=True,
        )

        return EnhancedSearchResponse(
            results=filtered,
            hit_keyword=keyword,
            total_raw=total_raw,
            total_filtered=len(filtered),
        )

    # 回退链全部耗尽，无有效结果
    return EnhancedSearchResponse(
        results=[],
        hit_keyword="",
        total_raw=total_raw,
        total_filtered=0,
    )


def _composite_score(
    r: SearchResult,
    query_norm: str,
    indexer_weights: Dict[str, int],
) -> float:
    """计算单条结果的综合评分，用于排序。
    
    indexer_weights 来自 Prowlarr 的索引器优先级（priority 越小越优先）。
    转换为 0-1 分数：(50 - priority) / 50，clamp 到 [0, 1]。
    """
    # 用 L2 match_chain 计算匹配度（0-100），归一化到 0-1
    title_match = match_chain([query_norm], [normalize(r.title)], []) / 100.0
    # Prowlarr priority: 1=最高优先, 50=最低。转换为 0-1 分数
    raw_priority = indexer_weights.get(r.indexer, 25)
    indexer_score = max(0.0, min(1.0, (50 - raw_priority) / 50))
    return (
        r.quality_rank * 0.4
        + min(r.seeders / 100, 1.0) * 0.3
        + indexer_score * 0.15
        + title_match * 0.15
    )


# 后续可以增加网盘搜刮逻辑
class NetdiskSearcher:
    """针对国内网盘聚合站的搜刮器 (示例逻辑)"""
    def search(self, query: str) -> List[Dict]:
        return [
            # 这是一个示例占位，后续可以通过爬虫对接具体的搜刮站
            {"title": f"{query} 4K 阿里资源", "url": "https://example.com/share/xxx", "source": "阿里云盘"},
            {"title": f"{query} 1080P 夸克版", "url": "https://example.com/share/yyy", "source": "夸克网盘"}
        ]
