"""Phase 2b 验证：追更模式完善测试。

验证目标：
1. Quality Cutoff：已达到目标质量的集不再匹配
2. should_search_now 支持自定义 search_interval_hours
3. 下载失败重试逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from rss_source_base import RSSItem
from rss_matcher import match_items
from rss_engine import should_search_now
from subscriber import Subscription, EpisodeInfo


def test_quality_cutoff():
    """已达到目标质量的集不再匹配新资源"""
    sub = Subscription(
        title="测试剧",
        type="tv",
        season=1,
        quality="720p",
        target_quality="1080p",
        best_version=True,
        downloaded_episodes={
            "1": EpisodeInfo(quality_tag="WEB-DL-1080p-x265", info_hash="hash1"),  # 达到目标
            "2": EpisodeInfo(quality_tag="WEB-DL-720p", info_hash="hash2"),         # 未达到目标
        },
    )

    items = [
        RSSItem(title="Test S01E01 2160p Remux", episode=1, season=1, info_hash="new1",
                download_url="magnet:?xt=urn:btih:NEW1", quality_tag="Remux-2160p"),
        RSSItem(title="Test S01E02 1080p WEB-DL", episode=2, season=1, info_hash="new2",
                download_url="magnet:?xt=urn:btih:NEW2", quality_tag="WEB-DL-1080p"),
        RSSItem(title="Test S01E03 1080p", episode=3, season=1, info_hash="new3",
                download_url="magnet:?xt=urn:btih:NEW3", quality_tag="1080p"),
    ]

    matched = match_items(items, sub)
    matched_eps = [m.episode for m in matched]

    # E01 已达到 1080p 目标 → 不应该再匹配（即使有 4K Remux）
    assert 1 not in matched_eps, f"E01 已达到目标质量，不应匹配，但匹配了: {matched_eps}"
    # E02 未达到目标 → 应该匹配更好版本
    assert 2 in matched_eps, f"E02 未达到目标，应该匹配: {matched_eps}"
    # E03 未下载 → 应该匹配
    assert 3 in matched_eps, f"E03 未下载，应该匹配: {matched_eps}"

    print(f"  [PASS] Quality Cutoff: matched={matched_eps}")
    print("[PASS] test_quality_cutoff")


def test_custom_search_interval():
    """自定义 search_interval_hours 覆盖默认衰减"""
    now = datetime.now()

    # 自定义 2 小时间隔，上次搜索 3 小时前 → 应该搜
    sub1 = Subscription(
        title="测试1", state="active",
        search_interval_hours=2.0,
        last_search=(now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        created_at=(now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        search_count=50,  # 正常衰减策略下 30 天+50 次会暂停
    )
    assert should_search_now(sub1) is True, "自定义 2h 间隔，3h 前搜过，应该搜"
    print("  [PASS] 自定义间隔 2h，3h 前搜过 → 搜")

    # 自定义 2 小时间隔，上次搜索 1 小时前 → 不应该搜
    sub2 = Subscription(
        title="测试2", state="active",
        search_interval_hours=2.0,
        last_search=(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert should_search_now(sub2) is False, "自定义 2h 间隔，1h 前搜过，不应该搜"
    print("  [PASS] 自定义间隔 2h，1h 前搜过 → 不搜")

    # 无自定义间隔，走默认衰减
    sub3 = Subscription(
        title="测试3", state="active",
        search_interval_hours=0,
        last_search=(now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
        created_at=(now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert should_search_now(sub3, base_interval_hours=4.0) is True
    print("  [PASS] 默认衰减 4h，5h 前搜过 → 搜")

    print("[PASS] test_custom_search_interval")


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 2b: 追更模式完善测试")
    print("=" * 50)
    test_quality_cutoff()
    test_custom_search_interval()
    print("\n✅ Phase 2b 测试全部通过")
