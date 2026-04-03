"""检查后端返回给前端的数据：folder_type、display_name 等"""
import sys, os, json
sys.path.insert(0, '.')
import organizer, config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"

# 构建 lib_map
lib_map = {}
for v in library:
    lib_map[v.get("file_path", "")] = v

# 检查几个关键文件夹
folders = [
    ("电影", "007：无暇赴死 No Time to Die (2021)"),
    ("动画电影", "千年女优 Millennium Actress (2002)"),
    ("动画电影", "阿基拉 AKIRA (1988)"),
    ("动画电影", "千与千寻 Spirited Away (2001)"),
    ("动画电影", "剑风传奇 黄金时代篇 剧场版1-3"),
    ("动画电影", "福音战士新剧场版 Evangelion 三部曲"),
    ("动画番", "冰菓 Hyouka"),
    ("电视剧", "冰与火之歌1-8季"),
    ("动画番", "来自深渊S1-S2"),
]

for cat, name in folders:
    fp = os.path.join(NAS, cat, name)
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {cat}/{name}")
        continue
    
    info = organizer.classify_folder(fp, library)
    ft = info.get("type", "")
    
    # 检查 library 中这个文件夹的条目
    lib_entries = []
    for v in library:
        if v.get("file_path", "").startswith(fp):
            lib_entries.append({
                "file": os.path.basename(v["file_path"]),
                "shadow_name": v.get("shadow_name", ""),
                "folder_type": v.get("folder_type", ""),
                "display_name": v.get("shadow_name") or os.path.basename(v["file_path"]),
            })
    
    # 检查子目录和散落视频
    items = os.listdir(fp)
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    videos = [f for f in items if os.path.isfile(os.path.join(fp, f)) and os.path.splitext(f)[1].lower() in {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}]
    
    print(f"\n{'='*60}")
    print(f"[{cat}] {name}")
    print(f"  classify_folder: {ft}")
    print(f"  子目录: {len(subdirs)}, 散落视频: {len(videos)}")
    print(f"  library 条目: {len(lib_entries)}")
    for e in lib_entries[:5]:
        print(f"    file: {e['file'][:50]}")
        print(f"    shadow: {e['shadow_name'][:50] if e['shadow_name'] else '(空)'}")
        print(f"    folder_type: {e['folder_type']}")
    if len(lib_entries) > 5:
        print(f"    ... +{len(lib_entries)-5} more")
