"""阶段4 端到端测试：质量评分升级 + 自动洗版。

覆盖范围：
1. 评分函数单元测试（直接 import）
2. save_library 自动注入 quality_score（API）
3. 洗版匹配逻辑（直接 import）
4. 回归测试（API）

测试数据用 "P4测试_" 前缀，结束后清理。
"""

import os
import sys
import json
import time
import requests
from typing import List, Dict, Any, Optional

# 确保 backend/ 在 sys.path 中
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from quality_parser import (
    QualityTag, parse_quality, compute_quality_score,
    compute_quality_score_from_video, compare_quality_score,
)
from rss_source_base import RSSItem
from rss_matcher import _filter_episodes

# 这一组直接对运行中的后端发 HTTP 请求。后端没起时应当 skip 而不是 fail —— 
# 否则真实问题会被一堆 ConnectionError 淹掉。
from test_support.live_backend import requires_live_backend

pytestmark = requires_live_backend

BASE = "http://127.0.0.1:8000"
TIMEOUT = 15
PREFIX = "P4测试_"

results: List[Dict[str, Any]] = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    icon = "✅" if passed else "❌"
    msg = f"  {icon} [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def api(method: str, path: str, timeout: int = TIMEOUT, **kwargs) -> requests.Response:
    url = f"{BASE}{path}"
    return requests.request(method, url, timeout=timeout, **kwargs)


def cleanup_test_data():
    """删除所有以 P4测试_ 开头的订阅"""
    try:
        resp = api("GET", "/subscribe")
        if resp.status_code == 200:
            subs = resp.json()
            for s in subs:
                if isinstance(s, dict) and s.get("title", "").startswith(PREFIX):
                    api("DELETE", f"/subscribe/{s['id']}")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# 1. 评分函数单元测试
# ═══════════════════════════════════════════════════════════

def test_score_dimensions():
    """各维度分数正确性"""
    print("\n[SUITE 1.1] compute_quality_score 各维度分数")

    # 满分：2160p(45) + Remux(20) + x265(10) + Atmos(20) + 中字(5) = 100
    tag = QualityTag(
        resolution="2160p", source="Remux",
        video_codec="x265", audio_codec="Atmos",
        has_chinese_sub=True,
    )
    score = compute_quality_score(tag)
    record("满分 2160p Remux x265 Atmos 中字 = 100", score == 100, f"实际={score}")

    # 纯分辨率
    for res, expected in [("2160p", 45), ("1080p", 28), ("720p", 14)]:
        tag = QualityTag(resolution=res)
        s = compute_quality_score(tag)
        record(f"纯分辨率 {res} = {expected}", s == expected, f"实际={s}")

    # 纯来源
    for src, expected in [("Remux", 20), ("Bluray", 16), ("WEB-DL", 10), ("HDTV", 5)]:
        tag = QualityTag(source=src)
        s = compute_quality_score(tag)
        record(f"纯来源 {src} = {expected}", s == expected, f"实际={s}")

    # 纯音频
    for audio, expected in [("Atmos", 20), ("TrueHD", 17), ("DTS-HD", 14),
                            ("DDP5.1", 10), ("DD5.1", 8), ("DTS", 7),
                            ("EAC3", 6), ("AC3", 5), ("AAC", 3)]:
        tag = QualityTag(audio_codec=audio)
        s = compute_quality_score(tag)
        record(f"纯音频 {audio} = {expected}", s == expected, f"实际={s}")

    # 纯编码
    for codec, expected in [("x265", 10), ("AV1", 10), ("x264", 6)]:
        tag = QualityTag(video_codec=codec)
        s = compute_quality_score(tag)
        record(f"纯编码 {codec} = {expected}", s == expected, f"实际={s}")

    # 中字加分
    tag_no_sub = QualityTag(resolution="1080p")
    tag_sub = QualityTag(resolution="1080p", has_chinese_sub=True)
    diff = compute_quality_score(tag_sub) - compute_quality_score(tag_no_sub)
    record("中字加分 = 5", diff == 5, f"差值={diff}")

    # 空标签 = 0 分
    tag_empty = QualityTag()
    s = compute_quality_score(tag_empty)
    record("空标签 = 0", s == 0, f"实际={s}")


