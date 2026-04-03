import sys; sys.path.insert(0, '.')
import tmdb_client, config_manager
config_m = config_manager.ConfigManager()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

for q in ["东京食尸鬼", "东京喰种", "Tokyo Ghoul", "东京食尸鬼 Tokyo Ghoul"]:
    tv = client.search_tv(q)
    print(f"search_tv('{q}'): {len(tv)} results")
    for r in tv[:2]:
        print(f"  id={r.get('id')} name={r.get('name')}")
