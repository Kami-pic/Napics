"""验证所有文件夹分类是否正确"""
import sys, os
sys.path.insert(0, '.')
import organizer as o

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

type_counts = {}
problems = []

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        total = sum(1 for r,d,f in os.walk(sp) for fn in f 
                    if os.path.splitext(fn)[1].lower() in video_exts)
        if total < 1:
            continue
        info = o.classify_folder(sp)
        ft = info.get('type', 'unknown')
        type_counts[ft] = type_counts.get(ft, 0) + 1

import json
print("类型分布:", json.dumps(type_counts, ensure_ascii=False))
print(f"总计: {sum(type_counts.values())} 个文件夹")
