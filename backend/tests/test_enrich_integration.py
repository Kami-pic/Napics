"""
C+E 方案综合集成测试：TMDB 英文名补全 + 持久化缓存
运行方式：python test_enrich_integration.py（在 backend/ 目录下）
"""
import os
import sys
import json
import time
import tempfile
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# 确保 backend 目录在 import 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

results = []


def record(name, passed, detail=""):
    tag = "[PASS]" if passed else "[FAIL]"
    msg = f"{tag} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append((name, passed, detail))


# ══════════════════════════════════════════════════════════════
# 测试 1：enrich_cache 持久化（写入 → 保存 → 清空 → 加载 → 验证恢复）
# ══════════════════════════════════════════════════════════════
def test_enrich_cache_persistence():
    import discover_enrich as disc

    # 保存原始状态
    orig_cache = disc._enrich_cache.copy()
    orig_path = disc._ENRICH_CACHE_PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        disc._ENRICH_CACHE_PATH = tmp.name

        # 写入测试数据
        disc._enrich_cache = {
            "douban_100": {
                "tmdb_id": 550,
                "en_title": "Fight Club",
                "original_title": "",
                "tmdb_rating": 8.4,
                "updated_at": datetime.now().isoformat(),
            },
            "tmdb_200": {
                "tmdb_id": 200,
                "en_title": "Inception",
                "original_title": "",
                "tmdb_rating": 8.8,
                "updated_at": datetime.now().isoformat(),
            },
            "douban_300": {
                "tmdb_id": 300,
                "en_title": "Parasite",
                "original_title": "기생충",
                "tmdb_rating": 8.6,
                "updated_at": datetime.now().isoformat(),
            },
        }

        # _save_enrich_cache 是异步线程写入，这里直接同步写入以确保可靠
        with open(disc._ENRICH_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(disc._enrich_cache, f, ensure_ascii=False)

        # 清空内存
        disc._enrich_cache = {}
        assert len(disc._enrich_cache) == 0, "清空后应为空"

        # 加载
        disc._load_enrich_cache()

        # 验证
        assert len(disc._enrich_cache) == 3, f"应恢复 3 条，实际 {len(disc._enrich_cache)}"
        assert disc._enrich_cache["douban_100"]["en_title"] == "Fight Club"
        assert disc._enrich_cache["tmdb_200"]["en_title"] == "Inception"
        assert disc._enrich_cache["douban_300"]["original_title"] == "기생충"

        record("1. enrich_cache 持久化", True)
    except Exception as e:
        record("1. enrich_cache 持久化", False, str(e))
    finally:
        # 恢复
        disc._enrich_cache = orig_cache
        disc._ENRICH_CACHE_PATH = orig_path
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════
# 测试 2：_inject_clean_names 缓存命中路径
# ══════════════════════════════════════════════════════════════
def test_inject_clean_names_cache_hit():
    import discover_enrich as disc

    orig_cache = disc._enrich_cache.copy()
    try:
        # 预写入缓存
        disc._enrich_cache["douban_123"] = {
            "tmdb_id": 550,
            "en_title": "The Shawshank Redemption",
            "original_title": "",
            "tmdb_rating": 9.3,
            "updated_at": datetime.now().isoformat(),
        }

        items = [{
            "title": "肖申克的救赎",
            "douban_id": "123",
            "media_type": "movie",
            "year": "1994",
        }]

        # mock _tmdb_client 确保不会被调用（缓存命中后 en 已有值，不进 need_enrich）
        with patch.object(disc, "_tmdb_client") as mock_tmdb:
            disc.inject_clean_names(items)
            # _tmdb_client 不应被调用（因为缓存命中后 en 已有值，不进 need_enrich 列表）
            # 注意：_tmdb_client 只在 need_enrich 非空时才被调用

        assert items[0].get("clean_name_en") == "The Shawshank Redemption", \
            f"期望 'The Shawshank Redemption'，实际 '{items[0].get('clean_name_en')}'"
        assert items[0].get("clean_name_cn"), "应有 clean_name_cn"

        record("2. _inject_clean_names 缓存命中", True)
    except Exception as e:
        record("2. _inject_clean_names 缓存命中", False, str(e))
    finally:
        disc._enrich_cache = orig_cache


# ══════════════════════════════════════════════════════════════
# 测试 3：_inject_clean_names 缓存未命中 + 同步补全
# ══════════════════════════════════════════════════════════════
def test_inject_clean_names_cache_miss_sync():
    import discover_enrich as disc

    orig_cache = disc._enrich_cache.copy()
    try:
        disc._enrich_cache = {}

        # 构造 fake tmdb 对象
        fake_tmdb = MagicMock()
        fake_tmdb.search_movie.return_value = [
            {"id": 550, "original_title": "Fight Club", "vote_average": 8.4}
        ]
        fake_tmdb.get_english_title.return_value = "Fight Club"

        items = [{
            "title": "搏击俱乐部",
            "douban_id": "99999",
            "media_type": "movie",
        }]

        with patch.object(disc, "_tmdb_client", return_value=fake_tmdb):
            disc.inject_clean_names(items)

        assert items[0].get("clean_name_en") == "Fight Club", \
            f"期望 'Fight Club'，实际 '{items[0].get('clean_name_en')}'"
        assert "douban_99999" in disc._enrich_cache, \
            f"enrich_cache 应包含 douban_99999，实际 keys: {list(disc._enrich_cache.keys())}"
        assert disc._enrich_cache["douban_99999"]["en_title"] == "Fight Club"

        record("3. _inject_clean_names 缓存未命中+同步补全", True)
    except Exception as e:
        record("3. _inject_clean_names 缓存未命中+同步补全", False, str(e))
    finally:
        disc._enrich_cache = orig_cache


# ══════════════════════════════════════════════════════════════
# 测试 4：_sync_enrich_english_names 超时降级
# ══════════════════════════════════════════════════════════════
def test_sync_enrich_timeout():
    import discover_enrich as disc

    orig_cache = disc._enrich_cache.copy()
    try:
        disc._enrich_cache = {}

        def slow_search(title):
            time.sleep(5)
            return [{"id": 1, "original_title": "Slow Movie", "vote_average": 5.0}]

        fake_tmdb = MagicMock()
        fake_tmdb.search_movie.side_effect = slow_search

        item = {
            "title": "超慢电影",
            "douban_id": "88888",
            "media_type": "movie",
            "clean_name_en": "",
        }

        timed_out = disc._sync_enrich_english_names([item], fake_tmdb, timeout=0.5)

        assert len(timed_out) > 0, f"应有超时条目，实际 timed_out={len(timed_out)}"
        assert item.get("clean_name_en", "") == "", \
            f"超时条目 clean_name_en 应为空，实际 '{item.get('clean_name_en')}'"

        record("4. _sync_enrich_english_names 超时降级", True)
    except Exception as e:
        record("4. _sync_enrich_english_names 超时降级", False, str(e))
    finally:
        disc._enrich_cache = orig_cache


# ══════════════════════════════════════════════════════════════
# 测试 5：enrich_cache_put 回写验证（模拟 media_info 场景）
# ══════════════════════════════════════════════════════════════
def test_enrich_cache_put():
    import discover_enrich as disc

    orig_cache = disc._enrich_cache.copy()
    orig_path = disc._ENRICH_CACHE_PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        # 用临时文件避免污染真实缓存
        disc._ENRICH_CACHE_PATH = tmp.name
        disc._enrich_cache = {}

        disc.enrich_cache_put(
            "douban_777",
            tmdb_id=100,
            en_title="Test Movie",
            tmdb_rating=7.5,
        )

        assert "douban_777" in disc._enrich_cache, "应包含 douban_777"
        entry = disc._enrich_cache["douban_777"]
        assert entry["tmdb_id"] == 100, f"tmdb_id 应为 100，实际 {entry['tmdb_id']}"
        assert entry["en_title"] == "Test Movie", f"en_title 应为 'Test Movie'，实际 '{entry['en_title']}'"
        assert entry["tmdb_rating"] == 7.5, f"tmdb_rating 应为 7.5，实际 {entry['tmdb_rating']}"
        assert "updated_at" in entry, "应有 updated_at 字段"

        record("5. enrich_cache_put 回写验证", True)
    except Exception as e:
        record("5. enrich_cache_put 回写验证", False, str(e))
    finally:
        disc._enrich_cache = orig_cache
        disc._ENRICH_CACHE_PATH = orig_path
        # 等一下异步写入线程完成
        time.sleep(0.3)
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════
# 测试 6：LRU 淘汰边界测试
# ══════════════════════════════════════════════════════════════
def test_lru_eviction():
    import discover_enrich as disc

    orig_cache = disc._enrich_cache.copy()
    orig_max = disc._ENRICH_CACHE_MAX
    orig_path = disc._ENRICH_CACHE_PATH

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        disc._ENRICH_CACHE_PATH = tmp.name
        disc._enrich_cache = {}
        disc._ENRICH_CACHE_MAX = 3

        # 写入 5 条，每条间隔一点时间确保 updated_at 不同
        for i in range(5):
            disc.enrich_cache_put(
                f"test_{i}",
                tmdb_id=i,
                en_title=f"Movie {i}",
                tmdb_rating=float(i),
            )
            time.sleep(0.05)  # 确保时间戳不同

        assert len(disc._enrich_cache) == 3, \
            f"应只保留 3 条，实际 {len(disc._enrich_cache)} 条: {list(disc._enrich_cache.keys())}"

        # 验证保留的是最新的 3 条（test_2, test_3, test_4）
        remaining_keys = set(disc._enrich_cache.keys())
        expected_keys = {"test_2", "test_3", "test_4"}
        assert remaining_keys == expected_keys, \
            f"应保留最新 3 条 {expected_keys}，实际 {remaining_keys}"

        record("6. LRU 淘汰边界测试", True)
    except Exception as e:
        record("6. LRU 淘汰边界测试", False, str(e))
    finally:
        disc._enrich_cache = orig_cache
        disc._ENRICH_CACHE_MAX = orig_max
        disc._ENRICH_CACHE_PATH = orig_path
        time.sleep(0.3)
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("C+E 方案综合集成测试")
    print("=" * 60)
    print()

    test_enrich_cache_persistence()
    test_inject_clean_names_cache_hit()
    test_inject_clean_names_cache_miss_sync()
    test_sync_enrich_timeout()
    test_enrich_cache_put()
    test_lru_eviction()

    # 等待所有异步写入线程完成
    time.sleep(0.5)

    print()
    print("=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    print(f"汇总: {passed} 通过, {failed} 失败, 共 {len(results)} 项")
    if failed:
        print("失败项:")
        for name, p, detail in results:
            if not p:
                print(f"  ✗ {name}: {detail}")
    else:
        print("全部通过 ✓")
    print("=" * 60)

    sys.exit(1 if failed else 0)
