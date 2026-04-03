import sys; sys.path.insert(0, '.')
from tmdb_client import parse_filename

tests = [
    "【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季1024高清02.rmvb",
    "冰与火之歌：权力的游戏第二季1280高清01 720p.rmvb",
    "权力的游戏第七季01.mp4",
    "权力的游戏.Game.of.Thrones.S05E01.中英字幕.WEB-HR.AAC.1024X576.x264.mp4",
]
for t in tests:
    r = parse_filename(t)
    print(f"  {t[:50]}")
    print(f"    S{r['season'] or '?'}E{r['episode'] or '?'}")
