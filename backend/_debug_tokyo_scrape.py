import sys; sys.path.insert(0, '.')
import tmdb_client, config_manager
config_m = config_manager.ConfigManager()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

for q in ["东京食尸鬼", "东京喰种", "Tokyo Ghoul", "东京食尸鬼 Tokyo Ghoul"]:
    r = client.scrape_by_filename(q)
    print(f"  '{q}' -> tmdb_id={r.tmdb_id} title={r.title} type={r.media_type}")
    
# 也直接搜 TV
results = client.search_tv("Tokyo Ghoul")
print(f"\nsearch_tv 'Tokyo Ghoul': {len(results)} results")
for r in results[:3]:
    print(f"  id={r.get('id')} name={r.get('name')} first_air={r.get('first_air_date','')[:4]}")
