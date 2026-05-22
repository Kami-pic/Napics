"""英文名缺失修复 — 全面测试

覆盖场景：
1. _inject_clean_names 英文名提取（routes/discover.py）
2. scan 初始化 clean_from_filename（routes/library.py）
3. 搜索词映射完整链路（search_keyword_mapper.py）
4. detect_language 准确性（text_processing.py）
"""
import pytest
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from text_processing import detect_language, split_by_language
from clean_name_system import clean_from_filename, clean_from_scrape, CleanNameResult
from search_keyword_mapper import (
    MultiLangKeywords, get_search_keywords_for_source,
    SOURCE_LANG_PRIORITY,
)


# ════════════════════════════════════════
# 辅助：模拟 _inject_clean_names 的核心逻辑
# ════════════════════════════════════════

def _inject_clean_names_logic(item: dict) -> dict:
    """从 routes/discover.py 提取的核心逻辑，独立可测"""
    title = item.get("title", "")
    if not title:
        return item
    if item.get("clean_name_cn"):
        return item

    raw_original = item.get("original_title") or item.get("_tmdb_original_title") or ""
    subtitle = item.get("subtitle", "")

    en = ""
    original = ""
    if raw_original and raw_original != title:
        lang = detect_language(raw_original)
        if lang == "en":
            en = raw_original
        elif lang in ("jp", "ko", "mixed"):
            original = raw_original

    if not en and subtitle:
        parts = re.split(r'\s*/\s*', subtitle)
        for p in parts:
            p = p.strip()
            if not p or p == title:
                continue
            lang = detect_language(p)
            if lang == "en":
                en = p
                break
            elif lang in ("jp", "ko") and not original:
                original = p

    result = clean_from_scrape(
        title=title,
        original_title=original,
        english_title=en,
        year=item.get("year", ""),
        source="tmdb",
    )
    item["clean_name_cn"] = result.cn
    item["clean_name_en"] = result.en
    item["clean_name_original"] = result.original
    return item


# ════════════════════════════════════════
# 1. _inject_clean_names 英文名提取
# ════════════════════════════════════════

