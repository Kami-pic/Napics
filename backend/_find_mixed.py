import sys, os
sys.path.insert(0, '.')
import organizer as o

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        total = sum(1 for r,d,f in os.walk(sp) for fn in f if os.path.splitext(fn)[1].lower() in video_exts)
        if total < 1:
            continue
        info = o.classify_folder(sp)
        ft = info.get('type', '')
        if ft == 'mixed':
            print(f"[{top}] {sub}: mixed ({total} vids)")
