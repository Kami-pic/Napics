"""RSS 订阅引擎单元测试：源基类、匹配引擎、频率衰减、Prowlarr 源。"""

import os
import sys

import pytest

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from rss_source_base import RSSItem, extract_episode, extract_season
from rss_matcher import match_items, _filter_quality, _filter_keywords, _filter_episodes
from rss_engine import should_search_now, RSSSourceManager

# Prowlarr 源由 rss-tv-movie 社区插件提供，未安装插件时相关用例跳过。
try:
    from rss_source_prowlarr import ProwlarrRSSSource
except ModuleNotFoundError:
    ProwlarrRSSSource = None

_NEED_PROWLARR = "需要 rss-tv-movie 插件提供 rss_source_prowlarr"
from subscriber import Subscription, EpisodeInfo
from datetime import datetime, timedelta

passed = 0
failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")


def fail(name, msg):
    global failed
    failed += 1
    print(f"  [FAIL] {name}: {msg}")


# ═══════════════════════════════════════════
# 1. 集号/季号提取
# ═══════════════════════════════════════════

def test_extract_episode():
    print("\n[SUITE] 集号提取")
    cases = [
        ("[SubGroup] Title S01E05 1080p", 5),
        ("[ANi] 进击的巨人 - 第12话", 12),
        ("Title EP03 720p", 3),
        ("[Mikan] Title - 08 [1080p]", 8),
        ("Movie.2024.2160p.WEB-DL", None),
        ("[字幕组] 三体 第5集 1080p", 5),
    ]
    for title, expected in cases:
        result = extract_episode(title)
        if result == expected:
            ok(f"extract_episode('{title[:30]}...') = {result}")
        else:
            fail(f"extract_episode('{title[:30]}...')", f"期望 {expected}，实际 {result}")


def test_extract_season():
    print("\n[SUITE] 季号提取")
    cases = [
        ("[SubGroup] Title S02E05 1080p", 2),
        ("Title Season 3 Complete", 3),
        ("第1季 全集", 1),
        ("Movie.2024.2160p", None),
    ]
    for title, expected in cases:
        result = extract_season(title)
        if result == expected:
            ok(f"extract_season('{title[:30]}...') = {result}")
        else:
            fail(f"extract_season('{title[:30]}...')", f"期望 {expected}，实际 {result}")


# ═══════════════════════════════════════════
# 2. 质量过滤
# ═══════════════════════════════════════════

def test_quality_filter():
    print("\n[SUITE] 质量过滤")
    items = [
        RSSItem(title="Movie.2024.2160p.WEB-DL.x265", resolution="2160p"),
        RSSItem(title="Movie.2024.1080p.Bluray", resolution="1080p"),
        RSSItem(title="Movie.2024.720p.HDTV", resolution="720p"),
        RSSItem(title="Movie.2024.SD", resolution=""),
    ]

    # 最低 1080p → 应保留 2160p 和 1080p
    result = _filter_quality(items, "1080p")
    if len(result) == 2:
        ok("最低1080p过滤: 保留2条")
    else:
        fail("最低1080p过滤", f"期望2条，实际{len(result)}")

    # 最低 2160p → 只保留 2160p
    result = _filter_quality(items, "2160p")
    if len(result) == 1:
        ok("最低2160p过滤: 保留1条")
    else:
        fail("最低2160p过滤", f"期望1条，实际{len(result)}")

    # 无要求 → 全部保留
    result = _filter_quality(items, "")
    if len(result) == 4:
        ok("无质量要求: 全部保留")
    else:
        fail("无质量要求", f"期望4条，实际{len(result)}")


# ═══════════════════════════════════════════
# 3. 关键词过滤
# ═══════════════════════════════════════════

