"""检查关键文件夹的分类结果和结构操作"""
import sys, os
sys.path.insert(0, '.')
import analyzer
import organizer
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

folders = [
    NAS + r"\动画电影\千年女优 Millennium Actress (2002)",
    NAS + r"\动画电影\茗记：2nd Life (2007)",
    NAS + r"\动画电影\剑风传奇 黄金时代篇 剧场版1-3",
    NAS + r"\动画电影\福音战士新剧场版 Evangelion 三部曲",
    NAS + r"\动画番\冰菓 Hyouka",
    NAS + r"\动画番\来自深渊S1-S2",
    NAS + r"\动画番\永生之酒 Baccano!",
    NAS + r"\电影\007：无暇赴死 No Time to Die (2021)",
    NAS + r"\电影\经典电影之新世代诠释 Reframed Next Gen Narratives",
    NAS + r"\电视剧\冰与火之歌1-8季",
    NAS + r"\动画番\进击的巨人s1-s5",
]

for fp in folders:
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {fp}")
        continue
    name = os.path.basename(fp)
    
    # 分类
    info = organizer.classify_folder(fp, library)
    ft = info.get("type", "")
    
    # 分析
    report = analyzer.analyze_folder(fp, library)
    struct_ops = report.get("structure_ops", [])
    
    # 检查散落视频
    items = os.listdir(fp)
    loose_videos = [f for f in items if os.path.isfile(os.path.join(fp, f)) 
                    and os.path.splitext(f)[1].lower() in video_exts]
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"  类型: {ft}")
    print(f"  散落视频: {len(loose_videos)}, 子目录: {len(subdirs)}")
    print(f"  结构操作: {len(struct_ops)}")
    for op in struct_ops[:5]:
        print(f"    {op.get('action')}: {op.get('desc', '')[:60]}")
    if len(struct_ops) > 5:
        print(f"    ... +{len(struct_ops)-5} more")
    
    if loose_videos and not struct_ops:
        print(f"  ⚠️ 有散落视频但无结构操作!")
        for v in loose_videos[:3]:
            print(f"    {v}")
