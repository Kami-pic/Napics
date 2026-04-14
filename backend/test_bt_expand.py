"""BT/磁力搜索扩展 + 网盘修复 — 集成测试。

测试项：
1. 网盘源修复：rrdynb + ddys
2. BT 直搜源：Bitsearch + 磁力熊 + XL720 + Nyaa + 蜜柑
3. 反爬基础设施：curl_cffi + CF 检测
4. 搜索路由合并：_merge_bt_extra_sources
5. 蜜柑 RSS 源：订阅框架注册
"""
import sys
import time

passed = 0
failed = 0
skipped = 0


def test(name, fn):
    global passed, failed, skipped
    try:
        result = fn()
        if result == "SKIP":
            print(f"  ⏭ {name} (跳过)")
            skipped += 1
        else:
            print(f"  ✓ {name}")
            passed += 1
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        failed += 1


# ============================================================
print("\n[1/6] 反爬基础设施")
# ============================================================

def test_curl_cffi_available():
    from curl_cffi import requests as cf_requests
    s = cf_requests.Session(impersonate="chrome131")
    assert s is not None

def test_scraper_base_curl_cffi():
    from scraper_base import ScraperBase
    s = ScraperBase(use_curl_cffi=True)
    assert s.use_curl_cffi is True
    assert s._get_cf_session() is not None

def test_scraper_base_cf_detection():
    from scraper_base import ScraperBase
    # 模拟 CF 响应
    class FakeResp:
        status_code = 403
        text = "<html><title>Just a moment...</title><body>Cloudflare challenge</body></html>"
    assert ScraperBase.is_cf_blocked(FakeResp()) is True
    # 正常响应
    class NormalResp:
        status_code = 200
        text = "<html><title>OK</title></html>"
    assert ScraperBase.is_cf_blocked(NormalResp()) is False

def test_scraper_base_cache():
    from scraper_base import ScraperBase
    s = ScraperBase()
    s.set_cached("test_key", [1, 2, 3])
    assert s.get_cached("test_key") == [1, 2, 3]
    # 空结果不缓存
    s.set_cached("empty_key", [])
    assert s.get_cached("empty_key") is None

test("curl_cffi 可用", test_curl_cffi_available)
test("ScraperBase curl_cffi 集成", test_scraper_base_curl_cffi)
test("ScraperBase CF 拦截检测", test_scraper_base_cf_detection)
test("ScraperBase 缓存机制", test_scraper_base_cache)


# ============================================================
print("\n[2/6] 网盘源修复")
# ============================================================

def test_rrdynb_import():
    from pan_scraper_rrdynb import RrdynbScraper
    s = RrdynbScraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "rrdynb"

def test_ddys_import():
    from pan_scraper_ddys import DdysScraper
    s = DdysScraper()
    assert s.SOURCE_NAME == "ddys"
    assert s.BASE_URL == "https://ddys.io"

def test_ddys_decode_link():
    from pan_scraper_ddys import DdysScraper
    import base64
    url = "https://pan.quark.cn/s/test123"
    encoded = base64.b64encode(url.encode()).decode()
    decoded = DdysScraper._decode_link(encoded)
    assert decoded == url

def test_ddys_detect_pan_type():
    from pan_scraper_ddys import DdysScraper
    from pan_models import PanType
    assert DdysScraper._detect_pan_type("夸克网盘", "") == PanType.QUARK
    assert DdysScraper._detect_pan_type("", "https://pan.baidu.com/s/xxx") == PanType.BAIDU
    assert DdysScraper._detect_pan_type("", "https://example.com") is None

test("rrdynb 爬虫初始化 + curl_cffi", test_rrdynb_import)
test("ddys 爬虫初始化 + 域名更新", test_ddys_import)
test("ddys base64 链接解码", test_ddys_decode_link)
test("ddys 网盘类型识别", test_ddys_detect_pan_type)


# ============================================================
print("\n[3/6] BT 直搜源")
# ============================================================

def test_bitsearch_import():
    from bt_scraper_bitsearch import BitsearchScraper
    s = BitsearchScraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "bitsearch"

def test_bitsearch_parse():
    from bt_scraper_bitsearch import BitsearchScraper
    s = BitsearchScraper()
    items = [{"title": "Test Movie 1080p", "infohash": "A" * 40, "size": 3 * 1024**3,
              "seeders": 100, "leechers": 50, "category": 2, "verified": True}]
    results = s._parse_items(items)
    assert len(results) == 1
    assert results[0].title == "Test Movie 1080p"
    assert results[0].infohash == "A" * 40

def test_cilixiong_import():
    from bt_scraper_cilixiong import CilixiongScraper
    s = CilixiongScraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "cilixiong"

def test_xl720_import():
    from bt_scraper_xl720 import XL720Scraper
    s = XL720Scraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "xl720"

def test_xl720_thunder_decode():
    from bt_scraper_xl720 import XL720Scraper
    import base64
    url = "magnet:?xt=urn:btih:" + "B" * 40
    encoded = base64.b64encode(("AA" + url + "ZZ").encode()).decode()
    decoded = XL720Scraper._decode_thunder(encoded)
    assert decoded == url

def test_nyaa_import():
    from bt_scraper_nyaa import NyaaScraper
    s = NyaaScraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "nyaa"

def test_nyaa_parse_size():
    from bt_scraper_nyaa import _parse_size
    assert _parse_size("3.2 GiB") == 3.2
    assert _parse_size("512 MiB") == 0.5
    assert _parse_size("1.5 TiB") == 1536.0

