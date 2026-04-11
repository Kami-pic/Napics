"""通过 HTTP API 测试改名和整理"""
import requests, json
BASE = "http://localhost:8000"

paths = [
    r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们",
    r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)",
    r"\\DS218play\share\视频\电影\测试文件夹\白2023",
]

for path in paths:
    print(f"\n{'='*50}")
    print(f"PATH: {path}")

    # 自动命名
    r = requests.post(f"{BASE}/organize/rename", params={"path": path, "dry_run": "true"}, timeout=20)
    d = r.json()
    items = d.get("items", [])
    changed = [i for i in items if not i.get("unchanged")]
    print(f"  自动命名: {len(items)} 项, 需改 {len(changed)} 项")
    for c in changed[:3]:
        print(f"    OLD: {c.get('old_name','')}")
        print(f"    NEW: {c.get('new_name','')}")

    # 标准结构
    r = requests.post(f"{BASE}/organize/structure", params={"path": path, "dry_run": "true"}, timeout=20)
    d = r.json()
    ops = d.get("ops", [])
    print(f"  标准结构: {len(ops)} 操作")
    for o in ops[:3]:
        print(f"    [{o.get('action','')}] {o.get('desc','')[:60]}")

    # 一键整理
    r = requests.post(f"{BASE}/organize/full", params={"path": path, "dry_run": "true"}, timeout=60)
    d = r.json()
    ft = d.get("folder_type", "N/A")
    s = d.get("summary", {})
    plan = d.get("plan", [])
    tmdb = d.get("tmdb_match", {})
    print(f"  一键整理: type={ft} vids={s.get('total_videos',0)} process={s.get('will_process',0)}")
    if tmdb.get("title"):
        print(f"    匹配: {tmdb['title']}")
    for p in plan[:5]:
        fn = p.get("original_filename", "")
        m = p.get("mapped", {})
        skip = p.get("skip_reason", "")
        if skip:
            print(f"    SKIP {fn}: {skip}")
        elif m:
            se = f"S{str(m.get('season',0)).zfill(2)}E{str(m.get('episode',0)).zfill(2)}"
            print(f"    OK {fn} -> {se}")

print("\n完成")
