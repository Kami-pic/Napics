import sys, os, zipfile
sys.path.insert(0, '.')
import organizer, scraper, tmdb_client, config_manager
from analyzer import _clean_filename_for_folder

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

p = r"\\DS218play\share\视频\电视剧\冰与火之歌1-8季"

# 恢复旧刮削
for d in [p] + [os.path.join(p, x) for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))]:
    zp = os.path.join(d, ".old_scrape.zip")
    if os.path.exists(zp):
        with zipfile.ZipFile(zp, 'r') as zf:
            zf.extractall(d)
        os.remove(zp)

# 备份删除旧刮削
from _organize_pipeline import archive_old_scrape
archive_old_scrape(p, delete_after=True)

# 刮削
scraper.scrape_folder(p, client, force=True)

# 标准名
result = organizer.rename_videos_in_folder(p, client, dry_run=True, library_data=library)

print("=== 冰与火之歌 前2季标准名 ===\n")

# 直接测试 generate_standard_name
from organizer import generate_standard_name
import scraper as scr
s1_path = os.path.join(p, "冰火S1")
s1_nfo = scr.read_nfo(s1_path)
print(f"S1 folder_scrape: title={s1_nfo.get('title') if s1_nfo else None} tmdb={s1_nfo.get('tmdb_id') if s1_nfo else None}")

# 测试第一个视频
s1_videos = [f for f in os.listdir(s1_path) if os.path.splitext(f)[1].lower() in {'.rmvb','.mp4','.mkv'}]
if s1_videos:
    v = s1_videos[0]
    print(f"Video: {v[:50]}")
    gen = generate_standard_name(v, s1_nfo, folder_title=s1_nfo.get('title','') if s1_nfo else '')
    print(f"Generated: {gen}")
print()

# 文件夹标准名
folder_items = [r for r in result if r.get("is_folder") and not r.get("is_subfolder")]
for r in folder_items:
    print(f"📁 文件夹: {r['old_name']}")
    print(f"   标准名: {r['shadow_name']}")
    print()

# S1
print("--- 第1季 ---")
s1_items = [r for r in result if not r.get("is_folder") and "冰火S1" in r.get("old_path", "")]
if not s1_items:
    s1_items = [r for r in result if not r.get("is_folder")][:10]
for r in s1_items[:10]:
    old = r.get("old_name", "")[:50]
    shadow = r.get("shadow_name", "")[:50]
    print(f"  原始: {old}")
    print(f"  标准: {shadow}")
    print()

# S2
print("--- 第2季 ---")
s2_items = [r for r in result if not r.get("is_folder") and "冰火S2" in r.get("old_path", "")]
for r in s2_items[:5]:
    old = r.get("old_name", "")[:50]
    shadow = r.get("shadow_name", "")[:50]
    print(f"  原始: {old}")
    print(f"  标准: {shadow}")
    print()

# 季目录标准名
subfolder_items = [r for r in result if r.get("is_subfolder")]
if subfolder_items:
    print("--- 季目录 ---")
    for r in subfolder_items[:4]:
        print(f"  {r['old_name']} → {r['shadow_name']}")
