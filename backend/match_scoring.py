"""L2 匹配评分模块 — 多维度匹配评分

提供匹配链（快速筛选）和多维度评分（精细排名）两种模式。
只负责"匹配度"（候选和目标有多像），不负责"质量评分"。

对应技能文档：.kiro/skills/L2-match-scoring.md
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from text_processing import normalize, split_by_language, is_short_name, tokenize
from text_utils import fuzzy_score


# ── 数据结构 ──

@dataclass
class MatchCandidate:
    """匹配候选项"""
    names: List[str] = field(default_factory=list)
    year: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None
    id: str = ""  # TMDB/IMDB ID

@dataclass
class MatchTarget:
    """匹配目标"""
    names: List[str] = field(default_factory=list)
    year: str = ""
    season: Optional[int] = None
    episode: Optional[int] = None
    id: str = ""
    aliases: List[str] = field(default_factory=list)  # 别名/译名

@dataclass
class DimensionConfig:
    """评分维度配置"""
    field: str = ""
    max_score: int = 80
    strategy: str = "best_of"  # best_of / tolerance / exact
    short_protect: bool = False
    tolerance: int = 0
    missing_penalty: float = 0.0  # 0 = 不惩罚，0.5 = 总分×0.5


# ── 英文停用词 ──
_STOP_WORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "to", "for",
    "is", "it", "and", "or", "but", "not", "no", "by", "with",
})


def _normalize_name(name: str) -> str:
    """标准化名称用于比较"""
    return normalize(name)


def _is_stop_word(word: str) -> bool:
    return word.lower().strip() in _STOP_WORDS


def _dynamic_fuzzy_threshold(text_len: int) -> float:
    """动态 fuzzy 阈值：短词更严格"""
    if text_len <= 4:
        return 999.0  # 禁用 fuzzy（阈值不可能达到）
    elif text_len <= 10:
        return 0.7
    else:
        return 0.8


def _score_name_pair(candidate_name: str, target_name: str, short_protect: bool = False) -> float:
    """计算两个名称之间的匹配分数（0.0-1.0）"""
    cn = _normalize_name(candidate_name)
    tn = _normalize_name(target_name)

    if not cn or not tn:
        return 0.0

    # 精确匹配
    if cn == tn:
        return 1.0

    # 短名字保护
    if short_protect and (is_short_name(candidate_name) or is_short_name(target_name)):
        return 0.0  # 短名字只允许精确匹配

    # 包含匹配
    if cn in tn or tn in cn:
        return 0.5

    # token_set 匹配
    c_tokens = set(tokenize(candidate_name))
    t_tokens = set(tokenize(target_name))
    if c_tokens and t_tokens:
        intersection = c_tokens & t_tokens
        if intersection:
            ratio = len(intersection) / max(len(c_tokens), len(t_tokens))
            if ratio >= 0.5:
                return 0.4 * ratio

    # 动态 fuzzy 匹配
    threshold = _dynamic_fuzzy_threshold(max(len(cn), len(tn)))
    score = fuzzy_score(cn, tn)
    if score >= threshold:
        return score * 0.5  # fuzzy 匹配最高 0.5

    return 0.0


# ════════════════════════════════════════
# 匹配链（快速筛选模式）
# ════════════════════════════════════════

def match_chain(
    candidate_names: List[str],
    target_titles: List[str],
    target_aliases: List[str],
    candidate_id: str = "",
    target_id: str = "",
) -> int:
    """匹配链：逐层放宽，首个通过即停止，返回 0-100 分"""

    # 1. ID 精确匹配 → 100分
    if candidate_id and target_id and candidate_id == target_id:
        return 100

    c_norms = [_normalize_name(n) for n in candidate_names if n]
    t_title_norms = [_normalize_name(n) for n in target_titles if n]
    t_alias_norms = [_normalize_name(n) for n in target_aliases if n]

    if not c_norms:
        return 0

    # 2. 主标题精确匹配 → 90分
    for cn in c_norms:
        if cn in t_title_norms:
            return 90

    # 3. 别名/译名精确匹配 → 80分
    for cn in c_norms:
        if cn in t_alias_norms:
            return 80

    # 3.5 子串包含匹配 → 70分（normalize 后 A 是 B 的子串）
    # 短名字保护：短名字不允许 contains（防止 "AI" 匹配 "RAIN"）
    for cn in c_norms:
        if len(cn) <= 4:
            continue  # 短名字跳过 contains
        for tn in t_title_norms + t_alias_norms:
            if len(tn) <= 4:
                continue
            if cn in tn or tn in cn:
                # 额外约束：子串长度至少是母串的 40%（防止 "流浪" 匹配 "流浪猫鲍勃流浪记"）
                shorter, longer = (cn, tn) if len(cn) <= len(tn) else (tn, cn)
                if len(shorter) >= len(longer) * 0.4:
                    return 70

    # 4. 标题拆分匹配 → 60分
    for c_name in candidate_names:
        c_tokens = set(tokenize(c_name))
        if not c_tokens or len(c_tokens) < 2:
            continue
        for t_name in target_titles + target_aliases:
            t_tokens = set(tokenize(t_name))
            if not t_tokens:
                continue
            intersection = c_tokens & t_tokens
            # 短名字保护：候选 token 只有 1 个且是短 token，跳过
            if len(c_tokens) == 1:
                continue
            # 候选 tokens 大部分出现在目标中（搜索词短，BT 标题长）
            # 或者目标 tokens 大部分出现在候选中（BT 标题短，搜索词长）
            c_ratio = len(intersection) / len(c_tokens) if c_tokens else 0
            t_ratio = len(intersection) / len(t_tokens) if t_tokens else 0
            if c_ratio >= 0.7 or (t_ratio >= 0.5 and len(intersection) >= 2):
                return 60

    # 5. 动态 fuzzy 匹配 → 40分
    for cn in c_norms:
        # 短名字保护
        if len(cn) <= 4:
            continue
        threshold = _dynamic_fuzzy_threshold(len(cn))
        for tn in t_title_norms + t_alias_norms:
            if len(tn) <= 4:
                continue
            score = fuzzy_score(cn, tn)
            if score >= threshold:
                return 40

    # 6. 不通过
    return 0


# ════════════════════════════════════════
# 多维度评分（精细排名模式）
# ════════════════════════════════════════

def multi_dimension_score(
    candidate: MatchCandidate,
    target: MatchTarget,
    dimensions: List[DimensionConfig],
    cross_validation: Optional[List[Dict]] = None,
    threshold: int = 0,
) -> Dict[str, Any]:
    """多维度独立评分，返回结构化结果"""

    breakdown: Dict[str, int] = {}
    penalties: List[str] = []
    cross_bonuses: List[str] = []

    for dim in dimensions:
        if dim.field == "name":
            breakdown["name"] = _score_name_dimension(candidate, target, dim)
        elif dim.field == "year":
            breakdown["year"] = _score_year_dimension(candidate, target, dim)
        elif dim.field == "season":
            breakdown["season"] = _score_season_dimension(candidate, target, dim)
        elif dim.field == "episode":
            breakdown["episode"] = _score_episode_dimension(candidate, target, dim)
        else:
            breakdown[dim.field] = 0

    # 计算原始总分
    raw_score = sum(breakdown.values())

    # 交叉验证加分
    bonus = 0
    if cross_validation:
        for cv in cross_validation:
            fields = cv.get("fields", [])
            cv_bonus = cv.get("bonus", 0)
            # 触发条件：每个维度得分 ≥ 该维度满分的 50%
            all_pass = True
            for f in fields:
                dim_config = next((d for d in dimensions if d.field == f), None)
                if dim_config and breakdown.get(f, 0) >= dim_config.max_score * 0.5:
                    continue
                else:
                    all_pass = False
                    break
            if all_pass:
                bonus += cv_bonus
                cross_bonuses.append(f"{'+'.join(fields)}: +{cv_bonus}")

    total = raw_score + bonus

    # 缺失惩罚（乘法）
    for dim in dimensions:
        if dim.missing_penalty > 0 and breakdown.get(dim.field, 0) == 0:
            # 检查是否"有约束但没匹配上"
            has_constraint = False
            if dim.field == "year" and target.year and candidate.year:
                has_constraint = True
            elif dim.field == "season" and target.season is not None and candidate.season is not None:
                has_constraint = True
            elif dim.field == "name":
                has_constraint = bool(target.names and candidate.names)

            if has_constraint:
                total = int(total * dim.missing_penalty)
                penalties.append(f"{dim.field}: ×{dim.missing_penalty}")

    return {
        "score": total,
        "breakdown": breakdown,
        "cross_bonuses": cross_bonuses,
        "penalties": penalties,
        "passed": total >= threshold,
    }


def _score_name_dimension(candidate: MatchCandidate, target: MatchTarget, dim: DimensionConfig) -> int:
    """name 维度评分：遍历所有名称组合，取最高分"""
    best = 0.0
    all_target_names = list(target.names) + list(target.aliases)

    for c_name in candidate.names:
        for t_name in all_target_names:
            score = _score_name_pair(c_name, t_name, short_protect=dim.short_protect)
            best = max(best, score)

    return int(best * dim.max_score)


def _score_year_dimension(candidate: MatchCandidate, target: MatchTarget, dim: DimensionConfig) -> int:
    """year 维度评分：容差匹配"""
    if not candidate.year or not target.year:
        return 0
    try:
        cy = int(candidate.year)
        ty = int(target.year)
    except (ValueError, TypeError):
        return 0

    diff = abs(cy - ty)
    if diff == 0:
        return dim.max_score
    elif diff <= dim.tolerance:
        return int(dim.max_score * 0.7)
    else:
        return 0


def _score_season_dimension(candidate: MatchCandidate, target: MatchTarget, dim: DimensionConfig) -> int:
    """season 维度评分：精确匹配"""
    if candidate.season is None or target.season is None:
        return 0
    return dim.max_score if candidate.season == target.season else 0


def _score_episode_dimension(candidate: MatchCandidate, target: MatchTarget, dim: DimensionConfig) -> int:
    """episode 维度评分：精确匹配"""
    if candidate.episode is None or target.episode is None:
        return 0
    return dim.max_score if candidate.episode == target.episode else 0
