"""测试 GitHub 资源仓库爬虫 + 聚合效果。"""
import time
import requests

KEYWORDS = ["流浪地球", "军火女王", "灌篮高手", "鬼灭之刃"]
CHECK_TIMEOUT = 5

# 1. 单独测试 GitHub 源
print("=" * 65)
print("  GitHub 资源仓库爬虫测试")
print("=" * 65)

from pan_scraper_github import GitHubPanScraper

gh = GitHubPanScraper()

for kw in KEYWORDS:
    t = time.time()
    results = gh.search(kw)
    elapsed = time.time() - t
    print(f"\n  搜索: {kw}  结果: {len(results)} 条  耗时: {elapsed:.1f}s")
    for r in results[:5]:
        print(f"    [{r.pan_type.value:6}] {r.clean_title[:55]:55} {r.share_url[:45]}")

print(f"\n  索引总量: {len(gh._index)} 条")

# 2. 链接存活检测（从每个关键词取前2条）
print(f"\n{'=' * 65}")
print(f"  链接存活检测")
print(f"{'=' * 65}")

all_check = []
for kw in KEYWORDS:
    results = gh.search(kw)
    for r in results[:2]:
        all_check.append(r)

alive = 0
for r in all_check:
    try:
        resp = requests.head(r.share_url, timeout=CHECK_TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        ok = resp.status_code < 400
        if ok:
            alive += 1
        icon = "✓" if ok else "✗"
        print(f"  {icon} {resp.status_code} {r.clean_title[:45]:45} {r.share_url[:45]}")
    except Exception as e:
        print(f"  ✗ ERR {r.clean_title[:45]:45} {str(e)[:30]}")

print(f"\n  存活: {alive}/{len(all_check)}")

# 3. 聚合测试
print(f"\n{'=' * 65}")
print(f"  聚合搜索（全部源）")
print(f"{'=' * 65}")

from pan_search_service import PanSearchService

svc = PanSearchService(
    search_sources={
        "pansearch": True, "pansou": True, "gogopanso": True, "github": True,
        "rrdynb": False, "ddys": False, "sites": False, "slowread": False, "wnsearch": False,
    },
    pansou_api_url="https://pansou.app",
)

for kw in KEYWORDS[:2]:
    t = time.time()
    resp = svc.search_sync(kw)
    elapsed = time.time() - t
    print(f"\n  搜索: {kw}  总结果: {resp.total} 条  耗时: {elapsed:.1f}s")
    for st in resp.source_statuses:
        if st.count > 0 or st.status != "disabled":
            icon = "✓" if st.status == "success" else ("✗" if st.status == "failed" else "○")
            print(f"    {icon} {st.name:12} {st.status:8} {st.count} 条")
    for pt, items in resp.groups.items():
        print(f"    {pt}: {len(items)} 条")

print(f"\n完成!")
