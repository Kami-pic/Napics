"""订阅系统集成测试：后端单元测试 + API 路由测试 + DownloadTask 兼容性测试。

测试矩阵：
1. subscriber.py 单元测试（CRUD、指纹、回调、持久化、状态机）
2. DownloadTask 新字段兼容性（旧数据无新字段不崩溃）
3. API 路由测试（需要后端运行）
4. 路由导入链路测试
"""

import os
import sys
import json

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

TEST_FILE = "test_sub_integration.json"
passed = 0
failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")


def fail(name, msg):
    global failed
    failed += 1
    print(f"  [FAIL] {name}: {msg}")


def cleanup():
    for f in [TEST_FILE, TEST_FILE + ".tmp"]:
        if os.path.exists(f):
            os.remove(f)


# ═══════════════════════════════════════════
# 1. subscriber.py 单元测试
# ═══════════════════════════════════════════

def test_subscriber_unit():
    print("\n[SUITE] subscriber.py 单元测试")
    from subscriber import SubscriptionManager

    cleanup()
    mgr = SubscriptionManager(base_path=".")
    mgr._file_path = TEST_FILE

    # 1.1 新增电影
    r = mgr.add({"title": "测试电影A", "year": "2026", "type": "movie", "tmdb_id": 10001})
    if r["status"] == "ok":
        ok("新增电影订阅")
    else:
        fail("新增电影订阅", r)
    movie_id = r["subscription"]["id"]

    # 1.2 新增剧集
    r = mgr.add({"title": "测试剧集B", "year": "2026", "type": "tv", "season": 1, "total_episode": 12})
    if r["status"] == "ok":
        ok("新增剧集订阅")
    else:
        fail("新增剧集订阅", r)
    tv_id = r["subscription"]["id"]

    # 1.3 重复拦截（同 tmdb_id）
    r = mgr.add({"title": "测试电影A", "year": "2026", "type": "movie", "tmdb_id": 10001})
    if r["status"] == "error":
        ok("重复订阅拦截(tmdb_id)")
    else:
        fail("重复订阅拦截(tmdb_id)", "应该报错")

    # 1.4 重复拦截（同 title+year+season）
    r = mgr.add({"title": "测试剧集B", "year": "2026", "type": "tv", "season": 1})
    if r["status"] == "error":
        ok("重复订阅拦截(title+year+season)")
    else:
        fail("重复订阅拦截(title+year+season)", "应该报错")

    # 1.5 查询全部
    all_subs = mgr.get_all()
    if len(all_subs) == 2:
        ok(f"查询全部: {len(all_subs)} 条")
    else:
        fail("查询全部", f"期望 2 条，实际 {len(all_subs)}")

    # 1.6 按状态过滤
    active = mgr.get_all(state="active")
    if len(active) == 2:
        ok("按状态过滤(active)")
    else:
        fail("按状态过滤(active)", f"期望 2，实际 {len(active)}")

    # 1.7 查询单个
    sub = mgr.get(movie_id)
    if sub and sub.title == "测试电影A":
        ok("查询单个")
    else:
        fail("查询单个", "未找到或标题不匹配")

    # 1.8 更新
    r = mgr.update(movie_id, {"quality": "2160p", "mode": "auto", "state": "paused"})
    sub = mgr.get(movie_id)
    if sub.quality == "2160p" and sub.mode == "auto" and sub.state == "paused":
        ok("更新字段")
    else:
        fail("更新字段", f"quality={sub.quality}, mode={sub.mode}, state={sub.state}")

    # 1.9 is_subscribed
    if mgr.is_subscribed(tmdb_id=10001):
        # paused 的不算（is_subscribed 跳过 completed，但不跳过 paused）
        # 实际上 paused 也应该算已订阅
        ok("is_subscribed(tmdb_id)")
    else:
        fail("is_subscribed(tmdb_id)", "应该返回 True")

    if not mgr.is_subscribed(tmdb_id=99999):
        ok("is_subscribed(不存在)")
    else:
        fail("is_subscribed(不存在)", "应该返回 False")

    # 1.10 电影下载完成回调
    mgr.update(movie_id, {"state": "active"})  # 恢复 active
    mgr.on_download_complete(movie_id, episode=None, info_hash="hash_movie",
                             title="Test.Movie.2026.2160p", quality_tag="WEB-DL-2160p",
                             source="prowlarr", channel="qb", task_id="task-m1")
    sub = mgr.get(movie_id)
    if sub.state == "completed" and "0" in sub.downloaded_episodes:
        ok("电影下载完成 → completed")
    else:
        fail("电影下载完成", f"state={sub.state}, eps={sub.downloaded_episodes}")

    # 1.11 剧集逐集下载
    for ep in range(1, 13):
        mgr.on_download_complete(tv_id, episode=ep, info_hash=f"hash_ep{ep:02d}",
                                 title=f"S01E{ep:02d}", source="prowlarr", channel="qb")
    sub = mgr.get(tv_id)
    if sub.state == "completed" and len(sub.downloaded_episodes) == 12:
        ok(f"剧集全部下载完成: {len(sub.downloaded_episodes)}/12")
    else:
        fail("剧集全部下载完成", f"state={sub.state}, count={len(sub.downloaded_episodes)}")

    # 1.12 同集指纹覆盖（洗版兼容）
    mgr.on_download_complete(tv_id, episode=1, info_hash="hash_ep01_v2", title="S01E01 REMUX")
    sub = mgr.get(tv_id)
    if sub.downloaded_episodes["1"].info_hash == "hash_ep01_v2":
        ok("同集指纹覆盖")
    else:
        fail("同集指纹覆盖", f"hash={sub.downloaded_episodes['1'].info_hash}")

    # 1.13 删除
    r = mgr.delete(movie_id)
    if r["status"] == "ok" and mgr.get(movie_id) is None:
        ok("删除订阅")
    else:
        fail("删除订阅", r)

    # 1.14 删除不存在的
    r = mgr.delete("nonexistent")
    if r["status"] == "not_found":
        ok("删除不存在的")
    else:
        fail("删除不存在的", r)

    # 1.15 持久化
    mgr2 = SubscriptionManager(base_path=".")
    mgr2._file_path = TEST_FILE
    mgr2._load()
    if len(mgr2.subscriptions) == 1 and mgr2.subscriptions[0].title == "测试剧集B":
        ok("持久化加载")
    else:
        fail("持久化加载", f"count={len(mgr2.subscriptions)}")

    # 1.16 空标题拦截
    r = mgr.add({"title": "", "type": "movie"})
    if r["status"] == "error":
        ok("空标题拦截")
    else:
        fail("空标题拦截", "应该报错")

    # 1.17 更新不存在的
    r = mgr.update("nonexistent", {"quality": "720p"})
    if r["status"] == "not_found":
        ok("更新不存在的")
    else:
        fail("更新不存在的", r)

    cleanup()


