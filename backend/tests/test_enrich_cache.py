"""测试 enrich_cache 核心逻辑（持久化缓存读写 + LRU 淘汰）"""
import os
import sys
import json
import tempfile
import threading

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(__file__))


def test_enrich_cache_put_and_read():
    """测试写入和读取 enrich_cache"""
    from discover_enrich import enrich_cache_put, _enrich_cache, _enrich_cache_lock

    # 写入一条
    enrich_cache_put("douban_12345", tmdb_id=550, en_title="Fight Club", tmdb_rating=8.4)

    with _enrich_cache_lock:
        entry = _enrich_cache.get("douban_12345")
    assert entry is not None, "缓存条目应存在"
    assert entry["en_title"] == "Fight Club"
    assert entry["tmdb_id"] == 550
    assert entry["tmdb_rating"] == 8.4
    assert "updated_at" in entry
    print("[PASS] enrich_cache_put 写入和读取正常")


def test_enrich_cache_key():
    """测试缓存 key 生成逻辑"""
    from discover_enrich import _enrich_cache_key

    # douban_id 优先
    assert _enrich_cache_key({"douban_id": "123", "tmdb_id": 456, "title": "T"}) == "douban_123"
    # 无 douban_id 时用 tmdb_id
    assert _enrich_cache_key({"tmdb_id": 456, "title": "T"}) == "tmdb_456"
    # 都没有时用 title_year
    assert _enrich_cache_key({"title": "Test", "year": "2024"}) == "title_Test_2024"
    print("[PASS] _enrich_cache_key 生成逻辑正确")


def test_enrich_cache_lru():
    """测试 LRU 淘汰（超过 MAX 时删除最旧的）"""
    import discover_enrich as discover
    # 临时调小 MAX
    old_max = discover._ENRICH_CACHE_MAX
    discover._ENRICH_CACHE_MAX = 5

    # 清空缓存
    with discover._enrich_cache_lock:
        discover._enrich_cache.clear()

    # 写入 7 条
    for i in range(7):
        discover.enrich_cache_put(f"test_{i}", en_title=f"Title {i}")
        import time; time.sleep(0.01)  # 确保 updated_at 不同

    with discover._enrich_cache_lock:
        count = len(discover._enrich_cache)
    assert count <= 5, f"缓存应不超过 5 条，实际 {count}"
    print(f"[PASS] LRU 淘汰正常，缓存 {count} 条")

    # 恢复
    discover._ENRICH_CACHE_MAX = old_max


if __name__ == "__main__":
    test_enrich_cache_key()
    test_enrich_cache_put_and_read()
    test_enrich_cache_lru()
    print("\n所有 enrich_cache 测试通过 ✓")
