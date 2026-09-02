"""搜索结果的年份信号。

match_chain（BT 搜索实际使用的评分函数）签名里连 year 都没有，重名不同年的两部片
得分完全一样 —— 而重名影片非常多，用户就是靠年份区分的。extract_bt_title_for_match
甚至会主动把年份从标题里删掉。

这里的设计取舍：**年份只加分，不减分、不改 junk 判定**。BT 标题里的年份不完全可靠
（有的标发行年、有的标制作年、合集标第一部的年份），拿它去否决结果会把本来能用的
搜索结果藏起来。同年的排到前面就够了。
"""
import pytest

from search_helpers import _YEAR_BONUS, apply_year_signal, enrich_result
from searcher import SearchResult


_hash_seq = iter(range(1000))


def _result(title: str) -> SearchResult:
    # download_url 必须各不相同：enhanced_search 会按它去重
    suffix = f"{next(_hash_seq):04d}"
    return SearchResult(
        title=title, size_gb=10.0, indexer="test", seeders=50, leechers=1,
        download_url="magnet:?xt=urn:btih:" + ("a" * 36) + suffix, info_url="",
        quality_tag="", quality=None, quality_rank=0,
    )


# ── apply_year_signal 本身 ──

def test_same_year_adds_bonus():
    d = {"title": "Dune.2021.1080p.BluRay.x265", "match_score": 70}
    apply_year_signal(d, "2021")
    assert d["year_match"] is True
    assert d["bt_year"] == "2021"
    assert d["match_score"] == 70 + _YEAR_BONUS


def test_one_year_off_still_counts_as_match():
    """发行年 vs 首播年常差 1 年。"""
    d = {"title": "Dune.2022.1080p.BluRay.x265", "match_score": 70}
    apply_year_signal(d, "2021")
    assert d["year_match"] is True


def test_year_mismatch_does_not_reduce_score():
    """这是整个设计的核心：年份对不上只标记，绝不扣分。"""
    d = {"title": "Dune.1984.1080p.BluRay.x265", "match_score": 70}
    apply_year_signal(d, "2021")
    assert d["year_match"] is False
    assert d["match_score"] == 70, "年份不匹配不能扣分"


def test_bonus_is_clamped_at_100():
    d = {"title": "Dune.2021.1080p", "match_score": 95}
    apply_year_signal(d, "2021")
    assert d["match_score"] == 100


def test_unparseable_years_are_neutral():
    for title, target in [
        ("Some.Release.Without.Year.1080p", "2021"),   # 标题没年份
        ("Dune.2021.1080p", ""),                       # 目标没年份
        ("Dune.2021.1080p", "不是年份"),                 # 目标解析不出
    ]:
        d = {"title": title, "match_score": 70}
        apply_year_signal(d, target)
        assert d["year_match"] is None, title
        assert d["match_score"] == 70, title


# ── enrich_result 集成 ──

def test_enrich_without_year_behaves_exactly_as_before():
    """不传 year 时不能有任何行为变化 —— 所有现有调用方都不传。"""
    r = _result("Dune.2021.1080p.BluRay.x265-GROUP")
    baseline = enrich_result(r, "Dune")
    assert "year_match" not in baseline
    assert "bt_year" not in baseline


def test_enrich_with_year_ranks_same_year_higher():
    """同名不同年的两条结果，同年的那条分更高 —— 用户的原始诉求。"""
    same = enrich_result(_result("Dune.2021.1080p.BluRay.x265"), "Dune", target_year="2021")
    other = enrich_result(_result("Dune.1984.1080p.BluRay.x265"), "Dune", target_year="2021")
    assert same["match_score"] > other["match_score"]
    assert same["year_match"] is True
    assert other["year_match"] is False


def test_year_mismatch_is_not_marked_junk():
    """年份对不上的结果照旧显示，只是排在后面。"""
    d = enrich_result(_result("Dune.1984.1080p.BluRay.x265"), "Dune", target_year="2021")
    assert not any("year" in reason for reason in d["junk_reasons"])


# ── SecondaryMatcher 的年份关卡与降级 ──

def test_secondary_matcher_year_gate_is_reachable():
    """matcher 里的年份关卡原来是空跑的：两个调用点都硬编码 target_year=""。"""
    from secondary_matcher import SecondaryMatcher

    matcher = SecondaryMatcher()
    assert matcher.match("Dune.2021.1080p.BluRay.x265", ["Dune"], target_year="2021").passed
    assert not matcher.match("Dune.1984.1080p.BluRay.x265", ["Dune"], target_year="2021").passed
    # 不传年份时照旧全过 —— 降级路径依赖这个行为
    assert matcher.match("Dune.1984.1080p.BluRay.x265", ["Dune"], target_year="").passed


def test_enhanced_search_falls_back_when_year_filters_everything(monkeypatch):
    """年份过滤后一条不剩时退回不带年份的结果。

    BT 标题的年份不完全可靠，宁可放宽也不要把本来能用的结果全过滤掉 ——
    否则「传年份」这个改动会让搜索从"有结果"变成"没结果"。
    """
    import searcher
    from alias_resolver import AliasSet

    # 全部结果的年份都和目标差很远。标题用长名字：match_chain 对 <=4 字符的
    # 短名字会跳过 contains/fuzzy，短名字的话标题关卡本身就过不了，测不到年份这一层。
    results = [_result(f"The.Wandering.Earth.1984.1080p.BluRay.x265-G{i}") for i in range(3)]

    class FakeClient:
        def search(self, keyword):
            return list(results)

        def get_indexer_priorities(self):
            return {}

    resp = searcher.enhanced_search(
        client=FakeClient(), title="The Wandering Earth", aliases=AliasSet(),
        year="2021", media_type="movie",
    )
    assert len(resp.results) == 3, "年份过滤后为空时必须退回不带年份的结果"
