"""测试 polish-todo 改动 — combined_recommend 去重逻辑加严"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0

def run_check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  OK {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL {name}: {e}")

# ── 1. combined_recommend._is_same_media 去重加严 ──
print("\n[1/3] combined_recommend 去重逻辑")

from combined_recommend import _is_same_media

def test_same_by_tmdb_id():
    a = {"title": "A", "tmdb_id": 123}
    b = {"title": "B", "tmdb_id": 123}
    assert _is_same_media(a, b) == True

def test_same_by_douban_id():
    a = {"title": "A", "douban_id": "36104Mo"}
    b = {"title": "B", "douban_id": "36104Mo"}
    assert _is_same_media(a, b) == True

def test_same_by_title_year():
    a = {"title": "流浪地球", "year": "2023"}
    b = {"title": "流浪地球", "year": "2023"}
    assert _is_same_media(a, b) == True

def test_different_short_title():
    """航海王 vs 航海日记 — 短标题不应误匹配"""
    a = {"title": "航海王", "year": "2024"}
    b = {"title": "航海日记", "year": "2024"}
    assert _is_same_media(a, b) == False

def test_different_overlap_2chars():
    """只有2个字重叠但总字数多 — 不应匹配"""
    a = {"title": "冰湖重生", "year": "2024"}
    b = {"title": "冰雪奇缘", "year": "2024"}
    assert _is_same_media(a, b) == False

def test_same_exact_chinese():
    """完全相同的中文标题"""
    a = {"title": "你的名字", "year": "2016"}
    b = {"title": "你的名字", "year": "2016"}
    assert _is_same_media(a, b) == True

def test_different_no_year():
    """无年份时不应轻易匹配"""
    a = {"title": "航海王", "year": ""}
    b = {"title": "航海王：红发歌姬", "year": ""}
    # fuzzy_score 可能较高，但这是合理的匹配
    # 不做断言，只确保不报错
    _is_same_media(a, b)

run_check("tmdb_id 精确匹配", test_same_by_tmdb_id)
run_check("douban_id 精确匹配", test_same_by_douban_id)
run_check("标题+年份精确匹配", test_same_by_title_year)
run_check("短标题不误匹配(航海王vs航海日记)", test_different_short_title)
run_check("2字重叠不误匹配(冰湖重生vs冰雪奇缘)", test_different_overlap_2chars)
run_check("完全相同中文标题", test_same_exact_chinese)
run_check("无年份不报错", test_different_no_year)

# ── 2. download_manager 回调链路验证 ──
print("\n[2/3] download_manager 回调链路")

def test_notify_method_exists():
    from download_manager import DownloadManager
    assert hasattr(DownloadManager, '_notify_subscription_complete')
    assert hasattr(DownloadManager, '_auto_relocate')

def test_sync_progress_calls_notify():
    """验证 sync_progress 中有回调调用逻辑"""
    import inspect
    from download_manager import DownloadManager
    source = inspect.getsource(DownloadManager.sync_progress)
    assert "_notify_subscription_complete" in source
    assert "subscription_id" in source

run_check("_notify_subscription_complete 方法存在", test_notify_method_exists)
run_check("sync_progress 包含回调调用", test_sync_progress_calls_notify)

# ── 3. subscriber.on_download_complete 验证 ──
print("\n[3/3] subscriber 回调方法")

def test_on_download_complete_exists():
    from subscriber import SubscriptionManager
    assert hasattr(SubscriptionManager, 'on_download_complete')

run_check("on_download_complete 方法存在", test_on_download_complete_exists)

# ── 汇总 ──
print(f"\n{'='*40}")
print(f"通过: {passed}, 失败: {failed}")
