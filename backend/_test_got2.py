import sys; sys.path.insert(0, '.')
import tmdb_client, config_manager
config_m = config_manager.ConfigManager()
client = tmdb_client.TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

for q in ["权力的游戏", "Game of Thrones", "冰与火之歌", "冰火"]:
    r = client.scrape_by_filename(q)
    print(f"  '{q}' -> tmdb_id={r.tmdb_id} title={r.title} type={r.media_type}")
