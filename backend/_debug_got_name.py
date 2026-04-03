import sys, os; sys.path.insert(0, '.')
from organizer import generate_standard_name
from tmdb_client import parse_filename
from analyzer import _clean_filename_for_folder

f = "【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季1024高清02.rmvb"
clean = _clean_filename_for_folder(f)
parsed = parse_filename(f)
print(f"clean: {clean}")
print(f"parsed: {parsed}")

# 模拟 scrape_data (season.nfo)
scrape = {"title": "权力的游戏", "original_title": "", "english_title": "", "year": "", "episode_title": ""}
result = generate_standard_name(f, scrape, folder_title="权力的游戏")
print(f"standard: {result}")

# 也测试没有 scrape_data 的情况
result2 = generate_standard_name(f, None, folder_title="权力的游戏")
print(f"no scrape: {result2}")
