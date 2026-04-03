import sys, os
sys.path.insert(0, '.')
import organizer, config_manager
config_m = config_manager.ConfigManager()
library = config_m.load_library()
NAS = r"\\DS218play\share\视频"
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

tests = [
    NAS + r"\电影\007：无暇赴死 No Time to Die (2021)",
    NAS + r"\动画电影\千年女优 Millennium Actress (2002)",
    NAS + r"\动画电影\阿基拉 AKIRA (1988)",
    NAS + r"\动画电影\千与千寻 Spirited Away (2001)",
    NAS + r"\动画电影\你的名字。 Your Name (2016)",
    NAS + r"\动画电影\心灵奇旅 Soul (2020)",
]
for fp in tests:
    if not os.path.isdir(fp):
        print(f"NOT FOUND: {fp}")
        continue
    info = organizer.classify_folder(fp, library)
    items = os.listdir(fp)
    vids = [f for f in items if os.path.isfile(os.path.join(fp, f)) and os.path.splitext(f)[1].lower() in video_exts]
    subdirs = [d for d in items if os.path.isdir(os.path.join(fp, d)) and not d.startswith('.')]
    name = os.path.basename(fp)
    print(f"{name}: type={info.get('type')} vids={len(vids)} subdirs={len(subdirs)}")
