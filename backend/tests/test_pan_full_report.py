"""完整测试报告：所有网盘搜索源结果 + 链接存活检测 + 站点可用性分析。"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

KEYWORD = "流浪地球"
CHECK_TIMEOUT = 5  # 链接存活检测超时（秒）


def check_url_alive(url: str) -> dict:
    """检测链接是否存活。返回 {alive, status_code, redirect_url}"""
    try:
        resp = requests.head(url, timeout=CHECK_TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"})
        alive = resp.status_code < 400
        return {"alive": alive, "status": resp.status_code, "final_url": resp.url[:80]}
    except requests.Timeout:
        return {"alive": False, "status": "timeout", "final_url": ""}
    except Exception as e:
        return {"alive": False, "status": str(e)[:40], "final_url": ""}


def batch_check_urls(results: list) -> list:
    """并发检测所有链接存活状态。"""
    checks = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(check_url_alive, r.share_url): i for i, r in enumerate(results)}
        for f in as_completed(futures):
            idx = futures[f]
            checks[idx] = f.result()
    return [checks.get(i, {"alive": False, "status": "skip", "final_url": ""}) for i in range(len(results))]


def test_source(name, create_fn):
    """测试单个源，返回 (results, elapsed, error)"""
    print(f"\n{'='*70}")
    print(f"  测试源: {name}")
    print(f"{'='*70}")
    try:
        scraper = create_fn()
        start = time.time()
        results = scraper.search(KEYWORD)
        elapsed = time.time() - start
        print(f"  结果数: {len(results)}  耗时: {elapsed:.1f}s")
        return results, elapsed, None
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return [], 0, str(e)


def test_site_accessibility():
    """测试各站点的可访问性。"""
    print(f"\n{'='*70}")
    print(f"  站点可访问性检测")
    print(f"{'='*70}")

    sites = [
        ("pansearch.me", "https://www.pansearch.me", "PanSearch 主力源"),
        ("pansou.app", "https://pansou.app/api/health", "PanSou API"),
        ("lingfengyun.com", "https://www.lingfengyun.com", "凌风云"),
        ("pansoso.com", "https://www.pansoso.com", "盘搜搜"),
        ("xiaobaipan.com", "https://www.xiaobaipan.com", "小白盘"),
        ("qupansou.com", "https://www.qupansou.com", "趣盘搜"),
        ("so.slowread.net", "https://so.slowread.net", "慢读搜索"),
        ("wnsearch.top", "https://www.wnsearch.top", "我能搜"),
    ]

    results = []
    for domain, url, desc in sites:
        try:
            start = time.time()
            resp = requests.get(url, timeout=8,
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
                                allow_redirects=True)
            elapsed = time.time() - start
            # 判断是否需要登录
            body = resp.text[:2000].lower()
            needs_login = any(kw in body for kw in ["login", "登录", "sign in", "注册"])
            # 判断是否有反爬
            has_cf = "cloudflare" in body or "cf-ray" in (resp.headers.get("server", "") + str(resp.headers.get("cf-ray", ""))).lower()
            has_js_challenge = "challenge" in body or "verify" in body or "captcha" in body

            status_str = f"{resp.status_code}"
            if has_cf:
                status_str += " [Cloudflare]"
            if has_js_challenge:
                status_str += " [JS验证]"
            if needs_login:
                status_str += " [需登录]"

            results.append({
                "domain": domain, "desc": desc, "status": resp.status_code,
                "time": f"{elapsed:.1f}s", "size": len(resp.text),
                "needs_login": needs_login, "cloudflare": has_cf,
                "js_challenge": has_js_challenge, "note": status_str,
            })
            print(f"  {domain:25s} {status_str:30s} {elapsed:.1f}s  {len(resp.text):>6} bytes")
        except requests.Timeout:
            results.append({"domain": domain, "desc": desc, "status": "timeout", "time": ">8s", "note": "超时"})
            print(f"  {domain:25s} {'超时':30s}")
        except Exception as e:
            results.append({"domain": domain, "desc": desc, "status": "error", "time": "-", "note": str(e)[:40]})
            print(f"  {domain:25s} {'错误: ' + str(e)[:40]:30s}")

    return results


def print_results_table(source_name, results, alive_checks):
    """打印结果明细表。"""
    if not results:
        print(f"  （无结果）")
        return

    print(f"\n  {'#':>3} {'网盘':6} {'存活':4} {'HTTP':5} {'标题':40} {'链接':50} {'提取码':6}")
    print(f"  {'─'*3} {'─'*6} {'─'*4} {'─'*5} {'─'*40} {'─'*50} {'─'*6}")

    alive_count = 0
    for i, r in enumerate(results):
        chk = alive_checks[i] if i < len(alive_checks) else {}
        alive = chk.get("alive", False)
        status = chk.get("status", "?")
        if alive:
            alive_count += 1
        alive_icon = "✓" if alive else "✗"

        title = (r.clean_title or r.title)[:38]
        url_short = r.share_url[:48]
        pwd = r.password[:6] if r.password else ""

        print(f"  {i+1:>3} {r.pan_type.value:6} {alive_icon:4} {str(status):5} {title:40} {url_short:50} {pwd:6}")

    print(f"\n  存活率: {alive_count}/{len(results)} ({alive_count*100//max(len(results),1)}%)")


if __name__ == "__main__":
    print(f"搜索关键词: {KEYWORD}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ── 第一部分：站点可访问性 ──
    site_results = test_site_accessibility()

    # ── 第二部分：搜索源测试 ──
    all_source_results = {}

    # PanSearch
    from pan_scraper_pansearch import PanSearchScraper
    r, t, e = test_source("PanSearch (pansearch.me)", lambda: PanSearchScraper())
    all_source_results["pansearch"] = {"results": r, "time": t, "error": e}

    # PanSou 增强版
    from pan_scraper_pansou import PanSouClient
    r, t, e = test_source("PanSou 增强版 (pansou.app)", lambda: PanSouClient(api_url="https://pansou.app"))
    all_source_results["pansou"] = {"results": r, "time": t, "error": e}

    # 通用站点（逐个测试）
    from pan_scraper_sites import GenericPanSiteScraper, SITE_CONFIGS
    for site_name, config in SITE_CONFIGS.items():
        r, t, e = test_source(f"通用站点: {config.name} ({site_name})", lambda c=config: GenericPanSiteScraper(c))
        all_source_results[site_name] = {"results": r, "time": t, "error": e}

    # 慢读
    from pan_scraper_slowread import SlowreadScraper
    r, t, e = test_source("慢读搜索 (so.slowread.net)", lambda: SlowreadScraper())
    all_source_results["slowread"] = {"results": r, "time": t, "error": e}

    # 我能搜
    from pan_scraper_wnsearch import WnSearchScraper
    r, t, e = test_source("我能搜 (wnsearch.top)", lambda: WnSearchScraper())
    all_source_results["wnsearch"] = {"results": r, "time": t, "error": e}

    # ── 第三部分：链接存活检测（只检测有结果的源）──
    print(f"\n{'='*70}")
    print(f"  链接存活检测（并发 HEAD 请求）")
    print(f"{'='*70}")

    for src_name, data in all_source_results.items():
        results = data["results"]
        if not results:
            continue
        print(f"\n  ── {src_name} ({len(results)} 条) ──")
        checks = batch_check_urls(results)
        data["alive_checks"] = checks
        print_results_table(src_name, results, checks)

    # ── 第四部分：汇总报告 ──
    print(f"\n{'='*70}")
    print(f"  汇总报告")
    print(f"{'='*70}")

    print(f"\n  {'源':15} {'结果数':>6} {'耗时':>6} {'存活':>6} {'存活率':>6} {'状态':15}")
    print(f"  {'─'*15} {'─'*6} {'─'*6} {'─'*6} {'─'*6} {'─'*15}")

    for src_name, data in all_source_results.items():
        results = data["results"]
        elapsed = data["time"]
        error = data["error"]
        checks = data.get("alive_checks", [])
        alive_count = sum(1 for c in checks if c.get("alive"))
        total = len(results)
        rate = f"{alive_count*100//max(total,1)}%" if total > 0 else "-"
        status = "❌ " + (error[:12] if error else "无结果") if total == 0 else "✅ 正常"

        print(f"  {src_name:15} {total:>6} {elapsed:>5.1f}s {alive_count:>6} {rate:>6} {status:15}")

    # ── 第五部分：反爬难度分析 ──
    print(f"\n{'='*70}")
    print(f"  反爬难度分析")
    print(f"{'='*70}")

    analysis = [
        ("pansearch.me", "PanSearch", "无", "低", "直接 requests 可用，偶尔限频需间隔"),
        ("pansou.app", "PanSou API", "无", "低", "公开 API，有文档，直接调用"),
        ("lingfengyun.com", "凌风云", "需登录+VIP", "高", "搜索需登录，结果页不含直链需二次跳转"),
        ("pansoso.com", "盘搜搜", "404/域名变更", "中", "可能换了域名或关站，需确认新地址"),
        ("xiaobaipan.com", "小白盘", "403 Forbidden", "中", "服务端拒绝，可能需要特定 Referer/Cookie"),
        ("qupansou.com", "趣盘搜", "超时", "中", "连接超时，可能需代理或已关站"),
        ("so.slowread.net", "慢读搜索", "纯 JS 渲染", "高", "搜索结果由前端 JS 动态加载，需 Playwright"),
        ("wnsearch.top", "我能搜", "纯 JS 渲染", "高", "同上，搜索结果由前端 JS 动态加载"),
    ]

    print(f"\n  {'站点':20} {'名称':10} {'障碍':15} {'难度':4} {'说明':50}")
    print(f"  {'─'*20} {'─'*10} {'─'*15} {'─'*4} {'─'*50}")
    for domain, name, barrier, difficulty, note in analysis:
        print(f"  {domain:20} {name:10} {barrier:15} {difficulty:4} {note:50}")

    print(f"\n完成! {time.strftime('%H:%M:%S')}")
