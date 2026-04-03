import sys; sys.path.insert(0, '.')
from organizer import generate_standard_name
from tmdb_client import parse_filename

f = "【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季1024高清02.rmvb"
parsed = parse_filename(f)
print(f"parsed: season={parsed['season']} episode={parsed['episode']} clean={parsed['clean_name'][:30]}")

# 模拟有 scrape_data (season.nfo)
scrape = {"title": "权力的游戏", "original_title": "", "english_title": "", "year": "", "episode_title": "", "media_type": "season"}
result = generate_standard_name(f, scrape, folder_title="权力的游戏")
print(f"with scrape: {result}")

# 模拟没有 scrape_data
result2 = generate_standard_name(f, None, folder_title="权力的游戏")
print(f"no scrape: {result2}")