def test_mikan_scraper_import():
    from bt_scraper_mikan import MikanScraper
    s = MikanScraper()
    assert s.use_curl_cffi is True
    assert s.SOURCE_NAME == "mikan"

test("Bitsearch 爬虫初始化", test_bitsearch_import)
test("Bitsearch 结果解析", test_bitsearch_parse)
test("磁力熊爬虫初始化", test_cilixiong_import)
test("XL720 爬虫初始化", test_xl720_import)
test("XL720 迅雷链接解码", test_xl720_thunder_decode)
test("Nyaa 爬虫初始化", test_nyaa_import)
test("Nyaa 大小解析", test_nyaa_parse_size)
test("蜜柑爬虫初始化", test_mikan_scraper_import)


# ============================================================
print("\n[4/6] 蜜柑 RSS 源")
# ============================================================

def test_mikan_rss_import():
    from rss_source_mikan import MikanRSSSource
    s = MikanRSSSource(proxy="")
    assert s.name == "mikan"
    assert s.display_name == "蜜柑计划"

def test_mikan_rss_parse_xml():
    from rss_source_mikan import MikanRSSSource
    s = MikanRSSSource()
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
    <channel><title>Test</title>
    <item>
        <title>[字幕组] 葬送的芙莉莲 第二季 / Sousou no Frieren S2 - 05 [1080p]</title>
        <enclosure url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12&amp;dn=test" length="524288000" type="application/x-bittorrent" />
        <pubDate>Mon, 14 Apr 2026 12:00:00 +0800</pubDate>
    </item>
    </channel></rss>"""
    items = s._parse_rss_xml(xml)
    assert len(items) == 1
    assert "葬送的芙莉莲" in items[0].title
    assert items[0].info_hash == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"
    assert items[0].episode == 5
    assert items[0].source_name == "mikan"
    assert items[0].size_gb > 0

def test_mikan_rss_empty_xml():
    from rss_source_mikan import MikanRSSSource
    s = MikanRSSSource()
    items = s._parse_rss_xml("<rss><channel></channel></rss>")
    assert items == []

test("蜜柑 RSS 源初始化", test_mikan_rss_import)
test("蜜柑 RSS XML 解析", test_mikan_rss_parse_xml)
test("蜜柑 RSS 空 XML", test_mikan_rss_empty_xml)


# ============================================================
print("\n[5/6] 搜索路由合并逻辑")
# ============================================================

def test_merge_function_exists():
    """验证 _merge_bt_extra_sources 函数存在且可调用"""
    from routes.search import _merge_bt_extra_sources
    assert callable(_merge_bt_extra_sources)

def test_shared_getters():
    """验证所有 shared.py 的 getter 函数存在"""
    from shared import (
        _get_bitsearch_scraper, _get_cilixiong_scraper,
        _get_xl720_scraper, _get_nyaa_scraper, _get_mikan_scraper,
    )
    # 只验证函数存在，不实际调用（避免触发网络请求）
    assert callable(_get_bitsearch_scraper)
    assert callable(_get_cilixiong_scraper)
    assert callable(_get_xl720_scraper)
    assert callable(_get_nyaa_scraper)
    assert callable(_get_mikan_scraper)

def test_search_result_format():
    """验证 SearchResult 模型兼容直搜源的字段"""
    from searcher import SearchResult
    from quality_parser import parse_quality, get_quality_level
    quality = parse_quality("Test.Movie.2024.1080p.BluRay.x265")
    r = SearchResult(
        title="Test Movie",
        size_gb=3.5,
        indexer="bitsearch",
        seeders=100,
        leechers=50,
        download_url="magnet:?xt=urn:btih:" + "C" * 40,
        quality_tag=quality.display,
        quality=quality,
        quality_rank=get_quality_level(quality).rank,
    )
    assert r.indexer == "bitsearch"
    assert "btih:" in r.download_url

test("合并函数存在", test_merge_function_exists)
test("shared.py getter 函数", test_shared_getters)
test("SearchResult 兼容直搜源", test_search_result_format)


# ============================================================
print("\n[6/6] 前端颜色映射")
# ============================================================

def test_indexer_colors_defined():
    """验证前端颜色映射文件语法正确（通过 import 检查）"""
    # 这里只能检查后端的常量定义，前端 TSX 需要 vitest
    # 但我们可以验证 search-enhance-todo 中记录的源名和后端一致
    from bt_scraper_bitsearch import BitsearchScraper
    from bt_scraper_cilixiong import CilixiongScraper
    from bt_scraper_xl720 import XL720Scraper
    from bt_scraper_nyaa import NyaaScraper
    from bt_scraper_mikan import MikanScraper
    names = {
        BitsearchScraper.SOURCE_NAME,
        CilixiongScraper.SOURCE_NAME,
        XL720Scraper.SOURCE_NAME,
        NyaaScraper.SOURCE_NAME,
        MikanScraper.SOURCE_NAME,
    }
    expected = {"bitsearch", "cilixiong", "xl720", "nyaa", "mikan"}
    assert names == expected, f"源名不匹配: {names} != {expected}"

test("直搜源名称一致性", test_indexer_colors_defined)


# ============================================================
print(f"\n{'='*40}")
print(f"结果: {passed} 通过, {failed} 失败, {skipped} 跳过")
print(f"{'='*40}")
sys.exit(1 if failed > 0 else 0)