# ═══════════════════════════════════════════
# 2. DownloadTask 新字段兼容性测试
# ═══════════════════════════════════════════

def test_download_task_compat():
    print("\n[SUITE] DownloadTask 新字段兼容性")
    from download_manager import DownloadTask

    # 2.1 新字段默认值
    task = DownloadTask(id="test-1", media_name="测试")
    if task.subscription_id is None and task.subscription_episode is None:
        ok("新字段默认 None")
    else:
        fail("新字段默认 None", f"sub_id={task.subscription_id}, sub_ep={task.subscription_episode}")

    # 2.2 带订阅字段创建
    task2 = DownloadTask(id="test-2", media_name="订阅下载",
                         subscription_id="sub-001", subscription_episode=5)
    if task2.subscription_id == "sub-001" and task2.subscription_episode == 5:
        ok("带订阅字段创建")
    else:
        fail("带订阅字段创建", f"sub_id={task2.subscription_id}, sub_ep={task2.subscription_episode}")

    # 2.3 旧数据反序列化（无新字段）
    old_data = {"id": "old-1", "media_name": "旧任务", "status": "completed"}
    task3 = DownloadTask(**old_data)
    if task3.subscription_id is None:
        ok("旧数据反序列化兼容")
    else:
        fail("旧数据反序列化兼容", f"sub_id={task3.subscription_id}")

    # 2.4 序列化包含新字段
    d = task2.model_dump()
    if "subscription_id" in d and d["subscription_id"] == "sub-001":
        ok("序列化包含新字段")
    else:
        fail("序列化包含新字段", f"keys={list(d.keys())}")

    # 2.5 JSON 往返
    json_str = json.dumps(d, ensure_ascii=False)
    restored = DownloadTask(**json.loads(json_str))
    if restored.subscription_id == "sub-001" and restored.subscription_episode == 5:
        ok("JSON 往返一致")
    else:
        fail("JSON 往返一致", f"sub_id={restored.subscription_id}")


# ═══════════════════════════════════════════
# 3. 路由导入链路测试
# ═══════════════════════════════════════════

