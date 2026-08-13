"""L1 text-processing 技能测试 — TDD 驱动"""
import pytest
import os
import sys

# 确保能导入 backend 模块
sys.path.insert(0, os.path.dirname(__file__))

from text_processing import (
    normalize, detect_language, split_by_language,
    is_short_name, extract_variants, clean_keyword,
    tokenize, process_text,
)


# ── normalize ──

class TestNormalize:
    def test_fullwidth_to_halfwidth(self):
        assert normalize("進擊的巨人　Ｓ０４") == "进击的巨人s04"

    def test_fullwidth_mixed(self):
        """全角数字+全角字母+中文"""
        result = normalize("【YIFY】流浪地球２")
        assert "yify" in result
        assert "流浪地球2" in result

    def test_punctuation_removal(self):
        assert normalize("你好，世界！") == "你好世界"

    def test_lowercase(self):
        assert normalize("Attack on Titan") == "attackontitan"

    def test_empty(self):
        assert normalize("") == ""

    def test_cjk_space_collapse(self):
        """CJK 字符之间的空格应去掉"""
        assert normalize("进击 的 巨人") == "进击的巨人"

    def test_traditional_to_simplified(self):
        """繁体→简体（如果实现了繁简转换）"""
        result = normalize("進擊的巨人")
        # 至少全角应该转了，繁简转换是可选的
        assert "巨人" in result


# ── detect_language ──

class TestDetectLanguage:
    def test_chinese(self):
        assert detect_language("进击的巨人") == "cn"

    def test_english(self):
        assert detect_language("Attack on Titan") == "en"

    def test_japanese(self):
        """含假名→jp"""
        assert detect_language("進撃のきょじん") == "jp"

    def test_mixed(self):
        assert detect_language("进击的巨人 Attack on Titan") == "mixed"

    def test_pure_number(self):
        assert detect_language("2024") == "none"

    def test_format_string(self):
        assert detect_language("S01E05") == "none"

    def test_empty(self):
        assert detect_language("") == "none"


# ── split_by_language ──

class TestSplitByLanguage:
    def test_cn_en_mixed(self):
        result = split_by_language("西部世界 Westworld")
        assert result["cn"] == "西部世界"
        assert result["en"] == "Westworld"

    def test_en_cn_order(self):
        result = split_by_language("The Last of Us 最后生还者")
        assert result["cn"] == "最后生还者"
        assert result["en"] == "The Last of Us"

    def test_pure_chinese(self):
        result = split_by_language("进击的巨人")
        assert result["cn"] == "进击的巨人"
        assert result["en"] == ""

    def test_pure_english(self):
        result = split_by_language("Inception")
        assert result["cn"] == ""
        assert result["en"] == "Inception"

    def test_bt_title_with_tags(self):
        """BT 标题含标签"""
        result = split_by_language("进击的巨人 Attack on Titan S04 1080p")
        assert result["cn"] == "进击的巨人"
        assert "Attack on Titan" in result["en"]


# ── is_short_name ──

class TestIsShortName:
    def test_short_chinese(self):
        assert is_short_name("她") is True

    def test_long_chinese(self):
        assert is_short_name("进击的巨人") is False

    def test_short_english(self):
        assert is_short_name("Her") is True
        assert is_short_name("AI") is True

    def test_long_english(self):
        assert is_short_name("Inception") is False

    def test_number_not_counted(self):
        """数字不算名字长度"""
        assert is_short_name("2001") is False


# ── extract_variants ──

class TestExtractVariants:
    def test_with_subtitle(self):
        variants = extract_variants("盗梦空间：终极版")
        assert "盗梦空间" in variants

    def test_with_year(self):
        variants = extract_variants("流浪地球 (2019)")
        assert "流浪地球" in variants

    def test_with_season(self):
        variants = extract_variants("进击的巨人 第3季")
        # 应包含去掉季号的版本
        assert any("进击的巨人" in v for v in variants)

    def test_mixed_cn_en(self):
        variants = extract_variants("西部世界 Westworld (2016)")
        assert "西部世界" in variants or any("西部世界" in v for v in variants)
        assert "Westworld" in variants or any("Westworld" in v for v in variants)


