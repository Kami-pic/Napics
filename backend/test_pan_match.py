"""用媒体库中不太热门的片子测试搜索匹配效果和相关性。"""
import time
import requests

# 测试关键词列表（不太热门的片子）
KEYWORDS = [
    ("嘉年华", "movie", "2017"),
    ("整容液", "movie", "2020"),
    ("军火女王", "tv", ""),
    ("蛇蝎美人", "tv", ""),
    ("夏日幽灵", "movie", "2021"),
]

CHECK_TIMEOUT = 5

def test_pan_search_relevance_and_link_alive_report():
    from pan_search_service import PanSearchService

    svc = PanSearchService(
        search_sources={
            "pansearch": True, "pansou": True, "gogopanso": True,
            "rrdynb": False, "ddys": False, "sites": False,
            "slowread": False, "wnsearch": False,
        },
        pansou_api_url="https://pansou.app",
    )

    for kw, mtype, year in KEYWORDS:
        print(f"\n{'=' * 65}")
        print(f"  搜索: {kw} ({mtype} {year})")
        print(f"{'=' * 65}")
        t = time.time()
        resp = svc.search_sync(kw, media_type=mtype)
        elapsed = time.time() - t

        assert resp.total >= 0
        assert isinstance(resp.results, list)

        # 各源状态
        for st in resp.source_statuses:
            if st.status == "success" and st.count > 0:
                print(f"  {st.name}: {st.count} 条原始结果")

        print(f"  聚合去重后: {resp.total} 条  耗时: {elapsed:.1f}s")

        if resp.total == 0:
            print(f"  （无结果）")
            continue

        # 按类型统计
        type_counts = []
        for pt, items in resp.groups.items():
            type_counts.append(f"{pt}={len(items)}")
        print(f"  分组: {', '.join(type_counts)}")

        # 展示结果 + 相关性判断 + 存活检测
        print(f"  {'#':>3} {'相关':4} {'存活':4} {'网盘':6} {'来源':10} {'标题':45} {'链接':40}")
        print(f"  {'─'*3} {'─'*4} {'─'*4} {'─'*6} {'─'*10} {'─'*45} {'─'*40}")

        # 简单相关性判断：标题是否包含搜索词的任意2字子串
        kw_parts = [kw[j:j + 2] for j in range(len(kw) - 1)]

        relevant_count = 0
        alive_count = 0
        show_count = min(len(resp.results), 12)

        for i, r in enumerate(resp.results[:show_count]):
            title = (r.clean_title or r.title)[:43]
            relevant = any(p in title for p in kw_parts)
            if relevant:
                relevant_count += 1
            rel_icon = "✓" if relevant else "✗"

            # 存活检测
            try:
                chk = requests.head(r.share_url, timeout=CHECK_TIMEOUT, allow_redirects=True,
                                    headers={"User-Agent": "Mozilla/5.0"})
                alive = chk.status_code < 400
            except Exception:
                alive = False
            if alive:
                alive_count += 1
            alive_icon = "✓" if alive else "✗"

            url_short = r.share_url[:38]
            print(f"  {i+1:>3} {rel_icon:4} {alive_icon:4} {r.pan_type.value:6} {r.source:10} {title:45} {url_short:40}")

        # 全量相关性统计
        total = len(resp.results)
        total_relevant = sum(1 for r in resp.results if any(p in (r.clean_title or r.title) for p in kw_parts))
        print(f"\n  相关性: {total_relevant}/{total} ({total_relevant * 100 // max(total, 1)}%)")
        print(f"  存活率(前{show_count}条): {alive_count}/{show_count} ({alive_count * 100 // max(show_count, 1)}%)")

    print(f"\n{'=' * 65}")
    print(f"  测试完成")
    print(f"{'=' * 65}")
