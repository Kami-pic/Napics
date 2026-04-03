"""修复脚本：1) 刮削未刮削的6个文件夹  2) 全量补填影子名"""
import sys, os, json, time, re, traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import scraper, organizer, analyzer, tmdb_client, config_manager
from organizer import classify_folder, generate_standard_name, _is_mostly_latin
from tmdb_client import parse_filename
from shadow_name_manager import ShadowNameManager
from _organize_pipeline import run_pipeline

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')
shadow_m = ShadowNameManager()

NAS = r"\\DS218play\share\视频"
SKIP_DIRS = {"其他视频"}
video_exts = {'.mp4','.mkv','.avi','.ts','.rmvb','.rm','.flv','.wmv','.mov','.m4v'}

# ── Part 1: 刮削未刮削的文件夹 ──
print("=" * 50)
print("Part 1: Scrape missing folders")
print("=" * 50)

NO_SCRAPE = [
    "双斩少女", "穷神", "紫罗兰花园[1080P][CHS][MP4]",
]

for name in NO_SCRAPE:
    # 找到路径
    for top in os.listdir(NAS):
        tp = os.path.join(NAS, top)
        if not os.path.isdir(tp): continue
        sp = os.path.join(tp, name)
        if os.path.isdir(sp):
            print(f"\n[{top}] {name}")
            try:
                r = run_pipeline(sp, execute=True)
                print(f"  OK: {r.get('folder_type','')}")
            except Exception as e:
                print(f"  ERR: {str(e)[:80]}")
            break

# ── Part 2: 全量补填影子名 ──
print("\n" + "=" * 50)
print("Part 2: Fill shadow names")
print("=" * 50)

def fill_shadows(folder_path, parent_nfo=None):
    """递归填充影子名，只用本地NFO"""
    count = 0
    folder_name = os.path.basename(folder_path)
    
    # 读NFO
    nfo = scraper.read_nfo(folder_path)
    ft = classify_folder(folder_path, library)
    is_coll = ft.get("type") in ("movie_collection","series_collection","mixed","variety","misc")
    
    # 文件夹影子名
    use_nfo = nfo if nfo and nfo.get("tmdb_id") else parent_nfo
    if use_nfo and use_nfo.get("title"):
        title = use_nfo["title"]
        en = use_nfo.get("english_title", "")
        orig = use_nfo.get("original_title", "")
        year = use_nfo.get("year", "")
        if not en and orig and orig != title and _is_mostly_latin(orig):
            en = orig
        shadow = title
        if en and en != title:
            shadow += " " + en
        if year:
            shadow += f" ({year})"
        if shadow_m.auto_fill(folder_path, shadow, source="parsed"):
            count += 1
    
    # 视频文件影子名
    for item in sorted(os.listdir(folder_path)):
        fp = os.path.join(folder_path, item)
        if not os.path.isfile(fp) or os.path.splitext(item)[1].lower() not in video_exts:
            continue
        
        vnfo = scraper.read_video_nfo(fp)
        sd = vnfo if vnfo and vnfo.get("tmdb_id") else (nfo if nfo and nfo.get("tmdb_id") else parent_nfo)
        
        # 补英文名
        if sd and not sd.get("english_title"):
            src = nfo or parent_nfo
            if src and src.get("english_title"):
                sd = dict(sd)
                sd["english_title"] = src["english_title"]
        
        ft_name = ""
        src_nfo = nfo or parent_nfo
        if src_nfo:
            ft_name = src_nfo.get("title", "") or src_nfo.get("original_title", "")
        if not ft_name:
            ft_name = re.sub(r'[\[\(].*?[\]\)]', '', folder_name).strip()
        
        new_name = generate_standard_name(item, sd, None, ft_name, is_collection=is_coll)
        shadow = os.path.splitext(new_name)[0]
        shadow = re.sub(r'\s+(2160p|1080p|720p)$', '', shadow)
        
        # 用父目录剧名修正
        if parent_nfo and parent_nfo.get("title"):
            ep_m = re.search(r'S\d+E\d+', shadow)
            if ep_m:
                pcn = parent_nfo["title"]
                pen = parent_nfo.get("english_title", "")
                if pen and not _is_mostly_latin(pen):
                    pen = ""
                ns = pcn
                if pen and pen != pcn:
                    ns += " " + pen
                ns += " " + ep_m.group(0)
                shadow = ns
        
        if shadow_m.auto_fill(fp, shadow, source="parsed"):
            count += 1
    
    # 递归子目录
    try:
        for item in sorted(os.listdir(folder_path)):
            sub = os.path.join(folder_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                count += fill_shadows(sub, parent_nfo=nfo or parent_nfo)
    except OSError:
        pass
    
    return count

total_folders = 0
total_filled = 0
total_errors = 0

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
            n = fill_shadows(sp)
            total_filled += n
            if n > 0:
                print(f"  [{top}] {sub}: {n}")
        except Exception as e:
            total_errors += 1
            print(f"  [{top}] {sub}: ERR {str(e)[:60]}")

print(f"\nDone: {total_folders} folders, {total_filled} shadows, {total_errors} errors")
