import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config_manager
from tmdb_client import TMDBClient

config_m = config_manager.ConfigManager()
client = TMDBClient(config_m.config.tmdb_api_key, proxy=config_m.config.http_proxy or '')

# 检查 tmdb_id=1107264
detail = client.get_tv_detail(1107264)
print(f"id={detail.tmdb_id}, title='{detail.title}', en='{detail.english_title}', seasons={detail.total_seasons}")
print(f"seasons_info={detail.seasons_info}")