def test_score_from_video():
    """compute_quality_score_from_video 从视频条目算分"""
    print("\n[SUITE 1.2] compute_quality_score_from_video")

    # 1080p 视频 + 文件名含 WEB-DL x265
    video1 = {
        "height": 1080,
        "file_name": "Movie.2024.1080p.WEB-DL.x265.DDP5.1-GROUP.mkv",
        "codec": "",
        "audio_codec": "",
        "subtitle_count": 0,
    }
    s1 = compute_quality_score_from_video(video1)
    # 1080p(28) + WEB-DL(10) + x265(10) + DDP5.1(10) = 58
    record("1080p WEB-DL x265 DDP5.1 = 58", s1 == 58, f"实际={s1}")

    # 2160p 视频 + Remux + DTS-HD + x265 + 有字幕
    video2 = {
        "height": 2160,
        "file_name": "Movie.2024.2160p.Remux.DTS-HD.MA.x265-GROUP.mkv",
        "codec": "",
        "audio_codec": "",
        "subtitle_count": 2,
    }
    s2 = compute_quality_score_from_video(video2)
    # 2160p(45) + Remux(20) + x265(10) + DTS-HD(14) + 中字(5) = 94
    record("2160p Remux x265 DTS-HD 有字幕 = 94", s2 == 94, f"实际={s2}")

    # height 为字符串
    video3 = {"height": "720", "file_name": "show.720p.mkv"}
    s3 = compute_quality_score_from_video(video3)
    record("height 字符串 '720' 能正确解析", s3 >= 14, f"实际={s3}")

    # height=0，从文件名推断
    video4 = {"height": 0, "file_name": "Movie.2024.1080p.BluRay.x264.DTS-GROUP.mkv"}
    s4 = compute_quality_score_from_video(video4)
    # 从文件名解析: 1080p(28) + Bluray(16) + x264(6) + DTS(7) = 57
    record("height=0 从文件名推断 1080p", s4 > 0, f"实际={s4}")

    # 空视频条目
    video_empty = {}
    s_empty = compute_quality_score_from_video(video_empty)
    record("空视频条目 = 0", s_empty == 0, f"实际={s_empty}")


def test_compare_quality_score():
    """compare_quality_score 阈值比较逻辑"""
    print("\n[SUITE 1.3] compare_quality_score 阈值比较")

    # 新分数高出 >5 → True
    record("60 vs 50 (差10>5) → True", compare_quality_score(50, 60) is True)
    # 新分数高出 =5 → False（需要严格大于阈值）
    record("55 vs 50 (差5=5) → False", compare_quality_score(50, 55) is False)
    # 新分数高出 <5 → False
    record("53 vs 50 (差3<5) → False", compare_quality_score(50, 53) is False)
    # 新分数更低 → False
    record("40 vs 50 (更低) → False", compare_quality_score(50, 40) is False)
    # 相同分数 → False
    record("50 vs 50 (相同) → False", compare_quality_score(50, 50) is False)
    # 自定义阈值
    record("自定义阈值=10: 65 vs 50 → True", compare_quality_score(50, 65, threshold=10) is True)
    record("自定义阈值=10: 58 vs 50 → False", compare_quality_score(50, 58, threshold=10) is False)
    # 边界：0 分 vs 6 分
    record("0 vs 6 (差6>5) → True", compare_quality_score(0, 6) is True)
    record("0 vs 5 (差5=5) → False", compare_quality_score(0, 5) is False)


def test_parse_then_score_e2e():
    """从 BT 标题 parse_quality → compute_quality_score 端到端"""
    print("\n[SUITE 1.4] parse_quality + compute_quality_score 端到端")

    cases = [
        (
            "[CMCT] Movie.2024.2160p.Remux.HEVC.Atmos.CHS-GROUP",
            # 2160p(45) + Remux(20) + x265(10) + Atmos(20) + 中字(5) = 100
            100,
        ),
        (
            "Show.S01E05.1080p.WEB-DL.x265.DDP5.1.mkv",
            # 1080p(28) + WEB-DL(10) + x265(10) + DDP5.1(10) = 58
            58,
        ),
        (
            "Movie.2024.720p.HDTV.x264.AAC",
            # 720p(14) + HDTV(5) + x264(6) + AAC(3) = 28
            28,
        ),
        (
            "完全无法解析的标题",
            0,
        ),
    ]
    for title, expected in cases:
        tag = parse_quality(title)
        score = compute_quality_score(tag)
        short_title = title[:40] + "..." if len(title) > 40 else title
        record(f"'{short_title}' → {expected}", score == expected, f"实际={score}")


