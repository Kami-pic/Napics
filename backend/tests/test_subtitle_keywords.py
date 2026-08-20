"""字幕搜索词构造测试。

锁定「字幕搜索」与「搜索升级」用同一套关键词规则
（对齐 frontend/components/search/useSearchState.ts 的 searchTags）。
曾经出错的点：
1. 缺少 "中文 英文" 组合词
2. SubHD / SubDL 只搜一个词，没有走回退链
3. SubDL 把季集号拼进搜索词，导致匹配不到（它有独立的季集参数）
"""

import os
import sys

import pytest

_PLUGIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "plugins",
    "subtitle-search",
)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from subtitle_keywords import (  # noqa: E402
    base_names_for_source,
    build_keyword_tags,
    keywords_for_source,
)


def _kw(tags):
    return [tag.keyword for tag in tags]


class TestMovieKeywords:
    """电影（无季集）：中文 → 中文+英文 → 英文"""

    def test_cn_en_combo_present(self):
        tags = build_keyword_tags(cn_name="信条", en_name="Tenet")
        assert _kw(tags) == ["信条", "信条 Tenet", "Tenet"]

    def test_two_char_cn_name_not_filtered(self):
        """中文片名只有两个字也必须保留（曾被 len>=3 过滤掉）"""
        tags = build_keyword_tags(cn_name="信条", en_name="")
        assert "信条" in _kw(tags)

    def test_cn_equals_en_dedupe(self):
        tags = build_keyword_tags(cn_name="Inception", en_name="Inception")
        assert _kw(tags) == ["Inception"]

    def test_only_en(self):
        tags = build_keyword_tags(cn_name="", en_name="Tenet")
        assert _kw(tags) == ["Tenet"]


class TestEpisodeKeywords:
    """有 episode_tag：中文 SxxExx → 英文 SxxExx → 中文+英文 → 中文 → 英文"""

    def test_order_matches_search_upgrade(self):
        tags = build_keyword_tags(
            cn_name="权力的游戏", en_name="Game of Thrones", episode_tag="S03E05"
        )
        assert _kw(tags) == [
            "权力的游戏 S03E05",
            "Game of Thrones S03E05",
            "权力的游戏 Game of Thrones",
            "权力的游戏",
            "Game of Thrones",
        ]


class TestSeasonKeywords:
    """季目录：中文第N季 → 英文 SNN → 中文+英文 → 中文 → 英文"""

    def test_season_folder(self):
        tags = build_keyword_tags(
            cn_name="进击的巨人",
            en_name="Attack on Titan",
            folder_type="season",
            season_number=3,
        )
        assert _kw(tags)[:3] == [
            "进击的巨人 第3季",
            "Attack on Titan S03",
            "进击的巨人 Attack on Titan",
        ]

    def test_tv_folder_has_no_cn_en_combo(self):
        """tv/series 分支不出 中文+英文 组合词（与前端一致）"""
        tags = build_keyword_tags(
            cn_name="进击的巨人",
            en_name="Attack on Titan",
            folder_type="tv",
            season_number=3,
        )
        assert "进击的巨人 Attack on Titan" not in _kw(tags)

    def test_original_name_appended(self):
        tags = build_keyword_tags(
            cn_name="进击的巨人",
            en_name="Attack on Titan",
            original_name="進撃の巨人",
        )
        assert "進撃の巨人" in _kw(tags)


class TestPerSourceFallbackChain:
    """每个源都要有回退链，且语言优先级不同"""

    def test_chinese_sources_prefer_cn(self):
        tags = build_keyword_tags(cn_name="信条", en_name="Tenet")
        assert keywords_for_source("assrt", tags)[0] == "信条"
        assert keywords_for_source("subhd", tags)[0] == "信条"

    def test_subdl_prefers_en(self):
        tags = build_keyword_tags(cn_name="信条", en_name="Tenet")
        assert base_names_for_source("subdl", tags)[0] == "Tenet"

    def test_every_source_gets_multiple_keywords(self):
        """回退链必须多于一个词，否则第一个词搜不到就没结果了"""
        tags = build_keyword_tags(cn_name="信条", en_name="Tenet")
        assert len(keywords_for_source("assrt", tags)) > 1
        assert len(keywords_for_source("subhd", tags)) > 1
        assert len(base_names_for_source("subdl", tags)) > 1

    def test_subdl_base_names_exclude_season_text(self):
        """SubDL 季集号走请求参数，搜索词里不能带 S03E05 / 第3季"""
        tags = build_keyword_tags(
            cn_name="权力的游戏",
            en_name="Game of Thrones",
            folder_type="season",
            season_number=3,
            episode_tag="S03E05",
        )
        for keyword in base_names_for_source("subdl", tags):
            assert "S03" not in keyword
            assert "第3季" not in keyword

    def test_assrt_keeps_season_text(self):
        """中文源保留季号文本，命中率更高"""
        tags = build_keyword_tags(
            cn_name="进击的巨人", en_name="Attack on Titan",
            folder_type="season", season_number=3,
        )
        assert keywords_for_source("assrt", tags)[0] == "进击的巨人 第3季"


class TestEmptyInput:
    def test_all_empty_returns_empty(self):
        assert build_keyword_tags() == []

    def test_query_only_fallback(self):
        tags = build_keyword_tags(query="某部电影")
        assert _kw(tags) == ["某部电影"]
