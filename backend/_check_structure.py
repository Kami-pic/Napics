"""检查关键文件夹的实际结构"""
import os, sys
sys.path.insert(0, '.')

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

folders = [
    NAS + r"\动画电影\剑风传奇 黄金时代篇 剧场版1-3",
    NAS + r"\动画电影\哥斯拉动画电影",
    NAS + r"\动画电影\壳中少女 Mardock Scramble",
    NAS + r"\动画电影\来自深渊剧场版三部曲",
    NAS + r"\动画电影\永远之久远",
    NAS + r"\动画电影\福音战士新剧场版 Evangelion 三部曲",
    NAS + r"\动画电影\千年女优 Millennium Actress (2002)",
    NAS + r"\动画电影\茗记：2nd Life (2007)",
    NAS + r"\动画番\来自深渊S1-S2",
    NAS + r"\动画番\永生之酒 Baccano!",
    NAS + r"\电影\经典电影之新世代诠释 Reframed Next Gen Narratives",
    NAS + r"\电影\007：无暇赴死 No Time to Die (2021)",
    NAS + r"\动画番\冰菓 Hyouka",
    NAS + r"\电视剧\冰与火之歌1-8季",
    NAS + r"\动画番\进击的巨人s1-s5",
]

for fp in folders:
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {fp}")
        continue
    name = os.path.basename(fp)
    items = sorted(os.listdir(fp))
    dirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    files = [f for f in items if os.path.isfile(os.path.join(fp, f))]
    videos = [f for f in files if os.path.splitext(f)[1].lower() in video_exts]
    non_videos = [f for f in files if f not in videos and not f.startswith('.')]
    
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"  子目录({len(dirs)}): {dirs[:10]}")
    print(f"  散落视频({len(videos)}):")
    for v in videos[:5]:
        print(f"    {v}")
    if len(videos) > 5:
        print(f"    ... +{len(videos)-5} more")
    if non_videos:
        print(f"  其他文件: {non_videos[:5]}")
    
    # 检查子目录内容
    for d in dirs[:5]:
        dp = os.path.join(fp, d)
        sub_items = sorted(os.listdir(dp))
        sub_vids = [f for f in sub_items if os.path.isfile(os.path.join(dp, f)) and os.path.splitext(f)[1].lower() in video_exts]
        sub_dirs = [f for f in sub_items if os.path.isdir(os.path.join(dp, f))]
        sub_others = [f for f in sub_items if f not in sub_vids and f not in sub_dirs and not f.startswith('.')]
        print(f"  [{d}]")
        print(f"    视频: {sub_vids[:3]}")
        if sub_dirs:
            print(f"    子目录: {sub_dirs[:3]}")
        if sub_others:
            print(f"    其他: {sub_others[:3]}")
