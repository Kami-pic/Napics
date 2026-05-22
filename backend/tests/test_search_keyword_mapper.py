"""search_keyword_mapper 单元测试"""
import pytest
from search_keyword_mapper import (
    MultiLangKeywords, get_search_keywords_for_source, get_default_keyword_for_source,
)


class TestKeywordMapping:
    """测试各源的搜索词选择"""

    def _kw(self, cn="", en="", original="", query="", season=0):
        return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)

    # ── 英文源优先 enName ──

    def test_prowlarr_en_first(self):
        kws = get_search_keywords_for_source("prowlarr", self._kw(cn="盗梦空间", en="Inception", query="盗梦空间"))
        assert kws[0] == "Inception"
        assert "盗梦空间" in kws  # 回退词

    def test_bitsearch_en_first(self):
        kws = get_search_keywords_for_source("bitsearch", self._kw(cn="盗梦空间", en="Inception"))
        assert kws[0] == "Inception"

    def test_yts_en_first(self):
        kws = get_search_keywords_for_source("yts", self._kw(cn="盗梦空间", en="Inception"))
        assert kws[0] == "Inception"

    # ── 中文源优先 cnName ──

    def test_cilixiong_cn_first(self):
        kws = get_search_keywords_for_source("cilixiong", self._kw(cn="盗梦空间", en="Inception"))
        assert kws[0] == "盗梦空间"
        assert "Inception" in kws

    def test_xl720_cn_first(self):
        kws = get_search_keywords_for_source("xl720", self._kw(cn="盗梦空间", en="Inception"))
        assert kws[0] == "盗梦空间"

    # ── 动画源优先 jpName ──

    def test_nyaa_jp_first(self):
        kws = get_search_keywords_for_source("nyaa", self._kw(cn="进击的巨人", en="Attack on Titan", original="進撃の巨人"))
        assert kws[0] == "進撃の巨人"
        assert "Attack on Titan" in kws

    def test_nyaa_no_jp_fallback_en(self):
        """jpName 为空时回退到 enName"""
        kws = get_search_keywords_for_source("nyaa", self._kw(cn="进击的巨人", en="Attack on Titan"))
        assert kws[0] == "Attack on Titan"

    def test_mikan_cn_first(self):
        kws = get_search_keywords_for_source("mikan", self._kw(cn="进击的巨人", en="Attack on Titan", original="進撃の巨人"))
        assert kws[0] == "进击的巨人"

    # ── 字幕组源 ──

    def test_acgrip_cn_first(self):
        kws = get_search_keywords_for_source("acgrip", self._kw(cn="葬送的芙莉莲", en="Frieren", original="葬送のフリーレン"))
        assert kws[0] == "葬送的芙莉莲"

    def test_bangumi_moe_cn_first(self):
        kws = get_search_keywords_for_source("bangumi_moe", self._kw(cn="葬送的芙莉莲", en="Frieren", original="葬送のフリーレン"))
        assert kws[0] == "葬送的芙莉莲"


class TestDedup:
    """测试去重逻辑"""

    def _kw(self, cn="", en="", original="", query="", season=0):
        return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)

    def test_cn_en_same_dedup(self):
        """cnName 和 enName 相同时不重复"""
        kws = get_search_keywords_for_source("cilixiong", self._kw(cn="Inception", en="Inception"))
        assert len(kws) == 1
        assert kws[0] == "Inception"

    def test_cn_en_same_case_insensitive(self):
        """大小写不同也去重"""
        kws = get_search_keywords_for_source("prowlarr", self._kw(cn="inception", en="Inception"))
        assert len(kws) == 1

    def test_max_three_keywords(self):
        """最多 3 个词"""
        kws = get_search_keywords_for_source("nyaa", self._kw(cn="中文", en="English", original="日本語", query="query"))
        assert len(kws) <= 3


class TestFallback:
    """测试兜底逻辑"""

    def _kw(self, cn="", en="", original="", query="", season=0):
        return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)

    def test_all_empty_use_original(self):
        """所有名称为空时用 original"""
        kws = get_search_keywords_for_source("prowlarr", self._kw(query="some query"))
        assert kws == ["some query"]

    def test_only_cn(self):
        """只有中文名"""
        kws = get_search_keywords_for_source("prowlarr", self._kw(cn="盗梦空间", query="盗梦空间"))
        # prowlarr 优先 en，en 为空跳过，然后 cn
        assert kws[0] == "盗梦空间"

    def test_only_en(self):
        """只有英文名"""
        kws = get_search_keywords_for_source("cilixiong", self._kw(en="Inception", query="Inception"))
        # cilixiong 优先 cn，cn 为空跳过，然后 en
        assert kws[0] == "Inception"


class TestSeasonAppend:
    """测试季号拼接"""

    def _kw(self, cn="", en="", original="", query="", season=0):
        return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)

    def test_cn_source_season(self):
        """中文源拼'第N季'"""
        kws = get_search_keywords_for_source("cilixiong", self._kw(cn="权力的游戏", en="Game of Thrones", season=3))
        assert kws[0] == "权力的游戏 第3季"

    def test_en_source_season(self):
        """英文源拼'S0N'"""
        kws = get_search_keywords_for_source("prowlarr", self._kw(cn="权力的游戏", en="Game of Thrones", season=3))
        assert kws[0] == "Game of Thrones S03"

    def test_nyaa_season(self):
        """Nyaa 是英文源，拼 S0N"""
        kws = get_search_keywords_for_source("nyaa", self._kw(original="進撃の巨人", en="Attack on Titan", season=4))
        assert kws[0] == "進撃の巨人 S04"

    def test_no_season(self):
        """season=0 不拼接"""
        kws = get_search_keywords_for_source("prowlarr", self._kw(en="Inception", season=0))
        assert kws[0] == "Inception"

    def test_season_dedup(self):
        """季号拼接后相同的词去重"""
        kws = get_search_keywords_for_source("cilixiong", self._kw(cn="权力的游戏", en="权力的游戏", season=1))
        assert len(kws) == 1

    def test_pan_source_season(self):
        """网盘源拼中文季号"""
        kws = get_search_keywords_for_source("pansearch", self._kw(cn="权力的游戏", en="Game of Thrones", season=2))
        assert kws[0] == "权力的游戏 第2季"


class TestDefaultKeyword:
    """测试 get_default_keyword_for_source"""

    def _kw(self, cn="", en="", original="", query="", season=0):
        return MultiLangKeywords(cn=cn, en=en, original=original, query=query, season_number=season)

    def test_prowlarr_default(self):
        kw = get_default_keyword_for_source("prowlarr", self._kw(cn="盗梦空间", en="Inception"))
        assert kw == "Inception"

    def test_cilixiong_default(self):
        kw = get_default_keyword_for_source("cilixiong", self._kw(cn="盗梦空间", en="Inception"))
        assert kw == "盗梦空间"

    def test_unknown_source_default_en(self):
        """未知源默认用英文"""
        kw = get_default_keyword_for_source("unknown_source", self._kw(cn="盗梦空间", en="Inception"))
        assert kw == "Inception"




