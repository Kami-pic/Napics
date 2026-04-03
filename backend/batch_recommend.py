"""批量推荐算法：多维度加权评分，为批量升级面板自动推荐最佳资源。

6 个评分维度：
- title_match (0.30)：标题匹配度，fuzzy_score 比对
- resolution_upgrade (0.25)：分辨率提升幅度，硬性拦截无提升
- codec_match (0.15)：编码匹配度，x265 > x264 > 其他
- seeder_health (0.15)：做种健康度，非线性（50+ 满分）
- chinese_sub (0.10)：中文字幕加分
- size_reasonable (0.05)：文件大小合理性，基于分辨率的期望区间

置信度：score >= 0.7 → high, >= 0.5 → medium, < 0.5 → low
"""

import math
from typing import List, Optional
from pydantic import BaseModel

from searcher import SearchResult
from quality_parser import parse_quality, QualityTag
from text_utils import normalize_text, fuzzy_score


class RecommendResult(BaseModel):
    """推荐结果"""
    best: Optional[SearchResult] = None
    score: float = 0.0
    confidence: str = "low"    # "high" | "medium" | "low"
    is_upgrade: bool = False   # 分辨率是否有提升
    score_details: dict = {}   # 各维度得分明细


# ── 分辨率阶梯 ──
_RES_RANK = {"": 0, "SD": 0, "720p": 1, "1080p": 2, "2160p": 3}

# ── 编码偏好排序（越高越好）──
_CODEC_RANK = {"": 0, "x264": 1, "x265": 2, "AV1": 3}

# ── 各分辨率的期望文件大小区间 (GB)，用于 size_reasonable 评分 ──
# (min_ideal, max_ideal) — 落在区间内满分，偏离越远扣分越多
_SIZE_EXPECTATIONS = {
    "2160p": (8.0, 60.0),
    "1080p": (2.0, 20.0),
    "720p":  (1.0, 8.0),
    "":      (0.5, 15.0),  # 未知分辨率的宽松区间
}

# ── 做种健康度阈值 ──
_SEEDER_FULL_SCORE = 50  # >= 50 做种拿满分


def _normalize_resolution(raw: str) -> str:
    """将各种分辨率表示统一为标准标签。"""
    if not raw:
        return ""
    low = raw.lower()
    if "2160" in low or "4k" in low:
        return "2160p"
    if "1080" in low:
        return "1080p"
    if "720" in low:
        return "720p"
    return ""


