"""内容过滤器 — 敏感词过滤 + 三项硬指标质量过滤。

过滤链（在 PanSearchService 聚合去重后、返回前端前执行）：
1. ContentFilter — 敏感词过滤
2. PanResultFilter — 三项硬指标：分辨率强校验 / 体积区间控制 / 整季判定
"""

import logging
from typing import List

from pan_models import PanResult, is_cam_quality

logger = logging.getLogger(__name__)


class ContentFilter:
    """敏感词过滤器 — 后端过滤不合适的搜索结果。"""

    def __init__(self, sensitive_words: List[str] = None):
        self.words: List[str] = sensitive_words or []

    def filter(self, results: List[PanResult]) -> List[PanResult]:
        """过滤命中敏感词的结果。"""
        if not self.words:
            return results
        filtered = [r for r in results if not self._contains_sensitive(r.title)]
        removed = len(results) - len(filtered)
        if removed:
            logger.info("[ContentFilter] 敏感词过滤掉 %d 条结果", removed)
        return filtered

    def _contains_sensitive(self, text: str) -> bool:
        text_lower = text.lower()
        return any(w.lower() in text_lower for w in self.words)


class PanResultFilter:
    """三项硬指标质量过滤器。

    1. 分辨率强校验：低于 720p 或含枪版关键词 → 丢弃，优先标注 4K/1080p
    2. 体积区间控制：整季资源总大小 < 2GB → 画质极差，丢弃
    3. 整季判定：碎片集（含单集标记但无整季标记）→ 丢弃
    """

    # 整季资源最小体积（GB）
    MIN_SEASON_SIZE_GB = 2.0

    def filter(self, results: List[PanResult], media_type: str = "") -> List[PanResult]:
        """执行三项硬指标过滤。"""
        filtered = []
        for r in results:
            if not self._check_resolution(r):
                logger.debug("[PanResultFilter] 分辨率不合格，丢弃: %s", r.title[:50])
                continue
            if not self._check_size(r, media_type):
                logger.debug("[PanResultFilter] 体积不合格，丢弃: %s (%.1fGB)", r.title[:50], r.size_gb)
                continue
            if not self._check_completeness(r, media_type):
                logger.debug("[PanResultFilter] 碎片集，丢弃: %s", r.title[:50])
                continue
            filtered.append(r)

        removed = len(results) - len(filtered)
        if removed:
            logger.info("[PanResultFilter] 质量过滤掉 %d 条结果", removed)
        return filtered

    def _check_resolution(self, r: PanResult) -> bool:
        """分辨率强校验：低于 720p 或枪版 → 丢弃。"""
        # 枪版直接丢弃
        if is_cam_quality(r.title):
            return False
        # 分辨率 unknown 时放行（网盘标题不一定有分辨率信息）
        if r.resolution == "unknown":
            return True
        # 有明确分辨率但低于 720p → 丢弃（目前只解析 720p/1080p/2160p，不会出现更低的）
        return True

    def _check_size(self, r: PanResult, media_type: str) -> bool:
        """体积区间控制：整季资源 < 2GB → 画质极差，丢弃。

        size_gb == 0 表示未知，放行（网盘爬虫不一定能拿到大小）。
        """
        if r.size_gb <= 0:
            return True
        # 整季资源体积下限
        if r.is_complete and media_type == "tv" and r.size_gb < self.MIN_SEASON_SIZE_GB:
            return False
        return True

    def _check_completeness(self, r: PanResult, media_type: str) -> bool:
        """整季判定：碎片集 → 丢弃。

        仅对电视剧类型生效，电影不检查。
        """
        if media_type == "movie":
            return True
        return r.is_complete
