"""检查每个大分类目录下是否有散落视频，以及每个子文件夹里是否有散落视频"""
import os

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

print("=== 检查大分类目录下的散落视频 ===\n")
for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    loose = [f for f in os.listdir(tp) if os.path.isfile(os.path.join(tp, f)) 
             and os.path.splitext(f)[1].lower() in video_exts]
    if loose:
        print(f"[{top}] 散落视频: {len(loose)}")
        for v in loose[:5]:
            print(f"  {v}")
        if len(loose) > 5:
            print(f"  ... +{len(loose)-5} more")

print("\n=== 检查子文件夹里的散落视频（有视频直接在文件夹根目录，没有自己的子文件夹）===\n")
for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        items = os.listdir(sp)
        loose_vids = [f for f in items if os.path.isfile(os.path.join(sp, f)) 
                      and os.path.splitext(f)[1].lower() in video_exts]
        subdirs = [d for d in items if os.path.isdir(os.path.join(sp, d)) and not d.startswith('.')]
        
        # 有散落视频的文件夹
        if loose_vids:
            print(f"[{top}/{sub}] 散落视频:{len(loose_vids)} 子目录:{len(subdirs)}")
            for v in loose_vids[:3]:
                print(f"  {v}")
            if len(loose_vids) > 3:
                print(f"  ... +{len(loose_vids)-3} more")