class BatchRecommendAlgo:
    """批量搜索推荐算法：多维度加权评分。"""

    DEFAULT_WEIGHTS = {
        "title_match": 0.30,
        "resolution_upgrade": 0.25,
        "codec_match": 0.15,
        "seeder_health": 0.15,
        "chinese_sub": 0.10,
        "size_reasonable": 0.05,
    }

    def __init__(self, custom_weights: dict = None):
        """custom_weights: 用户自定义权重字典，缺失字段用默认值补齐。"""
        self.WEIGHTS = {**self.DEFAULT_WEIGHTS}
        if custom_weights:
            for k in self.DEFAULT_WEIGHTS:
                if k in custom_weights:
                    self.WEIGHTS[k] = float(custom_weights[k])

    def score(
        self,
        result: SearchResult,
        target_title: str,
        current_resolution: str,
        preferred_codec: str = "x265",
    ) -> tuple:
        """计算单条结果的匹配分数 0.0-1.0，返回 (score, is_upgrade, details)。"""
        quality = result.quality or parse_quality(result.title)
        details = {}

        # ── 1. 标题匹配度 (0.0-1.0) ──
        target_norm = normalize_text(target_title)
        result_norm = normalize_text(result.title)
        title_score = fuzzy_score(target_norm, result_norm) if target_norm and result_norm else 0.0
        details["title_match"] = round(title_score, 3)

        # ── 2. 分辨率提升 (0.0-1.0)，硬性拦截无提升 ──
        cur_res = _normalize_resolution(current_resolution)
        res_res = quality.resolution or ""
        cur_rank = _RES_RANK.get(cur_res, 0)
        res_rank = _RES_RANK.get(res_res, 0)

        is_upgrade = res_rank > cur_rank
        if not is_upgrade:
            # 无提升 → 该维度 0 分
            res_score = 0.0
        else:
            # 提升幅度归一化：1级提升=0.5, 2级=0.8, 3级=1.0
            diff = res_rank - cur_rank
            res_score = min(diff * 0.4 + 0.1, 1.0)
        details["resolution_upgrade"] = round(res_score, 3)

        # ── 3. 编码匹配度 (0.0-1.0) ──
        preferred_rank = _CODEC_RANK.get(preferred_codec, 2)
        result_codec = quality.video_codec or ""
        result_rank = _CODEC_RANK.get(result_codec, 0)

        if result_rank == preferred_rank:
            codec_score = 1.0
        elif result_rank > preferred_rank:
            codec_score = 0.8  # 比偏好更好，也不错
        elif result_rank > 0:
            codec_score = 0.4  # 有编码但不是偏好的
        else:
            codec_score = 0.1  # 未知编码
        details["codec_match"] = round(codec_score, 3)

        # ── 4. 做种健康度 (0.0-1.0)，非线性 ──
        seeders = result.seeders or 0
        if seeders >= _SEEDER_FULL_SCORE:
            seeder_score = 1.0
        elif seeders <= 0:
            seeder_score = 0.0
        else:
            # 平方根曲线：增长快但逐渐饱和
            seeder_score = math.sqrt(seeders / _SEEDER_FULL_SCORE)
        details["seeder_health"] = round(seeder_score, 3)

        # ── 5. 中文字幕 (0.0 或 1.0) ──
        sub_score = 1.0 if quality.has_chinese_sub else 0.0
        details["chinese_sub"] = sub_score

        # ── 6. 文件大小合理性 (0.0-1.0) ──
        size_score = self._score_size(result.size_gb, res_res)
        details["size_reasonable"] = round(size_score, 3)

        # ── 加权求和 ──
        total = (
            title_score * self.WEIGHTS["title_match"]
            + res_score * self.WEIGHTS["resolution_upgrade"]
            + codec_score * self.WEIGHTS["codec_match"]
            + seeder_score * self.WEIGHTS["seeder_health"]
            + sub_score * self.WEIGHTS["chinese_sub"]
            + size_score * self.WEIGHTS["size_reasonable"]
        )
        # 严格钳位到 [0.0, 1.0]
        total = max(0.0, min(1.0, round(total, 4)))

        return total, is_upgrade, details

    def recommend(
        self,
        results: List[SearchResult],
        target_title: str,
        current_resolution: str,
        preferred_codec: str = "x265",
    ) -> RecommendResult:
        """从搜索结果中选出最佳推荐。

        返回 RecommendResult 含最佳资源、分数、置信度和是否有提升。
        """
        if not results:
            return RecommendResult()

        best_score = -1.0
        best_result = None
        best_upgrade = False
        best_details = {}

        for r in results:
            score, is_upgrade, details = self.score(
                r, target_title, current_resolution, preferred_codec
            )
            if score > best_score:
                best_score = score
                best_result = r
                best_upgrade = is_upgrade
                best_details = details

        # 置信度
        if best_score >= 0.7:
            confidence = "high"
        elif best_score >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        return RecommendResult(
            best=best_result,
            score=best_score if best_score >= 0 else 0.0,
            confidence=confidence,
            is_upgrade=best_upgrade,
            score_details=best_details,
        )

    @staticmethod
    def _score_size(size_gb: float, resolution: str) -> float:
        """文件大小合理性评分。

        基于分辨率的期望区间，落在区间内满分，
        偏离越远扣分越多（高斯衰减）。
        """
        if size_gb <= 0:
            return 0.0

        min_ideal, max_ideal = _SIZE_EXPECTATIONS.get(resolution, _SIZE_EXPECTATIONS[""])

        if min_ideal <= size_gb <= max_ideal:
            return 1.0

        # 偏离区间的距离
        if size_gb < min_ideal:
            distance = min_ideal - size_gb
            range_width = min_ideal
        else:
            distance = size_gb - max_ideal
            range_width = max_ideal

        # 高斯衰减：distance / range_width 越大，分数越低
        ratio = distance / range_width if range_width > 0 else 1.0
        return max(0.0, math.exp(-2.0 * ratio * ratio))
