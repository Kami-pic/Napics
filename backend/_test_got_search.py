import sys; sys.path.insert(0, '.')
from analyzer import _clean_filename_for_folder
import tmdb_client, config_manager, re
config_m = config_manager.ConfigManager()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

# 测试子目录文件名搜索
f = "【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季HD中英双字1280高清01.rmvb"
clean = _clean_filename_for_folder(f)
print(f"clean: {clean}")

parts = re.split(r'[：:·]', clean)
print(f"parts: {parts}")
for p in reversed(parts):
    p = p.strip()
    if len(p) >= 2:
        r = client.scrape_by_filename(p)
        print(f"  search '{p}' -> tmdb_id={r.tmdb_id} title={r.title} type={r.media_type}")
        if r.tmdb_id:
            break

# 也测试英文部分
en_parts = re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', f)
print(f"\nen_parts: {en_parts}")
