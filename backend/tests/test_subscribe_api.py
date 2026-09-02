"""订阅 API 路由测试：通过 HTTP 请求验证 CRUD 接口。"""

import os
import sys
import json
import requests
import time

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

BASE = "http://127.0.0.1:8000"


def test_api():
    """测试订阅 API 路由"""
    print("=" * 50)
    print("订阅 API 路由测试")
    print("=" * 50)

    passed = 0
    failed = 0

    # 1. 新增订阅
    print("\n[TEST] POST /subscribe — 新增订阅")
    try:
        r = requests.post(f"{BASE}/subscribe", json={
            "title": "API测试片",
            "year": "2026",
            "type": "movie",
            "quality": "1080p",
            "mode": "notify",
        }, timeout=10)
        data = r.json()
        assert data["status"] == "ok", f"新增失败: {data}"
        sub_id = data["subscription"]["id"]
        print(f"  [PASS] 新增成功: id={sub_id}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1
        return

    # 2. 查询全部
    print("\n[TEST] GET /subscribe — 查询全部")
    try:
        r = requests.get(f"{BASE}/subscribe", timeout=10)
        subs = r.json()
        assert isinstance(subs, list), f"返回格式错误: {type(subs)}"
        found = any(s["id"] == sub_id for s in subs)
        assert found, "新增的订阅不在列表中"
        print(f"  [PASS] 查询到 {len(subs)} 条订阅")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 3. 查询单个
    print(f"\n[TEST] GET /subscribe/{sub_id} — 查询单个")
    try:
        r = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
        data = r.json()
        assert data["title"] == "API测试片", f"标题不匹配: {data.get('title')}"
        assert data["quality"] == "1080p"
        print(f"  [PASS] 查询成功: {data['title']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 4. 检查订阅状态
    print("\n[TEST] GET /subscribe/check — 检查是否已订阅")
    try:
        r = requests.get(f"{BASE}/subscribe/check", params={"title": "API测试片", "year": "2026"}, timeout=10)
        data = r.json()
        assert data["subscribed"] is True, f"应该已订阅: {data}"
        print(f"  [PASS] 已订阅检查通过")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 5. 更新订阅
    print(f"\n[TEST] PUT /subscribe/{sub_id} — 更新订阅")
    try:
        r = requests.put(f"{BASE}/subscribe/{sub_id}", json={
            "quality": "2160p",
            "mode": "auto",
        }, timeout=10)
        data = r.json()
        assert data["status"] == "ok"
        assert data["subscription"]["quality"] == "2160p"
        assert data["subscription"]["mode"] == "auto"
        print(f"  [PASS] 更新成功: quality=2160p, mode=auto")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 6. 重复订阅拦截
    print("\n[TEST] POST /subscribe — 重复订阅拦截")
    try:
        r = requests.post(f"{BASE}/subscribe", json={
            "title": "API测试片",
            "year": "2026",
            "type": "movie",
        }, timeout=10)
        data = r.json()
        assert data["status"] == "error", f"应该报错: {data}"
        print(f"  [PASS] 重复订阅被拦截: {data['message']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 7. 手动搜索（占位）
    print(f"\n[TEST] POST /subscribe/{sub_id}/search — 手动搜索")
    try:
        r = requests.post(f"{BASE}/subscribe/{sub_id}/search", timeout=10)
        data = r.json()
        assert data["status"] == "ok"
        print(f"  [PASS] 搜索占位返回: {data['message']}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 8. 删除订阅
    print(f"\n[TEST] DELETE /subscribe/{sub_id} — 删除订阅")
    try:
        r = requests.delete(f"{BASE}/subscribe/{sub_id}", timeout=10)
        data = r.json()
        assert data["status"] == "ok"
        # 确认已删除
        r2 = requests.get(f"{BASE}/subscribe/{sub_id}", timeout=10)
        assert r2.json().get("status") == "not_found"
        print(f"  [PASS] 删除成功")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    # 9. 查询不存在的
    print("\n[TEST] GET /subscribe/nonexistent — 查询不存在")
    try:
        r = requests.get(f"{BASE}/subscribe/nonexistent", timeout=10)
        data = r.json()
        assert data.get("status") == "not_found"
        print(f"  [PASS] 不存在返回 not_found")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    print(f"\n{'=' * 50}")
    print(f"结果: {passed} 通过, {failed} 失败")


if __name__ == "__main__":
    # 先检查后端是否在运行
    try:
        r = requests.get(f"{BASE}/", timeout=3)
        print(f"后端状态: {r.json()['message']}\n")
    except Exception:
        print("错误: 后端未运行，请先启动 backend (port 8000)")
        sys.exit(1)

    test_api()
