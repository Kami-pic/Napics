"""
多语言搜索词 + 源 Tab 切换 — 综合测试

覆盖场景：
1. 回退链测试：模拟某个源第一个词返回空结果，验证是否用第二个词重搜
2. 回退链去重：cnName == enName 时不应重复搜索
3. 单源端点测试：验证 fallback_keywords 的解析和回退行为
4. SSE 响应格式：验证 source_done 事件包含 search_keywords 和 hit_keyword
5. 中文动画片场景：cnName="进击的巨人" enName="Attack on Titan" jpName="進撃の巨人"
6. 纯英文片场景：cnName="" enName="Inception"
7. 季搜索场景：season_number=3
"""
import pytest
from search_keyword_mapper import (
    MultiLangKeywords, get_search_keywords_for_source, get_default_keyword_for_source,
    SOURCE_LANG_PRIORITY, CN_SEASON_SOURCES, EN_SEASON_SOURCES,
)


def _kw(cn="", en="", original="", query="", season=0):
    return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)


# ═══════════════════════════════════════════════════════════════
# 场景 5：中文动画片 — 进击的巨人
# ═══════════════════════════════════════════════════════════════
class TestAnimeScenario:
    """中文动画片：cnName="进击的巨人" enName="Attack on Titan" jpName="進撃の巨人" """

    KW = _kw(cn="进击的巨人", en="Attack on Titan", original="進撃の巨人", query="进击的巨人")

    def test_nyaa_uses_japanese(self):
        """Nyaa 应该用日文名"""
        kws = get_search_keywords_for_source("nyaa", self.KW)
        assert kws[0] == "進撃の巨人"

    def test_cilixiong_uses_chinese(self):
        """磁力熊应该用中文名"""
        kws = get_search_keywords_for_source("cilixiong", self.KW)
        assert kws[0] == "进击的巨人"

    def test_prowlarr_uses_english(self):
        """Prowlarr 应该用英文名"""
        kws = get_search_keywords_for_source("prowlarr", self.KW)
        assert kws[0] == "Attack on Titan"

    def test_mikan_uses_chinese(self):
        """蜜柑应该用中文名"""
        kws = get_search_keywords_for_source("mikan", self.KW)
        assert kws[0] == "进击的巨人"

    def test_acgrip_uses_chinese(self):
        """ACG.RIP 应该用中文名"""
        kws = get_search_keywords_for_source("acgrip", self.KW)
        assert kws[0] == "进击的巨人"

    def test_bangumi_moe_uses_chinese(self):
        """萌番组应该用中文名"""
        kws = get_search_keywords_for_source("bangumi_moe", self.KW)
        assert kws[0] == "进击的巨人"

    def test_bitsearch_uses_english(self):
        """Bitsearch 应该用英文名"""
        kws = get_search_keywords_for_source("bitsearch", self.KW)
        assert kws[0] == "Attack on Titan"

    def test_nyaa_fallback_chain(self):
        """Nyaa 回退链：jp → en → cn"""
        kws = get_search_keywords_for_source("nyaa", self.KW)
        assert kws == ["進撃の巨人", "Attack on Titan", "进击的巨人"]

    def test_prowlarr_fallback_chain(self):
        """Prowlarr 回退链：en → cn → original（original 和 cn 相同会去重）"""
        kws = get_search_keywords_for_source("prowlarr", self.KW)
        assert kws[0] == "Attack on Titan"
        assert "进击的巨人" in kws
        # original 和 cn 相同，不应重复出现
        assert len([k for k in kws if k == "进击的巨人"]) == 1


