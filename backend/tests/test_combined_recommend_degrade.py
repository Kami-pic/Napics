"""发现页在数据源不可达时必须降级，而不是抛异常导致 500

真机现象（容器无外网）：
  [Errno 101] Network is unreachable
  TimeoutError: 2 (of 3) futures unfinished
  GET /discover/recommend/combined -> 500 Internal Server Error

根因：as_completed 的 timeout 是在迭代器上抛 TimeoutError 的，
原代码的 try 只包住了 future.result()，异常直接冒到路由层。
"""
import time

import pytest

import combined_recommend


@pytest.fixture(autouse=True)
def _no_local_state(monkeypatch):
    """屏蔽本地媒体库与缓存注入，隔离测试"""
    monkeypatch.setattr(combined_recommend, "_dedup_and_merge",
                        lambda items: [i for i, _ in items] if items and isinstance(items[0], tuple) else items,
                        raising=False)


def test_sources_unreachable_does_not_raise(monkeypatch):
    """数据源失败（模拟 Network is unreachable）时不能抛异常，必须返回列表。

    这里不断言结果为空：本机跑测试时 TMDB 可能真的联通，
    关键契约是「不抛异常」而不是「一定没有数据」。
    """
    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(combined_recommend.douban_api_v2, "get_hot_list", boom, raising=False)
    monkeypatch.setattr(combined_recommend.bangumi_client, "get_hot_anime", boom, raising=False)

    result = combined_recommend.get_combined_recommend()
    assert isinstance(result, list)


def test_slow_source_does_not_break_whole_page(monkeypatch):
    """某个源卡住超过 as_completed 超时：不能抛 TimeoutError"""
    def very_slow(*a, **k):
        time.sleep(30)
        return []

    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(combined_recommend, "_TARGET_COUNT", 10, raising=False)
    monkeypatch.setattr(combined_recommend.douban_api_v2, "get_hot_list", very_slow, raising=False)
    monkeypatch.setattr(combined_recommend.bangumi_client, "get_hot_anime", boom, raising=False)

    # 关键断言：不抛异常
    started = time.time()
    result = combined_recommend.get_combined_recommend()
    elapsed = time.time() - started

    assert isinstance(result, list)
    # 不应该等满 30 秒（shutdown 不等待未完成线程）
    assert elapsed < 25, f"接口被慢源拖住了 {elapsed:.1f}s"


def test_route_returns_200_when_sources_fail(monkeypatch):
    """路由层：数据源全挂时也要 200 + 空数据，不能 500"""
    from fastapi.testclient import TestClient
    from main import app

    def boom(*a, **k):
        raise OSError(101, "Network is unreachable")

    monkeypatch.setattr(combined_recommend.douban_api_v2, "get_hot_list", boom, raising=False)
    monkeypatch.setattr(combined_recommend.bangumi_client, "get_hot_anime", boom, raising=False)

    client = TestClient(app)
    r = client.get("/discover/recommend/combined", params={"start": 0, "count": 30})
    assert r.status_code == 200, f"数据源不可达时不应 500，实际 {r.status_code}"
