"""智能过滤（Smart Filter）业务技能测试

覆盖维度：
1. 各源特征差异（Prowlarr/Bitsearch/磁力熊/XL720/Nyaa）
2. 三条规则（枪版/低匹配/死种）的正确触发和不误伤
3. 边界情况和极端用例
4. match_chain 在真实 BT 标题上的评分验证

对应技能文档：.kiro/skills/smart-filter.md
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from search_helpers import compute_junk_flags as _compute_junk_flags, _MATCH_SCORE_THRESHOLD


# ════════════════════════════════════════
# 第一组：规则 1 — 枪版检测
# ════════════════════════════════════════

class TestJunkQuality:
    """枪版/低质量源检测"""

    @pytest.mark.parametrize("title", [
        "Inception.2010.CAM.x264-GROUP",
        "Movie.2024.TS.720p.x264",
        "Film.HDTC.1080p.2024",
        "Movie.TC.2024.x264",
        "Film.TELECINE.720p",
        "Movie.HDTS.2024",
        "Film.TELESYNC.720p",
        "Movie.2024.HDCAM.x264",
    ])
    def test_cam_variants_marked(self, title):
        """各种枪版关键词都应被识别"""
        d = {"title": title, "match_score": 90, "seeders": 50, "size_gb": 2.0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is True
        assert any("low_quality" in r for r in result["junk_reasons"]), f"未标记: {title}"

    @pytest.mark.parametrize("title", [
        "MONSTERS.2024.1080p.BluRay.x264",       # TS 不应匹配 MONSTERS
        "The.Last.of.Us.S02E01.1080p.WEB-DL",    # TS 不应匹配 "Last"
        "Cats.2019.1080p.BluRay",                 # TS 不应匹配 "Cats"
        "Ghosts.S03E05.720p.HDTV",               # TS 不应匹配 "Ghosts"
        "BITS.of.Life.2024.1080p",               # TS 不应匹配 "BITS"
        "Fantastic.Beasts.2022.4K.UHD",          # TC 不应匹配 "Fantastic"
        "Contact.1997.1080p.BluRay",             # TC 不应匹配 "Contact"
    ])
    def test_no_false_positive_cam(self, title):
        """不应误匹配含 TS/TC 子串的正常标题"""
        d = {"title": title, "match_score": 80, "seeders": 50, "size_gb": 5.0}
        result = _compute_junk_flags(d)
        assert not any("low_quality" in r for r in result["junk_reasons"]), f"误标记: {title}"


# ════════════════════════════════════════
# 第二组：规则 2 — 匹配度过低
# ════════════════════════════════════════

class TestLowMatch:
    """匹配度过低检测"""

    def test_low_match_marked(self):
        """match_score < 阈值应被标记"""
        d = {"title": "Completely.Unrelated.Movie.2024", "match_score": 20, "seeders": 100, "size_gb": 5.0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is True
        assert any("low_match" in r for r in result["junk_reasons"])

    def test_match_score_at_threshold_not_marked(self):
        """match_score 恰好等于阈值不应被标记"""
        d = {"title": "Movie.2024.1080p", "match_score": _MATCH_SCORE_THRESHOLD, "seeders": 10, "size_gb": 2.0}
        result = _compute_junk_flags(d)
        assert not any("low_match" in r for r in result["junk_reasons"])

    def test_match_score_zero_not_marked(self):
        """match_score=0（未计算）不应被标记"""
        d = {"title": "Movie.2024.1080p.BluRay", "match_score": 0, "seeders": 50, "size_gb": 8.0}
        result = _compute_junk_flags(d)
        assert not any("low_match" in r for r in result["junk_reasons"])

    def test_match_score_just_below_threshold(self):
        """match_score 刚好低于阈值 1 分应被标记"""
        d = {"title": "Movie.2024", "match_score": _MATCH_SCORE_THRESHOLD - 1, "seeders": 50, "size_gb": 3.0}
        result = _compute_junk_flags(d)
        assert any("low_match" in r for r in result["junk_reasons"])


# ════════════════════════════════════════
# 第三组：规则 3 — 死种检测（按源特征）
# ════════════════════════════════════════

class TestDeadSeed:
    """死种检测 + 磁力链接源豁免"""

    def test_prowlarr_dead_seed(self):
        """Prowlarr 结果 seeders=0 但有大小 → 死种"""
        d = {"title": "Movie.2024.1080p.BluRay", "match_score": 90, "seeders": 0, "size_gb": 8.5}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is True
        assert any("dead_seed" in r for r in result["junk_reasons"])

    def test_bitsearch_dead_seed(self):
        """Bitsearch 结果 seeders=0 但有大小 → 死种"""
        d = {"title": "Movie.2024.720p.WEB-DL", "match_score": 80, "seeders": 0, "size_gb": 3.2}
        result = _compute_junk_flags(d)
        assert any("dead_seed" in r for r in result["junk_reasons"])

    def test_cilixiong_magnet_exempt(self):
        """磁力熊结果（seeders=0, size=0）不应被标记为死种"""
        d = {"title": "流浪地球2.2023.4K.HDR", "match_score": 90, "seeders": 0, "size_gb": 0}
        result = _compute_junk_flags(d)
        assert not any("dead_seed" in r for r in result["junk_reasons"])
        assert result["is_junk"] is False

    def test_xl720_magnet_exempt(self):
        """XL720 结果（seeders=0, size=0）不应被标记为死种"""
        d = {"title": "西部世界.Westworld.S04.1080p", "match_score": 80, "seeders": 0, "size_gb": 0}
        result = _compute_junk_flags(d)
        assert not any("dead_seed" in r for r in result["junk_reasons"])
        assert result["is_junk"] is False

    def test_nyaa_dead_seed(self):
        """Nyaa 结果 seeders=0 但有大小 → 死种"""
        d = {"title": "[SubGroup] Anime Title - 01 [1080p]", "match_score": 60, "seeders": 0, "size_gb": 1.2}
        result = _compute_junk_flags(d)
        assert any("dead_seed" in r for r in result["junk_reasons"])

    def test_healthy_seed_not_marked(self):
        """有做种的结果不应被标记"""
        d = {"title": "Movie.2024.1080p", "match_score": 80, "seeders": 1, "size_gb": 5.0}
        result = _compute_junk_flags(d)
        assert not any("dead_seed" in r for r in result["junk_reasons"])


# ════════════════════════════════════════
# 第四组：多规则组合 + 极端情况
# ════════════════════════════════════════

class TestCombined:
    """多规则组合和极端情况"""

    def test_cam_plus_dead_seed_plus_low_match(self):
        """三个规则同时命中"""
        d = {"title": "Random.CAM.2024", "match_score": 10, "seeders": 0, "size_gb": 1.0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is True
        assert len(result["junk_reasons"]) == 3

    def test_perfect_result_not_junk(self):
        """完美结果：高匹配+高质量+有种"""
        d = {"title": "Inception.2010.2160p.UHD.BluRay.x265.DTS-HD", "match_score": 90, "seeders": 200, "size_gb": 45.0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is False
        assert result["junk_reasons"] == []

    def test_empty_title(self):
        """空标题不应崩溃"""
        d = {"title": "", "match_score": 0, "seeders": 0, "size_gb": 0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is False

    def test_missing_fields(self):
        """缺失字段不应崩溃"""
        d = {}
        result = _compute_junk_flags(d)
        assert "is_junk" in result
        assert "junk_reasons" in result


# ════════════════════════════════════════
# 第五组：真实 BT 标题 + match_chain 集成测试
# ════════════════════════════════════════

class TestMatchChainIntegration:
    """用真实 BT 标题验证 match_chain 评分 + 智能过滤的综合效果"""

    def _score(self, search_query: str, bt_title: str) -> int:
        """模拟 _enrich_result 中的 match_score 计算"""
        from match_scoring import match_chain
        from text_processing import split_by_language
        from search_helpers import extract_bt_title_for_match as _extract_bt_title_for_match

        parts = split_by_language(search_query)
        candidates = [n for n in [search_query, parts["cn"], parts["en"]] if n]
        bt_clean = _extract_bt_title_for_match(bt_title)
        bt_parts = split_by_language(bt_clean)
        targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
        return match_chain(candidates, targets, [])

    # ── 搜索"流浪地球" ──

    def test_liulang_exact_match(self):
        """搜索'流浪地球' → 精确匹配的 BT 标题应高分"""
        score = self._score("流浪地球", "流浪地球2.The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1")
        assert score >= 60, f"精确匹配应 ≥60，实际 {score}"

    def test_liulang_unrelated(self):
        """搜索'流浪地球' → 完全不相关的标题应低分"""
        score = self._score("流浪地球", "The.Matrix.1999.1080p.BluRay.x264-GROUP")
        assert score < _MATCH_SCORE_THRESHOLD, f"不相关应 <{_MATCH_SCORE_THRESHOLD}，实际 {score}"

    def test_liulang_partial_cn(self):
        """搜索'流浪地球' → 含'流浪'但不相关的标题"""
        score = self._score("流浪地球", "流浪猫鲍勃.A.Street.Cat.Named.Bob.2016.1080p")
        # 这是一个已知的边界情况：contains 匹配可能给出中等分数
        # 记录实际分数，后续优化时参考
        print(f"  [边界] '流浪地球' vs '流浪猫鲍勃': score={score}")

    # ── 搜索"Inception" ──

    def test_inception_exact(self):
        """搜索'Inception' → 精确匹配"""
        score = self._score("Inception", "Inception.2010.2160p.UHD.BluRay.x265.DTS-HD.MA.5.1-SWTYBLZ")
        assert score >= 60, f"精确匹配应 ≥60，实际 {score}"

    def test_inception_unrelated(self):
        """搜索'Inception' → 不相关"""
        score = self._score("Inception", "Interstellar.2014.1080p.BluRay.x264-SPARKS")
        assert score < _MATCH_SCORE_THRESHOLD, f"不相关应 <{_MATCH_SCORE_THRESHOLD}，实际 {score}"

    # ── 搜索"进击的巨人" ──

    def test_aot_cn_to_en(self):
        """搜索'进击的巨人' → 英文标题 Attack on Titan"""
        score = self._score("进击的巨人", "[SubGroup] Attack on Titan - The Final Season - 01 [1080p]")
        # 中文搜索词 vs 英文 BT 标题，match_chain 可能无法匹配
        # 这是已知限制：需要别名系统支持
        print(f"  [跨语言] '进击的巨人' vs 'Attack on Titan': score={score}")

    def test_aot_cn_exact(self):
        """搜索'进击的巨人' → 中文标题精确匹配"""
        score = self._score("进击的巨人", "[字幕组] 进击的巨人 最终季 第01集 [1080p]")
        assert score >= 60, f"中文精确匹配应 ≥60，实际 {score}"

    # ── 搜索"西部世界 Westworld" ──

    def test_westworld_bilingual(self):
        """搜索'西部世界 Westworld' → 英文标题"""
        score = self._score("西部世界 Westworld", "Westworld.S04E01.1080p.WEB.H264-CAKES")
        assert score >= 40, f"英文部分匹配应 ≥40，实际 {score}"

    def test_westworld_cn(self):
        """搜索'西部世界 Westworld' → 中文标题"""
        score = self._score("西部世界 Westworld", "西部世界.第四季.Westworld.S04.2160p.WEB-DL")
        assert score >= 60, f"中英文都匹配应 ≥60，实际 {score}"

    # ── 搜索短名字 ──

    def test_short_name_her(self):
        """搜索'她 Her' → 短名字保护"""
        score = self._score("她 Her", "Her.2013.1080p.BluRay.x264-SPARKS")
        # "Her" 是短名字（≤5字符），match_chain 应该用精确匹配
        print(f"  [短名字] '她 Her' vs 'Her.2013': score={score}")

    def test_short_name_no_false_match(self):
        """搜索'她 Her' → 不应匹配含 'her' 子串的不相关标题"""
        score = self._score("她 Her", "The.Other.Boleyn.Girl.2008.1080p")
        # "Other" 含 "her" 子串但不应匹配
        assert score < 60, f"不应高分匹配，实际 {score}"

    # ── Bitsearch 中文模糊匹配问题 ──

    def test_bitsearch_cn_noise(self):
        """模拟 Bitsearch 返回的中文噪声结果"""
        # 搜索"三体"，Bitsearch 可能返回"三体 三国 三生三世"等
        score = self._score("三体", "三国演义.1994.全84集.1080p.修复版")
        print(f"  [中文噪声] '三体' vs '三国演义': score={score}")
        # "三体" 是短名字（2字符），应该只允许精确匹配

    def test_bitsearch_cn_exact(self):
        """搜索'三体' → 精确匹配"""
        score = self._score("三体", "三体.Three-Body.2023.S01.4K.WEB-DL.H265")
        assert score >= 60, f"精确匹配应 ≥60，实际 {score}"

    # ── 综合：_compute_junk_flags 端到端 ──

    def test_end_to_end_filter_unrelated(self):
        """端到端：match_score=0 表示跨语言无法计算，不应被标记（规则设计）"""
        score = self._score("流浪地球", "The.Matrix.1999.1080p.BluRay.x264")
        d = {"title": "The.Matrix.1999.1080p.BluRay.x264", "match_score": score, "seeders": 50, "size_gb": 8.0}
        result = _compute_junk_flags(d)
        # match_score=0 不触发低匹配标记（可能是跨语言无法计算）
        assert not any("low_match" in r for r in result["junk_reasons"])
        # 但如果 match_score 被计算出来且很低（如 10），则应被标记
        d2 = {"title": "The.Matrix.1999.1080p.BluRay.x264", "match_score": 10, "seeders": 50, "size_gb": 8.0}
        result2 = _compute_junk_flags(d2)
        assert result2["is_junk"] is True

    def test_end_to_end_filter_relevant(self):
        """端到端：相关结果不应被标记"""
        score = self._score("流浪地球", "流浪地球2.2023.2160p.WEB-DL.H265")
        d = {"title": "流浪地球2.2023.2160p.WEB-DL.H265", "match_score": score, "seeders": 100, "size_gb": 15.0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is False, f"相关结果不应被标记，match_score={score}"

    def test_end_to_end_magnet_source_relevant(self):
        """端到端：磁力源的相关结果不应被标记"""
        score = self._score("流浪地球", "流浪地球2.The.Wandering.Earth.II.2023.4K.HDR")
        d = {"title": "流浪地球2.The.Wandering.Earth.II.2023.4K.HDR", "match_score": score, "seeders": 0, "size_gb": 0}
        result = _compute_junk_flags(d)
        assert result["is_junk"] is False, f"磁力源相关结果不应被标记，match_score={score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
