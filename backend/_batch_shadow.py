"""补填影子名 — 对所有已刮削的文件夹填充影子名（不调用TMDB API，只用本地NFO）"""
import sys, os, json, time, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import scraper
import organizer
from organizer import classify_folder, generate_standard_name, _extract_english_from_filename, _is_mostly_latin
from tmdb_client import parse_filename
from shadow_name_manager import ShadowNameManager
import config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
shadow_m = ShadowNameManager()

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

total_folders = 0
total_filled = 0
total_errors = 0

def fill_shadow_for_folder(folder_path):
    """只用本地NFO数据填充影子名，不调用TMDB API"""
    results = []
    folder_name = os.path.basename(folder_path)
    
    # 读文件夹级NFO
    folder_nfo = scraper.read_nfo(folder_path)
    folder_type = classify_folder(folder_path, library)
    is_coll = folder_type.get("type") in ("movie_collection","series_collection","mixed","variety","misc")
    
    # 文件夹影子名
    if folder_nfo and folder_nfo.get("title"):
        title = folder_nfo["title"]
        en = folder_nfo.get("english_title", "")
        orig = folder_nfo.get("original_title", "")
        year = folder_nfo.get("year", "")
        if not en and orig and orig != title and _is_mostly_latin(orig):
            en = orig
        shadow = title
        if en and en != title:
            shadow += " " + en
        if year:
            shadow += f" ({year})"
        results.append({"path": folder_path, "shadow": shadow})
    
    # 视频文件影子名
    for item in sorted(os.listdir(folder_path)):
        fp = os.path.join(folder_path, item)
        if os.path.isfile(fp) and os.path.splitext(item)[1].lower() in video_exts:
            # 读视频级NFO
            vnfo = scraper.read_video_nfo(fp)
            scrape_data = vnfo if vnfo and vnfo.get("tmdb_id") else folder_nfo
            
            ft = ""
            if folder_nfo:
                ft = folder_nfo.get("title", "") or folder_nfo.get("original_title", "")
                # 补英文名
                if scrape_data and not scrape_data.get("english_title") and folder_nfo.get("english_title"):
                    scrape_data = dict(scrape_data)
                    scrape_data["english_title"] = folder_nfo["english_title"]
            if not ft:
                ft = re.sub(r'[\[\(【（].*?[\]\)】）]', '', folder_name).strip()
            
            new_name = generate_standard_name(item, scrape_data, None, ft, is_collection=is_coll)
            shadow = os.path.splitext(new_name)[0]
            shadow = re.sub(r'\s+(2160p|1080p|720p)$', '', shadow)
            results.append({"path": fp, "shadow": shadow})
    
    # 递归子目录
    for item in sorted(os.listdir(folder_path)):
        sub = os.path.join(folder_path, item)
        if os.path.isdir(sub) and not item.startswith('.'):
            sub_results = fill_shadow_for_folder(sub)
            # 用父目录剧名修正子目录视频的影子名
            if folder_nfo:
                parent_cn = folder_nfo.get("title", "")
                parent_en = folder_nfo.get("english_title", "") or folder_nfo.get("original_title", "")
                if parent_en and not _is_mostly_latin(parent_en):
                    parent_en = ""
                if parent_cn:
                    for sr in sub_results:
                        shadow = sr["shadow"]
                        ep_match = re.search(r'S\d+E\d+', shadow)
                        if ep_match:
                            new_shadow = parent_cn
                            if parent_en and parent_en != parent_cn:
                                new_shadow += " " + parent_en
                            new_shadow += " " + ep_match.group(0)
                            sr["shadow"] = new_shadow
            results.extend(sub_results)
    
    return results

for top in sorted(os.listdir(NAS)):
    tp = os.path.join(NAS, top)
    if not os.path.isdir(tp) or top.startswith('.') or top in SKIP_DIRS:
        continue
    for sub in sorted(os.listdir(tp)):
        sp = os.path.join(tp, sub)
        if not os.path.isdir(sp) or sub.startswith('.'):
            continue
        
        total_folders += 1
        try:
            results = fill_shadow_for_folder(sp)
            count = 0
            for r in results:
                if r["path"] and r["shadow"]:
                    if shadow_m.auto_fill(r["path"], r["shadow"], source="parsed"):
                        count += 1
            total_filled += count
            if count > 0:
                print(f"  [{top}] {sub}: {count} filled")
        except Exception as e:
            total_errors += 1
            print(f"  [{top}] {sub}: ERROR {str(e)[:60]}")

print(f"\nDone: {total_folders} folders, {total_filled} shadow names, {total_errors} errors")
