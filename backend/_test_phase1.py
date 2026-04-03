"""Phase 1 验证脚本：parse_filename 绝对集数 + ScrapeResult.seasons_info + build_absolute_episode_map"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from tmdb_client import parse_filename, build_absolute_episode_map, ScrapeResult

print("=" * 60)
print("1. parse_filename 绝对集数测试")
print("=" * 60)

tests = [
    # (文件名, 期望 season, 期望 episode, 期望 absolute_episode)
    ("060.mkv", None, None, 60),
    ("[SubGroup] Shingeki no Kyojin [060].mkv", None, None, 60),
    ("S01E25.mkv", 1, 25, None),
    ("[字幕组] 作品名 [26].mkv", 1, 26, None),  # 26 < 50，不触发
    ("[字幕组] 作品名 [51].mkv", None, None, 51),  # 51 > 50，触发
    ("进击的巨人 第3季 01.mkv", 3, 1, None),  # 有"第3季"，season=3 是正确的
    ("Naruto Shippuden - 220.mkv", None, None, 220),
    ("S02E10.1080p.mkv", 2, 10, None),  # 标准 SxxExx，不触发
    ("第50集.mp4", 1, 50, None),  # 50 不 > 50，不触发
    ("第51集.mp4", None, None, 51),  # 51 > 50，触发
    ("README.mkv", None, None, None),  # 无集号
]

all_pass = True
for fname, exp_s, exp_e, exp_abs in tests:
    r = parse_filename(fname)
    s, e, a = r["season"], r["episode"], r["absolute_episode"]
    ok = (s == exp_s and e == exp_e and a == exp_abs)
    status = "✓" if ok else "✗"
    if not ok:
        all_pass = False
    print(f"  {status} {fname}")
    if not ok:
        print(f"    期望: season={exp_s}, episode={exp_e}, absolute={exp_abs}")
        print(f"    实际: season={s}, episode={e}, absolute={a}")

print()
print("=" * 60)
print("2. ScrapeResult.seasons_info 兼容性测试")
print("=" * 60)

# 旧缓存没有 seasons_info 字段
old_cache = {"tmdb_id": 1429, "media_type": "tv", "title": "进击的巨人"}
r = ScrapeResult(**old_cache)
print(f"  ✓ 旧缓存兼容: seasons_info={r.seasons_info}")

# 新数据有 seasons_info
new_data = {"tmdb_id": 1429, "media_type": "tv", "title": "进击的巨人",
            "seasons_info": [{"season_number": 0, "episode_count": 8},
                             {"season_number": 1, "episode_count": 25},
                             {"season_number": 2, "episode_count": 12}]}
r2 = ScrapeResult(**new_data)
print(f"  ✓ 新数据: seasons_info={r2.seasons_info}")

print()
print("=" * 60)
print("3. build_absolute_episode_map 测试")
print("=" * 60)

# 进击的巨人：S1=25, S2=12, S3=22, S4=28（含 Season 0 特别篇 8 集）
seasons = [
    {"season_number": 0, "episode_count": 8},
    {"season_number": 1, "episode_count": 25},
    {"season_number": 2, "episode_count": 12},
    {"season_number": 3, "episode_count": 22},
    {"season_number": 4, "episode_count": 28},
]
m = build_absolute_episode_map(seasons)

checks = [
    (1, (1, 1)),
    (25, (1, 25)),
    (26, (2, 1)),
    (37, (2, 12)),
    (38, (3, 1)),
    (59, (3, 22)),
    (60, (4, 1)),  # 注意：不是 (3,10)，因为 S3 只有 22 集
    (87, (4, 28)),
]

for abs_ep, expected in checks:
    actual = m.get(abs_ep)
    ok = actual == expected
    status = "✓" if ok else "✗"
    if not ok:
        all_pass = False
    print(f"  {status} abs={abs_ep} → {actual} (期望 {expected})")

print()
if all_pass:
    print("全部通过 ✓")
else:
    print("有失败项 ✗")
