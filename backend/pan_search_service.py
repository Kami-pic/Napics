"""网盘搜索聚合服务。

并发调用多个网盘搜索源，聚合去重、敏感词过滤、质量过滤、
按网盘类型分组、标记 Alist 挂载状态，返回统一响应。
"""

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from pan_models import (
    PanResult, PanSearchResponse, PanType, SourceStatus,
)
from content_filter import ContentFilter, PanResultFilter
from scraper_base import ScraperBase
from pan_scraper_rrdynb import RrdynbScraper
from pan_scraper_ddys import DdysScraper
from pan_scraper_pansou import PanSouClient
from pan_scraper_pansearch import PanSearchScraper

logger = logging.getLogger(__name__)

# 默认网盘优先级
DEFAULT_PAN_PRIORITY = ["quark", "aliyun", "pan115", "pikpak", "baidu"]

# 标题相似度阈值（Levenshtein > 此值视为同一资源）
TITLE_SIMILARITY_THRESHOLD = 0.9


class PanSearchService:
    """网盘搜索聚合服务。"""

    def __init__(
        self,
        search_sources: Dict[str, bool] = None,
        pansou_api_url: str = "",
        pan_type_priority: List[str] = None,
        sensitive_words: List[str] = None,
        scraper_proxy: str = "",
        alist_manager=None,  # AlistManager 实例（可选，用于挂载状态标记）
    ):
        self.pan_type_priority = pan_type_priority or DEFAULT_PAN_PRIORITY
        self.content_filter = ContentFilter(sensitive_words or [])
        self.quality_filter = PanResultFilter()
        self.alist_manager = alist_manager

        # 根据配置初始化已启用的爬虫
        sources = search_sources or {
            "pansearch": True, "rrdynb": True, "ddys": True, "pansou": False,
        }
        self.scrapers: Dict[str, ScraperBase] = {}
        # pansearch — 国内可直连，优先启用
        if sources.get("pansearch", True):
            self.scrapers["pansearch"] = PanSearchScraper(proxy=scraper_proxy or None)
        if sources.get("rrdynb"):
            self.scrapers["rrdynb"] = RrdynbScraper(proxy=scraper_proxy or None)
        if sources.get("ddys"):
            self.scrapers["ddys"] = DdysScraper(proxy=scraper_proxy or None)
        if sources.get("pansou") and pansou_api_url:
            self.scrapers["pansou"] = PanSouClient(
                api_url=pansou_api_url, proxy=scraper_proxy or None
            )

    async def search(
        self, keyword: str, media_type: str = ""
    ) -> PanSearchResponse:
        """并发搜索所有已启用的源，聚合返回。"""
        return self.search_sync(keyword, media_type)

    def search_sync(
        self, keyword: str, media_type: str = ""
    ) -> PanSearchResponse:
        """同步版搜索 — 用线程池并发调用爬虫。"""
        if not self.scrapers:
            return PanSearchResponse(
                source_statuses=[
                    SourceStatus(name="all", status="disabled", count=0)
                ]
            )

        # 用线程池并发调用爬虫（爬虫本身是同步的）
        source_statuses: List[SourceStatus] = []
        all_results: List[PanResult] = []

        with ThreadPoolExecutor(max_workers=len(self.scrapers)) as pool:
            futures = {name: pool.submit(scraper.search, keyword) for name, scraper in self.scrapers.items()}

            for name, future in futures.items():
                try:
                    results = future.result(timeout=30)
                    source_statuses.append(SourceStatus(
                        name=name, status="success", count=len(results),
                    ))
                    all_results.extend(results)
                except Exception as e:
                    logger.error("[PanSearchService] %s 搜索失败: %s", name, str(e))
                    source_statuses.append(SourceStatus(
                        name=name, status="failed", error=str(e),
                    ))

        # 补充未启用的源状态
        for name in ["pansearch", "rrdynb", "ddys", "pansou"]:
            if name not in self.scrapers:
                source_statuses.append(SourceStatus(
                    name=name, status="disabled",
                ))

        # 聚合处理流水线
        # 1. 双重去重
        deduped = self._deduplicate(all_results)
        # 2. 关键词相关性过滤（去掉和搜索词完全不相关的结果）
        relevant = self._filter_relevant(deduped, keyword)
        # 3. 敏感词过滤
        filtered = self.content_filter.filter(relevant)
        # 4. 质量过滤（三项硬指标）
        quality_filtered = self.quality_filter.filter(filtered, media_type)
        # 4. 标记挂载状态
        self._mark_mount_status(quality_filtered)
        # 5. 按网盘类型分组
        groups = self._group_by_pan_type(quality_filtered)

        return PanSearchResponse(
            results=quality_filtered,
            groups=groups,
            source_statuses=source_statuses,
            total=len(quality_filtered),
        )

    def _filter_relevant(self, results: List[PanResult], keyword: str) -> List[PanResult]:
        """关键词相关性过滤：标题中必须包含搜索关键词的至少一个主要词。

        搜索"流浪地球"→ 标题必须含"流浪"或"地球"中至少一个。
        如果过滤后结果为 0，回退返回全部结果（避免过度过滤）。
        """
        if not keyword or not keyword.strip():
            return results

        import re
        kw = keyword.strip()
        cn_parts = re.findall(r'[\u4e00-\u9fff]+', kw)
        en_parts = re.findall(r'[a-zA-Z]{2,}', kw)

        # 中文子词：每个中文段按2字滑窗切分
        cn_tokens = set()
        for part in cn_parts:
            if len(part) <= 2:
                cn_tokens.add(part)
            else:
                for i in range(len(part) - 1):
                    cn_tokens.add(part[i:i+2])

        en_tokens = {w.lower() for w in en_parts}
        all_tokens = cn_tokens | en_tokens
        if not all_tokens:
            return results

        filtered = []
        for r in results:
            title = (r.clean_title or r.title).lower()
            if any(t in title for t in all_tokens):
                filtered.append(r)

        # 如果过滤后为空，回退返回全部（避免过度过滤）
        if not filtered and results:
            logger.info("[PanSearchService] 相关性过滤后为空，回退返回全部 %d 条", len(results))
            return results

        removed = len(results) - len(filtered)
        if removed:
            logger.info("[PanSearchService] 相关性过滤掉 %d 条不相关结果", removed)
        return filtered

    def _deduplicate(self, results: List[PanResult]) -> List[PanResult]:
        """双重去重：
        1. share_url 精确去重
        2. 标题规范化去重（同 pan_type + Levenshtein > 0.9 → 保留 clean_title 更规范的）
        """
        # 第一轮：share_url 精确去重
        seen_urls = set()
        url_deduped = []
        for r in results:
            if r.share_url not in seen_urls:
                seen_urls.add(r.share_url)
                url_deduped.append(r)

        # 第二轮：标题相似度去重（同 pan_type 内）
        by_type: Dict[str, List[PanResult]] = defaultdict(list)
        for r in url_deduped:
            by_type[r.pan_type.value].append(r)

        final = []
        for pan_type, group in by_type.items():
            kept = []
            for r in group:
                is_dup = False
                for existing in kept:
                    sim = SequenceMatcher(
                        None, r.clean_title, existing.clean_title
                    ).ratio()
                    if sim > TITLE_SIMILARITY_THRESHOLD:
                        # 保留 clean_title 更短（更规范）的
                        if len(r.clean_title) < len(existing.clean_title):
                            kept.remove(existing)
                            kept.append(r)
                        is_dup = True
                        break
                if not is_dup:
                    kept.append(r)
            final.extend(kept)

        return final

    def _mark_mount_status(self, results: List[PanResult]) -> None:
        """标记各结果的 Alist 挂载状态。"""
        if not self.alist_manager:
            return
        for r in results:
            try:
                r.mounted = self.alist_manager.is_mounted(r.pan_type.value)
            except Exception:
                pass  # 挂载检查失败不影响结果

    def _group_by_pan_type(
        self, results: List[PanResult]
    ) -> Dict[str, List[PanResult]]:
        """按网盘类型分组，按配置的优先级排序。"""
        groups: Dict[str, List[PanResult]] = defaultdict(list)
        for r in results:
            groups[r.pan_type.value].append(r)

        # 按优先级排序
        ordered = {}
        for pt in self.pan_type_priority:
            if pt in groups:
                ordered[pt] = groups.pop(pt)
        # 剩余未在优先级列表中的类型追加到末尾
        for pt, items in groups.items():
            ordered[pt] = items

        return ordered