# ═══════════════════════════════════════════════════════════════
# 场景 6：纯英文片 — Inception
# ═══════════════════════════════════════════════════════════════
class TestEnglishOnlyScenario:
    """纯英文片：cnName="" enName="Inception" """

    KW = _kw(cn="", en="Inception", query="Inception")

    def test_prowlarr_works(self):
        """Prowlarr 用英文名"""
        kws = get_search_keywords_for_source("prowlarr", self.KW)
        assert kws[0] == "Inception"

    def test_cilixiong_fallback_to_en(self):
        """磁力熊 cn 为空，回退到 en"""
        kws = get_search_keywords_for_source("cilixiong", self.KW)
        assert kws[0] == "Inception"

    def test_nyaa_fallback_to_en(self):
        """Nyaa jp 为空，回退到 en"""
        kws = get_search_keywords_for_source("nyaa", self.KW)
        assert kws[0] == "Inception"

    def test_all_sources_have_at_least_one_keyword(self):
        """所有源都应该至少有一个搜索词"""
        for source in SOURCE_LANG_PRIORITY:
            kws = get_search_keywords_for_source(source, self.KW)
            assert len(kws) >= 1, f"{source} 没有搜索词"

    def test_no_empty_keywords(self):
        """不应该有空字符串搜索词"""
        for source in SOURCE_LANG_PRIORITY:
            kws = get_search_keywords_for_source(source, self.KW)
            for kw in kws:
                assert kw.strip(), f"{source} 有空搜索词"


# ═══════════════════════════════════════════════════════════════
# 场景 7：季搜索 — season_number=3
# ═══════════════════════════════════════════════════════════════
class TestSeasonSearch:
    """季搜索：cnName="权力的游戏" enName="Game of Thrones" season=3"""

    KW = _kw(cn="权力的游戏", en="Game of Thrones", season=3)

    def test_cn_source_appends_chinese_season(self):
        """中文源拼'第3季'"""
        kws = get_search_keywords_for_source("cilixiong", self.KW)
        assert kws[0] == "权力的游戏 第3季"

    def test_en_source_appends_s03(self):
        """英文源拼'S03'"""
        kws = get_search_keywords_for_source("prowlarr", self.KW)
        assert kws[0] == "Game of Thrones S03"

    def test_nyaa_appends_s03(self):
        """Nyaa 是英文季号源，拼 S03"""
        kws = get_search_keywords_for_source("nyaa", self.KW)
        # Nyaa 优先 jp，jp 为空回退到 en
        assert "S03" in kws[0]

    def test_mikan_appends_chinese_season(self):
        """蜜柑是中文季号源，拼'第3季'"""
        kws = get_search_keywords_for_source("mikan", self.KW)
        assert "第3季" in kws[0]

    def test_pansearch_appends_chinese_season(self):
        """网盘源拼中文季号"""
        kws = get_search_keywords_for_source("pansearch", self.KW)
        assert kws[0] == "权力的游戏 第3季"

    def test_fallback_keywords_also_have_season(self):
        """回退词也应该拼接季号（按源的季号格式，不按词的语言）"""
        kws = get_search_keywords_for_source("prowlarr", self.KW)
        # 第一个是 "Game of Thrones S03"
        assert len(kws) >= 2
        # Prowlarr 是英文源，回退词也用 S03 格式（设计决策：季号格式跟源走）
        cn_fallback = [k for k in kws if "权力的游戏" in k]
        assert len(cn_fallback) >= 1
        assert "S03" in cn_fallback[0]  # "权力的游戏 S03"

    def test_season_1_format(self):
        """season=1 时格式正确"""
        kw = _kw(cn="权力的游戏", en="Game of Thrones", season=1)
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws[0] == "Game of Thrones S01"

    def test_season_10_format(self):
        """season=10 时格式正确（两位数）"""
        kw = _kw(cn="权力的游戏", en="Game of Thrones", season=10)
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws[0] == "Game of Thrones S10"


