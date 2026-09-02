"""订阅系统子阶段A 端到端测试：CRUD + 前端入口。

直接对运行中的后端 (http://127.0.0.1:8000) 发 HTTP 请求，
覆盖正常路径、边界情况、数据完整性、并发安全。
测试数据统一用 "E2E测试_" 前缀，结束后自动清理。
"""

import sys
import time
import requests
import concurrent.futures
from typing import List, Dict, Any, Optional

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

BASE = "http://127.0.0.1:8000"
TIMEOUT = 10
PREFIX = "E2E测试_"

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


# ── 清理辅助 ──

def cleanup_test_data():
    """删除所有以 E2E测试_ 开头的订阅"""
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
#  正常路径测试
# ══════════════════════════════════════════

def test_add_movie():
    """新增电影订阅"""
    data = {
        "title": f"{PREFIX}星际穿越",
        "year": "2014",
        "type": "movie",
        "quality": "2160p",
        "mode": "auto",
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    ok = body.get("status") == "ok" and "subscription" in body
    sub = body.get("subscription", {})
    record("新增电影订阅", ok, f"id={sub.get('id')}")
    return sub.get("id")


def test_add_tv():
    """新增剧集订阅"""
    data = {
        "title": f"{PREFIX}三体",
        "year": "2023",
        "type": "tv",
        "quality": "1080p",
        "mode": "notify",
        "season": 1,
        "total_episode": 30,
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    ok = body.get("status") == "ok" and "subscription" in body
    sub = body.get("subscription", {})
    # 验证剧集特有字段
    has_season = sub.get("season") == 1
    has_ep = sub.get("total_episode") == 30
    record("新增剧集订阅", ok and has_season and has_ep,
           f"id={sub.get('id')}, season={sub.get('season')}, total_episode={sub.get('total_episode')}")
    return sub.get("id")


def test_list_all(expected_min: int):
    """查询全部订阅，验证数量和字段完整性"""
    resp = api("GET", "/subscribe")
    body = resp.json()
    ok = isinstance(body, list) and len(body) >= expected_min
    # 验证字段完整性（取第一条）
    field_ok = True
    required_fields = ["id", "title", "year", "type", "quality", "mode", "state", "created_at", "aliases"]
    if body:
        first = body[0]
        missing = [f for f in required_fields if f not in first]
        field_ok = len(missing) == 0
        if missing:
            record("查询全部订阅-字段完整性", False, f"缺少字段: {missing}")
            return body
    record("查询全部订阅", ok and field_ok, f"数量={len(body)}, 字段完整")
    return body


def test_get_single(sub_id: str):
    """查询单个订阅，验证所有字段"""
    resp = api("GET", f"/subscribe/{sub_id}")
    body = resp.json()
    required_fields = [
        "id", "title", "year", "type", "tmdb_id", "poster", "season",
        "total_episode", "downloaded_episodes", "quality", "include", "exclude",
        "save_path", "search_keyword", "aliases", "state", "mode",
        "found_resources", "best_version", "search_count", "created_at", "note",
    ]
    missing = [f for f in required_fields if f not in body]
    ok = body.get("id") == sub_id and len(missing) == 0
    record("查询单个订阅", ok, f"id={sub_id}, 缺少={missing}" if missing else f"id={sub_id}, 字段完整")
    return body


def test_update(sub_id: str):
    """更新订阅（quality/mode/state），验证更新后的值"""
    update_data = {
        "quality": "2160p",
        "mode": "auto",
        "state": "paused",
    }
    resp = api("PUT", f"/subscribe/{sub_id}", json=update_data)
    body = resp.json()
    ok = body.get("status") == "ok"
    sub = body.get("subscription", {})
    val_ok = (sub.get("quality") == "2160p" and
              sub.get("mode") == "auto" and
              sub.get("state") == "paused")
    record("更新订阅", ok and val_ok,
           f"quality={sub.get('quality')}, mode={sub.get('mode')}, state={sub.get('state')}")


def test_check_subscribed_true():
    """检查订阅状态（已订阅返回 true）"""
    resp = api("GET", "/subscribe/check", params={"title": f"{PREFIX}星际穿越", "year": "2014"})
    body = resp.json()
    ok = body.get("subscribed") is True
    record("检查已订阅状态", ok, f"subscribed={body.get('subscribed')}")


def test_delete(sub_id: str):
    """删除订阅"""
    resp = api("DELETE", f"/subscribe/{sub_id}")
    body = resp.json()
    ok = body.get("status") == "ok"
    record("删除订阅", ok, f"status={body.get('status')}")

    # 确认删除后查询返回 not_found
    resp2 = api("GET", f"/subscribe/{sub_id}")
    body2 = resp2.json()
    ok2 = body2.get("status") == "not_found"
    record("删除后查询返回not_found", ok2, f"status={body2.get('status')}")


def test_check_subscribed_false_after_delete():
    """删除后 check 接口返回 false"""
    resp = api("GET", "/subscribe/check", params={"title": f"{PREFIX}星际穿越", "year": "2014"})
    body = resp.json()
    ok = body.get("subscribed") is False
    record("删除后check返回false", ok, f"subscribed={body.get('subscribed')}")


def test_manual_search(sub_id: str):
    """手动搜索（当前返回占位）"""
    resp = api("POST", f"/subscribe/{sub_id}/search")
    body = resp.json()
    ok = body.get("status") == "ok"
    record("手动搜索(占位)", ok, f"message={body.get('message', '')}")


# ══════════════════════════════════════════
#  边界情况测试
# ══════════════════════════════════════════

def test_add_empty_title():
    """空标题新增 → 应返回 error"""
    data = {"title": "", "year": "2024", "type": "movie"}
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    ok = body.get("status") == "error"
    record("空标题新增", ok, f"status={body.get('status')}, message={body.get('message', '')}")


def test_add_whitespace_title():
    """纯空格标题新增 → 应返回 error"""
    data = {"title": "   ", "year": "2024", "type": "movie"}
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    ok = body.get("status") == "error"
    record("纯空格标题新增", ok, f"status={body.get('status')}, message={body.get('message', '')}")


def test_add_duplicate():
    """重复订阅（同 title+year）→ 应返回 error"""
    data = {"title": f"{PREFIX}重复测试", "year": "2024", "type": "movie"}
    # 第一次新增
    resp1 = api("POST", "/subscribe", json=data)
    body1 = resp1.json()
    first_ok = body1.get("status") == "ok"
    # 第二次新增（重复）
    resp2 = api("POST", "/subscribe", json=data)
    body2 = resp2.json()
    dup_ok = body2.get("status") == "error"
    record("重复订阅拒绝", first_ok and dup_ok,
           f"第一次={body1.get('status')}, 第二次={body2.get('status')}, msg={body2.get('message', '')}")


def test_get_nonexistent():
    """查询不存在的 ID → 应返回 not_found"""
    resp = api("GET", "/subscribe/nonexistent_id_12345")
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("查询不存在ID", ok, f"status={body.get('status')}")


def test_update_nonexistent():
    """更新不存在的 ID → 应返回 not_found"""
    resp = api("PUT", "/subscribe/nonexistent_id_12345", json={"quality": "720p"})
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("更新不存在ID", ok, f"status={body.get('status')}")


def test_delete_nonexistent():
    """删除不存在的 ID → 应返回 not_found"""
    resp = api("DELETE", "/subscribe/nonexistent_id_12345")
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("删除不存在ID", ok, f"status={body.get('status')}")


def test_search_nonexistent():
    """手动搜索不存在的 ID → 应返回 not_found"""
    resp = api("POST", "/subscribe/nonexistent_id_12345/search")
    body = resp.json()
    ok = body.get("status") == "not_found"
    record("搜索不存在ID", ok, f"status={body.get('status')}")


def test_default_type():
    """新增时不传 type → 验证默认值是否为 movie"""
    data = {"title": f"{PREFIX}默认类型测试", "year": "2024"}
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub = body.get("subscription", {})
    ok = body.get("status") == "ok" and sub.get("type") == "movie"
    record("默认type=movie", ok, f"type={sub.get('type')}")


def test_default_quality():
    """新增时不传 quality → 验证默认值是否为 1080p"""
    data = {"title": f"{PREFIX}默认质量测试", "year": "2024", "type": "movie"}
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub = body.get("subscription", {})
    ok = body.get("status") == "ok" and sub.get("quality") == "1080p"
    record("默认quality=1080p", ok, f"quality={sub.get('quality')}")


def test_default_mode():
    """新增时不传 mode → 验证默认值是否为 notify"""
    data = {"title": f"{PREFIX}默认模式测试", "year": "2024", "type": "movie"}
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub = body.get("subscription", {})
    ok = body.get("status") == "ok" and sub.get("mode") == "notify"
    record("默认mode=notify", ok, f"mode={sub.get('mode')}")


# ══════════════════════════════════════════
#  数据完整性测试
# ══════════════════════════════════════════

def test_data_integrity():
    """验证新增后返回的 subscription 对象数据完整性"""
    data = {
        "title": f"{PREFIX}数据完整性测试",
        "year": "2024",
        "type": "tv",
        "season": 1,
        "total_episode": 12,
        "quality": "1080p",
        "mode": "auto",
    }
    resp = api("POST", "/subscribe", json=data)
    body = resp.json()
    sub = body.get("subscription", {})

    # 1. 必须包含的顶层字段
    required = ["id", "title", "year", "type", "quality", "mode", "state", "created_at", "aliases"]
    missing = [f for f in required if f not in sub]
    record("数据完整性-必要字段", len(missing) == 0, f"缺少: {missing}" if missing else "全部存在")

    # 2. aliases 是 dict 且包含 cn/en/jp
    aliases = sub.get("aliases")
    aliases_ok = (isinstance(aliases, dict) and
                  "cn" in aliases and "en" in aliases and "jp" in aliases)
    record("数据完整性-aliases结构", aliases_ok,
           f"type={type(aliases).__name__}, keys={list(aliases.keys()) if isinstance(aliases, dict) else 'N/A'}")

    # 3. downloaded_episodes 是 dict（不是 list）
    dl_eps = sub.get("downloaded_episodes")
    dl_ok = isinstance(dl_eps, dict)
    record("数据完整性-downloaded_episodes是dict", dl_ok, f"type={type(dl_eps).__name__}")

    # 4. found_resources 是 list
    found = sub.get("found_resources")
    found_ok = isinstance(found, list)
    record("数据完整性-found_resources是list", found_ok, f"type={type(found).__name__}")

    # 5. id 非空
    id_ok = bool(sub.get("id"))
    record("数据完整性-id非空", id_ok, f"id={sub.get('id')}")

    # 6. created_at 非空
    ct_ok = bool(sub.get("created_at"))
    record("数据完整性-created_at非空", ct_ok, f"created_at={sub.get('created_at')}")

    # 7. state 默认 active
    state_ok = sub.get("state") == "active"
    record("数据完整性-state默认active", state_ok, f"state={sub.get('state')}")

    return sub.get("id")


# ══════════════════════════════════════════
#  并发安全测试
# ══════════════════════════════════════════

def test_concurrent_add():
    """快速连续新增 5 个不同订阅，验证全部成功且 ID 不重复"""
    titles = [f"{PREFIX}并发测试_{i}" for i in range(5)]

    def add_one(title: str):
        data = {"title": title, "year": "2024", "type": "movie"}
        resp = api("POST", "/subscribe", json=data)
        return resp.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(add_one, t): t for t in titles}
        results_list = []
        for future in concurrent.futures.as_completed(futures):
            results_list.append(future.result())

    ok_count = sum(1 for r in results_list if r.get("status") == "ok")
    ids = [r.get("subscription", {}).get("id") for r in results_list if r.get("status") == "ok"]
    unique_ids = set(ids)
    all_ok = ok_count == 5 and len(unique_ids) == 5
    record("并发新增5个订阅", all_ok, f"成功={ok_count}, 唯一ID数={len(unique_ids)}")
    return ids


def test_concurrent_delete(ids: List[str]):
    """快速连续删除，验证不会崩溃"""
    def delete_one(sub_id: str):
        try:
            resp = api("DELETE", f"/subscribe/{sub_id}")
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(delete_one, sid): sid for sid in ids}
        results_list = []
        for future in concurrent.futures.as_completed(futures):
            results_list.append(future.result())

    ok_count = sum(1 for r in results_list if r.get("status") == "ok")
    no_crash = all(r.get("status") in ("ok", "not_found") for r in results_list)
    record("并发删除不崩溃", no_crash, f"ok={ok_count}, 总数={len(results_list)}")


