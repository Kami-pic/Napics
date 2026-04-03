import sys, os
sys.path.insert(0, '.')
import organizer as o
from tmdb_client import parse_filename

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

for name in ['紫罗兰花园[1080P][CHS][MP4]', '秒速5厘米 5 Centimeters per Second']:
    # 搜索文件夹
    found = None
    for top in os.listdir(NAS):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp):
            continue
        for sub in os.listdir(tp):
            if name in sub:
                found = os.path.join(tp, sub)
                break
        if found:
            break
    
    if not found:
        print(f"NOT FOUND: {name}")
        continue
    
    info = o.classify_folder(found)
    ft = info.get('type', '')
    items = os.listdir(found)
    vids = [f for f in items if os.path.isfile(os.path.join(found, f)) and os.path.splitext(f)[1].lower() in video_exts]
    subdirs = [d for d in items if os.path.isdir(os.path.join(found, d)) and not d.startswith('.')]
    
    print(f"\n=== {os.path.basename(found)} ===")
    print(f"type: {ft}")
    print(f"vids: {len(vids)}, subdirs: {len(subdirs)}")
    
    for v in vids[:3]:
        p = parse_filename(v)
        print(f"  {v[:60]} -> ep={p.get('episode')}")
    if len(vids) > 3:
        print(f"  ... +{len(vids)-3} more")
    
    ep = o._count_episode_files(vids)
    print(f"ep_count: {ep}/{len(vids)}")
