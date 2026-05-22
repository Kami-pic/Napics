"""订阅系统子阶段B 端到端测试：RSS 源管理 + 手动搜索 + 搜索联动 + A阶段回归。

直接对运行中的后端 (http://127.0.0.1:8000) 发 HTTP 请求。
测试数据统一用 "B阶段测试_" 前缀，结束后自动清理。
"""

import sys
import requests
from typing import List, Dict, Any

BASE = "http://127.0.0.1:8000"
TIMEOUT = 15
PREFIX = "B阶段测试_"

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
    url = f"{BASE}{path}"
    return requests.request(method, url, timeout=TIMEOUT, **kwargs)


def cleanup_test_data():
    """删除所有以 B阶段测试_ 开头的订阅"""
    try:
        resp = api("GET", "/subscribe")
        if resp.status_code == 200:
            subs = resp.json()
            for s in subs:
                if isinstance(s, dict) and s.get("title", "").startswith(PREFIX):
                    api("DELETE", f"/subscribe/{s['id']}")
    except Exception as e:
        print(f"  ⚠️ 清理失败: {e}")


def create_subscription(title_suffix: str, **extra) -> str:
    """创建测试订阅，返回 id"""
    data = {
        "title": f"{PREFIX}{title_suffix}",
        "year": "2024",
        "type": "tv",
        "season": 1,
        "mode": "notify",
        **extra,
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    return body.get("subscription", {}).get("id", "")


# ══════════════════════════════════════════
#  1. 源管理测试
# ══════════════════════════════════════════

def test_list_sources():
    """GET /subscribe/sources 返回列表，包含 prowlarr 源"""
    resp = api("GET", "/subscribe/sources")
    body = resp.json()
    ok = isinstance(body, list) and len(body) > 0
    has_prowlarr = any(s.get("name") == "prowlarr" for s in body)
    record("源列表包含prowlarr", ok and has_prowlarr,
           f"源数量={len(body)}, 包含prowlarr={has_prowlarr}")
    return body


def test_prowlarr_default_enabled():
    """prowlarr 源默认 enabled=true"""
    resp = api("GET", "/subscribe/sources")
    body = resp.json()
    prowlarr = next((s for s in body if s.get("name") == "prowlarr"), None)
    ok = prowlarr is not None and prowlarr.get("enabled") is True
    record("prowlarr默认enabled=true", ok,
           f"enabled={prowlarr.get('enabled') if prowlarr else 'N/A'}")


def test_disable_prowlarr():
    """PUT /subscribe/sources/prowlarr 禁用后再查询确认 enabled=false"""
    resp = api("PUT", "/subscribe/sources/prowlarr", json={"enabled": False})
    body = resp.json()
    ok1 = body.get("status") == "ok"
    record("禁用prowlarr返回ok", ok1, f"status={body.get('status')}")

    # 查询确认
    resp2 = api("GET", "/subscribe/sources")
    body2 = resp2.json()
    prowlarr = next((s for s in body2 if s.get("name") == "prowlarr"), None)
    ok2 = prowlarr is not None and prowlarr.get("enabled") is False
    record("禁用后查询enabled=false", ok2,
           f"enabled={prowlarr.get('enabled') if prowlarr else 'N/A'}")


def test_enable_prowlarr():
    """PUT /subscribe/sources/prowlarr 重新启用"""
    resp = api("PUT", "/subscribe/sources/prowlarr", json={"enabled": True})
    body = resp.json()
    ok1 = body.get("status") == "ok"

    resp2 = api("GET", "/subscribe/sources")
    body2 = resp2.json()
    prowlarr = next((s for s in body2 if s.get("name") == "prowlarr"), None)
    ok2 = prowlarr is not None and prowlarr.get("enabled") is True
    record("重新启用prowlarr", ok1 and ok2,
           f"status={body.get('status')}, enabled={prowlarr.get('enabled') if prowlarr else 'N/A'}")


def test_toggle_nonexistent_source():
    """PUT /subscribe/sources/nonexistent 返回 not_found"""
    resp = api("PUT", "/subscribe/sources/nonexistent", json={"enabled": True})
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("不存在源返回not_found", ok, f"status={body.get('status')}")


# ══════════════════════════════════════════
#  2. 手动搜索测试
# ══════════════════════════════════════════

def test_manual_search():
    """创建订阅后手动搜索，验证返回结构"""
    sub_id = create_subscription("进击的巨人", type="tv", season=1)
    if not sub_id:
        record("手动搜索-创建订阅", False, "创建订阅失败")
        return None

    resp = api("POST", f"/subscribe/{sub_id}/search")
    body = resp.json()

    # 验证返回结构
    has_status = body.get("status") == "ok"
    has_matched = "matched" in body and isinstance(body["matched"], int)
    has_items = "items" in body and isinstance(body["items"], list)
    record("手动搜索返回结构", has_status and has_matched and has_items,
           f"status={body.get('status')}, matched={body.get('matched')}, items数量={len(body.get('items', []))}")

    # 如果有搜索结果，验证 items 字段
    items = body.get("items", [])
    if items:
        first = items[0]
        required_fields = ["title", "download_url", "source_name"]
        missing = [f for f in required_fields if f not in first]
        ok = len(missing) == 0
        record("搜索结果字段完整", ok,
               f"缺少={missing}" if missing else f"首条: {first.get('title', '')[:50]}")
    else:
        record("搜索结果字段完整", True, "Prowlarr 未返回结果（可能不可用），跳过字段验证")

    return sub_id


def test_search_nonexistent_id():
    """搜索不存在的 ID 返回 not_found"""
    resp = api("POST", "/subscribe/nonexistent_id_99999/search")
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("搜索不存在ID返回not_found", ok, f"status={body.get('status')}")


# ══════════════════════════════════════════
#  3. 搜索结果与订阅联动
# ══════════════════════════════════════════

def test_search_updates_subscription():
    """手动搜索后，订阅详情的 last_search 应该被更新"""
    sub_id = create_subscription("联动测试动画", type="tv", season=1)
    if not sub_id:
        record("联动测试-创建订阅", False, "创建订阅失败")
        return

    # 搜索前查询
    resp_before = api("GET", f"/subscribe/{sub_id}")
    before = resp_before.json()
    last_search_before = before.get("last_search", "")

    # 执行搜索
    api("POST", f"/subscribe/{sub_id}/search")

    # 搜索后查询
    resp_after = api("GET", f"/subscribe/{sub_id}")
    after = resp_after.json()
    last_search_after = after.get("last_search", "")

    ok = last_search_after != "" and last_search_after != last_search_before
    record("搜索后last_search更新", ok,
           f"before='{last_search_before}', after='{last_search_after}'")


def test_notify_mode_found_resources():
    """notify 模式搜索后，found_resources 应该有数据（如果搜到了）"""
    sub_id = create_subscription("通知模式测试", type="tv", season=1, mode="notify")
    if not sub_id:
        record("通知模式-创建订阅", False, "创建订阅失败")
        return

    # 执行搜索
    search_resp = api("POST", f"/subscribe/{sub_id}/search")
    search_body = search_resp.json()
    matched = search_body.get("matched", 0)

    # 查询订阅详情
    resp = api("GET", f"/subscribe/{sub_id}")
    body = resp.json()
    found = body.get("found_resources", [])

    if matched > 0:
        ok = len(found) > 0
        record("notify模式found_resources有数据", ok,
               f"matched={matched}, found_resources数量={len(found)}")
    else:
        record("notify模式found_resources有数据", True,
               f"Prowlarr 未返回结果（matched=0），跳过验证")


# ══════════════════════════════════════════
#  4. A 阶段回归测试
# ══════════════════════════════════════════

def test_regression_crud():
    """A 阶段 CRUD 回归：新增→查询→更新→删除→check"""
    # 新增
    data = {
        "title": f"{PREFIX}回归测试片",
        "year": "2024",
        "type": "movie",
        "quality": "1080p",
        "mode": "notify",
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    ok_add = body.get("status") == "ok"
    sub_id = body.get("subscription", {}).get("id", "")
    record("回归-新增订阅", ok_add, f"id={sub_id}")

    if not sub_id:
        record("回归-后续测试", False, "新增失败，跳过后续")
        return

    # 查询全部
    resp_list = api("GET", "/subscribe")
    subs = resp_list.json()
    ok_list = isinstance(subs, list) and any(s.get("id") == sub_id for s in subs)
    record("回归-查询全部包含新增", ok_list, f"列表长度={len(subs)}")

    # 查询单个
    resp_get = api("GET", f"/subscribe/{sub_id}")
    body_get = resp_get.json()
    ok_get = body_get.get("id") == sub_id and body_get.get("title") == f"{PREFIX}回归测试片"
    record("回归-查询单个", ok_get, f"title={body_get.get('title')}")

    # 更新
    resp_update = api("PUT", f"/subscribe/{sub_id}", json={"quality": "2160p", "state": "paused"})
    body_update = resp_update.json()
    sub_updated = body_update.get("subscription", {})
    ok_update = (body_update.get("status") == "ok" and
                 sub_updated.get("quality") == "2160p" and
                 sub_updated.get("state") == "paused")
    record("回归-更新订阅", ok_update,
           f"quality={sub_updated.get('quality')}, state={sub_updated.get('state')}")

    # check 接口
    resp_check = api("GET", "/subscribe/check",
                     params={"title": f"{PREFIX}回归测试片", "year": "2024"})
    # paused 状态仍算已订阅（is_subscribed 只排除 completed）
    body_check = resp_check.json()
    ok_check = body_check.get("subscribed") is True
    record("回归-check接口(paused仍算已订阅)", ok_check,
           f"subscribed={body_check.get('subscribed')}")

    # 删除
    resp_del = api("DELETE", f"/subscribe/{sub_id}")
    body_del = resp_del.json()
    ok_del = body_del.get("status") == "ok"
    record("回归-删除订阅", ok_del, f"status={body_del.get('status')}")

    # 删除后查询
    resp_after = api("GET", f"/subscribe/{sub_id}")
    body_after = resp_after.json()
    ok_after = body_after.get("status") == "not_found"
    record("回归-删除后查询not_found", ok_after, f"status={body_after.get('status')}")

    # 删除后 check
    resp_check2 = api("GET", "/subscribe/check",
                      params={"title": f"{PREFIX}回归测试片", "year": "2024"})
    body_check2 = resp_check2.json()
    ok_check2 = body_check2.get("subscribed") is False
    record("回归-删除后check=false", ok_check2,
           f"subscribed={body_check2.get('subscribed')}")


# ══════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  订阅系统子阶段B — 端到端测试")
    print("  RSS 源管理 + 手动搜索 + 搜索联动 + A阶段回归")
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

    # ── 1. 源管理 ──
    print("\n" + "─" * 40)
    print("📋 1. RSS 源管理测试")
    print("─" * 40)

    test_list_sources()
    test_prowlarr_default_enabled()
    test_disable_prowlarr()
    test_enable_prowlarr()
    test_toggle_nonexistent_source()

    # ── 2. 手动搜索 ──
    print("\n" + "─" * 40)
    print("📋 2. 手动搜索测试")
    print("─" * 40)

    test_manual_search()
    test_search_nonexistent_id()

    # ── 3. 搜索联动 ──
    print("\n" + "─" * 40)
    print("📋 3. 搜索结果与订阅联动")
    print("─" * 40)

    test_search_updates_subscription()
    test_notify_mode_found_resources()

    # ── 4. A 阶段回归 ──
    print("\n" + "─" * 40)
    print("📋 4. A 阶段回归测试")
    print("─" * 40)

    test_regression_crud()

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
