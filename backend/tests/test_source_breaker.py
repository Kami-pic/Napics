"""数据源熔断 + 未配置 API Key 时跳过

解决的实际问题：TMDB 没配 Key（或国内直连不通）时，每次请求都要白等一次超时，
把发现页整体拖慢。豆瓣早就返回了却要陪着等。
"""
import time

import pytest

from core.source_breaker import SourceBreaker


@pytest.fixture
def breaker():
    return SourceBreaker(threshold=3, cooldown_seconds=1.0)


def test_not_open_initially(breaker):
    assert breaker.is_open("tmdb") is False


def test_opens_after_threshold_failures(breaker):
    breaker.record_failure("tmdb")
    breaker.record_failure("tmdb")
    assert breaker.is_open("tmdb") is False, "未达阈值不应熔断"
    breaker.record_failure("tmdb")
    assert breaker.is_open("tmdb") is True, "达到阈值应熔断"


def test_success_resets_failures(breaker):
    breaker.record_failure("tmdb")
    breaker.record_failure("tmdb")
    breaker.record_success("tmdb")
    breaker.record_failure("tmdb")
    assert breaker.is_open("tmdb") is False, "成功后计数应重置"


def test_cooldown_expires_and_allows_retry(breaker):
    for _ in range(3):
        breaker.record_failure("tmdb")
    assert breaker.is_open("tmdb") is True
    time.sleep(1.1)
    assert breaker.is_open("tmdb") is False, "冷却结束应放行试探"


def test_sources_are_independent(breaker):
    for _ in range(3):
        breaker.record_failure("tmdb")
    assert breaker.is_open("tmdb") is True
    assert breaker.is_open("douban") is False, "熔断不应影响其他源"


def test_remaining_cooldown_reported(breaker):
    for _ in range(3):
        breaker.record_failure("tmdb")
    assert 0 < breaker.remaining_cooldown("tmdb") <= 1.0


def test_reset_clears_state(breaker):
    for _ in range(3):
        breaker.record_failure("tmdb")
    breaker.reset("tmdb")
    assert breaker.is_open("tmdb") is False


# ── 未配置 API Key 时不应发请求 ──

def test_tmdb_skipped_when_api_key_empty(monkeypatch, caplog):
    """TMDB Key 为空时应直接跳过该源，而不是发请求白等一次超时"""
    import logging

    import combined_recommend
    import shared
    from core.source_breaker import metadata_breaker

    metadata_breaker.reset()
    monkeypatch.setattr(shared.config_m.config, "tmdb_api_key", "")

    # 其余源直接失败，隔离出 TMDB 的行为
    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(combined_recommend.douban_api_v2, "movie_hot", boom, raising=False)
    monkeypatch.setattr(combined_recommend.douban_api_v2, "tv_hot", boom, raising=False)
    monkeypatch.setattr(combined_recommend.douban_api_v2, "tv_animation", boom, raising=False)
    monkeypatch.setattr(combined_recommend.bangumi_client, "get_hot_anime", boom, raising=False)

    with caplog.at_level(logging.INFO, logger="combined_recommend"):
        result = combined_recommend.get_combined_recommend()

    assert isinstance(result, list)
    assert any("未配置 TMDB API Key" in r.message for r in caplog.records), \
        "未配置 Key 时应记录跳过日志，而不是照样发请求"


def test_tmdb_attempted_when_api_key_present(monkeypatch, caplog):
    """配了 Key 时不应出现「跳过」日志（确认判断没写反）"""
    import logging

    import combined_recommend
    import shared
    from core.source_breaker import metadata_breaker

    metadata_breaker.reset()
    monkeypatch.setattr(shared.config_m.config, "tmdb_api_key", "dummy-key-for-test")

    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(combined_recommend.douban_api_v2, "movie_hot", boom, raising=False)
    monkeypatch.setattr(combined_recommend.douban_api_v2, "tv_hot", boom, raising=False)
    monkeypatch.setattr(combined_recommend.douban_api_v2, "tv_animation", boom, raising=False)
    monkeypatch.setattr(combined_recommend.bangumi_client, "get_hot_anime", boom, raising=False)

    with caplog.at_level(logging.INFO, logger="combined_recommend"):
        combined_recommend.get_combined_recommend()

    assert not any("未配置 TMDB API Key" in r.message for r in caplog.records)