# ══════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  订阅系统子阶段A — 端到端测试")
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

    # ── 正常路径 ──
    print("\n" + "─" * 40)
    print("📋 正常路径测试")
    print("─" * 40)

    movie_id = test_add_movie()
    tv_id = test_add_tv()
    test_list_all(expected_min=2)
    if movie_id:
        test_get_single(movie_id)
    if tv_id:
        test_update(tv_id)
    test_check_subscribed_true()
    if tv_id:
        test_manual_search(tv_id)
    if movie_id:
        test_delete(movie_id)
    test_check_subscribed_false_after_delete()

    # ── 边界情况 ──
    print("\n" + "─" * 40)
    print("📋 边界情况测试")
    print("─" * 40)

    test_add_empty_title()
    test_add_whitespace_title()
    test_add_duplicate()
    test_get_nonexistent()
    test_update_nonexistent()
    test_delete_nonexistent()
    test_search_nonexistent()
    test_default_type()
    test_default_quality()
    test_default_mode()

    # ── 数据完整性 ──
    print("\n" + "─" * 40)
    print("📋 数据完整性测试")
    print("─" * 40)

    test_data_integrity()

    # ── 并发安全 ──
    print("\n" + "─" * 40)
    print("📋 并发安全测试")
    print("─" * 40)

    concurrent_ids = test_concurrent_add()
    if concurrent_ids:
        test_concurrent_delete(concurrent_ids)

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