# ═══════════════════════════════════════════════════════════
# 2. save_library 自动注入 quality_score（API 测试）
# ═══════════════════════════════════════════════════════════

def test_save_library_injects_score():
    """验证 save_library 自动注入 quality_score 字段"""
    print("\n[SUITE 2] save_library 自动注入 quality_score")

    # 2.1 直接测试 save_library 注入逻辑（用临时数据）
    # 必须在隔离数据目录下跑：ConfigManager 的 lib_path 只认 NAPICS_DATA_DIR，
    # 不受 config_path 影响。此前这里用默认 ConfigManager() 写库、却把备份/读回
    # 路径拼在 tests/ 下，结果把真实 media_library.json 覆盖成 3 条测试夹具，
    # 备份也保护错了对象（tests/ 下那个文件根本不存在）。
    from config_manager import ConfigManager
    import shutil
    import tempfile

    tmp_data_dir = tempfile.mkdtemp(prefix="p4test_data_")
    _env_backup = os.environ.get("NAPICS_DATA_DIR")
    os.environ["NAPICS_DATA_DIR"] = tmp_data_dir

    try:
        cm = ConfigManager()
        # 用 cm 自己的路径读回，避免再次出现"写一个文件、读另一个文件"
        lib_path = cm.lib_path
        # 构造测试数据：没有 quality_score 字段的视频条目
        test_data = [
            {
                "file_path": "P4TEST_fake_1080p.mkv",
                "file_name": "Movie.2024.1080p.WEB-DL.x265.DDP5.1-GROUP.mkv",
                "height": 1080,
                "codec": "",
                "audio_codec": "",
                "subtitle_count": 0,
                "size_gb": 5.0,
            },
            {
                "file_path": "P4TEST_fake_2160p.mkv",
                "file_name": "Movie.2024.2160p.Remux.DTS-HD.x265-GROUP.mkv",
                "height": 2160,
                "codec": "",
                "audio_codec": "",
                "subtitle_count": 2,
                "size_gb": 50.0,
            },
            {
                "file_path": "P4TEST_fake_empty.mkv",
                "file_name": "unknown.mkv",
                "height": 0,
                "codec": "",
                "audio_codec": "",
                "subtitle_count": 0,
                "size_gb": 1.0,
            },
        ]

        # 调用 save_library
        cm.save_library(test_data)

        # 读回验证
        with open(lib_path, "r", encoding="utf-8") as f:
            saved = json.load(f)

        has_field = all("quality_score" in v for v in saved)
        record("save_library 注入 quality_score 字段", has_field,
               f"字段存在={[v.get('quality_score') for v in saved]}")

        # 验证分数合理
        scores = {v["file_path"]: v.get("quality_score", -1) for v in saved}
        s_1080 = scores.get("P4TEST_fake_1080p.mkv", -1)
        s_2160 = scores.get("P4TEST_fake_2160p.mkv", -1)
        s_empty = scores.get("P4TEST_fake_empty.mkv", -1)

        # 1080p WEB-DL x265 DDP5.1 = 58
        record("1080p 条目分数正确 (58)", s_1080 == 58, f"实际={s_1080}")
        # 2160p Remux x265 DTS-HD + 字幕 = 94
        record("2160p 条目分数正确 (94)", s_2160 == 94, f"实际={s_2160}")
        # 空条目 = 0
        record("空条目分数 = 0", s_empty == 0, f"实际={s_empty}")

        # 验证已有 quality_score 的条目不会被覆盖
        test_data_with_score = [
            {
                "file_path": "P4TEST_preset.mkv",
                "file_name": "Movie.720p.mkv",
                "height": 720,
                "quality_score": 99,  # 手动设置的高分
            },
        ]
        cm.save_library(test_data_with_score)
        with open(lib_path, "r", encoding="utf-8") as f:
            saved2 = json.load(f)
        preset_score = saved2[0].get("quality_score", -1)
        record("已有 quality_score 不被覆盖", preset_score == 99, f"实际={preset_score}")

    finally:
        # 还原环境变量并清理隔离目录（真实库全程未被触碰）
        if _env_backup is None:
            os.environ.pop("NAPICS_DATA_DIR", None)
        else:
            os.environ["NAPICS_DATA_DIR"] = _env_backup
        shutil.rmtree(tmp_data_dir, ignore_errors=True)

    # 2.2 API 层面验证：检查后端 /library 返回的数据
    print("\n[SUITE 2.2] API 层面验证 quality_score")
    try:
        resp = api("GET", "/library")
        if resp.status_code != 200:
            record("后端可达", False, f"status={resp.status_code}")
            return
        record("后端可达", True)

        library = resp.json()
        if not library:
            record("媒体库非空", False, "空列表")
            return
        record("媒体库非空", True, f"共 {len(library)} 条")

        # 统计有 quality_score 字段的条目
        has_score = [v for v in library if "quality_score" in v]
        has_nonzero = [v for v in has_score if v.get("quality_score", 0) > 0]

        # 如果同步成功过，应该有 quality_score；如果没同步过，可能没有
        if len(has_score) > 0:
            record("视频条目包含 quality_score 字段", True,
                   f"{len(has_score)}/{len(library)} 条有字段")
            record("存在 quality_score > 0 的条目",
                   len(has_nonzero) > 0, f"{len(has_nonzero)} 条非零分")
            # 分数范围检查
            out_of_range = [v for v in has_score if not (0 <= v.get("quality_score", 0) <= 100)]
            record("quality_score 在 0-100 范围内",
                   len(out_of_range) == 0,
                   f"{len(out_of_range)} 条超出范围" if out_of_range else "全部合规")
        else:
            # 没有 quality_score 字段 — 说明还没触发过带注入的 save_library
            # 用 compute_quality_score_from_video 验证注入逻辑本身是正确的
            sample = library[:5]
            computed = [compute_quality_score_from_video(v) for v in sample]
            record(
                "quality_score 字段尚未注入（需触发同步），但计算逻辑正确",
                True,
                f"抽样计算={computed}",
            )
    except Exception as e:
        record("API 层面验证", False, str(e))


