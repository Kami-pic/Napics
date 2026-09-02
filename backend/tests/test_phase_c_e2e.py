"""订阅系统子阶段C 端到端测试：日历 API + 媒体库联动 + A/B 阶段回归。

直接对运行中的后端 (http://127.0.0.1:8000) 发 HTTP 请求，
测试数据统一用 "C阶段测试_" 前缀，结束后自动清理。
"""

import sys

import time
import requests
from typing import List, Dict, Any

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

BASE = "http://127.0.0.1:8000"
TIMEOUT = 15
PREFIX = "C阶段测试_"

# ── 统计 ──
results: List[Dict[str, Any]] = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    icon = "✅" if passed else "❌"
    msg = f"  {icon} [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def api(method: str, path: str, **kwargs) -> requests.Response:
    """统一请求封装"""
    url = f"{BASE}{path}"
    return requests.request(method, url, timeout=TIMEOUT, **kwargs)


def cleanup_test_data():
    """删除所有以 C阶段测试_ 开头的订阅"""
    try:
        resp = api("GET", "/subscribe")
        if resp.status_code == 200:
            subs = resp.json()
            for s in subs:
                if isinstance(s, dict) and s.get("title", "").startswith(PREFIX):
                    api("DELETE", f"/subscribe/{s['id']}")
    except Exception as e:
        print(f"  ⚠️ 清理失败: {e}")


# ══════════════════════════════════════════
#  1. 日历 API 测试
# ══════════════════════════════════════════

def test_calendar_empty_or_list():
    """GET /subscribe/calendar 返回列表（可能为空）"""
    resp = api("GET", "/subscribe/calendar")
    body = resp.json()
    ok = isinstance(body, list)
    record("日历API返回列表", ok, f"type={type(body).__name__}, len={len(body) if isinstance(body, list) else 'N/A'}")