def test_keyword_filter():
    print("\n[SUITE] 关键词过滤")
    items = [
        RSSItem(title="Movie.2024.2160p.REMUX.DTS-HD"),
        RSSItem(title="Movie.2024.1080p.WEB-DL.AAC"),
        RSSItem(title="Movie.2024.CAM.TS"),
    ]

    # 排除 CAM
    result = _filter_keywords(items, "", "CAM")
    if len(result) == 2:
        ok("排除CAM: 保留2条")
    else:
        fail("排除CAM", f"期望2条，实际{len(result)}")

    # 包含 REMUX
    result = _filter_keywords(items, "REMUX", "")
    if len(result) == 1:
        ok("包含REMUX: 保留1条")
    else:
        fail("包含REMUX", f"期望1条，实际{len(result)}")

    # 排除 CAM + 包含 WEB-DL
    result = _filter_keywords(items, "WEB-DL", "CAM")
    if len(result) == 1 and "WEB-DL" in result[0].title:
        ok("组合过滤: WEB-DL且非CAM")
    else:
        fail("组合过滤", f"实际{len(result)}条")


# ═══════════════════════════════════════════
# 4. 集数匹配
# ═══════════════════════════════════════════

def test_episode_filter():
    print("\n[SUITE] 集数匹配")

    # 剧集订阅，已下载 E01 E02
    sub = Subscription(
        id="test", title="三体", type="tv", season=1, total_episode=30,
        downloaded_episodes={
            "1": EpisodeInfo(info_hash="hash1"),
            "2": EpisodeInfo(info_hash="hash2"),
        }
    )
    items = [
        RSSItem(title="三体 S01E01 1080p", episode=1, season=1, info_hash="hash1"),
        RSSItem(title="三体 S01E02 1080p", episode=2, season=1, info_hash="hash2"),
        RSSItem(title="三体 S01E03 1080p", episode=3, season=1, info_hash="hash3"),
        RSSItem(title="三体 S01E04 1080p", episode=4, season=1, info_hash="hash4"),
    ]
    result = _filter_episodes(items, sub)
    if len(result) == 2 and all(r.episode in (3, 4) for r in result):
        ok("剧集: 已下载E01E02，保留E03E04")
    else:
        fail("剧集匹配", f"期望2条(E03E04)，实际{len(result)}条")

    # 电影订阅，未下载
    movie_sub = Subscription(id="m1", title="沙丘3", type="movie")
    movie_items = [RSSItem(title="Dune3.2026.2160p", info_hash="dune_hash")]
    result = _filter_episodes(movie_items, movie_sub)
    if len(result) == 1:
        ok("电影: 未下载，保留")
    else:
        fail("电影未下载", f"期望1条，实际{len(result)}")

    # 电影已下载
    movie_sub2 = Subscription(
        id="m2", title="沙丘3", type="movie",
        downloaded_episodes={"0": EpisodeInfo(info_hash="old_hash")}
    )
    result = _filter_episodes(movie_items, movie_sub2)
    if len(result) == 0:
        ok("电影: 已下载，过滤")
    else:
        fail("电影已下载", f"期望0条，实际{len(result)}")


# ═══════════════════════════════════════════
# 5. 频率衰减
# ═══════════════════════════════════════════