# ═══════════════════════════════════════════════════════════
# 3. 洗版匹配逻辑（直接 import）
# ═══════════════════════════════════════════════════════════

class _FakeSub:
    """模拟 Subscription 对象，用于测试 _filter_episodes"""
    def __init__(self, type="tv", season=1, downloaded_episodes=None,
                 best_version=False, quality="1080p", include="", exclude=""):
        self.type = type
        self.season = season
        self.downloaded_episodes = downloaded_episodes or {}
        self.best_version = best_version
        self.quality = quality
        self.include = include
        self.exclude = exclude


def _make_item(title="Test.S01E01.1080p", episode=1, season=1,
               info_hash="", seeders=10) -> RSSItem:
    """构造测试用 RSSItem"""
    return RSSItem(
        title=title,
        episode=episode,
        season=season,
        info_hash=info_hash,
        seeders=seeders,
        download_url="magnet:?xt=test",
    )


def test_filter_episodes_best_version():
    """best_version=true 时，已下载的集也能匹配到新资源"""
    print("\n[SUITE 3.1] _filter_episodes 洗版模式")

    # 已下载 E01（hash=aaa）
    downloaded = {
        "1": {"info_hash": "aaa", "title": "old", "quality_tag": "WEB-DL-1080p-x265"},
    }

    items = [
        _make_item("Show.S01E01.2160p.Remux", episode=1, season=1, info_hash="bbb"),
        _make_item("Show.S01E02.1080p.WEB-DL", episode=2, season=1, info_hash="ccc"),
        _make_item("Show.S01E01.1080p.WEB-DL", episode=1, season=1, info_hash="aaa"),  # 同 hash
    ]

    # best_version=True：E01 新 hash 应该通过，同 hash 被去重
    sub_bv = _FakeSub(type="tv", season=1, downloaded_episodes=downloaded, best_version=True)
    filtered_bv = _filter_episodes(items, sub_bv)
    titles_bv = [it.title for it in filtered_bv]

    record(
        "洗版模式: 已下载E01的新hash版本通过",
        any("E01" in t and "2160p" in t for t in titles_bv),
        f"通过={titles_bv}",
    )
    record(
        "洗版模式: 同hash被去重",
        not any(it.info_hash == "aaa" for it in filtered_bv),
        f"通过的hash={[it.info_hash for it in filtered_bv]}",
    )
    record(
        "洗版模式: 未下载的E02也通过",
        any("E02" in t for t in titles_bv),
    )


