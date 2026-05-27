"""直接调用后端业务逻辑测试改名和整理（绕过 HTTP）"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))

from config_manager import ConfigManager
config_m = ConfigManager()

import organizer

paths = [
    (r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们", "自由的她们 (season)"),
    (r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)", "爱乐之城 (movie)"),
    (r"\\DS218play\share\视频\电影\测试文件夹\白2023", "白2023 (movie)"),
]

for path, label in paths:
    print(f"\n{'='*50}")
    print(f"📁 {label}: {path}")
    exists = os.path.isdir(path)
    print(f"   目录存在: {exists}")
    if exists:
        files = os.listdir(path)
        vids = [f for f in files if f.lower().endswith(('.mp4','.mkv','.avi','.rmvb','.ts'))]
        print(f"   文件数: {len(files)}, 视频数: {len(vids)}")
        for v in vids[:5]:
            print(f"   📹 {v}")

    # 自动命名预览
    print("\n  --- 自动命名预览 ---")
    try:
        result = organizer.auto_rename(path, dry_run=True)
        items = result.get("items", [])
        changed = [i for i in items if not i.get("unchanged")]
        print(f"  总计 {len(items)} 项, 需改 {len(changed)} 项")
        for c in changed[:3]:
            print(f"    {c.get('old_name','')} → {c.get('new_name','')}")
    except Exception as e:
        print(f"  错误: {e}")

    # 标准结构预览
    print("\n  --- 标准结构预览 ---")
    try:
        result = organizer.structure_organize(path, dry_run=True)
        ops = result.get("ops", [])
        print(f"  操作数: {len(ops)}")
        for o in ops[:3]:
            print(f"    [{o.get('action','')}] {o.get('desc','')[:60]}")
    except Exception as e:
        print(f"  错误: {e}")

    # 一键整理预览
    print("\n  --- 一键整理预览 ---")
    try:
        result = organizer.full_organize(path, dry_run=True)
        ft = result.get("folder_type", "N/A")
        s = result.get("summary", {})
        plan = result.get("plan", [])
        tmdb = result.get("tmdb_match", {})
        print(f"  类型: {ft}, 视频: {s.get('total_videos',0)}, 将处理: {s.get('will_process',0)}")
        if tmdb.get("title"):
            print(f"  匹配: {tmdb['title']}")
        for p in plan[:5]:
            fn = p.get("original_filename", "")
            m = p.get("mapped", {})
            skip = p.get("skip_reason", "")
            if skip:
                print(f"    ⏭️ {fn}: {skip}")
            elif m:
                print(f"    ✅ {fn} → S{str(m.get('season',0)).zfill(2)}E{str(m.get('episode',0)).zfill(2)}")
    except Exception as e:
        print(f"  错误: {e}")

print("\n完成")
