"""调试所有分类有问题的文件夹"""
import sys, os
sys.path.insert(0, '.')
import organizer as o
from tmdb_client import parse_filename

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

problems = {
    # 问题1：应为 movie 被判为 tv
    "斯巴达300勇士 300 (2007)": ("电影", "应为movie"),
    "阿黛尔的生活 La Vie d'Adèle - Chapitres 1 et 2 (2013)": ("电影", "应为movie"),
    "秒速5厘米 5 Centimeters per Second": ("动画电影", "应为movie"),
    # 问题2：应为 tv 被判为 mixed
    "我的阿勒泰.2160p": ("电视剧", "应为tv"),
    "逆局": ("电视剧", "应为tv"),
    "黑镜1-4季": ("电视剧", "应为tv"),
    "JOJO的奇妙冒险 JoJo's Bizarre Adventure": ("动画番", "应为tv"),
    "永生之酒 Baccano!": ("动画番", "应为tv"),
    "巴哈姆特之怒 s1-s3": ("动画番", "应为tv"),
    "进击的巨人s1-s5": ("动画番", "应为tv"),
    "黑礁s1-s2": ("动画番", "应为tv"),
}

for name, (cat, expected) in problems.items():
    fp = os.path.join(NAS, cat, name)
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {cat}/{name}")
        continue
    
    info = o.classify_folder(fp)
    ft = info.get('type', '')
    items = os.listdir(fp)
    vids = [f for f in items if os.path.isfile(os.path.join(fp, f)) and os.path.splitext(f)[1].lower() in video_exts]
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    
    print(f"\n{'='*50}")
    print(f"{name}: {ft} ({expected})")
    print(f"  vids={len(vids)} subdirs={len(subdirs)}")
    
    if vids:
        ep = o._count_episode_files(vids)
        print(f"  ep_count={ep}/{len(vids)}")
        for v in vids[:3]:
            p = parse_filename(v)
            print(f"    {v[:55]} ep={p.get('episode')}")
    
    if subdirs:
        season_dirs = [d for d in subdirs if o._is_season_dir(d)]
        non_season = [d for d in subdirs if not o._is_season_dir(d)]
        print(f"  season_dirs={len(season_dirs)} non_season={len(non_season)}")
        for d in subdirs[:5]:
            is_s = o._is_season_dir(d)
            dp = os.path.join(fp, d)
            sv = len([f for f in os.listdir(dp) if os.path.splitext(f)[1].lower() in video_exts]) if os.path.isdir(dp) else 0
            print(f"    [{d}] is_season={is_s} vids={sv}")
        if len(subdirs) > 5:
            print(f"    ... +{len(subdirs)-5} more")
    
    if vids and subdirs:
        print(f"  散落视频+子目录共存")
