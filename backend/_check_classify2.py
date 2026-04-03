"""检查来自深渊S1-S2 和其他关键文件夹的递归分类"""
import sys, os
sys.path.insert(0, '.')
import organizer, config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"

# 来自深渊S1-S2
fp = NAS + r"\动画番\来自深渊S1-S2"
info = organizer.classify_folder(fp, library)
print(f"来自深渊S1-S2: {info.get('type')}")
for d in sorted(os.listdir(fp)):
    dp = os.path.join(fp, d)
    if os.path.isdir(dp) and not d.startswith('.'):
        ci = organizer.classify_folder(dp, library)
        print(f"  [{d}]: {ci.get('type')}")

# 永生之酒 Baccano!
print()
fp2 = NAS + r"\动画番\永生之酒 Baccano!"
info2 = organizer.classify_folder(fp2, library)
print(f"永生之酒 Baccano!: {info2.get('type')}")
for d in sorted(os.listdir(fp2)):
    dp = os.path.join(fp2, d)
    if os.path.isdir(dp) and not d.startswith('.'):
        ci = organizer.classify_folder(dp, library)
        vids = [f for f in os.listdir(dp) if os.path.splitext(f)[1].lower() in {'.mp4','.mkv','.avi','.rmvb','.rm','.flv','.ts','.m4v','.mov','.wmv'}]
        print(f"  [{d}]: {ci.get('type')} ({len(vids)} vids)")

# 冰菓 — tv 类型但散落视频
print()
fp3 = NAS + r"\动画番\冰菓 Hyouka"
info3 = organizer.classify_folder(fp3, library)
print(f"冰菓 Hyouka: {info3.get('type')}")
vids3 = [f for f in os.listdir(fp3) if os.path.isfile(os.path.join(fp3, f)) and os.path.splitext(f)[1].lower() in {'.mp4','.mkv'}]
print(f"  散落视频: {len(vids3)}")
print(f"  前3个: {vids3[:3]}")

# 茗记
print()
fp4 = NAS + r"\动画电影\茗记：2nd Life (2007)"
info4 = organizer.classify_folder(fp4, library)
print(f"茗记: {info4.get('type')}")
vids4 = [f for f in os.listdir(fp4) if os.path.isfile(os.path.join(fp4, f)) and os.path.splitext(f)[1].lower() in {'.mp4','.mkv','.wmv','.flv','.rmvb'}]
print(f"  散落视频: {len(vids4)}")
for v in vids4:
    print(f"    {v}")