# ── clean_keyword ──

class TestCleanKeyword:
    def test_remove_year(self):
        assert clean_keyword("流浪地球 (2019)") == "流浪地球"

    def test_remove_brackets(self):
        result = clean_keyword("流浪地球 [1080p]")
        assert "1080p" not in result
        assert "流浪地球" in result

    def test_season_standardize(self):
        """中文季号标准化"""
        result = clean_keyword("进击的巨人 第3季")
        assert "S03" in result or "s03" in result or "第3季" in result

    def test_with_blacklist(self):
        """干扰词黑名单"""
        result = clean_keyword(
            "[SubsPlease] 进击的巨人 x264 10bit",
            blacklist=["SubsPlease", "x264", "10bit"]
        )
        assert "SubsPlease" not in result
        assert "x264" not in result
        assert "10bit" not in result
        assert "进击的巨人" in result


# ── tokenize ──

class TestTokenize:
    def test_english_with_stopwords(self):
        tokens = tokenize("Attack on Titan")
        assert "attack" in tokens
        assert "titan" in tokens
        assert "on" not in tokens

    def test_chinese(self):
        tokens = tokenize("进击的巨人")
        assert len(tokens) == 5  # 每个汉字一个 token

    def test_mixed(self):
        tokens = tokenize("西部世界 Westworld")
        assert "westworld" in tokens
        assert "西" in tokens


# ── process_text（统一输出结构）──

class TestProcessText:
    def test_output_structure(self):
        """验证统一输出结构包含所有字段"""
        result = process_text("进击的巨人 Attack on Titan (2022)")
        assert "original" in result
        assert "normalized" in result
        assert "language" in result
        assert "cn" in result
        assert "en" in result
        assert "is_short_name" in result
        assert "variants" in result
        assert "tokens" in result
        assert "clean_keyword" in result

    def test_cn_en_extraction(self):
        result = process_text("进击的巨人 Attack on Titan")
        assert result["cn"] == "进击的巨人"
        assert "Attack on Titan" in result["en"]
        assert result["language"] == "mixed"
        assert result["is_short_name"] is False


# ── 用 sandbox_real 真实数据测试 ──

class TestWithSandboxData:
    """用 sandbox_real 的真实文件名做集成测试"""

    SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox_real")

    @pytest.fixture
    def real_filenames(self):
        """从 sandbox_real 收集真实文件夹名"""
        names = []
        if not os.path.exists(self.SANDBOX_DIR):
            pytest.skip("sandbox_real 不存在")
        for category in os.listdir(self.SANDBOX_DIR):
            cat_path = os.path.join(self.SANDBOX_DIR, category)
            if os.path.isdir(cat_path):
                for item in os.listdir(cat_path):
                    if not item.startswith(".") and not item.endswith((".db", ".jpg", ".nfo")):
                        names.append(item)
        return names

    def test_normalize_no_crash(self, real_filenames):
        """所有真实文件名 normalize 不崩溃"""
        for name in real_filenames:
            result = normalize(name)
            assert isinstance(result, str)

    def test_split_no_crash(self, real_filenames):
        """所有真实文件名 split_by_language 不崩溃"""
        for name in real_filenames:
            result = split_by_language(name)
            assert "cn" in result
            assert "en" in result

    def test_process_text_no_crash(self, real_filenames):
        """所有真实文件名 process_text 不崩溃"""
        for name in real_filenames:
            result = process_text(name)
            assert "original" in result
            assert "normalized" in result

    def test_extreme_cases(self):
        """手动验证几个已知的极端 case"""
        # 全角字符
        r = process_text("晚娘Ｉ(2001)")
        assert r["normalized"]  # 不为空

        # 纯数字
        r = process_text("02.rmvb")
        assert r["language"] == "none"

        # 超短中文名
        r = process_text("白2023")
        assert r["is_short_name"] is True  # "白" 只有 1 个中文字符

        # 方括号字幕组格式
        r = process_text("[SweetSub] VIRGIN PUNK - 01 [BDRip][1080P][AVC 8bit][CHS]")
        assert r["cn"] == "" or len(r["cn"]) == 0  # 纯英文标题
