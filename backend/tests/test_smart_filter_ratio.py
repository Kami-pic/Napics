"""智能过滤 — 标题占比检查（规则 5）测试

验证：搜索词只是长标题的一小部分时，即使 match_score 在 40-70，也应被标记。
典型场景：合集标题、长描述标题、部分重叠标题。

对应技能文档：.kiro/skills/smart-filter.md
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from search_helpers import compute_junk_flags, extract_bt_title_for_match, _MATCH_SCORE_THRESHOLD
from match_scoring import match_chain
from text_processing import split_by_language


def _full_score(query, bt_title, match_names=None):
    """模拟完整的 enrich_result 评分 + junk 标记流程"""
    parts = split_by_language(query)
    candidates = [n for n in [query, parts["cn"], parts["en"]] if n]
    if match_names:
        for name in match_names:
            if name and name not in candidates:
                candidates.append(name)
                np = split_by_language(name)
                for p in [np["cn"], np["en"]]:
                    if p and p not in candidates:
                        candidates.append(p)
    candidates = list(dict.fromkeys(candidates))
    bt_clean = extract_bt_title_for_match(bt_title)
    bt_parts = split_by_language(bt_clean)
    targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
    score = match_chain(candidates, targets, [])
    d = {
        "title": bt_title, "match_score": score, "seeders": 50, "size_gb": 5.0,
        "_has_multilang_candidates": len(candidates) >= 3,
        "_bt_clean": bt_clean, "_search_names": candidates,
    }
    flags = compute_junk_flags(d)
    return score, flags, bt_clean


class TestTitleRatioCheck:
    """标题占比检查"""

    def test_cn_collection_title(self):
        """中文合集标题：搜'芙莉莲'，标题是多部动画合集"""
        score, flags, clean = _full_score(
            "芙莉莲",
            "2024年度最佳动画合集 芙莉莲 鬼灭之刃 咒术回战 1080p"
        )
        print(f"  [合集] score={score}, clean='{clean}', flags={flags}")
        # 芙莉莲只占标题很小一部分，应被标记
        assert any("low_title_ratio" in r for r in flags["junk_reasons"]), \
            f"合集标题应被标记，score={score}, reasons={flags['junk_reasons']}"

    def test_cn_partial_overlap(self):
        """中文部分重叠：搜'西部世界'，标题是'西部风云'"""
        score, flags, clean = _full_score("西部世界", "西部风云.Into.the.West.2005.S01.720p")
        print(f"  [重叠] score={score}, clean='{clean}', flags={flags}")
        # "西部" 只是公共前缀，占比低
        assert any("low_title_ratio" in r for r in flags["junk_reasons"]), \
            f"部分重叠应被标记，score={score}, reasons={flags['junk_reasons']}"

    def test_normal_match_not_flagged(self):
        """正常匹配不应被标记"""
        score, flags, clean = _full_score(
            "流浪地球",
            "流浪地球2.The.Wandering.Earth.II.2023.2160p.WEB-DL.H265"
        )
        print(f"  [正常] score={score}, clean='{clean}', flags={flags}")
        assert not any("low_title_ratio" in r for r in flags["junk_reasons"]), \
            f"正常匹配不应被标记，score={score}"

    def test_exact_match_not_flagged(self):
        """精确匹配（score=90）不受占比检查影响"""
        score, flags, clean = _full_score(
            "Inception",
            "Inception.2010.2160p.UHD.BluRay.x265.DTS-HD.MA.5.1-SWTYBLZ"
        )
        print(f"  [精确] score={score}, clean='{clean}', flags={flags}")
        assert score >= 80  # 精确匹配
        assert not any("low_title_ratio" in r for r in flags["junk_reasons"])

    def test_en_collection_title(self):
        """英文合集标题"""
        score, flags, clean = _full_score(
            "Frieren",
            "Top.10.Anime.2024.Frieren.One.Piece.Jujutsu.Kaisen.1080p",
            match_names=["Frieren Beyond Journeys End"]
        )
        print(f"  [英文合集] score={score}, clean='{clean}', flags={flags}")
        # Frieren 只是长标题的一小部分

    def test_cn_with_en_name_normal(self):
        """有英文名的正常匹配"""
        score, flags, clean = _full_score(
            "芙莉莲第二季",
            "Frieren.Beyond.Journeys.End.S02E01.1080p.WEB-DL",
            match_names=["Frieren Beyond Journeys End"]
        )
        print(f"  [跨语言正常] score={score}, clean='{clean}', flags={flags}")
        assert score >= 60
        assert not any("low_title_ratio" in r for r in flags["junk_reasons"])

    def test_season_title_not_flagged(self):
        """季度标题（含季号）不应被标记"""
        score, flags, clean = _full_score(
            "进击的巨人",
            "[字幕组] 进击的巨人 最终季 第01集 [1080p]"
        )
        print(f"  [季度] score={score}, clean='{clean}', flags={flags}")
        assert not any("low_title_ratio" in r for r in flags["junk_reasons"])

    def test_low_score_not_double_flagged(self):
        """match_score < 30 已被规则 2 标记，不应再被规则 5 标记"""
        d = {
            "title": "Random.Movie", "match_score": 20, "seeders": 50, "size_gb": 5.0,
            "_has_multilang_candidates": False,
            "_bt_clean": "Random Movie", "_search_names": ["芙莉莲"],
        }
        flags = compute_junk_flags(d)
        # 应该只有 low_match，不应有 low_title_ratio（score < 40 不触发规则 5）
        assert any("low_match" in r for r in flags["junk_reasons"])
        assert not any("low_title_ratio" in r for r in flags["junk_reasons"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
