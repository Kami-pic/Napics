import sys, os
sys.path.insert(0, '.')
import organizer as o

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

tests = [
    NAS + r"\动画番\UN-GO 因果日记 UN-GO",
    NAS + r"\动画番\来自深渊S1-S2",
    NAS + r"\电视剧\真探S1",
    NAS + r"\动画番\交响情人梦 Nodame Cantabile",
    NAS + r"\动画电影\千年女优 Millennium Actress (2002)",
    NAS + r"\动画电影\阿基拉 AKIRA (1988)",
]

for fp in tests:
    if not os.path.isdir(fp):
        # 可能已被回滚（一级目录下的散落视频）
        print(f"NOT FOUND: {os.path.basename(fp)}")
        continue
    info = o.classify_folder(fp)
    name = os.path.basename(fp)
    items = os.listdir(fp)
    vids = [f for f in items if os.path.isfile(os.path.join(fp, f)) and os.path.splitext(f)[1].lower() in video_exts]
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    ep = o._count_episode_files(vids) if vids else 0
    ft = info.get('type', '')
    print(f"{name}: type={ft} vids={len(vids)} subdirs={len(subdirs)} ep={ep}/{len(vids)}")
