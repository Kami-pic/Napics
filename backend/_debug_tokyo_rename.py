"""调试东京食尸鬼的标准名修正逻辑"""
import sys, os, zipfile, re
sys.path.insert(0, '.')
import organizer, scraper, tmdb_client, config_manager

config_m = config_manager.ConfigManager()
library = config_m.load_library()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

p = r"\\DS218play\share\视频\动画番\东京食尸鬼 Tokyo Ghoul"

# 恢复旧刮削
for d in [p] + [os.path.join(p, x) for x in os.listdir(p) if os.path.isdir(os.path.join(p, x))]:
    zp = os.path.join(d, ".old_scrape.zip")
    if os.path.exists(zp):
        with zipfile.ZipFile(zp, 'r') as zf: zf.extractall(d)
        os.remove(zp)

# 备份删除旧刮削
from _organize_pipeline import archive_old_scrape
archive_old_scrape(p, delete_after=True)

# 刮削
scraper.scrape_folder(p, client, force=True)

# 检查 tvshow.nfo
nfo = scraper.read_nfo(p)
print(f"tvshow.nfo title: {nfo.get('title') if nfo else 'NONE'}")
print(f"tvshow.nfo english: {nfo.get('english_title') if nfo else 'NONE'}")
print(f"tvshow.nfo original: {nfo.get('original_title') if nfo else 'NONE'}")

# 标准名
result = organizer.rename_videos_in_folder(p, client, dry_run=True, library_data=library)

# 检查 folder_scrape 是否传递到了子文件夹
folder_items = [r for r in result if r.get("is_folder") and not r.get("is_subfolder")]
sub_items = [r for r in result if r.get("is_subfolder")]
video_items = [r for r in result if not r.get("is_folder")]

print(f"\n文件夹标准名:")
for r in folder_items:
    print(f"  {r['old_name'][:30]} -> {r['shadow_name'][:40]}")

print(f"\n季目录标准名:")
for r in sub_items:
    print(f"  {r['old_name'][:30]} -> {r['shadow_name'][:40]}")

print(f"\n视频标准名 (前5):")
for r in video_items[:5]:
    print(f"  {r['old_name'][:35]} -> {r['shadow_name'][:40]}")