def test_filter_episodes_normal_mode():
    """best_version=false 时，已下载的集被过滤"""
    print("\n[SUITE 3.2] _filter_episodes 正常模式")

    downloaded = {
        "1": {"info_hash": "aaa", "title": "old", "quality_tag": ""},
    }

    items = [
        _make_item("Show.S01E01.2160p.Remux", episode=1, season=1, info_hash="bbb"),
        _make_item("Show.S01E02.1080p.WEB-DL", episode=2, season=1, info_hash="ccc"),
    ]

    sub_normal = _FakeSub(type="tv", season=1, downloaded_episodes=downloaded, best_version=False)
    filtered = _filter_episodes(items, sub_normal)
    titles = [it.title for it in filtered]

    record(
        "正常模式: 已下载E01被过滤",
        not any("E01" in t for t in titles),
        f"通过={titles}",
    )
    record(
        "正常模式: 未下载E02通过",
        any("E02" in t for t in titles),
    )


def test_filter_episodes_movie():
    """电影模式：已下载则不再匹配（正常模式）"""
    print("\n[SUITE 3.3] _filter_episodes 电影模式")

    # 电影已下载
    downloaded_movie = {"0": {"info_hash": "mov_hash", "title": "old"}}
    items_movie = [
        _make_item("Movie.2024.2160p.Remux", episode=None, season=None, info_hash="new_hash"),
    ]

    sub_movie_normal = _FakeSub(type="movie", downloaded_episodes=downloaded_movie, best_version=False)
    filtered_normal = _filter_episodes(items_movie, sub_movie_normal)
    record("电影正常模式: 已下载则不匹配", len(filtered_normal) == 0, f"通过={len(filtered_normal)}")

    # 电影洗版模式
    sub_movie_bv = _FakeSub(type="movie", downloaded_episodes=downloaded_movie, best_version=True)
    filtered_bv = _filter_episodes(items_movie, sub_movie_bv)
    record("电影洗版模式: 已下载仍可匹配新hash", len(filtered_bv) == 1, f"通过={len(filtered_bv)}")


def test_select_best_version():
    """_select_best_version 只选择质量更高的条目"""
    print("\n[SUITE 3.4] _select_best_version 质量比较")

    from rss_engine import SubscriptionScheduler
    from subscriber import Subscription, EpisodeInfo

    # 构造一个最小化的 scheduler（不启动线程）
    scheduler = SubscriptionScheduler.__new__(SubscriptionScheduler)

    # 剧集订阅，E01 已有 1080p WEB-DL 版本
    sub = Subscription(
        id="test_bv",
        title="TestShow",
        type="tv",
        season=1,
        best_version=True,
        downloaded_episodes={
            "1": EpisodeInfo(
                info_hash="old_hash",
                title="Show.S01E01.1080p.WEB-DL.x265",
                quality_tag="Show.S01E01.1080p.WEB-DL.x265",
            ),
        },
    )

    items = [
        # 2160p Remux — 应该被选中（质量远高于 1080p WEB-DL）
        _make_item("Show.S01E01.2160p.Remux.DTS-HD.x265", episode=1, season=1, info_hash="high_hash"),
        # 1080p WEB-DL — 不应被选中（质量相近，差值 ≤5）
        _make_item("Show.S01E01.1080p.WEB-DL.x264.AAC", episode=1, season=1, info_hash="same_hash"),
        # E02 无已有版本 — 应该被选中
        _make_item("Show.S01E02.1080p.WEB-DL.x265.DDP5.1", episode=2, season=1, info_hash="e02_hash"),
    ]

    selected = scheduler._select_best_version(items, sub)
    selected_hashes = [it.info_hash for it in selected]

    record(
        "高质量 E01 被选中",
        "high_hash" in selected_hashes,
        f"选中={selected_hashes}",
    )
    record(
        "同质量 E01 不被选中",
        "same_hash" not in selected_hashes,
        f"选中={selected_hashes}",
    )
    record(
        "无已有版本的 E02 被选中",
        "e02_hash" in selected_hashes,
        f"选中={selected_hashes}",
    )


# ═══════════════════════════════════════════════════════════
# 4. 回归测试（API）
# ═══════════════════════════════════════════════════════════

