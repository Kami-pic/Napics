"""检查哪些文件夹丢了第一集"""
import os

NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

checks = [
    ("电视剧", "我的阿勒泰.2160p"),
    ("电视剧", "真探S1"),
    ("电视剧", "逆局"),
    ("电视剧", "名姝S1"),
    ("动画番", "UN-GO 因果日记 UN-GO"),
]

for cat, name in checks:
    fp = os.path.join(NAS, cat, name)
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {cat}/{name}")
        continue
    
    # 收集所有视频（含子目录）
    all_vids = []
    for root, dirs, files in os.walk(fp):
        for f in files:
            if os.path.splitext(f)[1].lower() in video_exts:
                rel = os.path.relpath(os.path.join(root, f), fp)
                all_vids.append(rel)
    
    all_vids.sort()
    print(f"\n=== {name} ({len(all_vids)} vids) ===")
    for v in all_vids:
        print(f"  {v}")

# 也检查 organize_snapshots 里是否有这些文件的移动记录
print("\n=== 检查快照记录 ===")
import json, glob
snapshots = sorted(glob.glob("organize_snapshots/snapshot_*.json"), reverse=True)
for sf in snapshots[:20]:
    with open(sf, encoding='utf-8') as f:
        snap = json.load(f)
    ops = snap.get("ops", [])
    for op in ops:
        old = op.get("old_path", "")
        new = op.get("new_path", "")
        for name in ["我的阿勒泰", "真探", "逆局", "名姝", "UN-GO"]:
            if name in old or name in new:
                print(f"  [{os.path.basename(sf)}] {old[-50:]} -> {new[-50:]}")
                break
