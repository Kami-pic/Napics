"""测试新的层级清洗函数"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from analyzer import _clean_filename_for_folder, clean_season_name, clean_episode_name

print("=== 季名 clean_name ===")
tests = [
    ("Justified.S02.1080p.BluRay.x265-RARBG", "火线 The Wire", "火线 第2季"),
    ("westworld S3", "西部世界 Westworld", "西部世界 第3季"),
    ("西部世界S2", "西部世界 Westworld", "西部世界 第2季"),
    ("Season 01", "切尔诺贝利 Chernobyl", "切尔诺贝利 第1季"),
    ("第1季", "心理测量者", "心理测量者 第1季"),
    ("巴哈姆特之怒 第2季", "", "巴哈姆特之怒 第2季"),
    ("Season 01", "", "Season 01"),
]
all_pass = True
for name, parent, expected in tests:
    result = clean_season_name(name, parent)
    ok = result == expected
    if not ok: all_pass = False
    print(f"  {'✓' if ok else '✗'} {name} (parent={parent})")
    if not ok:
        print(f"    期望: {expected}")
        print(f"    实际: {result}")

print("\n=== 集名 clean_name ===")
ep_tests = [
    ("切尔诺贝利S01E01.1080p.HD中英双字[最新电影www.66e.cc].mp4", "切尔诺贝利 Chernobyl", "", "切尔诺贝利 S01E01"),
    ("02.rmvb", "钢之炼金术师 FA 鋼の錬金術師", "", "钢之炼金术师 FA S01E02"),
    ("The.Leftovers.S01E01.2014.1080p.Blu-ray.x265.AC3￡cXcY.mkv", "守望尘世 The Leftovers", "", "守望尘世 S01E01"),
    ("[SFEO-Raws] Samurai Champloo - 02 (BD 720P x264 10bit AAC)[3F5E8958].mp4", "混沌武士 Samurai Champloo", "", "混沌武士 S01E02"),
    ("westworld.s03e01.1080p.web.h264-xlf.chs.eng.mp4", "西部世界 Westworld", "", "西部世界 S03E01"),
    ("Justified.S02E01.1080p.BluRay.x265-RARBG.mp4", "火线 The Wire", "", "火线 S02E01"),
    # 纯英文无中文父级
    ("Justified.S02E01.1080p.BluRay.x265-RARBG.mp4", "", "", "Justified S02E01"),
]
for name, parent, ep_title, expected in ep_tests:
    result = clean_episode_name(name, parent, ep_title)
    ok = result == expected
    if not ok: all_pass = False
    print(f"  {'✓' if ok else '✗'} {name}")
    if not ok:
        print(f"    期望: {expected}")
        print(f"    实际: {result}")

print()
print("全部通过 ✓" if all_pass else "有失败项 ✗")
