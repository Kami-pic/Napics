"""Unit tests for SearchQueryBuilder."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from search_query_builder import SearchQueryBuilder
from alias_resolver import AliasSet


builder = SearchQueryBuilder()


# === build_tmdb_queries ===

def test_tmdb_queries_includes_original_title():
    """原始标题始终在列表中"""
    result = builder.build_tmdb_queries("流浪地球")
    assert "流浪地球" in result
    assert result[0] == "流浪地球"


def test_tmdb_queries_empty_title():
    """空标题返回空列表"""
    assert builder.build_tmdb_queries("") == []


def test_tmdb_queries_no_aliases():
    """无别名时仅返回原始标题"""
    result = builder.build_tmdb_queries("测试影片")
    assert result == ["测试影片"]


def test_tmdb_queries_with_en_names():
    """英文名排在中文标题之后"""
    aliases = AliasSet(
        cn_names=["坐白车的女人"],
        en_names=["The Woman in the White Car"],
    )
    result = builder.build_tmdb_queries("坐白车的女人", aliases, "2024")
    assert result[0] == "坐白车的女人"
    assert "The Woman in the White Car" in result
    assert result.index("The Woman in the White Car") == 1


def test_tmdb_queries_with_jp_names():
    """日文名排在英文名之后"""
    aliases = AliasSet(
        cn_names=["进击的巨人"],
        en_names=["Attack on Titan"],
        jp_names=["進撃の巨人"],
    )
    result = builder.build_tmdb_queries("进击的巨人", aliases)
    assert result.index("Attack on Titan") < result.index("進撃の巨人")


def test_tmdb_queries_with_colon_title():
    """含冒号标题生成简化版本"""
    result = builder.build_tmdb_queries("哈利·波特：魔法石")
    assert "哈利·波特" in result
    assert "哈利·波特：魔法石" in result


def test_tmdb_queries_max_6():
    """列表长度不超过 6"""
    aliases = AliasSet(
        cn_names=["名1", "名2", "名3"],
        en_names=["Name1", "Name2", "Name3", "Name4"],
        jp_names=["名前1"],
    )
    result = builder.build_tmdb_queries("名1", aliases)
    assert len(result) <= 6


def test_tmdb_queries_no_duplicates():
    """列表中无重复项"""
    aliases = AliasSet(
        cn_names=["流浪地球"],
        en_names=["The Wandering Earth"],
    )
    result = builder.build_tmdb_queries("流浪地球", aliases)
    assert len(result) == len(set(result))


def test_tmdb_queries_chinese_colon():
    """中文冒号也能简化"""
    result = builder.build_tmdb_queries("星球大战：新希望")
    assert "星球大战" in result


def test_tmdb_queries_dash_separator():
    """破折号分隔也能简化"""
    result = builder.build_tmdb_queries("Spider-Man - No Way Home")
    assert "Spider-Man" in result


# === build_bt_queries ===

def test_bt_queries_en_name_with_year_first():
    """英文名+年份排在最前"""
    aliases = AliasSet(
        cn_names=["流浪地球2"],
        en_names=["The Wandering Earth 2"],
    )
    result = builder.build_bt_queries("流浪地球2", aliases, "2023", "movie")
    assert result[0] == "The Wandering Earth 2 2023"


def test_bt_queries_includes_original_title():
    """原始标题在列表中"""
    aliases = AliasSet(en_names=["The Wandering Earth 2"])
    result = builder.build_bt_queries("流浪地球2", aliases, "2023")
    assert "流浪地球2" in result


def test_bt_queries_empty_title():
    """空标题返回空列表"""
    assert builder.build_bt_queries("") == []


def test_bt_queries_no_aliases():
    """无别名时仅返回原始标题"""
    result = builder.build_bt_queries("测试影片")
    assert result == ["测试影片"]


def test_bt_queries_jp_name_for_anime():
    """动画资源包含日文名"""
    aliases = AliasSet(
        cn_names=["进击的巨人"],
        en_names=["Attack on Titan"],
        jp_names=["進撃の巨人"],
    )
    result = builder.build_bt_queries("进击的巨人", aliases, "2013", "tv")
    assert "進撃の巨人" in result


def test_bt_queries_no_duplicates():
    """BT 列表无重复"""
    aliases = AliasSet(
        cn_names=["流浪地球2"],
        en_names=["流浪地球2"],  # same as title
    )
    result = builder.build_bt_queries("流浪地球2", aliases, "2023")
    assert len(result) == len(set(result))


def test_bt_queries_en_without_year():
    """无年份时英文名不带年份"""
    aliases = AliasSet(en_names=["The Matrix"])
    result = builder.build_bt_queries("黑客帝国", aliases)
    assert result[0] == "The Matrix"


def test_bt_queries_simplified_en():
    """英文名含冒号时生成简化版"""
    aliases = AliasSet(en_names=["Harry Potter: The Sorcerer's Stone"])
    result = builder.build_bt_queries("哈利波特", aliases, "2001")
    assert "Harry Potter" in result


# === _simplify_title ===

def test_simplify_english_colon():
    """英文冒号分割"""
    assert builder._simplify_title("Harry Potter: The Sorcerer's Stone") == "Harry Potter"


def test_simplify_chinese_colon():
    """中文冒号分割"""
    assert builder._simplify_title("哈利·波特：魔法石") == "哈利·波特"


def test_simplify_dash():
    """破折号分割"""
    assert builder._simplify_title("Spider-Man - No Way Home") == "Spider-Man"


def test_simplify_no_separator():
    """无分隔符返回原标题"""
    assert builder._simplify_title("流浪地球") == "流浪地球"


def test_simplify_empty():
    """空字符串返回空"""
    assert builder._simplify_title("") == ""
