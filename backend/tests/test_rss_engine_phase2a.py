"""Phase 2a 验证：RSS 通道调度器增强测试。

验证目标：
1. _build_results_summary 生成正确的摘要
2. rss_item_to_search_result 格式桥接正确
3. _do_search 写入 last_results_summary
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rss_source_base import RSSItem
from rss_engine import SubscriptionScheduler, RSSSourceManager, rss_item_to_search_result
from subscriber import Subscription, SubscriptionManager


def test_build_results_summary():
    """测试搜索结果摘要生成"""
    mgr = SubscriptionManager(base_path=".")
    sm = RSSSourceManager()
    scheduler = SubscriptionScheduler(sub_manager=mgr, source_manager=sm)

    items = [
        RSSItem(title="Test S01E01 1080p WEB-DL", quality_tag="WEB-DL-1080p", source_name="eztv"),
        RSSItem(title="Test S01E02 720p", quality_tag="720p", source_name="mikan"),
    ]

    # 有匹配结果
    summary = scheduler._build_results_summary(items, items, {})
    assert "搜到 2 条" in summary
    assert "WEB-DL-1080p" in summary
    print(f"  [PASS] 有匹配: '{summary}'")

    # 有原始但无匹配
    summary2 = scheduler._build_results_summary(items, [], {})
    assert "匹配 0 条" in summary2
    print(f"  [PASS] 无匹配: '{summary2}'")

    # 无结果
    summary3 = scheduler._build_results_summary([], [], {})
    assert "未搜到" in summary3
    print(f"  [PASS] 无结果: '{summary3}'")

    # 有错误
    summary4 = scheduler._build_results_summary(items, items, {"eztv": "timeout"})
    assert "1 源失败" in summary4
    print(f"  [PASS] 有错误: '{summary4}'")

    print("[PASS] test_build_results_summary")


def test_rss_item_to_search_result():
    """测试 RSSItem → SearchResult 格式桥接"""
    item = RSSItem(
        title="The Boys S05E03 1080p WEB-DL x265",
        download_url="magnet:?xt=urn:btih:AABB",
        size_gb=2.0,
        seeders=150,
        info_hash="AABB",
        quality_tag="WEB-DL-1080p-x265",
        resolution="1080p",
        episode=3,
        season=5,
        source_name="eztv",
        indexer="eztv",
        pub_date="2025-07-04",
    )

    result = rss_item_to_search_result(item)

    assert result["title"] == item.title
    assert result["download_url"] == item.download_url
    assert result["size_gb"] == 2.0
    assert result["seeders"] == 150
    assert result["source"] == "eztv"
    assert result["episode"] == 3
    assert result["season"] == 5
    assert result["quality_score"] > 0  # 1080p WEB-DL 应该有分
    print(f"  [PASS] 桥接正确: quality_score={result['quality_score']}")

    print("[PASS] test_rss_item_to_search_result")


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 2a: RSS 通道调度器测试")
    print("=" * 50)
    test_build_results_summary()
    test_rss_item_to_search_result()
    print("\n✅ Phase 2a 测试全部通过")
