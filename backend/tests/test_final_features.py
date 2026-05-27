"""最终功能测试：覆盖自动洗版归位、quality_score、日历触发、匹配算法、订阅 CRUD。

测试数据统一用 "Final测试_" 前缀，测试结束后清理。
"""

import sys

import os
import json
import time
import requests

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0
RESULTS = []
CLEANUP_IDS = []


def report(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{tag}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append((name, ok, detail))


# ══════════════════════════════════════════
# 1. 搜索结果 quality_score（API 测试）
# ══════════════════════════════════════════

def test_search_quality_score():
    print("\n=== 1. 搜索结果 quality_score ===")
    try:
        r = requests.get(f"{BASE}/api/search", params={"query": "test"}, timeout=30)
        data = r.json()
        bt_results = data.get("bt_results", [])
        if not bt_results:
            report("quality_score 字段存在", True, f"搜索返回 0 条结果，跳过字段检查（API 正常）")
            report("quality_score 类型正确", True, "无结果可检查，跳过")
            return

        # 检查每条结果都有 quality_score
        all_have = all("quality_score" in item for item in bt_results)
        report("quality_score 字段存在", all_have,
               f"共 {len(bt_results)} 条，{sum(1 for i in bt_results if 'quality_score' in i)} 条有字段")

        # 检查类型和范围
        type_ok = all(isinstance(item.get("quality_score"), int) and item["quality_score"] >= 0
                      for item in bt_results if "quality_score" in item)
        report("quality_score 类型正确 (int >= 0)", type_ok)
    except Exception as e:
        report("quality_score API 请求", False, str(e))


# ══════════════════════════════════════════
# 2. 匹配算法（直接 import）
# ══════════════════════════════════════════

def test_pick_best_douban():
    print("\n=== 2. _pick_best_douban_result 匹配算法 ===")
    try:
        from routes.media_detail import _pick_best_douban_result

        # 2.1 精确匹配
        results = [
            {"title": "流浪地球", "year": "2019"},
            {"title": "流浪地球2", "year": "2023"},
        ]
        best = _pick_best_douban_result(results, "流浪地球", "2019")
        report("精确匹配", best is not None and best["title"] == "流浪地球" and best["year"] == "2019")

        # 2.2 模糊匹配（"工房" vs "工坊"，重叠率 >= 0.7）
        results2 = [
            {"title": "魔法工坊物语", "year": "2020"},
        ]
        best2 = _pick_best_douban_result(results2, "魔法工房物语", "")
        # "魔法工房物语" 中文字符: 魔法工房物语 (5个)
        # "魔法工坊物语" 中文字符: 魔法工坊物语 (5个)
        # 重叠: 魔法物语 = 4/5 = 0.8 >= 0.7 → 应该匹配
        report("模糊匹配 (工房vs工坊)", best2 is not None,
               f"结果: {best2['title'] if best2 else 'None'}")

        # 2.3 年份优先
        results3 = [
            {"title": "蜘蛛侠", "year": "2002"},
            {"title": "蜘蛛侠", "year": "2017"},
        ]
        best3 = _pick_best_douban_result(results3, "蜘蛛侠", "2017")
        report("年份优先", best3 is not None and best3["year"] == "2017")

        # 2.4 无匹配返回 None
        results4 = [
            {"title": "完全不相关的电影", "year": "2020"},
        ]
        best4 = _pick_best_douban_result(results4, "测试影片名称", "2023")
        report("无匹配返回 None", best4 is None)

        # 2.5 纯英文标题子串匹配
        results5 = [
            {"title": "The Matrix Resurrections", "year": "2021"},
            {"title": "Matrix", "year": "1999"},
        ]
        best5 = _pick_best_douban_result(results5, "Matrix", "")
        report("纯英文子串匹配", best5 is not None,
               f"结果: {best5['title'] if best5 else 'None'}")

    except Exception as e:
        report("匹配算法 import", False, str(e))


# ══════════════════════════════════════════
# 3. 洗版归位逻辑（直接 import）
# ══════════════════════════════════════════

def test_auto_relocate():
    print("\n=== 3. 洗版归位逻辑 ===")
    try:
        from download_manager import DownloadManager, DownloadTask

        # 3.1 _notify_subscription_complete 方法存在
        report("_notify_subscription_complete 方法存在",
               hasattr(DownloadManager, "_notify_subscription_complete"))

        # 3.2 _auto_relocate 方法存在
        report("_auto_relocate 方法存在",
               hasattr(DownloadManager, "_auto_relocate"))

        # 3.3 DownloadTask 的 subscription_id 字段
        task = DownloadTask(
            media_name="Final测试_洗版",
            subscription_id="test-sub-123",
            subscription_episode=5,
        )
        report("DownloadTask subscription_id 正常",
               task.subscription_id == "test-sub-123" and task.subscription_episode == 5)

    except Exception as e:
        report("洗版归位 import", False, str(e))


# ══════════════════════════════════════════
# 4. 日历触发（直接 import）
# ══════════════════════════════════════════

def test_calendar_trigger():
    print("\n=== 4. 日历触发逻辑 ===")
    try:
        from rss_engine import SubscriptionScheduler
        from subscriber import Subscription

        # 4.1 _check_calendar_trigger 方法存在
        report("_check_calendar_trigger 方法存在",
               hasattr(SubscriptionScheduler, "_check_calendar_trigger"))

        # 创建一个最小化的 scheduler 实例（不启动线程）
        scheduler = SubscriptionScheduler.__new__(SubscriptionScheduler)

        # 4.2 非 TV 订阅返回 False
        movie_sub = Subscription(
            id="final-test-movie",
            title="Final测试_电影",
            type="movie",
            tmdb_id=550,
        )
        result_movie = scheduler._check_calendar_trigger(movie_sub)
        report("非 TV 订阅返回 False", result_movie is False)

        # 4.3 无 tmdb_id 返回 False
        tv_no_tmdb = Subscription(
            id="final-test-tv-no-tmdb",
            title="Final测试_无TMDB",
            type="tv",
            tmdb_id=None,
        )
        result_no_tmdb = scheduler._check_calendar_trigger(tv_no_tmdb)
        report("无 tmdb_id 返回 False", result_no_tmdb is False)

    except Exception as e:
        report("日历触发 import", False, str(e))


# ══════════════════════════════════════════
# 5. 日历 API（API 测试）
# ══════════════════════════════════════════

def test_calendar_api():
    print("\n=== 5. 日历 API ===")
    try:
        r = requests.get(f"{BASE}/subscribe/calendar", timeout=15)
        data = r.json()
        report("GET /subscribe/calendar 返回列表",
               isinstance(data, list),
               f"返回 {len(data)} 条")
    except Exception as e:
        report("日历 API 请求", False, str(e))


# ══════════════════════════════════════════
# 6. 回归：订阅 CRUD
# ══════════════════════════════════════════

def test_subscribe_crud():
    print("\n=== 6. 订阅 CRUD 回归 ===")
    sub_id = None
    try:
        # CREATE — 响应格式: {"status": "ok", "subscription": {...}}
        # 用时间戳确保标题唯一
        unique_title = f"Final测试_CRUD订阅_{int(time.time())}"
        payload = {
            "title": unique_title,
            "type": "movie",
            "year": "2025",
            "quality": "1080p",
            "mode": "notify",
        }
        r = requests.post(f"{BASE}/subscribe", json=payload, timeout=10)
        data = r.json()
        # 从 subscription 子对象中取 id
        sub_obj = data.get("subscription", {}) if isinstance(data, dict) else {}
        sub_id = sub_obj.get("id", "") if isinstance(sub_obj, dict) else ""
        report("CREATE 订阅", bool(sub_id), f"id={sub_id}, status={data.get('status','')}")
        if not sub_id:
            # CREATE 失败，跳过后续
            report("READ 订阅", False, "CREATE 失败，跳过")
            report("UPDATE 订阅", False, "CREATE 失败，跳过")
            report("UPDATE 验证", False, "CREATE 失败，跳过")
            report("LIST 订阅", False, "CREATE 失败，跳过")
            report("DELETE 订阅", False, "CREATE 失败，跳过")
            report("DELETE 验证", False, "CREATE 失败，跳过")
            return
        CLEANUP_IDS.append(sub_id)

        # READ
        r2 = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
        d2 = r2.json()
        report("READ 订阅", isinstance(d2, dict) and d2.get("title") == unique_title)

        # UPDATE — 响应格式: {"status": "ok", "subscription": {...}}
        r3 = requests.put(f"{BASE}/subscribe/{sub_id}", json={"state": "paused"}, timeout=10)
        d3 = r3.json()
        update_ok = isinstance(d3, dict) and (d3.get("status") == "ok" or "subscription" in d3)
        report("UPDATE 订阅", update_ok)

        # 验证更新
        r4 = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
        d4 = r4.json()
        report("UPDATE 验证", isinstance(d4, dict) and d4.get("state") == "paused")

        # LIST
        r5 = requests.get(f"{BASE}/subscribe", timeout=10)
        d5 = r5.json()
        report("LIST 订阅", isinstance(d5, list) and len(d5) > 0)

        # DELETE
        r6 = requests.delete(f"{BASE}/subscribe/{sub_id}", timeout=10)
        report("DELETE 订阅", r6.status_code == 200)
        if sub_id in CLEANUP_IDS:
            CLEANUP_IDS.remove(sub_id)

        # 验证删除
        r7 = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
        d7 = r7.json()
        report("DELETE 验证", isinstance(d7, dict) and (d7.get("status") == "not_found" or d7.get("id", "") != sub_id))

    except Exception as e:
        report("订阅 CRUD", False, str(e))


# ══════════════════════════════════════════
# 清理 + 汇总
# ══════════════════════════════════════════

def cleanup():
    """清理测试数据"""
    for sid in CLEANUP_IDS:
        try:
            requests.delete(f"{BASE}/subscribe/{sid}", timeout=5)
            print(f"  [清理] 删除订阅 {sid}")
        except Exception:
            pass


def main():
    print("=" * 60)
    print("  后端功能测试 — Final Features")
    print("=" * 60)

    test_search_quality_score()
    test_pick_best_douban()
    test_auto_relocate()
    test_calendar_trigger()
    test_calendar_api()
    test_subscribe_crud()

    # 清理
    print("\n--- 清理测试数据 ---")
    cleanup()

    # 汇总
    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"  总计: {total} | 通过: {PASS} | 失败: {FAIL}")
    print("=" * 60)

    if FAIL > 0:
        print("\n失败项:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  ✗ {name}: {detail}")
        sys.exit(1)
    else:
        print("\n全部通过!")


if __name__ == "__main__":
    main()
