"""测试发现页 API 链路：推荐源字段 + 详情多源算法 + 极端情况"""
import requests
import json
import sys

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label} {detail}")

def run_recommend_source_case(source: str, checks: dict):
    """测试推荐源返回的数据"""
    print(f"\n{'='*50}")
    print(f"推荐源: {source}")
    try:
        r = requests.get(f"{BASE}/discover/recommend/{source}?start=0&count=5", timeout=15)
        data = r.json()
        items = data.get("items", [])
        check("有数据返回", len(items) > 0, f"got {len(items)}")
        if items:
            item = items[0]
            for field, desc in checks.items():
                val = item.get(field)
                check(f"{desc}: {field}={val}", val is not None and val != "" and val != 0 and val != [])
    except Exception as e:
        check("请求成功", False, str(e))

def run_media_info_case(title: str, source: str, id: str = "", year: str = "", type: str = "movie", expect_source: str = ""):
    """测试详情接口"""
    print(f"\n{'='*50}")
    print(f"详情: title={title} source={source} id={id}")
    try:
        params = {"title": title, "year": year, "type": type, "source": source, "id": id}
        r = requests.get(f"{BASE}/media/info", params=params, timeout=30)
        d = r.json()
        found = d.get("found", False)
        check("找到结果", found)
        if found:
            check(f"标题: {d.get('title')}", bool(d.get("title")))
            check(f"评分: {d.get('rating')}", d.get("rating", 0) > 0)
            check(f"简介: {(d.get('overview') or '')[:30]}...", bool(d.get("overview")))
            actual_source = d.get("source", "未标注")
            if expect_source:
                check(f"数据源: {actual_source} (期望 {expect_source})", actual_source == expect_source)
            else:
                print(f"  ℹ️ 数据源: {actual_source}")
    except Exception as e:
        check("请求成功", False, str(e))

if __name__ == "__main__":
    print("=" * 50)
    print("一、推荐源数据字段验证")
    print("=" * 50)

    run_recommend_source_case("douban_movie_hot", {
        "rating": "豆瓣评分", "genres": "类型", "countries": "国家", "year": "年份"
    })
    run_recommend_source_case("douban_tv_hot", {
        "rating": "豆瓣评分", "genres": "类型", "episodes_info": "集数信息"
    })
    run_recommend_source_case("bangumi_calendar", {
        "rating": "Bangumi评分", "title": "标题", "year": "年份", "media_type": "类型"
    })
    run_recommend_source_case("tmdb_trending", {
        "rating": "TMDB评分", "title": "标题", "year": "年份", "media_type": "类型"
    })

    print("\n\n" + "=" * 50)
    print("二、详情接口多源算法验证")
    print("=" * 50)

    # 豆瓣 tab → 优先豆瓣
    run_media_info_case("密探", "douban", id="36697078", year="2025", type="movie", expect_source="douban")
    # 豆瓣 tab → 无 ID 时搜索
    run_media_info_case("霸王别姬", "douban", year="1993", type="movie", expect_source="douban")
    # TMDB tab → 优先 TMDB
    run_media_info_case("Inception", "tmdb", year="2010", type="movie", expect_source="tmdb")
    # Bangumi tab → 用 bgm_id 直接拉
    run_media_info_case("进击的巨人", "bangumi", id="12189", type="tv", expect_source="bangumi")
    # Bangumi tab → 无 ID 搜索
    run_media_info_case("我独自升级", "bangumi", type="tv", expect_source="bangumi")

    print("\n\n" + "=" * 50)
    print("三、极端情况 & Fallback 验证")
    print("=" * 50)

    # 不存在的影片
    run_media_info_case("完全不存在的影片12345", "douban", type="movie")
    # Bangumi 搜不到 → fallback 豆瓣
    run_media_info_case("霸王别姬", "bangumi", type="movie")
    # TMDB 搜不到的中文片 → fallback 豆瓣
    run_media_info_case("白日提灯", "tmdb", type="tv")

    print(f"\n\n{'='*50}")
    print(f"结果: {PASS} 通过, {FAIL} 失败")
    if FAIL > 0:
        sys.exit(1)