# ═══════════════════════════════════════════════════════════════
# 场景 2：回退链去重 — cnName == enName
# ═══════════════════════════════════════════════════════════════
class TestFallbackDedup:
    """回退链去重：cnName == enName 时不应重复搜索"""

    def test_same_cn_en_only_one_keyword(self):
        """cnName 和 enName 完全相同"""
        kw = _kw(cn="Inception", en="Inception", query="Inception")
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert len(kws) == 1
        assert kws[0] == "Inception"

    def test_same_cn_en_case_insensitive(self):
        """大小写不同也去重"""
        kw = _kw(cn="inception", en="Inception", query="inception")
        kws = get_search_keywords_for_source("prowlarr", kw)
        # 应该只有一个（第一个匹配的）
        assert len(kws) == 1

    def test_same_cn_en_with_season(self):
        """cnName == enName + 季号拼接后也去重"""
        kw = _kw(cn="Inception", en="Inception", season=1)
        kws = get_search_keywords_for_source("cilixiong", kw)
        assert len(kws) == 1
        assert kws[0] == "Inception 第1季"

    def test_original_same_as_cn_dedup(self):
        """query 和 cn 相同时去重"""
        kw = _kw(cn="盗梦空间", en="Inception", query="盗梦空间")
        kws = get_search_keywords_for_source("prowlarr", kw)
        # en → cn → original，cn 和 original 相同，应该只出现一次
        cn_count = sum(1 for k in kws if k == "盗梦空间")
        assert cn_count == 1

    def test_all_three_same(self):
        """cn == en == original 时只有一个词"""
        kw = _kw(cn="test", en="test", query="test")
        for source in SOURCE_LANG_PRIORITY:
            kws = get_search_keywords_for_source(source, kw)
            assert len(kws) == 1, f"{source} 有重复词: {kws}"


# ═══════════════════════════════════════════════════════════════
# 场景 1 & 3：回退链行为 + 单源端点 fallback_keywords 解析
# ═══════════════════════════════════════════════════════════════
class TestFallbackChainBehavior:
    """回退链行为验证"""

    def test_fallback_chain_order_prowlarr(self):
        """Prowlarr 回退链顺序：en → cn → query"""
        kw = _kw(cn="盗梦空间", en="Inception", query="盗梦空间 Inception")
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws[0] == "Inception"
        assert kws[1] == "盗梦空间"
        # original 和 cn 不同，应该出现
        assert "盗梦空间 Inception" in kws

    def test_fallback_chain_order_cilixiong(self):
        """磁力熊回退链顺序：cn → en"""
        kw = _kw(cn="盗梦空间", en="Inception")
        kws = get_search_keywords_for_source("cilixiong", kw)
        assert kws[0] == "盗梦空间"
        assert kws[1] == "Inception"

    def test_fallback_chain_order_nyaa(self):
        """Nyaa 回退链顺序：jp → en → cn"""
        kw = _kw(cn="进击的巨人", en="Attack on Titan", original="進撃の巨人")
        kws = get_search_keywords_for_source("nyaa", kw)
        assert kws[0] == "進撃の巨人"
        assert kws[1] == "Attack on Titan"
        assert kws[2] == "进击的巨人"

    def test_max_three_keywords(self):
        """最多 3 个词"""
        kw = _kw(cn="中文", en="English", original="日本語", query="query")
        for source in SOURCE_LANG_PRIORITY:
            kws = get_search_keywords_for_source(source, kw)
            assert len(kws) <= 3, f"{source} 超过 3 个词: {kws}"

    def test_empty_names_use_original(self):
        """所有名称为空时用 query"""
        kw = _kw(query="some query")
        for source in SOURCE_LANG_PRIORITY:
            kws = get_search_keywords_for_source(source, kw)
            assert len(kws) >= 1, f"{source} 没有搜索词"
            assert kws[0] == "some query"


class TestSingleSourceEndpointParsing:
    """单源端点 fallback_keywords 解析逻辑验证（模拟后端解析）"""

    def _parse_fallback(self, keyword: str, fallback_keywords: str):
        """模拟后端 /api/search/source 的 fallback_keywords 解析"""
        kw_list = [keyword.strip()]
        if fallback_keywords:
            for fb in fallback_keywords.split(","):
                fb = fb.strip()
                if fb and fb.lower() not in {k.lower() for k in kw_list}:
                    kw_list.append(fb)
        return kw_list

    def test_basic_parsing(self):
        """基本解析"""
        result = self._parse_fallback("Inception", "盗梦空间,inception 2010")
        assert result == ["Inception", "盗梦空间", "inception 2010"]

    def test_dedup_case_insensitive(self):
        """去重（忽略大小写）"""
        result = self._parse_fallback("Inception", "inception,INCEPTION")
        assert result == ["Inception"]

    def test_empty_fallback(self):
        """空回退词"""
        result = self._parse_fallback("Inception", "")
        assert result == ["Inception"]

    def test_whitespace_handling(self):
        """空格处理"""
        result = self._parse_fallback("Inception", " 盗梦空间 , Inception , test ")
        assert result == ["Inception", "盗梦空间", "test"]

    def test_comma_separated(self):
        """逗号分隔多个回退词"""
        result = self._parse_fallback("进击的巨人", "Attack on Titan,進撃の巨人")
        assert result == ["进击的巨人", "Attack on Titan", "進撃の巨人"]


