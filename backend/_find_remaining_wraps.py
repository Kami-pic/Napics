"""找出所有还残留的错误 wrap 子目录"""
import os
NAS = r"\\DS218play\share\视频"
SKIP = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        items = os.listdir(sp)
        subdirs = [d for d in items if os.path.isdir(os.path.join(sp, d)) and not d.startswith('.')]
        if not subdirs:
            continue
        # 检查是否有"单视频+.old_scrape.zip"的子目录（wrap 特征）
        wrap_count = 0
        for d in subdirs:
            dp = os.path.join(sp, d)
            sub_items = os.listdir(dp)
            sub_vids = [f for f in sub_items if os.path.splitext(f)[1].lower() in video_exts]
            if len(sub_vids) == 1 and '.old_scrape.zip' in sub_items and len(sub_items) == 2:
                wrap_count += 1
        if wrap_count >= 3:
            print(f"[{top}/{sub}] {wrap_count}/{len(subdirs)} wrap子目录")
