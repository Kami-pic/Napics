"""DetailDrawer 拆分端到端测试 — 用实际有内容的子目录测试"""
import requests, json, sys, os

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend
BASE = "http://localhost:8000"
PASS = FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ✅ {label}")
    else: FAIL += 1; print(f"  ❌ {label} {detail}")

def get(url, params=None, timeout=15):
    try: return requests.get(f"{BASE}{url}", params=params, timeout=timeout).json()
    except Exception as e: return {"_error": str(e)}

def run_leaf_case(path, label, ft):
    """测试末端刮削单元（movie/tv/season）"""
    print(f"\n{'='*60}")
    print(f"📁 {label}")
    print(f"   {path} (type={ft})")
    print(f"{'='*60}")

    # 刮削读取
    d = get("/scrape/read", {"path": path})
    check("刮削读取接口", "_error" not in d)
    has = d.get("status") == "ok" and (d.get("data") or {}).get("title")
    title = (d.get("data") or {}).get("title", "N/A")
    print(f"  ℹ️ 刮削: status={d.get('status')} title={title}")

    # 海报
    try:
        r = requests.get(f"{BASE}/scrape/poster", params={"path": path}, timeout=10)
        check(f"海报 HTTP {r.status_code}", r.status_code in [200, 404])
        if r.status_code == 200:
            check("海报缓存头", "max-age" in r.headers.get("cache-control", ""))
    except Exception as e:
        check("海报接口", False, str(e))

    # 一键刮削
    name = os.path.basename(path)
    d = get("/scrape", {"name": name, "path": path}, timeout=25)
    check("一键刮削接口", "_error" not in d)
    sd = (d.get("self") or {}).get("data") or {}
    if sd.get("title"):
        conf = (d.get("self") or {}).get("confidence") or {}
        check(f"刮削匹配: {sd['title']} (置信度={conf.get('level','?')} {conf.get('score','?')}分)", True)
    else:
        print(f"  ℹ️ 刮削未匹配 (name={name})")

    # 候选搜索
    for src, api_path in [("TMDB", "/scrape/candidates"), ("豆瓣", "/scrape/douban"), ("Bangumi", "/scrape/bangumi")]:
        d = get(api_path, {"name": name})
        cs = d.get("candidates", [])
        check(f"{src} 候选: {len(cs)} 个", len(cs) >= 0)
        if cs:
            c = cs[0]
            print(f"    首个: {c.get('title','')} rating={c.get('rating',0)}")

    # 自动命名
    d = get("/rename", {"path": path, "dry_run": "true"})
    items = d.get("items", [])
    changed = [i for i in items if not i.get("unchanged")]
    check(f"自动命名: {len(items)} 项, 需改 {len(changed)} 项", "_error" not in d)

    # 标准结构
    d = get("/organize/structure", {"path": path, "dry_run": "true"})
    check(f"标准结构: {len(d.get('ops',[]))} 操作", "_error" not in d)

    # 一键整理
    d = get("/organize/full", {"path": path, "dry_run": "true"}, timeout=30)
    check("一键整理接口", "_error" not in d)
    s = d.get("summary", {})
    print(f"  ℹ️ 整理: type={d.get('folder_type')} vids={s.get('total_videos',0)} process={s.get('will_process',0)}")

def run_container_case(path, label, ft):
    """测试聚合容器"""
    print(f"\n{'='*60}")
    print(f"📦 {label} (聚合容器)")
    print(f"   {path} (type={ft})")
    print(f"{'='*60}")
    # 聚合容器：海报、禁止刮削
    try:
        r = requests.get(f"{BASE}/scrape/poster", params={"path": path, "cover": "true"}, timeout=10)
        check(f"容器封面 HTTP {r.status_code}", r.status_code in [200, 404])
    except Exception as e:
        check("容器封面", False, str(e))
    d = get("/no-scrape")
    check("禁止刮削接口", isinstance(d, list))

if __name__ == "__main__":
    print("🧪 DetailDrawer 拆分端到端测试（实际数据）\n")
    try:
        requests.get(f"{BASE}/config", timeout=5)
        check("后端在线", True)
    except:
        print("❌ 后端未启动"); sys.exit(1)

    # ── 洗版测试（聚合容器 + 2 个子目录）──
    run_container_case("\\\\NAS\\share\\视频\\其他视频\\洗版测试", "洗版测试", "collection")
    run_leaf_case("\\\\NAS\\share\\视频\\其他视频\\洗版测试\\Season 01", "洗版测试/Season 01 (电影)", "movie")
    run_leaf_case("\\\\NAS\\share\\视频\\其他视频\\洗版测试\\XiBanCeShi", "洗版测试/XiBanCeShi (电影)", "movie")

    # ── 测试动画合集（tv 容器 + 2 个 season）──
    run_container_case("\\\\NAS\\share\\视频\\动画番\\测试动画合集", "测试动画合集", "tv")
    run_leaf_case("\\\\NAS\\share\\视频\\动画番\\测试动画合集\\自由的她们", "测试动画合集/自由的她们 (season)", "season")

    # ── 测试文件夹（collection + 3 个 movie）──
    run_container_case("\\\\NAS\\share\\视频\\电影\\测试文件夹", "测试文件夹", "collection")
    run_leaf_case("\\\\NAS\\share\\视频\\电影\\测试文件夹\\爱乐之城 La La Land (2016)", "测试文件夹/爱乐之城 (电影)", "movie")
    run_leaf_case("\\\\NAS\\share\\视频\\电影\\测试文件夹\\白2023", "测试文件夹/白2023 (电影)", "movie")

    # ── 详情多源算法 ──
    print(f"\n{'='*60}")
    print("📡 详情多源算法")
    for title, src, tp, id_ in [
        ("霸王别姬", "douban", "movie", ""), ("进击的巨人", "bangumi", "tv", ""),
        ("Inception", "tmdb", "movie", ""), ("爱乐之城", "douban", "movie", ""),
    ]:
        d = get("/media/info", {"title": title, "source": src, "type": tp, "id": id_}, timeout=25)
        check(f"[{src}] {title}: found={d.get('found')} src={d.get('source','?')} rating={d.get('rating',0)}", d.get("found"))

    print(f"\n{'='*60}")
    print(f"📊 结果: {PASS} 通过, {FAIL} 失败")
    sys.exit(1 if FAIL else 0)