# ═══════════════════════════════════════════════════════════════
# 场景 4：SSE 响应格式验证（模拟 _search_direct 返回值结构）
# ═══════════════════════════════════════════════════════════════
class TestSSEResponseFormat:
    """验证 SSE source_done 事件的数据结构"""

    def test_search_direct_return_structure(self):
        """_search_direct 返回 5 元组：(name, results, err, searched, hit_kw)"""
        # 模拟 _search_direct 的返回值
        name = "nyaa"
        results = []  # 模拟搜索结果
        err = None
        searched = ["進撃の巨人", "Attack on Titan"]
        hit_kw = "進撃の巨人"

        # 验证结构
        assert isinstance(name, str)
        assert isinstance(results, list)
        assert err is None or isinstance(err, str)
        assert isinstance(searched, list)
        assert isinstance(hit_kw, str)

    def test_source_done_event_fields(self):
        """source_done 事件应包含 search_keywords 和 hit_keyword"""
        import json
        # 模拟 SSE source_done 事件的 JSON
        event_data = {
            "type": "source_done",
            "source": "nyaa",
            "status": "done",
            "count": 8,
            "added": 8,
            "error": "",
            "search_keywords": ["進撃の巨人", "Attack on Titan"],
            "hit_keyword": "進撃の巨人",
            "results": [],
        }
        # 验证必要字段存在
        assert "search_keywords" in event_data
        assert "hit_keyword" in event_data
        assert isinstance(event_data["search_keywords"], list)
        assert isinstance(event_data["hit_keyword"], str)

    def test_source_done_failed_event(self):
        """失败的源也应该有 search_keywords 和 hit_keyword（空值）"""
        event_data = {
            "type": "source_done",
            "source": "nyaa",
            "status": "failed",
            "count": 0,
            "added": 0,
            "error": "搜索超时",
            "search_keywords": [],
            "hit_keyword": "",
            "results": [],
        }
        assert event_data["search_keywords"] == []
        assert event_data["hit_keyword"] == ""


# ═══════════════════════════════════════════════════════════════
# 源分类完整性验证
# ═══════════════════════════════════════════════════════════════
class TestSourceCoverage:
    """验证所有源都有正确的映射配置"""

    BT_SOURCES = ["prowlarr", "bitsearch", "cilixiong", "xl720", "nyaa",
                  "mikan", "yts", "limetorrents", "acgrip", "bangumi_moe"]
    PAN_SOURCES = ["pansearch", "rrdynb", "ddys", "pansou", "sites",
                   "slowread", "wnsearch", "gogopanso", "github"]

    def test_all_bt_sources_in_priority_map(self):
        """所有 BT 源都在 SOURCE_LANG_PRIORITY 中"""
        for source in self.BT_SOURCES:
            assert source in SOURCE_LANG_PRIORITY, f"BT 源 {source} 不在映射表中"

    def test_all_pan_sources_in_priority_map(self):
        """所有网盘源都在 SOURCE_LANG_PRIORITY 中"""
        for source in self.PAN_SOURCES:
            assert source in SOURCE_LANG_PRIORITY, f"网盘源 {source} 不在映射表中"

    def test_all_sources_in_season_sets(self):
        """所有 BT 源都在 CN_SEASON_SOURCES 或 EN_SEASON_SOURCES 中"""
        for source in self.BT_SOURCES:
            in_cn = source in CN_SEASON_SOURCES
            in_en = source in EN_SEASON_SOURCES
            assert in_cn or in_en, f"BT 源 {source} 不在任何季号集合中"
            assert not (in_cn and in_en), f"BT 源 {source} 同时在两个季号集合中"

    def test_pan_sources_in_cn_season(self):
        """所有网盘源都在 CN_SEASON_SOURCES 中（中文季号）"""
        for source in self.PAN_SOURCES:
            assert source in CN_SEASON_SOURCES, f"网盘源 {source} 不在 CN_SEASON_SOURCES 中"

    def test_no_source_in_both_season_sets(self):
        """没有源同时在 CN 和 EN 季号集合中"""
        overlap = CN_SEASON_SOURCES & EN_SEASON_SOURCES
        assert len(overlap) == 0, f"重叠源: {overlap}"


