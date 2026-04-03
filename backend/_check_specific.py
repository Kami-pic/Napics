"""检查特定问题文件夹"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from organizer import rename_videos_in_folder, classify_folder
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"

checks = [
    ("动画番", "紫罗兰花园[1080P][CHS][MP4]"),
    ("动画电影", "命运之夜 无限剑制 Fatestay night [Unlimited Blade Works]"),
    ("动画电影", "福音战士新剧场版 Evangelion 三部曲"),
    ("动画电影", "茗记：2nd Life (2007)"),
    ("动画电影", "来自深渊剧场版三部曲"),
    ("动画电影", "动画短片合集"),
    ("电影", "经典电影之新世代诠释 Reframed Next Gen Narratives"),
    ("电视剧", "斯巴达克斯s0-s2"),
]

for top, name in checks:
    sp = os.path.join(NAS, top, name)
    if not os.path.isdir(sp):
        print(f"NOT FOUND: {name}")
        continue
    
    ft = classify_folder(sp, library)
    print(f"\n{'='*60}")
    print(f"[{top}] {name}")
    print(f"  type: {ft.get('type')}")
    
    result = rename_videos_in_folder(sp, None, dry_run=True, library_data=library)
    folder_items = [r for r in result if r.get("is_folder") and not r.get("is_subfolder")]
    video_items = [r for r in result if not r.get("is_folder")]
    
    if folder_items:
        print(f"  folder shadow: {folder_items[0].get('shadow_name', '')[:50]}")
    
    print(f"  videos: {len(video_items)}")
    for r in video_items[:5]:
        old = r.get("old_name", "")[:35]
        shadow = r.get("shadow_name", "")[:50]
        print(f"    {old}")
        print(f"      -> {shadow}")
    if len(video_items) > 5:
        print(f"    ... +{len(video_items)-5} more")
