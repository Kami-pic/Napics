"""智能过滤 — 跨语言匹配 + unmatched 规则测试

验证：
1. enrich_result 传入 match_names 后，跨语言匹配能正确评分
2. match_score=0 + 有多语言候选 → 标记为 unmatched
3. match_score=0 + 无多语言候选（用户手动搜索）→ 不标记
4. 真实场景：搜"芙莉莲第二季"出现 Zootopia 应被过滤

对应技能文档：.kiro/skills/smart-filter.md
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from search_helpers import (
    compute_junk_flags, extract_bt_title_for_match, enrich_result,
    _MATCH_SCORE_THRESHOLD,
)
from match_scoring import match_chain
from text_processing import split_by_language


def _score_with_names(search_query: str, bt_title: str, match_names: list = None) -> int:
    """模拟 enrich_result 中的 match_score 计算（含 match_names）"""
    parts = split_by_language(search_query)
    candidates = [n for n in [search_query, parts["cn"], parts["en"]] if n]
    if match_names:
        for name in match_names:
            name = name.strip() if name else ""
            if name and name not in candidates:
                candidates.append(name)
                name_parts = split_by_language(name)
                for p in [name_parts["cn"], name_parts["en"]]:
                    if p and p not in candidates:
                        candidates.append(p)
    candidates = list(dict.fromkeys(candidates))
    bt_clean = extract_bt_title_for_match(bt_title)
    bt_parts = split_by_language(bt_clean)
    targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
    return match_chain(candidates, targets, [])


# ════════════════════════════════════════
# 第一组：unmatched 规则
# ════════════════════════════════════════

class TestUnmatchedRule:
    """match_score=0 + 有多语言候选 → unmatched"""

    def test_unmatched_with_multilang(self):
        """有多语言候选但 match_score=0 → 标记 unmatched"""
        d = {"title": "Zootopia.2016.1080p.BluRay", "match_score": 0,
             "seeders": 100, "size_gb": 8.0, "_has_multilang_candidates": True}
        result = compute_junk_flags(d)
        assert result["is_junk"] is True
        assert any("unmatched" in r for r in result["junk_reasons"])

    def test_no_unmatched_without_multilang(self):
        """无多语言候选时 match_score=0 不标记（用户手动搜索）"""
        d = {"title": "Zootopia.2016.1080p.BluRay", "match_score": 0,
             "seeders": 100, "size_gb": 8.0, "_has_multilang_candidates": False}
        result = compute_junk_flags(d)
        assert not any("unmatched" in r for r in result["junk_reasons"])

    def test_no_unmatched_when_matched(self):
        """match_score > 0 时不标记 unmatched（即使有多语言候选）"""
        d = {"title": "Movie.2024.1080p", "match_score": 60,
             "seeders": 50, "size_gb": 5.0, "_has_multilang_candidates": True}
        result = compute_junk_flags(d)
        assert not any("unmatched" in r for r in result["junk_reasons"])

    def test_unmatched_magnet_source(self):
        """磁力源 + unmatched → 仍然标记（磁力源只豁免死种，不豁免 unmatched）"""
        d = {"title": "Random.Movie.2024", "match_score": 0,
             "seeders": 0, "size_gb": 0, "_has_multilang_candidates": True}
        result = compute_junk_flags(d)
        assert any("unmatched" in r for r in result["junk_reasons"])
        # 但不应有 dead_seed（磁力源豁免）
        assert not any("dead_seed" in r for r in result["junk_reasons"])


# ════════════════════════════════════════
# 第二组：match_names 跨语言匹配
# ════════════════════════════════════════

class TestMatchNamesIntegration:
    """传入 match_names 后跨语言匹配应生效"""

    def test_frieren_cn_vs_en_without_names(self):
        """搜'芙莉莲' vs 英文标题 — 无 match_names → 0 分"""
        score = _score_with_names("芙莉莲第二季", "Frieren.Beyond.Journeys.End.S02.1080p.WEB-DL")
        print(f"  [无名称] '芙莉莲第二季' vs 'Frieren...': score={score}")
        assert score == 0, f"跨语言无名称应为 0，实际 {score}"

    def test_frieren_cn_vs_en_with_names(self):
        """搜'芙莉莲' vs 英文标题 — 有 match_names → 应匹配"""
        score = _score_with_names(
            "芙莉莲第二季",
            "Frieren.Beyond.Journeys.End.S02.1080p.WEB-DL",
            match_names=["Frieren Beyond Journeys End"]
        )
        print(f"  [有名称] '芙莉莲第二季' + en='Frieren...' vs 'Frieren...': score={score}")
        assert score >= 60, f"有英文名应 ≥60，实际 {score}"

    def test_frieren_vs_zootopia_with_names(self):
        """搜'芙莉莲' vs Zootopia — 即使有 match_names 也不应匹配"""
        score = _score_with_names(
            "芙莉莲第二季",
            "Zootopia.2016.1080p.BluRay.x264-SPARKS",
            match_names=["Frieren Beyond Journeys End"]
        )
        print(f"  [不相关] '芙莉莲第二季' + en='Frieren...' vs 'Zootopia': score={score}")
        assert score == 0, f"不相关应为 0，实际 {score}"

    def test_wandering_earth_cn_vs_en_with_names(self):
        """搜'流浪地球' vs 英文标题 — 有 match_names"""
        score = _score_with_names(
            "流浪地球",
            "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX",
            match_names=["The Wandering Earth"]
        )
        print(f"  [有名称] '流浪地球' + en='The Wandering Earth' vs 英文标题: score={score}")
        assert score >= 60, f"有英文名应 ≥60，实际 {score}"

    def test_aot_cn_vs_en_with_names(self):
        """搜'进击的巨人' vs 英文标题 — 有 match_names"""
        score = _score_with_names(
            "进击的巨人",
            "Attack.on.Titan.The.Final.Season.Part.4.2024.1080p.WEB-DL.x264",
            match_names=["Attack on Titan"]
        )
        print(f"  [有名称] '进击的巨人' + en='Attack on Titan' vs 英文标题: score={score}")
        assert score >= 60, f"有英文名应 ≥60，实际 {score}"


# ════════════════════════════════════════
# 第三组：端到端场景 — 搜"芙莉莲第二季"
# ════════════════════════════════════════

class TestFrierenScenario:
    """模拟真实场景：搜'芙莉莲第二季'，Prowlarr 返回大量不相关结果"""

    def test_scenario(self):
        """端到端：有 match_names 时，不相关结果应被标记为 unmatched"""
        query = "芙莉莲第二季"
        match_names = ["Frieren Beyond Journeys End", "葬送のフリーレン"]

        results = [
            # 相关：英文标题
            ("Frieren.Beyond.Journeys.End.S02E01.1080p.WEB-DL.x264", 100, 1.5),
            # 相关：中文标题
            ("[字幕组] 葬送的芙莉莲 第二季 第01集 [1080p]", 30, 0.5),
            # 不相关：Zootopia
            ("Zootopia.2016.1080p.BluRay.x264-SPARKS", 200, 8.0),
            # 不相关：随机电影
            ("The.Matrix.Resurrections.2021.2160p.WEB-DL", 80, 15.0),
            # 不相关：另一部动画
            ("[SubsPlease] One Piece - 1100 (1080p) [hash].mkv", 50, 1.2),
            # 磁力源 — 相关
            ("芙莉莲 第二季 | Frieren.S02.2025.4K.WEB-DL", 0, 0),
            # 磁力源 — 不相关
            ("疯狂动物城.Zootopia.2016.4K.HDR", 0, 0),
        ]

        print(f"\n  === 搜索场景: '{query}' (match_names={match_names}) ===")
        for title, seeders, size_gb in results:
            score = _score_with_names(query, title, match_names)
            has_multilang = len(set([query] + match_names)) >= 3
            d = {"title": title, "match_score": score, "seeders": seeders,
                 "size_gb": size_gb, "_has_multilang_candidates": has_multilang}
            flags = compute_junk_flags(d)
            status = "🚫 JUNK" if flags["is_junk"] else "✅ OK"
            reasons = ", ".join(flags["junk_reasons"]) if flags["junk_reasons"] else "无"
            print(f"  {status} score={score:3d} | {title[:60]:<60} | reasons: {reasons}")

        # 验证关键断言
        # Zootopia 应被标记
        zootopia_score = _score_with_names(query, "Zootopia.2016.1080p.BluRay.x264-SPARKS", match_names)
        assert zootopia_score == 0
        d_zoo = {"title": "Zootopia.2016.1080p.BluRay.x264-SPARKS", "match_score": 0,
                 "seeders": 200, "size_gb": 8.0, "_has_multilang_candidates": True}
        assert compute_junk_flags(d_zoo)["is_junk"] is True

        # Frieren 英文标题应通过
        frieren_score = _score_with_names(query, "Frieren.Beyond.Journeys.End.S02E01.1080p.WEB-DL.x264", match_names)
        assert frieren_score >= 60

        # 芙莉莲中文标题应通过
        cn_score = _score_with_names(query, "[字幕组] 葬送的芙莉莲 第二季 第01集 [1080p]", match_names)
        assert cn_score >= 60


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