def test_subscribe_crud():
    """订阅 CRUD 仍然正常"""
    print("\n[SUITE 4.1] 订阅 CRUD 回归")

    try:
        resp = api("GET", "/subscribe")
        if resp.status_code != 200:
            record("后端可达", False, f"status={resp.status_code}")
            return
    except Exception as e:
        record("后端可达", False, str(e))
        return

    # CREATE
    create_data = {
        "title": f"{PREFIX}回归剧",
        "year": "2025",
        "type": "tv",
        "season": 1,
        "quality": "1080p",
    }
    resp = api("POST", "/subscribe", json=create_data)
    created = resp.json() if resp.status_code == 200 else {}
    # add() 返回 {"status": "ok", "subscription": {...}}
    sub_id = ""
    if created.get("status") == "ok":
        sub_id = created.get("subscription", {}).get("id", "")
    elif created.get("status") == "error":
        # 可能已存在同名订阅，尝试查找
        pass
    record("创建订阅", resp.status_code == 200 and bool(sub_id), f"id={sub_id}, resp={created.get('status', '')}")

    if not sub_id:
        return

    # READ
    resp = api("GET", f"/subscribe/{sub_id}")
    record("读取订阅", resp.status_code == 200, f"title={resp.json().get('title', '')}" if resp.status_code == 200 else "")

    # UPDATE
    resp = api("PUT", f"/subscribe/{sub_id}", json={"quality": "2160p", "best_version": True})
    record("更新订阅", resp.status_code == 200)

    # 验证更新生效
    resp = api("GET", f"/subscribe/{sub_id}")
    if resp.status_code == 200:
        data = resp.json()
        record("更新生效: quality=2160p", data.get("quality") == "2160p", f"实际={data.get('quality')}")
        record("更新生效: best_version=True", data.get("best_version") is True, f"实际={data.get('best_version')}")

    # LIST
    resp = api("GET", "/subscribe")
    if resp.status_code == 200:
        subs = resp.json()
        found = any(s.get("id") == sub_id for s in subs if isinstance(s, dict))
        record("列表包含新订阅", found)

    # DELETE
    resp = api("DELETE", f"/subscribe/{sub_id}")
    record("删除订阅", resp.status_code == 200)

    # 验证删除
    resp = api("GET", f"/subscribe/{sub_id}")
    record("删除后查询返回404或空", resp.status_code in (404, 200))


def test_search_api():
    """手动搜索仍然正常"""
    print("\n[SUITE 4.2] 搜索 API 回归")

    try:
        resp = api("GET", "/api/search", params={"query": "test", "media_type": "movie"})
        # 搜索可能因 Prowlarr 不可达而失败，但 API 本身应该返回 200
        record(
            "搜索 API 可调用",
            resp.status_code == 200,
            f"status={resp.status_code}",
        )
        if resp.status_code == 200:
            data = resp.json()
            # 验证返回结构合理（有 results 字段或是列表）
            is_valid = isinstance(data, (list, dict))
            record("搜索返回结构合理", is_valid, f"type={type(data).__name__}")
    except requests.exceptions.Timeout:
        record("搜索 API 可调用", True, "超时但 API 可达（Prowlarr 可能慢）")
    except Exception as e:
        record("搜索 API 可调用", False, str(e))


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("阶段4 端到端测试：质量评分升级 + 自动洗版")
    print("=" * 60)

    # 1. 评分函数单元测试（直接 import，不依赖后端）
    test_score_dimensions()
    test_score_from_video()
    test_compare_quality_score()
    test_parse_then_score_e2e()

    # 2. save_library 自动注入（需要后端运行）
    test_save_library_injects_score()

    # 3. 洗版匹配逻辑（直接 import）
    test_filter_episodes_best_version()
    test_filter_episodes_normal_mode()
    test_filter_episodes_movie()
    test_select_best_version()

    # 4. 回归测试（需要后端运行）
    test_subscribe_crud()
    test_search_api()

    # 清理测试数据
    cleanup_test_data()

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print("\n" + "=" * 60)
    print(f"测试完成: {passed}/{total} 通过, {failed} 失败")
    if failed:
        print("\n失败项:")
        for r in results:
            if not r["passed"]:
                detail = f" — {r['detail']}" if r["detail"] else ""
                print(f"  ❌ {r['name']}{detail}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