def test_calendar_with_tv_subscription():
    """创建 TV 订阅（tmdb_id=1399 权力的游戏），查询日历，验证返回结构"""
    # 创建订阅
    data = {
        "title": f"{PREFIX}权力的游戏",
        "year": "2011",
        "type": "tv",
        "tmdb_id": 1399,
        "quality": "1080p",
        "mode": "notify",
        "season": 1,
        "total_episode": 10,
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub_id = body.get("subscription", {}).get("id")
    create_ok = body.get("status") == "ok" and sub_id
    record("创建权力的游戏订阅", create_ok, f"id={sub_id}")

    if not sub_id:
        record("日历结构验证", False, "订阅创建失败，跳过")
        return sub_id

    # 查询日历
    resp2 = api("GET", "/subscribe/calendar")
    calendar = resp2.json()
    is_list = isinstance(calendar, list)

    if not is_list:
        record("日历结构验证", False, f"返回非列表: {type(calendar).__name__}")
        return sub_id

    # 日历可能为空（TMDB 无法访问时），也可能有数据
    if len(calendar) == 0:
        record("日历结构验证(空)", True, "日历为空（TMDB 可能不可达），结构验证跳过")
    else:
        # 验证条目结构
        required_fields = ["subscription_id", "title", "season", "episode", "air_date", "downloaded"]
        entry = calendar[0]
        missing = [f for f in required_fields if f not in entry]
        fields_ok = len(missing) == 0
        record("日历条目字段完整性", fields_ok,
               f"缺少={missing}" if missing else f"字段完整, 共{len(calendar)}条")

        # 验证 subscription_id 关联
        has_our_sub = any(e.get("subscription_id") == sub_id for e in calendar)
        record("日历包含新建订阅", has_our_sub,
               f"sub_id={sub_id}, 匹配条目数={sum(1 for e in calendar if e.get('subscription_id') == sub_id)}")

        # 验证字段类型
        if fields_ok:
            type_ok = (
                isinstance(entry.get("season"), int) and
                isinstance(entry.get("episode"), int) and
                isinstance(entry.get("air_date"), str) and
                isinstance(entry.get("downloaded"), bool)
            )
            record("日历字段类型正确", type_ok,
                   f"season={type(entry.get('season')).__name__}, episode={type(entry.get('episode')).__name__}, "
                   f"air_date={type(entry.get('air_date')).__name__}, downloaded={type(entry.get('downloaded')).__name__}")

    return sub_id


# ══════════════════════════════════════════
#  2. 媒体库联动测试
# ══════════════════════════════════════════

def test_downloaded_episodes_field(sub_id: str):
    """创建 TV 订阅后查询详情，验证 downloaded_episodes 字段存在"""
    if not sub_id:
        record("downloaded_episodes字段存在", False, "无有效订阅ID")
        return

    resp = api("GET", f"/subscribe/{sub_id}")
    body = resp.json()
    has_field = "downloaded_episodes" in body
    is_dict = isinstance(body.get("downloaded_episodes"), dict)
    record("downloaded_episodes字段存在", has_field and is_dict,
           f"存在={has_field}, 类型={type(body.get('downloaded_episodes')).__name__}, "
           f"内容={body.get('downloaded_episodes')}")


# ══════════════════════════════════════════
#  3. A+B 阶段回归测试
# ══════════════════════════════════════════

def test_crud_regression():
    """CRUD 基本操作回归"""
    # 新增
    data = {
        "title": f"{PREFIX}回归CRUD测试",
        "year": "2024",
        "type": "movie",
        "quality": "2160p",
        "mode": "auto",
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub_id = body.get("subscription", {}).get("id")
    add_ok = body.get("status") == "ok" and sub_id
    record("回归-新增订阅", add_ok, f"id={sub_id}")

    if not sub_id:
        record("回归-查询/更新/删除", False, "新增失败，跳过后续")
        return

    # 查询
    resp2 = api("GET", f"/subscribe/{sub_id}")
    body2 = resp2.json()
    get_ok = body2.get("id") == sub_id and body2.get("title") == f"{PREFIX}回归CRUD测试"
    record("回归-查询订阅", get_ok, f"title={body2.get('title')}")

    # 更新
    resp3 = api("PUT", f"/subscribe/{sub_id}", json={"quality": "720p", "state": "paused"})
    body3 = resp3.json()
    update_ok = body3.get("status") == "ok"
    updated_sub = body3.get("subscription", {})
    val_ok = updated_sub.get("quality") == "720p" and updated_sub.get("state") == "paused"
    record("回归-更新订阅", update_ok and val_ok,
           f"quality={updated_sub.get('quality')}, state={updated_sub.get('state')}")

    # 列表查询
    resp4 = api("GET", "/subscribe")
    list_ok = isinstance(resp4.json(), list) and len(resp4.json()) > 0
    record("回归-列表查询", list_ok, f"数量={len(resp4.json())}")

    # 删除
    resp5 = api("DELETE", f"/subscribe/{sub_id}")
    del_ok = resp5.json().get("status") == "ok"
    record("回归-删除订阅", del_ok)

    # 删除后确认
    resp6 = api("GET", f"/subscribe/{sub_id}")
    gone_ok = resp6.json().get("status") == "not_found"
    record("回归-删除后查询", gone_ok)


def test_source_management_regression():
    """源管理回归"""
    resp = api("GET", "/subscribe/sources")
    body = resp.json()
    is_list = isinstance(body, list)
    record("回归-源列表查询", is_list, f"type={type(body).__name__}, len={len(body) if is_list else 'N/A'}")

    # 如果有源，测试 toggle
    if is_list and len(body) > 0:
        source_name = body[0].get("name", "")
        if source_name:
            resp2 = api("PUT", f"/subscribe/sources/{source_name}", json={"enabled": True})
            toggle_ok = resp2.json().get("status") == "ok"
            record("回归-源启用切换", toggle_ok, f"source={source_name}")
        else:
            record("回归-源启用切换", True, "源名为空，跳过（不影响）")
    else:
        record("回归-源启用切换", True, "无源可测，跳过（不影响）")


def test_manual_search_regression():
    """手动搜索回归"""
    # 创建临时订阅
    data = {
        "title": f"{PREFIX}搜索回归测试",
        "year": "2024",
        "type": "tv",
        "quality": "1080p",
        "mode": "notify",
        "season": 1,
        "total_episode": 12,
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub_id = body.get("subscription", {}).get("id")

    if not sub_id:
        record("回归-手动搜索", False, "订阅创建失败")
        return

    # 触发搜索
    resp2 = api("POST", f"/subscribe/{sub_id}/search")
    body2 = resp2.json()
    search_ok = body2.get("status") == "ok"
    has_matched = "matched" in body2
    record("回归-手动搜索", search_ok and has_matched,
           f"status={body2.get('status')}, matched={body2.get('matched')}")

    # 搜索后验证 search_count 和 last_search 更新
    resp3 = api("GET", f"/subscribe/{sub_id}")
    body3 = resp3.json()
    has_search_count = "search_count" in body3
    has_last_search = "last_search" in body3
    record("回归-搜索状态字段", has_search_count and has_last_search,
           f"search_count={body3.get('search_count')}, last_search={body3.get('last_search')}")


def test_check_subscribed_regression():
    """check 接口回归"""
    # 创建临时订阅
    data = {
        "title": f"{PREFIX}Check回归",
        "year": "2024",
        "type": "movie",
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()

    # 检查已订阅
    resp2 = api("GET", "/subscribe/check", params={"title": f"{PREFIX}Check回归", "year": "2024"})
    check_ok = resp2.json().get("subscribed") is True
    record("回归-check已订阅", check_ok)

    # 检查未订阅
    resp3 = api("GET", "/subscribe/check", params={"title": "不存在的影片XYZ", "year": "9999"})
    check_false = resp3.json().get("subscribed") is False
    record("回归-check未订阅", check_false)


# ══════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  订阅系统子阶段C — 端到端测试")
    print("=" * 60)

    # 检查后端是否在运行
    print("\n🔍 检查后端连接...")
    try:
        resp = api("GET", "/")
        if resp.status_code != 200:
            print(f"  ❌ 后端返回异常状态码: {resp.status_code}，跳过测试")
            sys.exit(1)
        print(f"  ✅ 后端已连接: {resp.json().get('message', '')}")
    except requests.ConnectionError:
        print("  ❌ 无法连接后端 (http://127.0.0.1:8000)，跳过测试")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ 连接异常: {e}，跳过测试")
        sys.exit(1)

    # 先清理残留测试数据
    print("\n🧹 清理残留测试数据...")
    cleanup_test_data()

    # ── 1. 日历 API ──
    print("\n" + "─" * 40)
    print("📋 1. 日历 API 测试")
    print("─" * 40)

    test_calendar_empty_or_list()
    got_sub_id = test_calendar_with_tv_subscription()

    # ── 2. 媒体库联动 ──
    print("\n" + "─" * 40)
    print("📋 2. 媒体库联动测试")
    print("─" * 40)

    test_downloaded_episodes_field(got_sub_id)

    # ── 3. A+B 阶段回归 ──
    print("\n" + "─" * 40)
    print("📋 3. A+B 阶段回归测试")
    print("─" * 40)

    test_crud_regression()
    test_source_management_regression()
    test_manual_search_regression()
    test_check_subscribed_regression()

    # ── 清理 ──
    print("\n🧹 清理所有测试数据...")
    cleanup_test_data()

    # ── 统计 ──
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print(f"  📊 测试统计: 总计 {total} 项, 通过 {passed} 项, 失败 {failed} 项")
    if failed > 0:
        print(f"\n  ❌ 失败项:")
        for r in results:
            if not r["passed"]:
                print(f"     • {r['name']}: {r['detail']}")
    else:
        print("  🎉 全部通过!")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
