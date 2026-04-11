"""测试自动命名 + 标准结构 + 一键整理（dry_run 预览）"""
import requests, json, sys
BASE = "http://localhost:8000"
P = F = 0

def check(l, c, d=""):
    global P, F
    if c: P+=1; print(f"  ✅ {l}")
    else: F+=1; print(f"  ❌ {l} {d}")

def get(url, params=None, t=20):
    try: return requests.get(f"{BASE}{url}", params=params, timeout=t).json()
    except Exception as e: return {"_error": str(e)}

tests = [
    ("自由的她们 (动画season)", "\\\\DS218play\\share\\视频\\动画番\\测试动画合集\\自由的她们"),
    ("爱乐之城 (电影)", "\\\\DS218play\\share\\视频\\电影\\测试文件夹\\爱乐之城 La La Land (2016)"),
    ("白2023 (电影)", "\\\\DS218play\\share\\视频\\电影\\测试文件夹\\白2023"),
    ("测试动画合集 (tv容器)", "\\\\DS218play\\share\\视频\\动画番\\测试动画合集"),
    ("测试文件夹 (collection)", "\\\\DS218play\\share\\视频\\电影\\测试文件夹"),
]

for label, path in tests:
    print(f"\n{'='*50}")
    print(f"📁 {label}")
    print(f"   {path}")

    # 自动命名预览
    d = get("/rename", {"path": path, "dry_run": "true"})
    items = d.get("items", [])
    changed = [i for i in items if not i.get("unchanged")]
    check(f"自动命名: {len(items)} 项, 需改 {len(changed)} 项", "_error" not in d, d.get("_error",""))
    for c in changed[:3]:
        old = c.get("old_name", "")
        new = c.get("new_name", "")
        print(f"    📝 {old}")
        print(f"     → {new}")
    if len(changed) > 3:
        print(f"    ... 还有 {len(changed)-3} 项")

    # 标准结构预览
    d = get("/organize/structure", {"path": path, "dry_run": "true"})
    ops = d.get("ops", [])
    check(f"标准结构: {len(ops)} 操作", "_error" not in d, d.get("_error",""))
    for o in ops[:3]:
        action = o.get("action", "")
        desc = o.get("desc", "")[:80]
        print(f"    📦 [{action}] {desc}")
    if len(ops) > 3:
        print(f"    ... 还有 {len(ops)-3} 项")

    # 一键整理预览
    d = get("/organize/full", {"path": path, "dry_run": "true"}, t=60)
    s = d.get("summary", {})
    ft = d.get("folder_type", "N/A")
    plan = d.get("plan", [])
    wp = d.get("wrap_plan", [])
    tmdb = d.get("tmdb_match", {})
    check(f"一键整理: type={ft} vids={s.get('total_videos',0)} process={s.get('will_process',0)}", "_error" not in d, d.get("_error",""))
    if tmdb.get("title"):
        print(f"    🎬 匹配: {tmdb['title']} ({tmdb.get('english_title','')})")
    if wp:
        print(f"    📦 封装: {len(wp)} 项")
    for p in plan[:5]:
        fn = p.get("original_filename", "")
        m = p.get("mapped", {})
        skip = p.get("skip_reason", "")
        if skip:
            print(f"    ⏭️ {fn}: {skip}")
        elif m:
            se = f"S{str(m.get('season',0)).zfill(2)}E{str(m.get('episode',0)).zfill(2)}"
            print(f"    ✅ {fn} → {se}")
    if len(plan) > 5:
        print(f"    ... 还有 {len(plan)-5} 项")

print(f"\n{'='*50}")
print(f"📊 结果: {P} 通过, {F} 失败")
sys.exit(1 if F else 0)
