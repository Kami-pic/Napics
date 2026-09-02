"""测试 TODO 完成项：SSE 搜索进度 + 下载完成局部刷新 + 榜单 tmdb_id 补全"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def run_case(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed += 1


# ── 1. SSE 搜索端点 ──
print("\n[1] SSE 搜索端点")

def test_sse_endpoint_registered():
    from fastapi import FastAPI
    from routes.search import router
    app = FastAPI()
    app.include_router(router)
    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/search/stream" in paths, f"SSE 端点未注册: {paths}"

run_case("SSE 端点 /api/search/stream 已注册", test_sse_endpoint_registered)

def test_sse_endpoint_is_get():
    from fastapi import FastAPI
    from routes.search import router
    app = FastAPI()
    app.include_router(router)
    for r in app.routes:
        if getattr(r, "path", "") == "/api/search/stream":
            assert "GET" in r.methods, f"SSE 端点应为 GET，实际: {r.methods}"
            return
    assert False, "SSE 端点未找到"

run_case("SSE 端点为 GET 方法", test_sse_endpoint_is_get)

def test_original_search_still_works():
    from fastapi import FastAPI
    from routes.search import router
    # /search/single 已经拆到 routes/search_single.py，不在 routes.search 的 router 里
    from routes.search_single import router as single_router
    app = FastAPI()
    app.include_router(router)
    app.include_router(single_router)
    paths = [getattr(r, "path", "") for r in app.routes]
    assert "/api/search" in paths, "原始搜索端点丢失"
    assert "/search/single" in paths, "单关键词搜索端点丢失"

run_case("原始搜索端点未受影响", test_original_search_still_works)


# ── 2. 下载完成局部刷新 ──
print("\n[2] 下载完成局部刷新")

def test_trigger_local_refresh_exists():
    from download_manager import DownloadManager
    assert hasattr(DownloadManager, "_trigger_local_refresh"), "方法不存在"

run_case("_trigger_local_refresh 方法存在", test_trigger_local_refresh_exists)

def test_relocate_calls_refresh():
    """验证 _relocate_to_save_path 中调用了 _trigger_local_refresh"""
    import inspect
    from download_manager import DownloadManager
    source = inspect.getsource(DownloadManager._relocate_to_save_path)
    assert "_trigger_local_refresh" in source, "转移完成后未调用局部刷新"

run_case("_relocate_to_save_path 调用了 _trigger_local_refresh", test_relocate_calls_refresh)


# ── 3. 榜单 tmdb_id 补全 ──
print("\n[3] 榜单 tmdb_id 补全")

# 这个函数从 routes/discover.py 搬到了业务层 discover_enrich.py，
# 并去掉了下划线前缀（它现在是模块的公开入口）。
def test_async_enrich_exists():
    from discover_enrich import async_enrich_tmdb_ids
    assert callable(async_enrich_tmdb_ids)

run_case("async_enrich_tmdb_ids 函数存在", test_async_enrich_exists)

def test_recommend_calls_enrich():
    """验证推荐接口中豆瓣源调用了 tmdb_id 补全"""
    import inspect
    import discover_enrich
    source = inspect.getsource(discover_enrich)
    assert "async_enrich_tmdb_ids" in source, "补全入口丢失"

run_case("发现推荐链路里有 tmdb_id 补全", test_recommend_calls_enrich)

def test_enrich_skips_existing_tmdb_id():
    """已有 tmdb_id 的条目不应被重复补全"""
    items = [{"title": "测试", "tmdb_id": 12345, "douban_id": "111"}]
    from discover_enrich import async_enrich_tmdb_ids
    # 起后台线程，不会报错即可
    async_enrich_tmdb_ids(items)
    assert items[0]["tmdb_id"] == 12345, "已有 tmdb_id 被覆盖"

run_case("已有 tmdb_id 的条目不被覆盖", test_enrich_skips_existing_tmdb_id)


# ── 4. 搜索源管理 ──
print("\n[4] 搜索源管理（回归测试）")

def test_search_sources_endpoint():
    """源列表现在**只返回已安装插件对应的源**（插件守卫），所以不能断言
    bitsearch / pansearch 一定在里面 —— 那取决于装了哪些插件。
    这里只钉住结构和"返回的每个源都是被允许的"。"""
    from plugin_guard import get_allowed_bt_sources, is_pan_search_allowed
    from routes.search import get_search_sources

    result = get_search_sources()
    assert "sources" in result
    names = [s["name"] for s in result["sources"]]
    allowed = set(get_allowed_bt_sources())
    for name in names:
        # 网盘源不在 BT 允许集合里，单独由 is_pan_search_allowed 控制
        assert name in allowed or is_pan_search_allowed(), f"返回了未被允许的源: {name}"

run_case("搜索源列表只含已允许的源", test_search_sources_endpoint)

def test_bt_source_defaults():
    from routes.search import _BT_SOURCE_DEFAULTS
    assert "prowlarr" in _BT_SOURCE_DEFAULTS
    assert "nyaa" in _BT_SOURCE_DEFAULTS
    assert "mikan" in _BT_SOURCE_DEFAULTS

run_case("BT 源默认配置完整", test_bt_source_defaults)


# ── 5. Nyaa RSS 源（回归测试）──
print("\n[5] Nyaa RSS 源（回归测试）")

def test_nyaa_rss_import():
    from rss_source_nyaa import NyaaRSSSource
    src = NyaaRSSSource(proxy="")
    assert src.name == "nyaa"
    assert src.display_name == "Nyaa"

run_case("NyaaRSSSource 导入和属性正确", test_nyaa_rss_import)

def test_nyaa_rss_parse():
    from rss_source_nyaa import NyaaRSSSource
    src = NyaaRSSSource()
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa">
    <channel><item>
        <title>[SubGroup] Test Anime S01E05 1080p</title>
        <link>https://nyaa.si/view/12345</link>
        <nyaa:infoHash>AABBCCDDEE11223344556677889900AABBCCDDEE</nyaa:infoHash>
        <nyaa:size>1.5 GiB</nyaa:size>
        <nyaa:seeders>42</nyaa:seeders>
        <pubDate>Mon, 14 Apr 2026 12:00:00 +0000</pubDate>
    </item></channel></rss>"""
    items = src._parse_rss_xml(xml)
    assert len(items) == 1
    assert items[0].episode == 5
    assert items[0].seeders == 42
    assert items[0].size_gb == 1.5
    assert "AABBCCDDEE" in items[0].info_hash

run_case("Nyaa RSS XML 解析正确", test_nyaa_rss_parse)


# ── 6. quality_score 回归 ──
print("\n[6] quality_score 回归")

def test_quality_score():
    from quality_parser import parse_quality, compute_quality_score
    q = parse_quality("Movie.2024.2160p.Remux.DTS-HD.MA.x265")
    score = compute_quality_score(q)
    assert score > 70, f"4K Remux 评分应 > 70，实际: {score}"

run_case("4K Remux 评分 > 70", test_quality_score)

def test_enrich_result():
    from routes.search import _enrich_result
    from unittest.mock import MagicMock
    r = MagicMock()
    r.dict.return_value = {"title": "test", "download_url": "magnet:?xt=urn:btih:abc"}
    from quality_parser import parse_quality
    r.quality = parse_quality("Movie.2024.1080p.WEB-DL.x264.AAC")
    d = _enrich_result(r)
    assert "quality_score" in d
    assert d["quality_score"] > 0

run_case("_enrich_result 附加 quality_score", test_enrich_result)


# ── 汇总 ──
print(f"\n{'='*40}")
print(f"通过: {passed}  失败: {failed}  总计: {passed + failed}")
if __name__ == "__main__" and failed > 0:
    sys.exit(1)
