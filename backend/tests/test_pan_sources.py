"""测试所有网盘搜索源 — 逐个调用，输出结果数量和样本。"""

import sys
import time

# 测试关键词
KEYWORD = "流浪地球"

def test_pansearch():
    """测试 PanSearch（当前主力源）"""
    print("\n" + "=" * 60)
    print("【1】PanSearch (pansearch.me)")
    print("=" * 60)
    try:
        from pan_scraper_pansearch import PanSearchScraper
        scraper = PanSearchScraper()
        start = time.time()
        results = scraper.search(KEYWORD)
        elapsed = time.time() - start
        print(f"  结果数: {len(results)}  耗时: {elapsed:.1f}s")
        for r in results[:3]:
            print(f"  - [{r.pan_type.value}] {r.clean_title[:40]}  {r.share_url[:60]}")
        return len(results)
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return 0


def test_pansou():
    """测试 PanSou 增强版"""
    print("\n" + "=" * 60)
    print("【2】PanSou 增强版 (pansou.app)")
    print("=" * 60)
    try:
        from pan_scraper_pansou import PanSouClient
        scraper = PanSouClient(api_url="https://pansou.app")
        start = time.time()
        results = scraper.search(KEYWORD)
        elapsed = time.time() - start
        print(f"  结果数: {len(results)}  耗时: {elapsed:.1f}s")
        for r in results[:3]:
            print(f"  - [{r.pan_type.value}] {r.clean_title[:40]}  {r.share_url[:60]}")
        return len(results)
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return 0


def test_sites():
    """测试通用网盘搜索站（凌风云/盘搜搜/小白盘/趣盘搜）"""
    print("\n" + "=" * 60)
    print("【3】通用网盘搜索站 (凌风云/盘搜搜/小白盘/趣盘搜)")
    print("=" * 60)
    try:
        from pan_scraper_sites import MultiSiteScraper, GenericPanSiteScraper, SITE_CONFIGS
        # 逐个测试
        total = 0
        for name, config in SITE_CONFIGS.items():
            scraper = GenericPanSiteScraper(config)
            start = time.time()
            try:
                results = scraper.search(KEYWORD)
                elapsed = time.time() - start
                print(f"  [{name}] {config.name}: {len(results)} 条  耗时: {elapsed:.1f}s")
                for r in results[:2]:
                    print(f"    - [{r.pan_type.value}] {r.clean_title[:40]}  {r.share_url[:60]}")
                total += len(results)
            except Exception as e:
                elapsed = time.time() - start
                print(f"  [{name}] {config.name}: ❌ {e}  耗时: {elapsed:.1f}s")
        return total
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return 0


def test_slowread():
    """测试慢读搜索"""
    print("\n" + "=" * 60)
    print("【4】慢读搜索 (so.slowread.net)")
    print("=" * 60)
    try:
        from pan_scraper_slowread import SlowreadScraper
        scraper = SlowreadScraper()
        start = time.time()
        results = scraper.search(KEYWORD)
        elapsed = time.time() - start
        print(f"  结果数: {len(results)}  耗时: {elapsed:.1f}s")
        for r in results[:3]:
            print(f"  - [{r.pan_type.value}] {r.clean_title[:40]}  {r.share_url[:60]}")
        return len(results)
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return 0


def test_wnsearch():
    """测试我能搜"""
    print("\n" + "=" * 60)
    print("【5】我能搜 (wnsearch.top)")
    print("=" * 60)
    try:
        from pan_scraper_wnsearch import WnSearchScraper
        scraper = WnSearchScraper()
        start = time.time()
        results = scraper.search(KEYWORD)
        elapsed = time.time() - start
        print(f"  结果数: {len(results)}  耗时: {elapsed:.1f}s")
        for r in results[:3]:
            print(f"  - [{r.pan_type.value}] {r.clean_title[:40]}  {r.share_url[:60]}")
        return len(results)
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return 0


def test_aggregated():
    """测试聚合搜索服务"""
    print("\n" + "=" * 60)
    print("【6】聚合搜索 (PanSearchService)")
    print("=" * 60)
    try:
        from pan_search_service import PanSearchService
        service = PanSearchService(
            search_sources={
                "pansearch": True,
                "pansou": True,
                "sites": True,
                "slowread": True,
                "wnsearch": True,
                "rrdynb": False,
                "ddys": False,
            },
            pansou_api_url="https://pansou.app",
        )
        start = time.time()
        response = service.search_sync(KEYWORD)
        elapsed = time.time() - start
        print(f"  总结果数: {response.total}  耗时: {elapsed:.1f}s")
        print(f"  各源状态:")
        for s in response.source_statuses:
            icon = "✓" if s.status == "success" else ("✗" if s.status == "failed" else "○")
            print(f"    {icon} {s.name}: {s.status} ({s.count} 条)")
        print(f"  分组:")
        for pt, items in response.groups.items():
            print(f"    {pt}: {len(items)} 条")
        return response.total
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    print(f"搜索关键词: {KEYWORD}")
    print(f"开始时间: {time.strftime('%H:%M:%S')}")

    totals = {}
    totals["pansearch"] = test_pansearch()
    totals["pansou"] = test_pansou()
    totals["sites"] = test_sites()
    totals["slowread"] = test_slowread()
    totals["wnsearch"] = test_wnsearch()
    totals["aggregated"] = test_aggregated()

    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    for name, count in totals.items():
        icon = "✓" if count > 0 else "✗"
        print(f"  {icon} {name}: {count} 条")
    print(f"\n总计（聚合去重后）: {totals['aggregated']} 条")
