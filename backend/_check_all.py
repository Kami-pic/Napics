"""检查所有文件夹的整理结果"""
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import scraper
from organizer import rename_videos_in_folder
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()

NAS = r"\\DS218play\share\视频"
SKIP = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

issues = []

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        vids = sum(1 for r, d, f in os.walk(sp) for fn in f if os.path.splitext(fn)[1].lower() in video_exts)
        if vids < 1:
            continue

        folder_issues = []

        nfo = scraper.read_nfo(sp)
        has_folder_nfo = bool(nfo and nfo.get('tmdb_id'))
        has_sub_nfo = False
        for d in os.listdir(sp):
            dp = os.path.join(sp, d)
            if os.path.isdir(dp) and not d.startswith('.'):
                snfo = scraper.read_nfo(dp)
                if snfo and snfo.get('tmdb_id'):
                    has_sub_nfo = True
                    break

        if not has_folder_nfo and not has_sub_nfo:
            folder_issues.append("NO_SCRAPE")

        rename_result = rename_videos_in_folder(sp, None, dry_run=True, library_data=library)
        video_results = [r for r in rename_result if not r.get("is_folder")]
        no_ep = [r for r in video_results if r.get("shadow_name") and not re.search(r'S\d+E\d+', r["shadow_name"])]

        if no_ep and len(no_ep) > vids * 0.3 and vids > 1:
            folder_issues.append(f"NO_EP({len(no_ep)}/{vids})")

        if folder_issues:
            issues.append((top, sub, vids, folder_issues))

print(f"问题文件夹: {len(issues)}")
for top, name, vids, probs in issues:
    prob_str = " | ".join(probs)
    print(f"  [{top}] {name} ({vids}): {prob_str}")