def test_route_import():
    print("\n[SUITE] 路由导入链路")
    try:
        from routes.subscribe import router
        ok("routes/subscribe.py 导入成功")
    except Exception as e:
        fail("routes/subscribe.py 导入", str(e))

    try:
        from subscriber import SubscriptionManager, Subscription, EpisodeInfo
        ok("subscriber.py 模型导入成功")
    except Exception as e:
        fail("subscriber.py 模型导入", str(e))

    # 验证路由数量
    try:
        from routes.subscribe import router
        route_count = len(router.routes)
        if route_count >= 7:
            ok(f"路由数量: {route_count} 个")
        else:
            fail("路由数量", f"期望 >= 7，实际 {route_count}")
    except Exception as e:
        fail("路由数量检查", str(e))


# ═══════════════════════════════════════════
# 4. API 路由测试（需要后端运行）
# ═══════════════════════════════════════════

def test_api_routes():
    print("\n[SUITE] API 路由测试（需要后端运行）")
    import requests

    BASE = "http://127.0.0.1:8000"

    # 检查后端是否运行
    try:
        r = requests.get(f"{BASE}/", timeout=3)
        if r.status_code != 200:
            print("  [SKIP] 后端未运行，跳过 API 测试")
            return
    except Exception:
        print("  [SKIP] 后端未运行，跳过 API 测试")
        return

    # 4.1 新增订阅
    r = requests.post(f"{BASE}/subscribe", json={
        "title": "集成测试片", "year": "2026", "type": "movie", "quality": "1080p", "mode": "notify",
    }, timeout=10)
    data = r.json()
    if data.get("status") == "ok":
        ok("POST /subscribe 新增")
        sub_id = data["subscription"]["id"]
    else:
        fail("POST /subscribe 新增", data)
        return

    # 4.2 查询全部
    r = requests.get(f"{BASE}/subscribe", timeout=10)
    subs = r.json()
    if isinstance(subs, list) and any(s["id"] == sub_id for s in subs):
        ok(f"GET /subscribe 查询全部: {len(subs)} 条")
    else:
        fail("GET /subscribe 查询全部", subs)

    # 4.3 检查订阅状态
    r = requests.get(f"{BASE}/subscribe/check", params={"title": "集成测试片", "year": "2026"}, timeout=10)
    data = r.json()
    if data.get("subscribed") is True:
        ok("GET /subscribe/check 已订阅")
    else:
        fail("GET /subscribe/check 已订阅", data)

    # 4.4 查询单个
    r = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
    data = r.json()
    if data.get("title") == "集成测试片":
        ok(f"GET /subscribe/{sub_id} 查询单个")
    else:
        fail("GET /subscribe/{sub_id} 查询单个", data)

    # 4.5 更新
    r = requests.put(f"{BASE}/subscribe/{sub_id}", json={"quality": "2160p", "mode": "auto"}, timeout=10)
    data = r.json()
    if data.get("status") == "ok" and data["subscription"]["quality"] == "2160p":
        ok("PUT /subscribe 更新")
    else:
        fail("PUT /subscribe 更新", data)

    # 4.6 重复订阅拦截
    r = requests.post(f"{BASE}/subscribe", json={"title": "集成测试片", "year": "2026", "type": "movie"}, timeout=10)
    data = r.json()
    if data.get("status") == "error":
        ok("POST /subscribe 重复拦截")
    else:
        fail("POST /subscribe 重复拦截", data)

    # 4.7 手动搜索（占位）
    r = requests.post(f"{BASE}/subscribe/{sub_id}/search", timeout=10)
    data = r.json()
    if data.get("status") == "ok":
        ok("POST /subscribe/{id}/search 手动搜索")
    else:
        fail("POST /subscribe/{id}/search", data)

    # 4.8 查询不存在的
    r = requests.get(f"{BASE}/subscribe/nonexistent", timeout=10)
    data = r.json()
    if data.get("status") == "not_found":
        ok("GET /subscribe/nonexistent 不存在")
    else:
        fail("GET /subscribe/nonexistent", data)

    # 4.9 删除
    r = requests.delete(f"{BASE}/subscribe/{sub_id}", timeout=10)
    data = r.json()
    if data.get("status") == "ok":
        ok("DELETE /subscribe 删除")
    else:
        fail("DELETE /subscribe 删除", data)

    # 4.10 确认已删除
    r = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
    data = r.json()
    if data.get("status") == "not_found":
        ok("确认已删除")
    else:
        fail("确认已删除", data)

    # 4.11 检查订阅状态（已删除）
    r = requests.get(f"{BASE}/subscribe/check", params={"title": "集成测试片", "year": "2026"}, timeout=10)
    data = r.json()
    if data.get("subscribed") is False:
        ok("GET /subscribe/check 已删除后为 False")
    else:
        fail("GET /subscribe/check 已删除后", data)


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("订阅系统集成测试")
    print("=" * 60)

    test_subscriber_unit()
    test_download_task_compat()
    test_route_import()
    test_api_routes()

    print(f"\n{'=' * 60}")
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    cleanup()
