"""测试 DetailDrawer 拆分后的功能回归：验证刮削、重命名、整理等 API 链路"""
import requests
import json
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label} {detail}")

def test_api(method, url, params=None, json_body=None, expect_key=None):
    """通用 API 测试"""
    try:
        if method == "GET":
            r = requests.get(f"{BASE}{url}", params=params, timeout=15)
        else:
            r = requests.post(f"{BASE}{url}", params=params, json=json_body, timeout=15)
        data = r.json()
        if expect_key:
            check(f"{url} 返回 {expect_key}", expect_key in data, f"keys={list(data.keys())}")
        return data
    except Exception as e:
        check(f"{url} 请求成功", False, str(e))
        return None

# ── 测试用例 1：电影文件夹（其他视频/洗版测试） ──
print("\n" + "=" * 50)
print("测试 1：电影文件夹 - 刮削 + 读取")
print("=" * 50)

# 读取刮削数据
data = test_api("GET", "/scrape/read", {"path": r"\\DS218play\share\视频\其他视频\洗版测试"}, expect_key="status")
if data and data.get("status") == "ok":
    check("刮削数据存在", True)
    d = data.get("data", {})
    check(f"标题: {d.get('title')}", bool(d.get("title")))
else:
    check("刮削数据存在", data and data.get("status") == "ok", f"status={data.get('status') if data else 'N/A'}")

# 读取海报
try:
    r = requests.get(f"{BASE}/scrape/poster", params={"path": r"\\DS218play\share\视频\其他视频\洗版测试"}, timeout=10)
    check(f"海报接口响应 (status={r.status_code})", r.status_code in [200, 404])
except Exception as e:
    check("海报接口", False, str(e))

# ── 测试用例 2：动画文件夹（动画番/测试动画合集） ──
print("\n" + "=" * 50)
print("测试 2：动画文件夹 - 刮削 + 读取")
print("=" * 50)

data = test_api("GET", "/scrape/read", {"path": r"\\DS218play\share\视频\动画番\测试动画合集"}, expect_key="status")
if data:
    check(f"状态: {data.get('status')}", data.get("status") in ["ok", "not_found"])

# ── 测试用例 3：电影文件夹（电影/测试文件夹） ──
print("\n" + "=" * 50)
print("测试 3：电影文件夹 - 刮削 + 读取")
print("=" * 50)

data = test_api("GET", "/scrape/read", {"path": r"\\DS218play\share\视频\电影\测试文件夹"}, expect_key="status")
if data:
    check(f"状态: {data.get('status')}", data.get("status") in ["ok", "not_found"])

# ── 测试用例 4：刮削候选搜索（TMDB/豆瓣/Bangumi） ──
print("\n" + "=" * 50)
print("测试 4：刮削候选搜索")
print("=" * 50)

# TMDB 候选
data = test_api("GET", "/scrape/candidates", {"name": "盗梦空间"}, expect_key="candidates")
if data:
    candidates = data.get("candidates", [])
    check(f"TMDB 候选数量: {len(candidates)}", len(candidates) > 0)
    if candidates:
        c = candidates[0]
        check(f"候选有评分: {c.get('rating')}", "rating" in c)

# 豆瓣候选
data = test_api("GET", "/scrape/douban", {"name": "盗梦空间"}, expect_key="candidates")
if data:
    candidates = data.get("candidates", [])
    check(f"豆瓣候选数量: {len(candidates)}", len(candidates) > 0)
    if candidates:
        c = candidates[0]
        check(f"候选有评分: {c.get('rating')}", c.get("rating", 0) > 0)
        check(f"候选有类型: {c.get('genres')}", bool(c.get("genres")))

# Bangumi 候选
data = test_api("GET", "/scrape/bangumi", {"name": "进击的巨人"}, expect_key="candidates")
if data:
    candidates = data.get("candidates", [])
    check(f"Bangumi 候选数量: {len(candidates)}", len(candidates) > 0)
    if candidates:
        c = candidates[0]
        check(f"候选有评分: {c.get('rating')}", c.get("rating", 0) > 0)

# ── 测试用例 5：详情多源算法 ──
print("\n" + "=" * 50)
print("测试 5：详情多源算法")
print("=" * 50)

# 豆瓣优先
data = test_api("GET", "/media/info", {"title": "霸王别姬", "source": "douban", "type": "movie"})
if data:
    check(f"豆瓣优先: found={data.get('found')}, source={data.get('source')}", data.get("found") and data.get("source") == "douban")

# Bangumi 优先
data = test_api("GET", "/media/info", {"title": "进击的巨人", "source": "bangumi", "type": "tv", "id": "12189"})
if data:
    check(f"Bangumi 优先: found={data.get('found')}, source={data.get('source')}", data.get("found") and data.get("source") == "bangumi")

# TMDB 优先
data = test_api("GET", "/media/info", {"title": "Inception", "source": "tmdb", "type": "movie"})
if data:
    check(f"TMDB 优先: found={data.get('found')}, source={data.get('source')}", data.get("found") and data.get("source") == "tmdb")

# ── 测试用例 6：影子名 API ──
print("\n" + "=" * 50)
print("测试 6：影子名 API")
print("=" * 50)

data = test_api("GET", "/media/shadow-names", expect_key=None)
check("影子名接口可用", data is not None)

# ── 测试用例 7：禁止刮削列表 ──
print("\n" + "=" * 50)
print("测试 7：禁止刮削列表")
print("=" * 50)

data = test_api("GET", "/no-scrape")
check("禁止刮削接口可用", data is not None)

print(f"\n{'='*50}")
print(f"结果: {PASS} 通过, {FAIL} 失败")
if FAIL > 0:
    sys.exit(1)
