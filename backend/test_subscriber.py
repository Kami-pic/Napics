"""订阅管理器测试：CRUD + 指纹去重 + 下载完成回调 + 持久化。"""

import os
import json
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from subscriber import SubscriptionManager, Subscription

TEST_FILE = "test_subscriptions.json"


def cleanup():
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)


def test_crud():
    """测试基础 CRUD"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    # 新增电影订阅
    result = mgr.add({"title": "流浪地球3", "year": "2027", "type": "movie", "tmdb_id": 99999})
    assert result["status"] == "ok", f"新增失败: {result}"
    sub_id = result["subscription"]["id"]
    print(f"  [PASS] 新增电影订阅: {sub_id}")

    # 重复订阅检查
    result2 = mgr.add({"title": "流浪地球3", "year": "2027", "type": "movie", "tmdb_id": 99999})
    assert result2["status"] == "error", "重复订阅应该报错"
    print(f"  [PASS] 重复订阅拦截")

    # 查询单个
    sub = mgr.get(sub_id)
    assert sub is not None, "查询失败"
    assert sub.title == "流浪地球3"
    print(f"  [PASS] 查询单个订阅")

    # 查询全部
    all_subs = mgr.get_all()
    assert len(all_subs) == 1
    print(f"  [PASS] 查询全部订阅: {len(all_subs)} 条")

    # 更新
    result3 = mgr.update(sub_id, {"quality": "2160p", "mode": "auto"})
    assert result3["status"] == "ok"
    assert mgr.get(sub_id).quality == "2160p"
    assert mgr.get(sub_id).mode == "auto"
    print(f"  [PASS] 更新订阅")

    # 删除
    result4 = mgr.delete(sub_id)
    assert result4["status"] == "ok"
    assert mgr.get(sub_id) is None
    print(f"  [PASS] 删除订阅")

    # 删除不存在的
    result5 = mgr.delete("nonexistent")
    assert result5["status"] == "not_found"
    print(f"  [PASS] 删除不存在的订阅")

    cleanup()


def test_tv_subscription():
    """测试剧集订阅 + 集数追踪"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    result = mgr.add({
        "title": "进击的巨人",
        "year": "2013",
        "type": "tv",
        "tmdb_id": 1429,
        "season": 1,
        "total_episode": 25,
    })
    assert result["status"] == "ok"
    sub_id = result["subscription"]["id"]
    print(f"  [PASS] 新增剧集订阅: {sub_id}")

    # 下载完成回调 — 第 1 集
    mgr.on_download_complete(
        subscription_id=sub_id,
        episode=1,
        info_hash="hash_ep01",
        title="[SubGroup] Shingeki no Kyojin S01E01 1080p",
        quality_tag="WEB-DL-1080p-x265",
        source="prowlarr",
        channel="qb",
        task_id="task-001",
    )
    sub = mgr.get(sub_id)
    assert "1" in sub.downloaded_episodes
    assert sub.downloaded_episodes["1"].info_hash == "hash_ep01"
    assert sub.state == "active"  # 还没下完
    print(f"  [PASS] 下载回调 E01, state={sub.state}")

    # 下载完成回调 — 模拟全部下完
    for ep in range(2, 26):
        mgr.on_download_complete(
            subscription_id=sub_id,
            episode=ep,
            info_hash=f"hash_ep{ep:02d}",
            title=f"[SubGroup] S01E{ep:02d}",
            source="prowlarr",
            channel="qb",
            task_id=f"task-{ep:03d}",
        )
    sub = mgr.get(sub_id)
    assert sub.state == "completed"
    assert len(sub.downloaded_episodes) == 25
    print(f"  [PASS] 全部下载完成, state={sub.state}, episodes={len(sub.downloaded_episodes)}")

    cleanup()


def test_movie_auto_complete():
    """测试电影订阅下载完成自动标记 completed"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    result = mgr.add({"title": "沙丘3", "year": "2026", "type": "movie"})
    sub_id = result["subscription"]["id"]

    mgr.on_download_complete(
        subscription_id=sub_id,
        episode=None,
        info_hash="hash_dune3",
        title="Dune.Part.Three.2026.2160p.WEB-DL",
        quality_tag="WEB-DL-2160p-x265",
        source="prowlarr",
        channel="qb",
    )
    sub = mgr.get(sub_id)
    assert sub.state == "completed"
    assert "0" in sub.downloaded_episodes
    print(f"  [PASS] 电影下载完成自动 completed")

    cleanup()


def test_persistence():
    """测试持久化：保存后重新加载"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    mgr.add({"title": "测试片1", "year": "2026", "type": "movie"})
    mgr.add({"title": "测试剧1", "year": "2026", "type": "tv", "season": 1})

    # 重新加载
    mgr2 = SubscriptionManager(base_path=".")
    mgr2._file_path = TEST_FILE
    mgr2._load()

    assert len(mgr2.subscriptions) == 2
    assert mgr2.subscriptions[0].title == "测试片1"
    assert mgr2.subscriptions[1].title == "测试剧1"
    print(f"  [PASS] 持久化加载: {len(mgr2.subscriptions)} 条")

    cleanup()


def test_is_subscribed():
    """测试订阅状态检查"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    mgr.add({"title": "流浪地球3", "year": "2027", "type": "movie", "tmdb_id": 99999})

    assert mgr.is_subscribed(tmdb_id=99999) is True
    assert mgr.is_subscribed(tmdb_id=11111) is False
    assert mgr.is_subscribed(title="流浪地球3", year="2027") is True
    assert mgr.is_subscribed(title="不存在的片", year="2027") is False
    print(f"  [PASS] 订阅状态检查")

    cleanup()


def test_duplicate_episode_prevention():
    """测试同一集不会被重复记录（指纹覆盖）"""
    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    result = mgr.add({"title": "测试剧", "year": "2026", "type": "tv", "total_episode": 12})
    sub_id = result["subscription"]["id"]

    # 第一次下载 E01
    mgr.on_download_complete(sub_id, episode=1, info_hash="hash_v1", title="V1")
    # 同一集再次下载（洗版场景）
    mgr.on_download_complete(sub_id, episode=1, info_hash="hash_v2", title="V2")

    sub = mgr.get(sub_id)
    assert sub.downloaded_episodes["1"].info_hash == "hash_v2"  # 应该被覆盖
    assert len(sub.downloaded_episodes) == 1  # 不应该有两条
    print(f"  [PASS] 同集指纹覆盖（洗版兼容）")

    cleanup()


if __name__ == "__main__":
    print("=" * 50)
    print("订阅管理器测试")
    print("=" * 50)

    tests = [
        ("CRUD 基础操作", test_crud),
        ("剧集订阅 + 集数追踪", test_tv_subscription),
        ("电影自动完成", test_movie_auto_complete),
        ("持久化", test_persistence),
        ("订阅状态检查", test_is_subscribed),
        ("同集指纹覆盖", test_duplicate_episode_prevention),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            print(f"\n[TEST] {name}")
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"结果: {passed} 通过, {failed} 失败")
    cleanup()
