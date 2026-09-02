"""搜索关键词里的年份处理。

用户报的现象：输入「XXX2011」这种带年份的词，期望能去掉年份再独立搜一次，
实际却变成搜「2011」。实测下来两种输入各有各的病，而且和直觉正好相反：

  「沙丘 2011」（带空格）→ split_by_language 拆成 cn="沙丘" en="2011"
      它判断数字归中文还是英文只看紧邻的前后一个 token，而空格本身就是一个
      token，把邻接关系切断了。prowlarr / bitsearch / yts / 1337x 的语言优先级
      第一位是 en，于是第一个搜索词就是「2011」，搜出一堆 2011 年的片、
      命中即短路，真正的「沙丘」永远轮不到。
  「沙丘2011」（没空格）→ cn="沙丘2011" 整串去搜，BT 站基本搜不到，
      而回退链里根本没有「去掉年份再搜一次」这一步。

split_by_language 本身没动（compute_junk_flags、extract_variants 等一堆地方都在
用它），处理放在搜索词这一层。
"""
import pytest

from search_keyword_mapper import (
    MultiLangKeywords, get_search_keywords_for_source,
    is_bare_year, strip_trailing_year,
)
from search_service import build_keywords


# ── 基础判定 ──

@pytest.mark.parametrize("text", ["2011", " 2011 ", "(2011)", "[1999]", "（2024）"])
def test_is_bare_year_true(text):
    assert is_bare_year(text)


@pytest.mark.parametrize("text", ["沙丘2011", "2011太空漫游", "Dune 2011", "", "20110", "abc"])
def test_is_bare_year_false(text):
    assert not is_bare_year(text)


def test_strip_trailing_year_handles_both_spacings():
    assert strip_trailing_year("沙丘 2011") == "沙丘"
    assert strip_trailing_year("沙丘2011") == "沙丘"   # \s* 可为零宽
    assert strip_trailing_year("Dune (2021)") == "Dune"


def test_strip_trailing_year_keeps_year_only_titles():
    """1917 / 2012 是真片名，不能剥成空串。"""
    assert strip_trailing_year("1917") == "1917"
    assert strip_trailing_year("2012") == "2012"


def test_strip_trailing_year_keeps_leading_year():
    """年份在开头的是片名的一部分。"""
    assert strip_trailing_year("2001太空漫游") == "2001太空漫游"


# ── build_keywords：纯年份不能成为搜索词 ──

def test_spaced_year_does_not_become_the_english_keyword():
    """这条是原 bug 的直接复现。"""
    kw = build_keywords(query="沙丘 2011")
    assert kw.en != "2011"
    assert kw.en == ""
    assert kw.cn == "沙丘"
    # 摘下来的年份转成 year 信号，不浪费
    assert kw.year == "2011"


def test_explicit_year_argument_wins_over_parsed_one():
    kw = build_keywords(query="沙丘 2011", year="2021")
    assert kw.year == "2021"
    assert kw.en == ""


def test_year_only_query_still_searchable():
    """输入就是「1917」时不能把搜索词清空 —— 那是真片名。"""
    kw = build_keywords(query="1917")
    assert get_search_keywords_for_source("prowlarr", kw), "搜索词不能为空"


# ── 回退链 ──

def test_fallback_chain_never_contains_bare_year():
    kw = MultiLangKeywords(cn="沙丘", en="2011", query="沙丘 2011")
    for source in ("prowlarr", "bitsearch", "yts", "1337x", "cilixiong"):
        chain = get_search_keywords_for_source(source, kw)
        assert "2011" not in chain, f"{source} 的回退链里出现了纯年份: {chain}"


def test_fallback_chain_first_word_is_the_title_not_the_year():
    """en 优先的源也必须先搜片名。"""
    kw = build_keywords(query="沙丘 2011")
    chain = get_search_keywords_for_source("prowlarr", kw)
    assert chain[0] == "沙丘"


def test_fallback_chain_adds_de_yeared_variant():
    """「沙丘2011」这种紧贴写法，回退链里要有去掉年份的那一版。"""
    kw = MultiLangKeywords(cn="沙丘2011", query="沙丘2011")
    chain = get_search_keywords_for_source("cilixiong", kw)
    assert "沙丘2011" in chain
    assert "沙丘" in chain, f"缺少去年份变体: {chain}"


def test_de_yeared_variant_not_added_when_nothing_to_strip():
    kw = MultiLangKeywords(cn="沙丘", en="Dune", query="沙丘")
    chain = get_search_keywords_for_source("cilixiong", kw)
    assert chain == ["沙丘", "Dune"]


def test_season_number_still_appended():
    """去年份不能把季号拼接搞坏。"""
    kw = MultiLangKeywords(cn="某剧2020", season_number=2, query="某剧2020")
    chain = get_search_keywords_for_source("cilixiong", kw)
    assert chain[0] == "某剧2020 第2季"
    assert "某剧 第2季" in chain


# ── 相关性词 ──

def test_relevance_terms_exclude_bare_year():
    """纯年份当相关性词的话，标题里含 2011 的什么片都算「相关」。"""
    from search_service import _build_relevance_terms

    terms = _build_relevance_terms(MultiLangKeywords(cn="沙丘", en="2011", query="沙丘 2011"))
    assert "2011" not in terms
    assert "沙丘" in terms
