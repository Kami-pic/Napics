"""L2 match-scoring 技能测试 — TDD 驱动"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from match_scoring import (
    match_chain, multi_dimension_score, MatchCandidate, MatchTarget, DimensionConfig,
)


# ── 匹配链 ──

class TestMatchChain:
    def test_exact_title(self):
        """主标题精确匹配 → 90分"""
        score = match_chain(
            candidate_names=["进击的巨人"],
            target_titles=["进击的巨人"],
            target_aliases=[],
        )
        assert score >= 90

    def test_alias_match(self):
        """别名匹配 → 80分（低于主标题）"""
        score = match_chain(
            candidate_names=["Attack on Titan"],
            target_titles=["进击的巨人"],
            target_aliases=["Attack on Titan"],
        )
        assert 75 <= score <= 85

    def test_split_match(self):
        """标题拆分匹配 → 60分"""
        score = match_chain(
            candidate_names=["进击的巨人 第四季 完结篇"],
            target_titles=["进击的巨人"],
            target_aliases=[],
        )
        assert 40 <= score <= 70

    def test_fuzzy_match(self):
        """拼写接近的长标题应该能匹配上"""
        # 完全相同的 token 子集
        score = match_chain(
            candidate_names=["Attack on Titan Final Season Part 2"],
            target_titles=["Attack on Titan"],
            target_aliases=[],
        )
        assert score >= 40  # token_set 或 fuzzy 应该能匹配

    def test_no_match(self):
        """完全不匹配 → 0分"""
        score = match_chain(
            candidate_names=["美国派"],
            target_titles=["进击的巨人"],
            target_aliases=["Attack on Titan"],
        )
        assert score == 0

    def test_short_name_protection(self):
        """短名字保护：短名字不允许 contains/fuzzy"""
        score = match_chain(
            candidate_names=["她的秘密花园"],
            target_titles=["她"],
            target_aliases=[],
        )
        # "她" 是短名字，不应该因为 contains "她" 就匹配上
        assert score == 0

    def test_id_match(self):
        """ID 精确匹配 → 100分"""
        score = match_chain(
            candidate_names=["随便什么名字"],
            target_titles=["进击的巨人"],
            target_aliases=[],
            candidate_id="tt12345",
            target_id="tt12345",
        )
        assert score == 100

    def test_dynamic_fuzzy_short_word(self):
        """动态 fuzzy：长度 ≤ 4 禁用 fuzzy"""
        score = match_chain(
            candidate_names=["Herr"],  # 4 字符，和 "Her" 很像但不该 fuzzy 匹配
            target_titles=["Her"],
            target_aliases=[],
        )
        # Her 是短名字，Herr 也很短，不应该 fuzzy 匹配
        assert score == 0


# ── 多维度评分 ──

class TestMultiDimensionScore:
    def test_exact_name_match(self):
        """精确名称匹配 → name 维度满分"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["进击的巨人"]),
            target=MatchTarget(names=["进击的巨人"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of", short_protect=True)],
        )
        assert result["breakdown"]["name"] == 80
        assert result["score"] >= 80

    def test_contains_match(self):
        """包含匹配 → name 维度半分"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["进击的巨人 第四季"]),
            target=MatchTarget(names=["进击的巨人"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of")],
        )
        assert 30 <= result["breakdown"]["name"] <= 50

    def test_short_name_protection(self):
        """短名字保护：短名字 contains 不得分"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["她的秘密花园"]),
            target=MatchTarget(names=["她"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of", short_protect=True)],
        )
        assert result["breakdown"]["name"] == 0

    def test_year_tolerance(self):
        """年份容差匹配"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["X"], year="2023"),
            target=MatchTarget(names=["X"], year="2022"),
            dimensions=[
                DimensionConfig(field="name", max_score=80, strategy="best_of"),
                DimensionConfig(field="year", max_score=30, strategy="tolerance", tolerance=1),
            ],
        )
        assert result["breakdown"]["year"] > 0  # 容差内应得分

    def test_year_mismatch(self):
        """年份不匹配（超出容差）"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["X"], year="2020"),
            target=MatchTarget(names=["X"], year="2023"),
            dimensions=[
                DimensionConfig(field="name", max_score=80, strategy="best_of"),
                DimensionConfig(field="year", max_score=30, strategy="tolerance", tolerance=1),
            ],
        )
        assert result["breakdown"]["year"] == 0

    def test_missing_penalty(self):
        """缺失惩罚：有年份但不匹配 → 总分 ×0.5"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["进击的巨人"], year="2020"),
            target=MatchTarget(names=["进击的巨人"], year="2023"),
            dimensions=[
                DimensionConfig(field="name", max_score=80, strategy="best_of"),
                DimensionConfig(field="year", max_score=30, strategy="tolerance", tolerance=1, missing_penalty=0.5),
            ],
        )
        # name 满分 80，year 不匹配触发惩罚 → 总分 = 80 × 0.5 = 40
        assert result["score"] <= 45
        assert len(result["penalties"]) > 0

    def test_cross_validation(self):
        """交叉验证：name + year 都匹配 → 加分"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["进击的巨人"], year="2022"),
            target=MatchTarget(names=["进击的巨人"], year="2022"),
            dimensions=[
                DimensionConfig(field="name", max_score=80, strategy="best_of"),
                DimensionConfig(field="year", max_score=30, strategy="tolerance", tolerance=1),
            ],
            cross_validation=[{"fields": ["name", "year"], "bonus": 15}],
        )
        assert result["score"] >= 80 + 30 + 15  # name + year + bonus
        assert len(result["cross_bonuses"]) > 0

    def test_season_exact(self):
        """季号精确匹配"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["X"], season=4),
            target=MatchTarget(names=["X"], season=4),
            dimensions=[
                DimensionConfig(field="name", max_score=80, strategy="best_of"),
                DimensionConfig(field="season", max_score=20, strategy="exact"),
            ],
        )
        assert result["breakdown"]["season"] == 20

    def test_output_structure(self):
        """输出结构完整性"""
        result = multi_dimension_score(
            candidate=MatchCandidate(names=["X"]),
            target=MatchTarget(names=["X"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of")],
        )
        assert "score" in result
        assert "breakdown" in result
        assert "cross_bonuses" in result
        assert "penalties" in result
        assert "passed" in result

    def test_dynamic_fuzzy_threshold(self):
        """动态 fuzzy 阈值：短词更严格"""
        # 长词（>10字符）允许 fuzzy
        result_long = multi_dimension_score(
            candidate=MatchCandidate(names=["Attck on Titan Final"]),  # 拼写错误
            target=MatchTarget(names=["Attack on Titan Final"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of")],
        )
        # 短词（<=4字符）禁用 fuzzy
        result_short = multi_dimension_score(
            candidate=MatchCandidate(names=["Herr"]),
            target=MatchTarget(names=["Her"]),
            dimensions=[DimensionConfig(field="name", max_score=80, strategy="best_of", short_protect=True)],
        )
        assert result_short["breakdown"]["name"] == 0  # 短词不允许 fuzzy
