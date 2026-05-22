"""Unit tests for EnhancedScorer."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from enhanced_scorer import EnhancedScorer, MatchResult
from alias_resolver import AliasSet


def test_exact_match_cn_title():
    """精确匹配中文标题 → 100 分"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "id": 1, "release_date": "2019-02-05",
                 "popularity": 50}
    result = scorer.score_candidate("流浪地球", candidate)
    assert result.match_details.get("exact_cn") == 100
    assert result.score >= 100
    assert result.confidence == "high"
    assert result.media_type == "movie"


def test_exact_match_original_title():
    """精确匹配 original_title → 80 分"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "original_title": "The Wandering Earth",
                 "id": 2, "release_date": "2019-02-05", "popularity": 10}
    result = scorer.score_candidate("The Wandering Earth", candidate)
    assert result.match_details.get("exact_orig") == 80
    assert result.score >= 80
    assert result.confidence == "high"


def test_prefix_match():
    """前缀匹配 → 70 分"""
    scorer = EnhancedScorer()
    candidate = {"title": "哈利波特与魔法石", "id": 3,
                 "release_date": "2001-11-16", "popularity": 80}
    result = scorer.score_candidate("哈利波特", candidate)
    assert result.match_details.get("prefix") == 70
    assert result.score >= 70


def test_contains_match():
    """包含匹配 → 50 分"""
    scorer = EnhancedScorer()
    candidate = {"title": "星球大战：新希望", "id": 4,
                 "release_date": "1977-05-25", "popularity": 90}
    result = scorer.score_candidate("新希望", candidate)
    assert result.match_details.get("contains") == 50


def test_year_match_bonus():
    """年份匹配 → +20"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "id": 1, "release_date": "2019-02-05",
                 "popularity": 0}
    result = scorer.score_candidate("流浪地球", candidate, year="2019")
    assert result.match_details.get("year_match") == 20
    assert result.score >= 120  # 100 (exact) + 20 (year)


def test_year_close_bonus():
    """年份差1 → +10"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "id": 1, "release_date": "2019-02-05",
                 "popularity": 0}
    result = scorer.score_candidate("流浪地球", candidate, year="2020")
    assert result.match_details.get("year_close") == 10


def test_year_mismatch_penalty():
    """年份差>1 → -30"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "id": 1, "release_date": "2019-02-05",
                 "popularity": 0}
    result = scorer.score_candidate("流浪地球", candidate, year="2023")
    assert result.match_details.get("year_mismatch") == -30


def test_popularity_bonus():
    """热度加分（最高 +10）"""
    scorer = EnhancedScorer()
    candidate = {"title": "流浪地球", "id": 1, "release_date": "2019-02-05",
                 "popularity": 200}
    result = scorer.score_candidate("流浪地球", candidate)
    assert result.match_details.get("popularity") == 10  # capped at 10


def test_confidence_high():
    """score >= 80 → high"""
    scorer = EnhancedScorer()
    candidate = {"title": "测试影片", "id": 10, "release_date": "2024-01-01",
                 "popularity": 0}
    result = scorer.score_candidate("测试影片", candidate, year="2024")
    assert result.confidence == "high"
    assert result.score >= 80


def test_confidence_medium():
    """50 <= score < 80 → medium"""
    scorer = EnhancedScorer()
    candidate = {"title": "前缀匹配测试很长的标题", "id": 11,
                 "release_date": "", "popularity": 0}
    result = scorer.score_candidate("前缀匹配测试", candidate)
    # prefix match = 70, no year, no popularity → medium
    assert result.confidence == "medium"
    assert 50 <= result.score < 80


def test_confidence_low():
    """score < 50 → low"""
    scorer = EnhancedScorer()
    candidate = {"title": "完全不同的标题", "id": 12,
                 "release_date": "2020-01-01", "popularity": 0}
    result = scorer.score_candidate("毫无关系的查询", candidate)
    assert result.confidence == "low"
    assert result.score < 50


def test_alias_bonus():
    """别名交叉验证加分"""
    scorer = EnhancedScorer()
    aliases = AliasSet(
        cn_names=["坐白车的女人"],
        en_names=["The Woman in the White Car"],
    )
    candidate = {"title": "The Woman in the White Car", "id": 20,
                 "release_date": "2024-01-01", "popularity": 30}
    result = scorer.score_candidate("坐白车的女人", candidate, aliases, "2024")
    # 别名中有英文名与候选标题精确匹配 → alias_bonus = 25
    assert result.match_details.get("alias_bonus") == 25


def test_best_match_returns_highest():
    """best_match 返回得分最高的候选"""
    scorer = EnhancedScorer()
    candidates = [
        {"title": "完全不同", "id": 1, "release_date": "", "popularity": 0},
        {"title": "流浪地球", "id": 2, "release_date": "2019-02-05",
         "popularity": 100},
        {"title": "部分匹配", "id": 3, "release_date": "", "popularity": 0},
    ]
    result = scorer.best_match("流浪地球", candidates, year="2019")
    assert result is not None
    assert result.tmdb_id == 2
    assert result.confidence == "high"


def test_best_match_empty_candidates():
    """空候选列表 → None"""
    scorer = EnhancedScorer()
    result = scorer.best_match("test", [])
    assert result is None


def test_media_type_movie():
    """有 title 字段 → movie"""
    scorer = EnhancedScorer()
    candidate = {"title": "Test", "id": 1, "release_date": "", "popularity": 0}
    result = scorer.score_candidate("Test", candidate)
    assert result.media_type == "movie"


def test_media_type_tv():
    """有 name 字段（无 title）→ tv"""
    scorer = EnhancedScorer()
    candidate = {"name": "Test Show", "id": 2, "first_air_date": "",
                 "popularity": 0}
    result = scorer.score_candidate("Test Show", candidate)
    assert result.media_type == "tv"


def test_tv_candidate_scoring():
    """TV 候选项使用 name/original_name/first_air_date"""
    scorer = EnhancedScorer()
    candidate = {"name": "进击的巨人", "original_name": "進撃の巨人",
                 "id": 5, "first_air_date": "2013-04-07", "popularity": 150}
    result = scorer.score_candidate("进击的巨人", candidate, year="2013")
    assert result.match_details.get("exact_cn") == 100
    assert result.match_details.get("year_match") == 20
    assert result.media_type == "tv"
