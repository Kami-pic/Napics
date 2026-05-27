"""完整测试 polish-todo 所有后端改动"""
import sys, os, json, importlib
sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0

def assert_true(cond):
    assert cond

def run_case(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  OK {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL {name}: {e}")

# ── 1. combined_recommend 去重 ──
print("\n[1/7] combined_recommend 去重")
from combined_recommend import _is_same_media, _calc_final_score, _dedup_and_merge

run_case("tmdb_id 精确匹配", lambda: assert_true(_is_same_media({"title":"A","tmdb_id":1}, {"title":"B","tmdb_id":1})))
run_case("短标题不误匹配", lambda: assert_true(not _is_same_media({"title":"航海王","year":"2024"}, {"title":"航海日记","year":"2024"})))
run_case("冷门降权生效", lambda: assert_true(_calc_final_score({"rating":5,"_source":"tmdb","_normalized_score":4.0,"vote_count":10}, 1) < 4.0))
run_case("非冷门不降权", lambda: assert_true(_calc_final_score({"rating":8,"_source":"douban","_normalized_score":8.0,"vote_count":5000}, 1) >= 8.0))

# 封面合并：仅 ID 匹配时覆盖
def test_cover_merge():
    items = [
        ({"title":"A","tmdb_id":1,"cover_url":"old.jpg","rating":5}, "douban"),
        ({"title":"A","tmdb_id":1,"poster_url":"new.jpg","cover_url":"new.jpg","rating":8}, "tmdb"),
    ]
    merged = _dedup_and_merge(items)
    assert merged[0].get("cover_url") == "new.jpg", f"cover should be new.jpg, got {merged[0].get('cover_url')}"

def test_cover_no_merge_fuzzy():
    items = [
        ({"title":"冰湖重生","cover_url":"correct.jpg","rating":7}, "douban"),
        ({"title":"冰湖传说","poster_url":"wrong.jpg","cover_url":"wrong.jpg","rating":9}, "tmdb"),
    ]
    merged = _dedup_and_merge(items)
    # 模糊匹配不应覆盖封面
    assert len(merged) >= 1
    assert merged[0].get("cover_url") == "correct.jpg", f"cover should stay correct.jpg"

run_case("封面合并-ID匹配时覆盖", test_cover_merge)
run_case("封面合并-模糊匹配不覆盖", test_cover_no_merge_fuzzy)

# ── 2. config 新字段 ──
print("\n[2/7] config 新字段")
from config_manager import AppConfig

def test_config_fields():
    c = AppConfig()
    assert c.subscribe_interval_hours == 4.0
    assert c.bt_search_sources == {}
    assert c.pan_search_sources == {}

run_case("subscribe_interval_hours 默认值", test_config_fields)

# ── 3. subscriber sources 字段 ──
print("\n[3/7] subscriber sources 字段")
from subscriber import Subscription

def test_sub_sources():
    s = Subscription(title="test")
    assert s.sources == []
    s2 = Subscription(title="test", sources=["prowlarr","mikan"])
    assert s2.sources == ["prowlarr","mikan"]

run_case("Subscription.sources 默认空列表", test_sub_sources)

# ── 4. 搜索源管理接口 ──
print("\n[4/7] 搜索源管理")
import requests as req

def test_search_sources_api():
    r = req.get("http://localhost:8000/search/sources", timeout=5)
    assert r.status_code == 200
    data = r.json()
    sources = data.get("sources", [])
    names = [s["name"] for s in sources]
    assert "prowlarr" in names
    assert "bitsearch" in names
    assert "pansearch" in names
    bt_sources = [s for s in sources if s["type"] == "bt"]
    pan_sources = [s for s in sources if s["type"] == "pan"]
    assert len(bt_sources) >= 6, f"BT sources: {len(bt_sources)}"
    assert len(pan_sources) >= 5, f"Pan sources: {len(pan_sources)}"

def test_toggle_source():
    r = req.put("http://localhost:8000/search/sources/bitsearch",
                json={"enabled": False}, timeout=5)
    assert r.status_code == 200
    assert r.json()["enabled"] == False
    # 恢复
    req.put("http://localhost:8000/search/sources/bitsearch",
            json={"enabled": True}, timeout=5)

run_case("GET /search/sources 返回所有源", test_search_sources_api)
run_case("PUT /search/sources 切换开关", test_toggle_source)

# ── 5. 订阅源接口 ──
print("\n[5/7] 订阅源管理")

def test_subscribe_sources():
    r = req.get("http://localhost:8000/subscribe/sources", timeout=5)
    assert r.status_code == 200
    data = r.json()
    sources = data if isinstance(data, list) else data.get("sources", [])
    names = [s["name"] for s in sources]
    assert "prowlarr" in names
    assert "mikan" in names
    assert "nyaa" in names, f"Nyaa not registered! Got: {names}"

run_case("GET /subscribe/sources 包含 nyaa", test_subscribe_sources)

# ── 6. Nyaa RSS 源 ──
print("\n[6/7] Nyaa RSS 源")

def test_nyaa_rss_source():
    from rss_source_nyaa import NyaaRSSSource
    src = NyaaRSSSource()
    assert src.name == "nyaa"
    assert src.display_name == "Nyaa"

run_case("NyaaRSSSource 基本属性", test_nyaa_rss_source)

# ── 7. BT 搜索接口 ──
print("\n[7/7] BT 搜索接口")

def test_bt_search():
    r = req.get("http://localhost:8000/search/single",
                params={"keyword": "hello", "skip_filter": "true"}, timeout=120)
    assert r.status_code == 200
    data = r.json()
    assert data.get("bt_count", 0) > 0, f"bt_count={data.get('bt_count')}"

run_case("BT 搜索返回结果", test_bt_search)

# ── 汇总 ──
print(f"\n{'='*40}")
print(f"通过: {passed}, 失败: {failed}")
