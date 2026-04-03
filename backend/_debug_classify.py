"""调试分类错误的文件夹"""
import sys, os
sys.path.insert(0, '.')
import organizer, config_manager
from tmdb_client import parse_filename

config_m = config_manager.ConfigManager()
library = config_m.load_library()
NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

problems = [
    (NAS + r"\动画番\UN-GO 因果日记 UN-GO", "应为 tv"),
    (NAS + r"\动画番\来自深渊S1-S2", "应为 tv"),
    (NAS + r"\电视剧\真探S1", "应为 tv"),
    (NAS + r"\动画番\交响情人梦 Nodame Cantabile", "应为 tv"),
]

for fp, expected in problems:
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {fp}")
        continue
    name = os.path.basename(fp)
    info = organizer.classify_folder(fp, library)
    ft = info.get("type", "")
    
    items = os.listdir(fp)
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    videos = [f for f in items if os.path.isfile(os.path.join(fp, f)) and os.path.splitext(f)[1].lower() in video_exts]
    
    print(f"\n{'='*60}")
    print(f"{name}: {ft} ({expected})")
    print(f"  子目录: {len(subdirs)}, 散落视频: {len(videos)}")
    
    if subdirs:
        print(f"  子目录列表: {subdirs[:5]}")
        # 检查子目录是否被判为季目录
        for d in subdirs[:3]:
            is_season = organizer._is_season_dir(d)
            print(f"    [{d}] is_season={is_season}")
    
    if videos:
        print(f"  视频文件: {videos[:5]}")
        # 检查集号识别
        ep_count = 0
        for v in videos[:5]:
            parsed = parse_filename(v)
            ep = parsed.get("episode")
            print(f"    [{v[:50]}] episode={ep}")
            if ep is not None:
                ep_count += 1
        total_ep = organizer._count_episode_files(videos)
        print(f"  集号识别: {total_ep}/{len(videos)}")