def test_frequency_decay():
    print("\n[SUITE] 频率衰减")
    now = datetime.now()

    # 从未搜索 → 立即搜
    sub = Subscription(id="t1", state="active", last_search="", created_at=now.strftime("%Y-%m-%d %H:%M:%S"))
    if should_search_now(sub):
        ok("从未搜索 → 立即搜")
    else:
        fail("从未搜索", "应该返回 True")

    # 刚搜过 1 小时 → 不搜（间隔 4h）
    sub2 = Subscription(
        id="t2", state="active",
        last_search=(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    if not should_search_now(sub2):
        ok("1小时前搜过 → 不搜")
    else:
        fail("1小时前搜过", "应该返回 False")

    # 5 小时前搜过 → 搜（间隔 4h）
    sub3 = Subscription(
        id="t3", state="active",
        last_search=(now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
        created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    if should_search_now(sub3):
        ok("5小时前搜过 → 搜")
    else:
        fail("5小时前搜过", "应该返回 True")

    # 暂停状态 → 不搜
    sub4 = Subscription(id="t4", state="paused", last_search="")
    if not should_search_now(sub4):
        ok("暂停状态 → 不搜")
    else:
        fail("暂停状态", "应该返回 False")

    # 超过 30 天 → 不搜
    sub5 = Subscription(
        id="t5", state="active", search_count=25,
        last_search=(now - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S"),
        created_at=(now - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    if not should_search_now(sub5):
        ok("超过30天 → 不搜")
    else:
        fail("超过30天", "应该返回 False")


# ═══════════════════════════════════════════
# 6. 源管理器
# ═══════════════════════════════════════════

def test_source_manager():
    print("\n[SUITE] 源管理器")
    if ProwlarrRSSSource is None:
        pytest.skip(_NEED_PROWLARR)
    mgr = RSSSourceManager()

    # 注册源
    src = ProwlarrRSSSource()
    mgr.register(src)
    if len(mgr.get_all_sources()) == 1:
        ok("注册源")
    else:
        fail("注册源", f"期望1个，实际{len(mgr.get_all_sources())}")

    # 启用的源
    if len(mgr.get_enabled_sources()) == 1:
        ok("默认启用")
    else:
        fail("默认启用", f"期望1个")

    # 禁用
    mgr.set_enabled("prowlarr", False)
    if len(mgr.get_enabled_sources()) == 0:
        ok("禁用后为0")
    else:
        fail("禁用后", f"期望0个")

    # 重新启用
    mgr.set_enabled("prowlarr", True)
    if len(mgr.get_enabled_sources()) == 1:
        ok("重新启用")
    else:
        fail("重新启用", f"期望1个")

    # 不存在的源
    if not mgr.set_enabled("nonexistent", True):
        ok("不存在的源返回 False")
    else:
        fail("不存在的源", "应该返回 False")


# ═══════════════════════════════════════════
# 7. Prowlarr 源搜索词构造
# ═══════════════════════════════════════════

def test_prowlarr_search_group():
    print("\n[SUITE] Prowlarr 搜索词构造")
    if ProwlarrRSSSource is None:
        pytest.skip(_NEED_PROWLARR)
    src = ProwlarrRSSSource()

    # 剧集 + 别名
    sub = Subscription(
        title="进击的巨人", year="2013", type="tv", season=1,
        aliases={"cn": ["进击的巨人"], "en": ["Attack on Titan"], "jp": ["進撃の巨人"]},
    )
    kws = src._build_search_group(sub)
    if "Attack on Titan S01" in kws:
        ok("英文名+季号")
    else:
        fail("英文名+季号", f"关键词: {kws}")

    if "進撃の巨人 S01" in kws:
        ok("日文名+季号")
    else:
        fail("日文名+季号", f"关键词: {kws}")

    # 自定义搜索词优先
    sub2 = Subscription(title="三体", search_keyword="Three Body Problem")
    kws2 = src._build_search_group(sub2)
    if kws2 == ["Three Body Problem"]:
        ok("自定义搜索词优先")
    else:
        fail("自定义搜索词", f"关键词: {kws2}")

    # 电影无季号
    sub3 = Subscription(title="流浪地球3", year="2027", type="movie")
    kws3 = src._build_search_group(sub3)
    has_season = any("S0" in kw for kw in kws3)
    if not has_season:
        ok("电影无季号后缀")
    else:
        fail("电影无季号", f"关键词: {kws3}")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("RSS 订阅引擎单元测试")
    print("=" * 60)

    test_extract_episode()
    test_extract_season()
    test_quality_filter()
    test_keyword_filter()
    test_episode_filter()
    test_frequency_decay()
    test_source_manager()
    test_prowlarr_search_group()

    print(f"\n{'=' * 60}")
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
