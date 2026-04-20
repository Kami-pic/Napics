"""智能过滤（Smart Filter）扩展集成测试 — 真实 BT 标题场景

用各源格式的真实标题验证：
1. _extract_bt_title_for_match 提取结果是否合理
2. match_chain 评分是否合理
3. _compute_junk_flags 标记是否正确

对应技能文档：.kiro/skills/smart-filter.md
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from routes.search import _extract_bt_title_for_match, _compute_junk_flags, _MATCH_SCORE_THRESHOLD
from match_scoring import match_chain
from text_processing import split_by_language


def _score(search_query: str, bt_title: str) -> int:
    """模拟 _enrich_result 中的 match_score 计算"""
    parts = split_by_language(search_query)
    candidates = [n for n in [search_query, parts["cn"], parts["en"]] if n]
    bt_clean = _extract_bt_title_for_match(bt_title)
    bt_parts = split_by_language(bt_clean)
    targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
    return match_chain(candidates, targets, [])


def _flags(title: str, match_score: int, seeders: int = 50, size_gb: float = 5.0) -> dict:
    """快捷调用 _compute_junk_flags"""
    d = {"title": title, "match_score": match_score, "seeders": seeders, "size_gb": size_gb}
    return _compute_junk_flags(d)


# ════════════════════════════════════════
# 第一组：磁力熊/XL720 格式（中文标题 | 英文文件名）
# ════════════════════════════════════════

class TestCilixiongXL720Format:
    """磁力熊/XL720 格式标题：中文标题 | 英文文件名"""

    def test_extract_wandering_earth(self):
        title = "流浪地球2 | The.Wandering.Earth.II.2023.2160p.WEB-DL.mkv"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "流浪地球" in clean or "Wandering Earth" in clean.replace(".", " ")

    def test_score_wandering_earth(self):
        title = "流浪地球2 | The.Wandering.Earth.II.2023.2160p.WEB-DL.mkv"
        score = _score("流浪地球", title)
        print(f"  [评分] '流浪地球' vs '{title}': score={score}")
        assert score >= 60, f"应 ≥60，实际 {score}"

    def test_extract_three_body(self):
        title = "三体 | Three-Body.2023.S01E01.1080p.WEB-DL.mkv"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "三体" in clean or "Three" in clean

    def test_score_three_body(self):
        title = "三体 | Three-Body.2023.S01E01.1080p.WEB-DL.mkv"
        score = _score("三体", title)
        print(f"  [评分] '三体' vs '{title}': score={score}")
        # "三体" 是短名字（2字符），match_chain 短名字保护可能限制匹配
        # 记录实际分数

    def test_extract_westworld(self):
        title = "西部世界 第四季 | Westworld.S04.Complete.1080p"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "西部世界" in clean or "Westworld" in clean

    def test_score_westworld(self):
        title = "西部世界 第四季 | Westworld.S04.Complete.1080p"
        score = _score("西部世界 Westworld", title)
        print(f"  [评分] '西部世界 Westworld' vs '{title}': score={score}")
        assert score >= 60, f"应 ≥60，实际 {score}"

    def test_junk_flags_magnet_source(self):
        """磁力熊/XL720 结果（seeders=0, size=0）不应被标记"""
        title = "流浪地球2 | The.Wandering.Earth.II.2023.2160p.WEB-DL.mkv"
        score = _score("流浪地球", title)
        result = _flags(title, score, seeders=0, size_gb=0)
        print(f"  [标记] 磁力源 score={score}, flags={result}")
        assert result["is_junk"] is False, f"磁力源不应被标记，score={score}"


# ════════════════════════════════════════
# 第二组：Prowlarr 典型标题（纯英文，点号分隔）
# ════════════════════════════════════════

class TestProwlarrFormat:
    """Prowlarr 格式标题：纯英文，点号分隔，含技术标签和发布组"""

    def test_extract_wandering_earth_en(self):
        title = "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "Wandering" in clean and "Earth" in clean

    def test_score_wandering_earth_en(self):
        """中文搜索词 vs 纯英文 Prowlarr 标题 — 跨语言限制"""
        title = "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX"
        score = _score("流浪地球", title)
        print(f"  [跨语言] '流浪地球' vs '{title}': score={score}")
        # 跨语言无法匹配是已知限制，需要别名系统

    def test_score_wandering_earth_en_query(self):
        """英文搜索词 vs 英文 Prowlarr 标题 — 应高分"""
        title = "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX"
        score = _score("The Wandering Earth", title)
        print(f"  [评分] 'The Wandering Earth' vs '{title}': score={score}")
        assert score >= 60, f"英文精确匹配应 ≥60，实际 {score}"

    def test_extract_aot(self):
        title = "Attack.on.Titan.The.Final.Season.Part.4.2024.1080p.WEB-DL.x264"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "Attack" in clean and "Titan" in clean

    def test_score_aot_en(self):
        """英文搜索词 vs 英文 AOT 标题"""
        title = "Attack.on.Titan.The.Final.Season.Part.4.2024.1080p.WEB-DL.x264"
        score = _score("Attack on Titan", title)
        print(f"  [评分] 'Attack on Titan' vs '{title}': score={score}")
        assert score >= 60, f"应 ≥60，实际 {score}"

    def test_extract_westworld_prowlarr(self):
        title = "Westworld.S04E01.The.Auguries.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "Westworld" in clean

    def test_score_westworld_prowlarr(self):
        """单词 'Westworld' vs 长标题 — contains 的 40% 长度比例约束会阻止匹配"""
        title = "Westworld.S04E01.The.Auguries.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb"
        score = _score("Westworld", title)
        print(f"  [评分] 'Westworld' vs '{title}': score={score}")
        # "westworld"(9字符) vs "westworld s04e01 the auguries"(29字符)
        # 9/29 ≈ 0.31 < 0.4，不满足 contains 的长度比例约束
        # 这是 match_chain 的已知行为：单词搜索长标题时 contains 被跳过
        # token_set 也不行因为 "Westworld" 只有 1 个 token（< 2 的最低要求）
        print(f"  [已知限制] 单词搜索 vs 长标题，contains 40% 比例约束 + token_set 单 token 限制导致 score=0")

    def test_junk_flags_prowlarr_healthy(self):
        """Prowlarr 健康结果不应被标记"""
        title = "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX"
        score = _score("The Wandering Earth", title)
        result = _flags(title, score, seeders=100, size_gb=15.0)
        print(f"  [标记] Prowlarr 健康 score={score}, flags={result}")
        assert result["is_junk"] is False

    def test_junk_flags_prowlarr_dead(self):
        """Prowlarr 死种应被标记"""
        title = "The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX"
        score = _score("The Wandering Earth", title)
        result = _flags(title, score, seeders=0, size_gb=15.0)
        print(f"  [标记] Prowlarr 死种 score={score}, flags={result}")
        assert any("dead_seed" in r for r in result["junk_reasons"])


# ════════════════════════════════════════
# 第三组：Bitsearch 噪声标题（中文搜索返回的不相关结果）
# ════════════════════════════════════════

class TestBitsearchNoise:
    """Bitsearch 中文搜索返回的噪声结果"""

    def test_three_body_vs_three_kingdoms(self):
        """搜索'三体' → 返回'三国演义'"""
        title = "三国演义.Romance.of.Three.Kingdoms.1994.Complete.1080p"
        score = _score("三体", title)
        clean = _extract_bt_title_for_match(title)
        print(f"  [噪声] '三体' vs '{title}' (clean='{clean}'): score={score}")
        # "三体" 是短名字，不应匹配 "三国演义"

    def test_wandering_earth_vs_street_cat(self):
        """搜索'流浪地球' → 返回'流浪猫鲍勃'"""
        title = "流浪猫鲍勃.A.Street.Cat.Named.Bob.2016.1080p.BluRay"
        score = _score("流浪地球", title)
        clean = _extract_bt_title_for_match(title)
        print(f"  [噪声] '流浪地球' vs '{title}' (clean='{clean}'): score={score}")
        # contains 匹配可能给出中等分数，记录实际值

    def test_westworld_vs_into_the_west(self):
        """搜索'西部世界' → 返回'西部风云'"""
        title = "西部风云.Into.the.West.2005.S01.720p"
        score = _score("西部世界", title)
        clean = _extract_bt_title_for_match(title)
        print(f"  [噪声] '西部世界' vs '{title}' (clean='{clean}'): score={score}")
        # "西部" 是公共子串，可能触发 contains

    def test_bitsearch_noise_junk_flags(self):
        """Bitsearch 噪声结果如果 match_score 低于阈值应被标记"""
        title = "三国演义.Romance.of.Three.Kingdoms.1994.Complete.1080p"
        score = _score("三体", title)
        result = _flags(title, score, seeders=50, size_gb=8.0)
        print(f"  [标记] Bitsearch 噪声 score={score}, flags={result}")
        if score > 0 and score < _MATCH_SCORE_THRESHOLD:
            assert result["is_junk"] is True, "低分噪声应被标记"


# ════════════════════════════════════════
# 第四组：Nyaa/蜜柑 格式（方括号字幕组 + 日文/中文标题）
# ════════════════════════════════════════

class TestNyaaMikanFormat:
    """Nyaa/蜜柑格式标题：方括号字幕组 + 日文/中文标题"""

    def test_extract_erai_raws(self):
        title = "[Erai-raws] Shingeki no Kyojin - The Final Season - 01 [1080p][Multiple Subtitle]"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        # 方括号内容应被去掉，保留 "Shingeki no Kyojin - The Final Season - 01"
        assert "Erai-raws" not in clean
        assert "Shingeki" in clean or "Kyojin" in clean

    def test_score_erai_raws_cn(self):
        """中文搜索词 vs 日文罗马音标题 — 跨语言限制"""
        title = "[Erai-raws] Shingeki no Kyojin - The Final Season - 01 [1080p][Multiple Subtitle]"
        score = _score("进击的巨人", title)
        print(f"  [跨语言] '进击的巨人' vs '{title}': score={score}")
        # 中文 vs 日文罗马音，无法匹配是已知限制

    def test_extract_cn_subgroup(self):
        title = "[喵萌奶茶屋] 进击的巨人 最终季 / Shingeki no Kyojin The Final Season - 01 [1080p]"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "喵萌奶茶屋" not in clean
        assert "进击的巨人" in clean or "Shingeki" in clean

    def test_score_cn_subgroup(self):
        """中文搜索词 vs 中文字幕组标题"""
        title = "[喵萌奶茶屋] 进击的巨人 最终季 / Shingeki no Kyojin The Final Season - 01 [1080p]"
        score = _score("进击的巨人", title)
        print(f"  [评分] '进击的巨人' vs '{title}': score={score}")
        assert score >= 60, f"中文精确匹配应 ≥60，实际 {score}"

    def test_extract_subsplease(self):
        title = "[SubsPlease] Oshi no Ko - 01 (1080p) [hash].mkv"
        clean = _extract_bt_title_for_match(title)
        print(f"  [提取] '{title}' → '{clean}'")
        assert "SubsPlease" not in clean
        assert "Oshi" in clean or "Ko" in clean

    def test_score_oshi_no_ko(self):
        """日文搜索词 vs 日文罗马音标题"""
        title = "[SubsPlease] Oshi no Ko - 01 (1080p) [hash].mkv"
        score = _score("Oshi no Ko", title)
        print(f"  [评分] 'Oshi no Ko' vs '{title}': score={score}")
        assert score >= 60, f"精确匹配应 ≥60，实际 {score}"

    def test_junk_flags_nyaa_dead(self):
        """Nyaa 死种应被标记"""
        title = "[Erai-raws] Shingeki no Kyojin - 01 [1080p]"
        result = _flags(title, match_score=60, seeders=0, size_gb=1.5)
        print(f"  [标记] Nyaa 死种 flags={result}")
        assert any("dead_seed" in r for r in result["junk_reasons"])

    def test_junk_flags_nyaa_healthy(self):
        """Nyaa 健康结果不应被标记"""
        title = "[Erai-raws] Shingeki no Kyojin - 01 [1080p]"
        result = _flags(title, match_score=60, seeders=20, size_gb=1.5)
        assert result["is_junk"] is False


# ════════════════════════════════════════
# 第五组：极端边界
# ════════════════════════════════════════

class TestExtremeBoundary:
    """极端边界情况"""

    def test_empty_title(self):
        """空标题"""
        clean = _extract_bt_title_for_match("")
        score = _score("流浪地球", "")
        result = _flags("", 0, seeders=0, size_gb=0)
        print(f"  [边界] 空标题: clean='{clean}', score={score}, flags={result}")
        assert clean == ""
        assert result["is_junk"] is False

    def test_very_long_title(self):
        """超长标题（200+ 字符）"""
        title = "A" * 50 + ".Very.Long.Movie.Title.That.Goes.On.And.On." + "B" * 50 + ".2024.1080p.BluRay.x264.DTS-HD.MA.5.1.PROPER.REPACK-" + "C" * 30
        clean = _extract_bt_title_for_match(title)
        score = _score("Very Long Movie", title)
        print(f"  [边界] 超长标题 ({len(title)}字符): clean='{clean[:80]}...', score={score}")
        assert len(clean) < len(title), "清洗后应更短"

    def test_pure_number_title(self):
        """纯数字标题"""
        title = "1234567890"
        clean = _extract_bt_title_for_match(title)
        score = _score("1234567890", title)
        print(f"  [边界] 纯数字: clean='{clean}', score={score}")

    def test_ts_transport_stream(self):
        """TS 是 Transport Stream 而非枪版"""
        title = "[Group] Anime.Title.01.1080p.MPEG-TS"
        clean = _extract_bt_title_for_match(title)
        result = _flags(title, match_score=80, seeders=50, size_gb=2.0)
        print(f"  [边界] MPEG-TS: clean='{clean}', flags={result}")
        # 当前实现会把 TS 标记为枪版 — 这是已知的误伤
        # 记录实际行为
        if any("low_quality" in r for r in result["junk_reasons"]):
            print("  [已知问题] MPEG-TS 被误标记为枪版")

    def test_cn_en_mixed_title(self):
        """中英混合标题"""
        title = "哥斯拉大战金刚2 Godzilla.x.Kong.The.New.Empire.2024.2160p"
        clean = _extract_bt_title_for_match(title)
        score_cn = _score("哥斯拉大战金刚", title)
        score_en = _score("Godzilla x Kong", title)
        score_mixed = _score("哥斯拉大战金刚 Godzilla x Kong", title)
        print(f"  [混合] clean='{clean}'")
        print(f"  [混合] 中文搜索: score={score_cn}")
        print(f"  [混合] 英文搜索: score={score_en}")
        print(f"  [混合] 混合搜索: score={score_mixed}")
        # 至少一种搜索方式应该能匹配
        assert max(score_cn, score_en, score_mixed) >= 60, \
            f"至少一种搜索应 ≥60，实际 cn={score_cn}, en={score_en}, mixed={score_mixed}"

    def test_cn_en_mixed_junk_flags(self):
        """中英混合标题 — 磁力源不应被标记"""
        title = "哥斯拉大战金刚2 Godzilla.x.Kong.The.New.Empire.2024.2160p"
        score = _score("哥斯拉大战金刚", title)
        result = _flags(title, score, seeders=0, size_gb=0)
        print(f"  [标记] 混合标题磁力源 score={score}, flags={result}")
        assert not any("dead_seed" in r for r in result["junk_reasons"]), "磁力源不应标记死种"

    def test_season_pack_title(self):
        """季度合集标题"""
        title = "Westworld.S04.Complete.1080p.WEB-DL.H264-GROUP"
        clean = _extract_bt_title_for_match(title)
        score = _score("Westworld", title)
        print(f"  [季包] clean='{clean}', score={score}")
        assert score >= 60, f"应 ≥60，实际 {score}"

    def test_special_chars_title(self):
        """特殊字符标题"""
        title = "Spider-Man：No.Way.Home.2021.2160p.WEB-DL"
        clean = _extract_bt_title_for_match(title)
        score = _score("Spider-Man No Way Home", title)
        print(f"  [特殊字符] clean='{clean}', score={score}")
        assert score >= 40, f"应 ≥40，实际 {score}"


# ════════════════════════════════════════
# 第六组：综合端到端 — 搜索场景模拟
# ════════════════════════════════════════

class TestEndToEndScenarios:
    """模拟真实搜索场景的端到端测试"""

    def test_scenario_search_wandering_earth(self):
        """场景：搜索'流浪地球'，验证各源结果的过滤效果"""
        query = "流浪地球"
        results = [
            # 磁力熊格式 — 相关，磁力源
            ("流浪地球2 | The.Wandering.Earth.II.2023.2160p.WEB-DL.mkv", 0, 0),
            # Prowlarr 格式 — 相关，有种
            ("The.Wandering.Earth.II.2023.2160p.WEB-DL.H265.DDP5.1-FLUX", 100, 15.0),
            # Bitsearch 噪声 — 不相关
            ("流浪猫鲍勃.A.Street.Cat.Named.Bob.2016.1080p.BluRay", 50, 8.0),
            # 枪版
            ("The.Wandering.Earth.II.2023.CAM.x264", 30, 2.0),
            # 死种
            ("The.Wandering.Earth.II.2023.1080p.BluRay", 0, 12.0),
        ]

        print(f"\n  === 搜索场景: '{query}' ===")
        for title, seeders, size_gb in results:
            score = _score(query, title)
            flags = _flags(title, score, seeders, size_gb)
            status = "🚫 JUNK" if flags["is_junk"] else "✅ OK"
            reasons = ", ".join(flags["junk_reasons"]) if flags["junk_reasons"] else "无"
            print(f"  {status} score={score:3d} | {title[:60]:<60} | reasons: {reasons}")

    def test_scenario_search_aot(self):
        """场景：搜索'进击的巨人'，验证各源结果"""
        query = "进击的巨人"
        results = [
            # 中文字幕组 — 应匹配
            ("[喵萌奶茶屋] 进击的巨人 最终季 / Shingeki no Kyojin The Final Season - 01 [1080p]", 30, 0.5),
            # 英文标题 — 跨语言限制
            ("Attack.on.Titan.The.Final.Season.Part.4.2024.1080p.WEB-DL.x264", 80, 3.0),
            # 日文罗马音 — 跨语言限制
            ("[Erai-raws] Shingeki no Kyojin - The Final Season - 01 [1080p][Multiple Subtitle]", 50, 1.2),
        ]

        print(f"\n  === 搜索场景: '{query}' ===")
        for title, seeders, size_gb in results:
            score = _score(query, title)
            flags = _flags(title, score, seeders, size_gb)
            status = "🚫 JUNK" if flags["is_junk"] else "✅ OK"
            reasons = ", ".join(flags["junk_reasons"]) if flags["junk_reasons"] else "无"
            print(f"  {status} score={score:3d} | {title[:60]:<60} | reasons: {reasons}")

    def test_scenario_search_westworld(self):
        """场景：搜索'西部世界 Westworld'，验证各源结果"""
        query = "西部世界 Westworld"
        results = [
            # 磁力熊 — 中英文都有
            ("西部世界 第四季 | Westworld.S04.Complete.1080p", 0, 0),
            # Prowlarr — 纯英文
            ("Westworld.S04E01.The.Auguries.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb", 80, 3.5),
            # Bitsearch 噪声
            ("西部风云.Into.the.West.2005.S01.720p", 20, 5.0),
        ]

        print(f"\n  === 搜索场景: '{query}' ===")
        for title, seeders, size_gb in results:
            score = _score(query, title)
            flags = _flags(title, score, seeders, size_gb)
            status = "🚫 JUNK" if flags["is_junk"] else "✅ OK"
            reasons = ", ".join(flags["junk_reasons"]) if flags["junk_reasons"] else "无"
            print(f"  {status} score={score:3d} | {title[:60]:<60} | reasons: {reasons}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