class TestInjectCleanNames:
    """测试 discover 页面的英文名提取逻辑"""

    def test_chinese_movie_en_from_subtitle(self):
        """中国电影：en 应该从 subtitle 提取"""
        item = {
            "title": "流浪地球",
            "original_title": "流浪地球",
            "subtitle": "The Wandering Earth",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "流浪地球"
        assert result["clean_name_en"] == "The Wandering Earth"

    def test_japanese_anime_original_is_jp(self):
        """日本动画：original 应该是日文，en 应该为空"""
        item = {
            "title": "进击的巨人",
            "original_title": "進撃の巨人",
            "subtitle": "",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "进击的巨人"
        assert result["clean_name_original"] == "進撃の巨人"
        # 没有英文来源，en 应该为空
        assert result["clean_name_en"] == ""

    def test_us_movie_en_from_original_title(self):
        """美国电影：en 应该是 Inception"""
        item = {
            "title": "盗梦空间",
            "original_title": "Inception",
            "subtitle": "",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "盗梦空间"
        assert result["clean_name_en"] == "Inception"

    def test_korean_movie_en_from_subtitle(self):
        """韩国电影：original 是韩文，en 从 subtitle 提取"""
        item = {
            "title": "寄生虫",
            "original_title": "기생충",
            "subtitle": "Parasite",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "寄生虫"
        assert result["clean_name_original"] == "기생충"
        assert result["clean_name_en"] == "Parasite"

    def test_no_subtitle_no_original(self):
        """无 subtitle 无 original_title：cn 有值，en 和 original 为空"""
        item = {
            "title": "某部电影",
            "original_title": "",
            "subtitle": "",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "某部电影"
        assert result["clean_name_en"] == ""
        assert result["clean_name_original"] == ""

    def test_original_same_as_title_chinese(self):
        """original_title 和 title 相同（中国电影）：不应把中文当英文"""
        item = {
            "title": "流浪地球",
            "original_title": "流浪地球",
            "subtitle": "",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "流浪地球"
        # original_title == title，被跳过，en 应该为空
        assert result["clean_name_en"] == ""
        assert result["clean_name_original"] == ""

    def test_subtitle_with_multiple_parts(self):
        """subtitle 含多个斜杠分隔的名称，应取第一个英文"""
        item = {
            "title": "千与千寻",
            "original_title": "千と千尋の神隠し",
            "subtitle": "Spirited Away / 神隠し",
        }
        result = _inject_clean_names_logic(item)
        assert result["clean_name_cn"] == "千与千寻"
        assert result["clean_name_en"] == "Spirited Away"
        assert result["clean_name_original"] == "千と千尋の神隠し"

    def test_skip_if_already_has_cn(self):
        """已有 clean_name_cn 时跳过"""
        item = {
            "title": "盗梦空间",
            "original_title": "Inception",
            "subtitle": "",
            "clean_name_cn": "已有中文名",
        }
        result = _inject_clean_names_logic(item)
        # 不应被覆盖
        assert result["clean_name_cn"] == "已有中文名"


# ════════════════════════════════════════
# 2. scan 初始化 clean_from_filename
# ════════════════════════════════════════

class TestCleanFromFilename:
    """测试文件名解析的多语言名称提取"""

    def test_bracket_anime_filename(self):
        """[字幕组][进击的巨人][01][1080p].mkv → cn 应该有值"""
        result = clean_from_filename("[字幕组][进击的巨人][01][1080p].mkv")
        assert result.cn, f"cn 不应为空，实际: '{result.cn}'"
        # cn 应该包含"进击的巨人"
        assert "进击" in result.cn or "巨人" in result.cn

    def test_english_movie_filename(self):
        """Inception.2010.1080p.BluRay.mkv → en 应该有值"""
        result = clean_from_filename("Inception.2010.1080p.BluRay.mkv")
        assert result.en, f"en 不应为空，实际: '{result.en}'"
        assert "Inception" in result.en or "inception" in result.en.lower()

    def test_mixed_cn_en_filename(self):
        """盗梦空间.Inception.2010.mkv → cn 和 en 都应该有值"""
        result = clean_from_filename("盗梦空间.Inception.2010.mkv")
        assert result.cn, f"cn 不应为空，实际: '{result.cn}'"
        assert result.en, f"en 不应为空，实际: '{result.en}'"
        assert "盗梦空间" in result.cn
        assert "Inception" in result.en or "inception" in result.en.lower()

    def test_pure_chinese_filename(self):
        """纯中文文件名"""
        result = clean_from_filename("流浪地球.2019.mkv")
        assert result.cn, f"cn 不应为空"
        assert "流浪地球" in result.cn

    def test_complex_anime_filename(self):
        """复杂动漫文件名"""
        result = clean_from_filename("[Sakurato] Shingeki no Kyojin [01][1080p].mkv")
        # 应该能提取出英文名
        assert result.en or result.cn, "至少应该有一个名称"

    def test_display_not_empty(self):
        """display 字段不应为空（只要有任何名称）"""
        result = clean_from_filename("Inception.2010.1080p.BluRay.mkv")
        assert result.display, "display 不应为空"

    def test_source_is_parsed(self):
        """来源应该是 parsed"""
        result = clean_from_filename("盗梦空间.Inception.2010.mkv")
        assert result.source == "parsed"


# ════════════════════════════════════════
# 3. 搜索词映射完整链路
# ════════════════════════════════════════

class TestSearchKeywordMapper:
    """测试从 clean_name 结构化字段到搜索词的完整链路"""

    def test_only_cn_prowlarr_fallback(self):
        """只有 cn 没有 en：Prowlarr 应该回退到 cn"""
        kw = MultiLangKeywords(cn="进击的巨人", en="", original="", query="进击的巨人")
        result = get_search_keywords_for_source("prowlarr", kw)
        # prowlarr 优先 en，但 en 为空，应回退到 cn
        assert len(result) >= 1
        assert "进击的巨人" in result[0]

    def test_only_en_cilixiong_fallback(self):
        """只有 en 没有 cn：磁力熊应该回退到 en"""
        kw = MultiLangKeywords(cn="", en="Inception", original="", query="Inception")
        result = get_search_keywords_for_source("cilixiong", kw)
        # cilixiong 优先 cn，但 cn 为空，应回退到 en
        assert len(result) >= 1
        assert "Inception" in result[0]

    def test_all_names_nyaa_uses_original(self):
        """cn + en + original 都有：Nyaa 用 original"""
        kw = MultiLangKeywords(
            cn="进击的巨人", en="Attack on Titan",
            original="進撃の巨人", query="进击的巨人",
        )
        result = get_search_keywords_for_source("nyaa", kw)
        # nyaa 优先 original
        assert result[0] == "進撃の巨人"

    def test_all_names_prowlarr_uses_en(self):
        """cn + en + original 都有：Prowlarr 用 en"""
        kw = MultiLangKeywords(
            cn="进击的巨人", en="Attack on Titan",
            original="進撃の巨人", query="进击的巨人",
        )
        result = get_search_keywords_for_source("prowlarr", kw)
        # prowlarr 优先 en
        assert result[0] == "Attack on Titan"

    def test_all_names_cilixiong_uses_cn(self):
        """cn + en + original 都有：磁力熊用 cn"""
        kw = MultiLangKeywords(
            cn="进击的巨人", en="Attack on Titan",
            original="進撃の巨人", query="进击的巨人",
        )
        result = get_search_keywords_for_source("cilixiong", kw)
        # cilixiong 优先 cn
        assert result[0] == "进击的巨人"

    def test_fallback_chain_order(self):
        """回退链顺序正确：prowlarr [en, cn, query]"""
        kw = MultiLangKeywords(
            cn="寄生虫", en="Parasite", original="기생충", query="寄生虫",
        )
        result = get_search_keywords_for_source("prowlarr", kw)
        # 第一个是 en，第二个是 cn 回退
        assert result[0] == "Parasite"
        assert len(result) >= 2
        assert result[1] == "寄生虫"

    def test_season_appended_cn_source(self):
        """中文源季号拼接"第N季"格式"""
        kw = MultiLangKeywords(
            cn="进击的巨人", en="Attack on Titan",
            original="", query="进击的巨人", season_number=3,
        )
        result = get_search_keywords_for_source("cilixiong", kw)
        assert "第3季" in result[0]

    def test_season_appended_en_source(self):
        """英文源季号拼接"S0N"格式"""
        kw = MultiLangKeywords(
            cn="进击的巨人", en="Attack on Titan",
            original="", query="进击的巨人", season_number=3,
        )
        result = get_search_keywords_for_source("prowlarr", kw)
        assert "S03" in result[0]

    def test_empty_all_uses_query_fallback(self):
        """所有名称都为空时，用 query 兜底"""
        kw = MultiLangKeywords(cn="", en="", original="", query="某部电影")
        result = get_search_keywords_for_source("prowlarr", kw)
        assert len(result) >= 1
        assert "某部电影" in result[0]

    def test_dedup_same_keyword(self):
        """相同的搜索词应该被去重"""
        kw = MultiLangKeywords(
            cn="Inception", en="Inception", original="", query="Inception",
        )
        result = get_search_keywords_for_source("prowlarr", kw)
        # en 和 cn 相同，不应重复
        assert result.count("Inception") == 1


# ════════════════════════════════════════
# 4. detect_language 准确性
# ════════════════════════════════════════

class TestDetectLanguage:
    """测试 detect_language 对各种文本的判断"""

    def test_english(self):
        assert detect_language("Inception") == "en"

    def test_chinese(self):
        assert detect_language("盗梦空间") == "cn"

    def test_japanese(self):
        assert detect_language("進撃の巨人") == "jp"

    def test_korean(self):
        assert detect_language("기생충") == "ko"

    def test_french_name_latin_alphabet(self):
        """法语名但拉丁字母 → 应该识别为 en"""
        result = detect_language("Adèle")
        # 拉丁字母为主，应该是 en（法语名用拉丁字母）
        assert result == "en", f"期望 'en'，实际: '{result}'"

    def test_chinese_simplified(self):
        assert detect_language("流浪地球") == "cn"

    def test_empty_string(self):
        assert detect_language("") == "none"

    def test_pure_numbers(self):
        assert detect_language("2024") == "none"

    def test_mixed_cn_en(self):
        """中英混合文本"""
        result = detect_language("盗梦空间 Inception")
        assert result == "mixed"

    def test_japanese_katakana(self):
        """纯片假名"""
        assert detect_language("ドラゴンボール") == "jp"

    def test_japanese_hiragana(self):
        """纯平假名"""
        assert detect_language("すずめの戸締まり") == "jp"


# ════════════════════════════════════════
# 5. 端到端集成：discover → search 完整链路
# ════════════════════════════════════════

class TestEndToEndFlow:
    """端到端测试：从 discover 注入名称到搜索词生成"""

    def test_chinese_movie_full_chain(self):
        """中国电影完整链路：discover 注入 → 搜索词映射"""
        # 模拟 discover 数据
        item = {
            "title": "流浪地球",
            "original_title": "流浪地球",
            "subtitle": "The Wandering Earth",
            "year": "2019",
        }
        _inject_clean_names_logic(item)

        # 构造搜索词
        kw = MultiLangKeywords(
            cn=item["clean_name_cn"],
            en=item["clean_name_en"],
            original=item["clean_name_original"],
            query=item["title"],
        )

        # Prowlarr 应该用英文
        prowlarr_kw = get_search_keywords_for_source("prowlarr", kw)
        assert "The Wandering Earth" in prowlarr_kw[0]

        # 磁力熊应该用中文
        cilixiong_kw = get_search_keywords_for_source("cilixiong", kw)
        assert "流浪地球" in cilixiong_kw[0]

    def test_japanese_anime_full_chain(self):
        """日本动画完整链路"""
        item = {
            "title": "进击的巨人",
            "original_title": "進撃の巨人",
            "subtitle": "Attack on Titan",
            "year": "2013",
        }
        _inject_clean_names_logic(item)

        kw = MultiLangKeywords(
            cn=item["clean_name_cn"],
            en=item["clean_name_en"],
            original=item["clean_name_original"],
            query=item["title"],
        )

        # Nyaa 应该用日文原名
        nyaa_kw = get_search_keywords_for_source("nyaa", kw)
        assert "進撃の巨人" in nyaa_kw[0]

        # Prowlarr 应该用英文
        prowlarr_kw = get_search_keywords_for_source("prowlarr", kw)
        assert "Attack on Titan" in prowlarr_kw[0]

        # 磁力熊应该用中文
        cilixiong_kw = get_search_keywords_for_source("cilixiong", kw)
        assert "进击的巨人" in cilixiong_kw[0]

    def test_korean_movie_full_chain(self):
        """韩国电影完整链路"""
        item = {
            "title": "寄生虫",
            "original_title": "기생충",
            "subtitle": "Parasite",
            "year": "2019",
        }
        _inject_clean_names_logic(item)

        assert item["clean_name_cn"] == "寄生虫"
        assert item["clean_name_en"] == "Parasite"
        assert item["clean_name_original"] == "기생충"

        kw = MultiLangKeywords(
            cn=item["clean_name_cn"],
            en=item["clean_name_en"],
            original=item["clean_name_original"],
            query=item["title"],
        )

        # Prowlarr 用英文
        prowlarr_kw = get_search_keywords_for_source("prowlarr", kw)
        assert prowlarr_kw[0] == "Parasite"

    def test_no_en_name_fallback(self):
        """没有英文名时，Prowlarr 回退到中文"""
        item = {
            "title": "某部国产电影",
            "original_title": "某部国产电影",
            "subtitle": "",
            "year": "2024",
        }
        _inject_clean_names_logic(item)

        kw = MultiLangKeywords(
            cn=item["clean_name_cn"],
            en=item["clean_name_en"],
            original=item["clean_name_original"],
            query=item["title"],
        )

        prowlarr_kw = get_search_keywords_for_source("prowlarr", kw)
        # en 为空，应回退到 cn
        assert len(prowlarr_kw) >= 1
        assert "某部国产电影" in prowlarr_kw[0]


# ════════════════════════════════════════
# 6. clean_from_scrape 补充测试
# ════════════════════════════════════════

class TestCleanFromScrape:
    """测试刮削结果构建清洗名的多语言分配"""

    def test_cn_title_en_english_title(self):
        """中文 title + 英文 english_title"""
        result = clean_from_scrape(
            title="盗梦空间",
            original_title="",
            english_title="Inception",
            year="2010",
            source="tmdb",
        )
        assert result.cn == "盗梦空间"
        assert result.en == "Inception"

    def test_jp_original_title(self):
        """日文 original_title 归入 original"""
        result = clean_from_scrape(
            title="进击的巨人",
            original_title="進撃の巨人",
            english_title="",
            year="2013",
            source="tmdb",
        )
        assert result.cn == "进击的巨人"
        assert result.original == "進撃の巨人"

    def test_en_original_title_as_en(self):
        """英文 original_title 归入 en"""
        result = clean_from_scrape(
            title="盗梦空间",
            original_title="Inception",
            english_title="",
            year="2010",
            source="tmdb",
        )
        assert result.cn == "盗梦空间"
        assert result.en == "Inception"

    def test_pure_en_title(self):
        """纯英文 title"""
        result = clean_from_scrape(
            title="Inception",
            original_title="",
            english_title="",
            year="2010",
            source="tmdb",
        )
        assert result.en == "Inception"

    def test_ko_original_title(self):
        """韩文 original_title 归入 original"""
        result = clean_from_scrape(
            title="寄生虫",
            original_title="기생충",
            english_title="Parasite",
            year="2019",
            source="tmdb",
        )
        assert result.cn == "寄生虫"
        assert result.en == "Parasite"
        assert result.original == "기생충"