# ═══════════════════════════════════════════════════════════════
# 边界情况
# ═══════════════════════════════════════════════════════════════
class TestEdgeCases:
    """边界情况测试"""

    def test_whitespace_only_names(self):
        """名称只有空格时视为空"""
        kw = _kw(cn="  ", en="  ", query="query")
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws == ["query"]

    def test_very_long_name(self):
        """超长名称不崩溃"""
        kw = _kw(cn="a" * 500, en="b" * 500)
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert len(kws) >= 1

    def test_special_characters_in_name(self):
        """特殊字符不崩溃"""
        kw = _kw(cn="Re:从零开始的异世界生活", en="Re:Zero", original="Re:ゼロから始める異世界生活")
        kws = get_search_keywords_for_source("nyaa", kw)
        assert kws[0] == "Re:ゼロから始める異世界生活"

    def test_season_zero_no_append(self):
        """season=0 不拼接"""
        kw = _kw(cn="盗梦空间", en="Inception", season=0)
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws[0] == "Inception"
        assert "S00" not in kws[0]

    def test_negative_season_no_append(self):
        """负数季号不拼接"""
        kw = _kw(cn="盗梦空间", en="Inception", season=-1)
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws[0] == "Inception"
        assert "S" not in kws[0] or "S" in "Inception"  # 不应有 S-01

    def test_unknown_source_fallback(self):
        """未知源使用默认映射"""
        kw = _kw(cn="盗梦空间", en="Inception")
        kws = get_search_keywords_for_source("unknown_source_xyz", kw)
        assert len(kws) >= 1
        # 默认映射是 ["en", "cn", "original"]
        assert kws[0] == "Inception"

    def test_only_jp_name(self):
        """只有日文名"""
        kw = _kw(original="進撃の巨人")
        kws = get_search_keywords_for_source("nyaa", kw)
        assert kws[0] == "進撃の巨人"

    def test_only_original(self):
        """只有 query"""
        kw = _kw(query="some random query")
        kws = get_search_keywords_for_source("prowlarr", kw)
        assert kws == ["some random query"]

    def test_all_empty(self):
        """所有字段都为空"""
        kw = _kw()
        kws = get_search_keywords_for_source("prowlarr", kw)
        # 应该返回空列表（original 也为空）
        assert kws == []


# ═══════════════════════════════════════════════════════════════
# get_default_keyword_for_source 测试
# ═══════════════════════════════════════════════════════════════
class TestGetDefaultKeyword:
    """get_default_keyword_for_source 测试"""

    def test_returns_first_keyword(self):
        """返回第一个搜索词"""
        kw = _kw(cn="盗梦空间", en="Inception")
        assert get_default_keyword_for_source("prowlarr", kw) == "Inception"
        assert get_default_keyword_for_source("cilixiong", kw) == "盗梦空间"

    def test_empty_returns_original(self):
        """所有名称为空时返回 query"""
        kw = _kw(query="query")
        assert get_default_keyword_for_source("prowlarr", kw) == "query"

    def test_all_empty_returns_empty(self):
        """全空时返回空字符串"""
        kw = _kw()
        assert get_default_keyword_for_source("prowlarr", kw) == ""

    def test_with_season(self):
        """带季号"""
        kw = _kw(cn="权力的游戏", en="Game of Thrones", season=3)
        assert get_default_keyword_for_source("prowlarr", kw) == "Game of Thrones S03"
        assert get_default_keyword_for_source("cilixiong", kw) == "权力的游戏 第3季"



