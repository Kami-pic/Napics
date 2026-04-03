"""测试当前清洗函数对不同层级文件名的效果"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from analyzer import _clean_filename_for_folder
from tmdb_client import parse_filename

print("=== 剧名（tv 父文件夹） ===")
tv_names = [
    "西部世界1-3季",
    "混沌武士  Samurai Champloo (BD 720P x264 10bit AAC)",
    "进击的巨人s1-s5",
    "心理测量者s1-s3",
    "火线1-6季",
    "钢之炼金术师FA",
    "只有我不在的街道只有我不在的城市[Boku_Dake_ga_Inai_Machi][BDrip][01_12][GB][1080P][HEVC_Main10]",
    "奇巧计程车[odd taxi][01~13][GB_MP4][1280X720]",
    "紫罗兰花园[1080P][CHS][MP4]",
    "黑街Gangsta [BD HEVC 720p AAC]",
]
for n in tv_names:
    c = _clean_filename_for_folder(n + ".tmp")
    print(f"  {n}")
    print(f"    → {c}")

print("\n=== 季名（season 文件夹） ===")
season_names = [
    "Justified.S02.1080p.BluRay.x265-RARBG",
    "westworld S3",
    "西部世界S2",
    "Season 01",
    "第1季",
    "巴哈姆特之怒 第2季",
]
for n in season_names:
    c = _clean_filename_for_folder(n + ".tmp")
    print(f"  {n}")
    print(f"    → {c}")

print("\n=== 集名（单集视频） ===")
ep_names = [
    "切尔诺贝利S01E01.1080p.HD中英双字[最新电影www.66e.cc].mp4",
    "The.Leftovers.S01E01.2014.1080p.Blu-ray.x265.AC3￡cXcY.mkv",
    "[SFEO-Raws] Samurai Champloo - 02 (BD 720P x264 10bit AAC)[3F5E8958].mp4",
    "自由的她们.Libres.EP1.720p.WEBrip.中法双语.弯弯字幕组.mp4",
    "02.rmvb",
    "守望者.Watchmen.S01E05.中英字幕.WEBrip.720P-人人影视.mp4",
]
for n in ep_names:
    c = _clean_filename_for_folder(n)
    p = parse_filename(n)
    print(f"  {n}")
    print(f"    clean_folder → {c}")
    print(f"    parse_filename → clean={p['clean_name']}, s={p['season']}, e={p['episode']}, abs={p['absolute_episode']}")
