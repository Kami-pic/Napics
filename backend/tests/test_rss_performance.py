"""RSS 调度并发、缓存和通道隔离性能回归。"""

import shutil
import tempfile
import threading
import time

from rss_engine import (
    RSSSourceManager,
    SubscriptionScheduler,
    _search_cache,
)
from rss_source_base import RSSItem
from subscriber import Subscription


class FakeSubscriptionManager:
    def __init__(self):
        self.updates = []

    def update(self, subscription_id, data):
        self.updates.append((subscription_id, data))

    def get_all(self, state=None):
        return []

    def get(self, subscription_id):
        return None


class TimedRSSSource:
    display_name = "性能测试源"
    enabled = True

    def __init__(self, name: str, delay: float):
        self.name = name
        self.delay = delay
        self.calls = 0

    def fetch(self, subscription):
        self.calls += 1
        time.sleep(self.delay)
        return [RSSItem(
            title=f"{subscription.title} 1080p",
            download_url=f"magnet:?xt=urn:btih:{self.name}",
            info_hash=self.name,
            source_name=self.name,
        )]


def _make_subscription(subscription_id: str) -> Subscription:
    return Subscription(
        id=subscription_id,
        title="Performance Test",
        type="movie",
        aliases={"cn": [], "en": ["Performance Test"], "original": []},
    )


def test_multiple_rss_sources_fetch_in_parallel():
    """四个慢源应并行完成，而不是累加为串行耗时。"""
    _search_cache.clear()
    manager = RSSSourceManager()
    sources = [TimedRSSSource(f"parallel_{index}", 0.2) for index in range(4)]
    for source in sources:
        manager.register(source)
    scheduler = SubscriptionScheduler(
        FakeSubscriptionManager(),
        manager,
        max_source_workers=4,
        source_timeout_seconds=2,
    )
    subscription = _make_subscription("parallel")
    # 预热匹配和通知模块，基准只衡量多源网络聚合路径。
    from rss_matcher import match_items
    import notification_service
    match_items(
        [RSSItem(title="Performance Test 1080p", source_name="warmup")],
        subscription,
    )

    started = time.perf_counter()
    scheduler.search_one(subscription)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.55
    assert [source.calls for source in sources] == [1, 1, 1, 1]


def test_rss_result_cache_prevents_duplicate_fetch():
    """相同源和查询在缓存期内只发起一次真实请求。"""
    _search_cache.clear()
    manager = RSSSourceManager()
    source = TimedRSSSource("cache_once", 0.01)
    manager.register(source)
    scheduler = SubscriptionScheduler(FakeSubscriptionManager(), manager)
    subscription = _make_subscription("cache")

    scheduler.search_one(subscription)
    scheduler.search_one(subscription)

    assert source.calls == 1


def test_slow_source_respects_total_search_budget():
    """慢源超过总预算时不得阻塞已完成的快源。"""
    _search_cache.clear()
    manager = RSSSourceManager()
    fast = TimedRSSSource("budget_fast", 0.01)
    slow = TimedRSSSource("budget_slow", 0.5)
    manager.register(fast)
    manager.register(slow)
    scheduler = SubscriptionScheduler(
        FakeSubscriptionManager(),
        manager,
        max_source_workers=2,
        source_timeout_seconds=0.1,
    )

    started = time.perf_counter()
    scheduler.search_one(_make_subscription("budget"))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3
    assert fast.calls == 1


def test_direct_search_scheduler_is_not_blocked_by_rss_tick():
    """RSS 通道阻塞时，直搜调度线程仍应立即运行。"""
    scheduler = SubscriptionScheduler(
        FakeSubscriptionManager(),
        RSSSourceManager(),
        check_interval_seconds=60,
        search_interval_seconds=60,
    )
    rss_started = threading.Event()
    release_rss = threading.Event()
    search_started = threading.Event()

    def slow_rss_tick():
        rss_started.set()
        release_rss.wait(1)

    scheduler._tick = slow_rss_tick
    scheduler._tick_search = search_started.set
    scheduler.start()
    try:
        assert rss_started.wait(0.2)
        assert search_started.wait(0.2)
    finally:
        release_rss.set()
        scheduler.stop()


def test_subscription_aggregate_updates_are_atomic():
    """RSS 与直搜并发完成时，资源、日志和通知不能互相覆盖。"""
    from subscriber import (
        NotificationEntry,
        SearchLogEntry,
        SubscriptionManager,
    )

    directory = tempfile.mkdtemp(prefix="rss_atomic_", dir="tests")
    try:
        manager = SubscriptionManager(base_path=directory)
        manager.subscriptions.append(_make_subscription("atomic"))

        def append_batch(channel: str):
            for index in range(10):
                manager.merge_found_resources("atomic", [{
                    "title": f"{channel}-{index}",
                    "download_url": f"magnet:?xt={channel}-{index}",
                    "info_hash": f"{channel}-{index}",
                }])
                manager.append_search_log(
                    "atomic",
                    SearchLogEntry(channel=channel, summary=str(index)),
                )
                manager.append_notification(
                    "atomic",
                    NotificationEntry(type=channel, message=str(index)),
                )

        threads = [
            threading.Thread(target=append_batch, args=("rss",)),
            threading.Thread(target=append_batch, args=("search",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        subscription = manager.get("atomic")
        assert len(subscription.found_resources) == 20
        assert len(subscription.search_logs) == 20
        assert len(subscription.notifications) == 20
    finally:
        shutil.rmtree(directory, ignore_errors=True)
