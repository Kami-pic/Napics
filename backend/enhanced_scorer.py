"""
增强匹配评分器：对 TMDB 候选结果进行多维度评分并输出置信度等级。

评分维度：
- 精确匹配（最高 100 分）
- 模糊匹配（阈值 >= 0.85）
- 前缀匹配（70 分）
- 包含匹配（50 分）
- 别名交叉验证（+15~25 分）
- 年份匹配（+20/-30 分）
- 热度加分（最高 +10 分）

置信度：score >= 80 → high, 50-79 → medium, < 50 → low
"""
from dataclasses import dataclass, field
from typing import List, Optional

from text_utils import normalize_text, fuzzy_score
from alias_resolver import AliasSet


@dataclass
class MatchResult:
    """匹配结果，包含置信度"""
    item: dict                              # TMDB 搜索结果原始数据
    score: int                              # 综合评分
    confidence: str                         # "high" | "medium" | "low"
    match_details: dict = field(default_factory=dict)  # 各维度得分明细
    tmdb_id: int = 0
    media_type: str = ""                    # "movie" | "tv"


class EnhancedScorer:
    """增强匹配评分器"""

    HIGH_CONFIDENCE = 80
    MEDIUM_CONFIDENCE = 50

    def score_candidate(self, query: str, candidate: dict,
                        aliases: Optional[AliasSet] = None,
                        year: Optional[str] = None) -> MatchResult:
        """对单个候选项进行多维度评分。

        前置条件: query 非空, candidate 是有效的 TMDB 搜索结果 dict
        后置条件: 返回 MatchResult，confidence 与 score 一致
        """
        if aliases is None:
            aliases = AliasSet()

        query_norm = normalize_text(query)
        title = candidate.get("title") or candidate.get("name", "")
        original = (candidate.get("original_title")
                    or candidate.get("original_name", ""))
        title_norm = normalize_text(title)
        orig_norm = normalize_text(original)
        cand_year = (candidate.get("release_date", "")
                     or candidate.get("first_air_date", ""))[:4]

        details = {}
        score = 0

        # 维度 1：精确匹配（最高 100 分）
        if query_norm and title_norm and title_norm == query_norm:
            details["exact_cn"] = 100
            score = 100
        elif query_norm and orig_norm and orig_norm == query_norm:
            details["exact_orig"] = 80
            score = 80
        else:
            # 维度 2：模糊匹配
            if query_norm and title_norm:
                fuzzy_cn = fuzzy_score(query_norm, title_norm)
                if fuzzy_cn >= 0.85:
                    details["fuzzy_cn"] = int(fuzzy_cn * 90)
                    score = max(score, details["fuzzy_cn"])

            if query_norm and orig_norm:
                fuzzy_orig = fuzzy_score(query_norm, orig_norm)
                if fuzzy_orig >= 0.85:
                    details["fuzzy_orig"] = int(fuzzy_orig * 75)
                    score = max(score, details["fuzzy_orig"])

            # 维度 3：前缀/包含匹配
            if title_norm and query_norm:
                if (title_norm.startswith(query_norm)
                        or query_norm.startswith(title_norm)):
                    details["prefix"] = 70
                    score = max(score, 70)
                elif title_norm in query_norm or query_norm in title_norm:
                    details["contains"] = 50
                    score = max(score, 50)

        # 维度 4：别名交叉验证（+15~25 分）
        alias_bonus = self._alias_match_score(query_norm, aliases,
                                              title_norm, orig_norm)
        if alias_bonus > 0:
            details["alias_bonus"] = alias_bonus
            score += alias_bonus

        # 维度 5：年份匹配
        if year and cand_year:
            try:
                year_diff = abs(int(year) - int(cand_year))
                if year_diff == 0:
                    details["year_match"] = 20
                    score += 20
                elif year_diff <= 1:
                    details["year_close"] = 10
                    score += 10
                else:
                    details["year_mismatch"] = -30
                    score -= 30
            except (ValueError, TypeError):
                pass

        # 维度 6：热度加分（最高 +10）
        popularity = candidate.get("popularity", 0)
        if isinstance(popularity, (int, float)) and popularity > 0:
            pop_bonus = min(int(popularity / 10), 10)
            if pop_bonus > 0:
                details["popularity"] = pop_bonus
                score += pop_bonus

        # 确定置信度
        if score >= self.HIGH_CONFIDENCE:
            confidence = "high"
        elif score >= self.MEDIUM_CONFIDENCE:
            confidence = "medium"
        else:
            confidence = "low"

        # 判断 media_type: "title" 字段存在 → movie, 否则 → tv
        media_type = "movie" if "title" in candidate else "tv"

        return MatchResult(
            item=candidate,
            score=score,
            confidence=confidence,
            match_details=details,
            tmdb_id=candidate.get("id", 0),
            media_type=media_type,
        )

    def best_match(self, query: str, candidates: List[dict],
                   aliases: Optional[AliasSet] = None,
                   year: Optional[str] = None) -> Optional[MatchResult]:
        """从候选列表中选出最佳匹配。

        返回得分最高的 MatchResult，无候选项时返回 None。
        """
        if not candidates:
            return None

        best: Optional[MatchResult] = None
        for candidate in candidates:
            result = self.score_candidate(query, candidate, aliases, year)
            if best is None or result.score > best.score:
                best = result

        return best

    def _alias_match_score(self, query_norm: str, aliases: AliasSet,
                           title_norm: str = "",
                           orig_norm: str = "") -> int:
        """别名交叉匹配加分（+15~25 分）。

        检查候选项的标题/原始标题是否出现在别名集合中，
        或者别名集合中的名称是否与查询词匹配。
        """
        if not query_norm:
            return 0

        bonus = 0
        all_alias_names = (
            aliases.cn_names + aliases.en_names + aliases.jp_names
        )

        for alias_name in all_alias_names:
            alias_norm = normalize_text(alias_name)
            if not alias_norm:
                continue

            # 候选项标题与别名精确匹配 → +25
            if title_norm and title_norm == alias_norm:
                return 25
            if orig_norm and orig_norm == alias_norm:
                return 25

            # 候选项标题与别名模糊匹配 → +20
            if title_norm and fuzzy_score(title_norm, alias_norm) >= 0.85:
                bonus = max(bonus, 20)
            if orig_norm and fuzzy_score(orig_norm, alias_norm) >= 0.85:
                bonus = max(bonus, 20)

            # 别名与查询词模糊匹配（说明查询词本身是别名之一）→ +15
            if fuzzy_score(query_norm, alias_norm) >= 0.85:
                bonus = max(bonus, 15)

        return bonus
