import sys, os
sys.path.insert(0, '.')
import organizer as o

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}
fp = NAS + r"\动画番\永生之酒 Baccano!"
info = o.classify_folder(fp)
print("parent:", info.get('type'))
for d in sorted(os.listdir(fp)):
    dp = os.path.join(fp, d)
    if os.path.isdir(dp) and not d.startswith('.'):
        ci = o.classify_folder(dp)
        vids = [f for f in os.listdir(dp) if os.path.splitext(f)[1].lower() in video_exts]
        print(f"  [{d}] type={ci.get('type')} vids={len(vids)}")
        for v in vids[:2]:
            print(f"    {v[:60]}")
