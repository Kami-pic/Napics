"""Tests for AliasResolver"""
import pytest
from alias_resolver import AliasSet, AliasResolver, _classify_name, _merge_alias_set


# ── Mock clients ──

class MockDoubanClient:
    def __init__(self, results=None, should_fail=False):
        self._results = results or []
        self._should_fail = should_fail
        self.call_count = 0

    def search(self, query):
        self.call_count += 1
        if self._should_fail:
            raise ConnectionError("douban unavailable")
        return self._results


class MockBangumiClient:
    def __init__(self, results=None, should_fail=False):
        self._results = results or []
        self._should_fail = should_fail
        self.call_count = 0

    def search(self, query, type_filter=0):
        self.call_count += 1
        if self._should_fail:
            raise ConnectionError("bangumi unavailable")
        return self._results


# ── classify_name tests ──

def test_classify_chinese():
    assert _classify_name("流浪地球") == "cn"

def test_classify_english():
    assert _classify_name("The Wandering Earth") == "en"

def test_classify_japanese():
    assert _classify_name("となりのトトロ") == "jp"

def test_classify_mixed_cn():
    assert _classify_name("坐白车的女人") == "cn"


# ── resolve: original title always in cn_names ──

def test_resolve_includes_original_title():
    douban = MockDoubanClient()
    bangumi = MockBangumiClient()
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("流浪地球2", year="2023")
    assert "流浪地球2" in result.cn_names

def test_resolve_empty_title_returns_empty():
    resolver = AliasResolver(douban=MockDoubanClient(), bangumi=MockBangumiClient())
    result = resolver.resolve("")
    assert result.cn_names == []
    assert result.en_names == []


# ── resolve: douban subtitle extraction ──

def test_resolve_extracts_douban_subtitle():
    douban = MockDoubanClient(results=[
        {"title": "流浪地球2", "subtitle": "The Wandering Earth 2", "year": "2023"},
    ])
    bangumi = MockBangumiClient()
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("流浪地球2", year="2023")
    assert "The Wandering Earth 2" in result.en_names
    assert "流浪地球2" in result.cn_names

def test_resolve_douban_subtitle_with_slash():
    douban = MockDoubanClient(results=[
        {"title": "千与千寻", "subtitle": "千と千尋の神隠し / Spirited Away", "year": "2001"},
    ])
    bangumi = MockBangumiClient()
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("千与千寻")
    assert "Spirited Away" in result.en_names
    assert "千と千尋の神隠し" in result.jp_names


# ── resolve: bangumi original_title extraction ──

def test_resolve_extracts_bangumi_original():
    douban = MockDoubanClient()
    bangumi = MockBangumiClient(results=[
        {"title": "进击的巨人", "original_title": "進撃の巨人", "year": "2013"},
    ])
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("进击的巨人")
    assert "進撃の巨人" in result.jp_names


# ── caching ──

def test_resolve_caches_results():
    douban = MockDoubanClient(results=[
        {"title": "流浪地球2", "subtitle": "The Wandering Earth 2", "year": "2023"},
    ])
    bangumi = MockBangumiClient()
    resolver = AliasResolver(douban=douban, bangumi=bangumi)

    result1 = resolver.resolve("流浪地球2")
    result2 = resolver.resolve("流浪地球2")

    assert result1 is result2
    assert douban.call_count == 1
    assert bangumi.call_count == 1


# ── graceful degradation ──

def test_resolve_douban_failure_skipped():
    douban = MockDoubanClient(should_fail=True)
    bangumi = MockBangumiClient(results=[
        {"title": "进击的巨人", "original_title": "進撃の巨人", "year": "2013"},
    ])
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("进击的巨人")
    # Should still have original title and bangumi data
    assert "进击的巨人" in result.cn_names
    assert "進撃の巨人" in result.jp_names

def test_resolve_bangumi_failure_skipped():
    douban = MockDoubanClient(results=[
        {"title": "流浪地球2", "subtitle": "The Wandering Earth 2", "year": "2023"},
    ])
    bangumi = MockBangumiClient(should_fail=True)
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("流浪地球2")
    assert "流浪地球2" in result.cn_names
    assert "The Wandering Earth 2" in result.en_names

def test_resolve_both_fail_still_returns_original():
    douban = MockDoubanClient(should_fail=True)
    bangumi = MockBangumiClient(should_fail=True)
    resolver = AliasResolver(douban=douban, bangumi=bangumi)
    result = resolver.resolve("测试影片")
    assert "测试影片" in result.cn_names
    assert result.en_names == []
    assert result.jp_names == []


# ── merge_alias_set ──

def test_merge_deduplicates():
    target = AliasSet(cn_names=["流浪地球"], en_names=["Earth"])
    source = AliasSet(cn_names=["流浪地球", "流浪地球2"], en_names=["Earth", "Wandering"])
    _merge_alias_set(target, source)
    assert target.cn_names == ["流浪地球", "流浪地球2"]
    assert target.en_names == ["Earth", "Wandering"]


def test_disabled_sources_are_not_called():
    douban = MockDoubanClient(should_fail=True)
    bangumi = MockBangumiClient(should_fail=True)
    resolver = AliasResolver(
        douban=douban,
        bangumi=bangumi,
        enable_douban=False,
        enable_bangumi=False,
    )

    result = resolver.resolve("测试影片")

    assert result.cn_names == ["测试影片"]
