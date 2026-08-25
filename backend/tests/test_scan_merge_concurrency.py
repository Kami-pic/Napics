"""/scan 落盘阶段的合并规则。

扫描要跑几分钟 ffprobe，落盘时必须基于锁内重新读到的库做合并。原实现用的是
扫描开始时的 existing 快照，于是这期间别处写进库的东西全部被抹掉。

「复用」分支的条目本身就是那份旧快照对象，所以合并不能整份写回，
只能以最新条目为底、覆盖扫描真正负责的字段（`SCAN_MANAGED_NAME_FIELDS`）。
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_manager
import scanner
from routes import library as library_routes
from scan_name_filler import SCAN_MANAGED_NAME_FIELDS


def _consume(response) -> list:
    async def run():
        events = []
        async for chunk in response.body_iterator:
            text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")
            for part in text.split("\n\n"):
                part = part.strip()
                if part.startswith("data: "):
                    events.append(json.loads(part[len("data: "):]))
        return events

    return asyncio.run(run())


@pytest.fixture
def scan_env(tmp_path, monkeypatch):
    """临时数据目录 + 一个真实的假视频文件"""
    data_dir = tmp_path / "data"
    media_root = tmp_path / "media"
    movie_dir = media_root / "钢铁侠 Iron Man (2008)"
    data_dir.mkdir(parents=True)
    movie_dir.mkdir(parents=True)
    video = movie_dir / "钢铁侠 Iron Man (2008).mkv"
    video.write_bytes(b"\x00" * 4096)

    monkeypatch.setenv("NAPICS_DATA_DIR", str(data_dir))
    mgr = config_manager.ConfigManager()
    mgr._config.scan_paths = [str(media_root)]
    mgr._config.media_libraries = []
    mgr._config.exclude_dirs = ""
    mgr.save_library([])

    monkeypatch.setattr(library_routes, "config_m", mgr)
    monkeypatch.setattr(library_routes.scanner, "get_video_metadata", scanner._fallback_info)

    return mgr, str(media_root), str(video)


def _existing_entry(video_path: str, **extra) -> dict:
    """一条"已扫描过"的记录。size_gb 与真实文件一致，扫描会走复用分支。"""
    size_gb = round(os.path.getsize(video_path) / (1024 ** 3), 2)
    entry = {
        "file_path": video_path,
        "file_name": os.path.basename(video_path),
        "height": 1080,
        "size_gb": size_gb,
        "folder_name": "钢铁侠 Iron Man (2008)",
    }
    entry.update(extra)
    return entry


def test_scan_keeps_entries_added_elsewhere(scan_env, tmp_path):
    """扫描期间下载归位入库的条目（在扫描路径之外、但属于已配置路径）不能被抹掉。

    注意"不属于任何已配置路径"的孤立条目本来就该被清理，那是设计意图，
    所以这里把并发新增放在第二个已配置路径下。
    """
    mgr, media_root, video_path = scan_env
    other_root = tmp_path / "media2"
    other_root.mkdir()
    mgr._config.scan_paths = [media_root, str(other_root)]
    other_path = str(other_root / "新片.mkv")
    mgr.save_library([{"file_path": other_path, "file_name": "新片.mkv", "height": 1080}])

    assert other_path in {v["file_path"] for v in mgr.load_library()}, "夹具失效：并发条目没写进库"
    assert str(other_root) in mgr.config.scan_paths, "夹具失效：第二个扫描路径没生效"

    _consume(asyncio.run(library_routes.scan_path(media_root)))

    paths = {v["file_path"] for v in mgr.load_library()}
    assert video_path in paths
    assert other_path in paths, "扫描把扫描路径外的条目删掉了"


def test_scan_does_not_rollback_fields_written_elsewhere(scan_env, monkeypatch):
    """复用分支不能把期间刮削写进这条的字段回滚掉。

    复用条目是扫描开始时的快照对象，整份写回等于用几分钟前的内容覆盖最新库。
    """
    mgr, media_root, video_path = scan_env
    mgr.save_library([_existing_entry(video_path)])

    original_load = mgr.load_library
    calls = {"n": 0}

    def load_with_concurrent_scrape():
        calls["n"] += 1
        data = original_load()
        # 第二次读库 = 落盘阶段的锁内重读，此时刮削已经写了标准名
        if calls["n"] >= 2:
            for item in data:
                if item.get("file_path") == video_path:
                    item["shadow_name"] = "Iron Man (2008)"
                    item["shadow_name_source"] = "tmdb"
                    item["poster_downloaded"] = True
            return data
        return data

    monkeypatch.setattr(mgr, "load_library", load_with_concurrent_scrape)

    _consume(asyncio.run(library_routes.scan_path(media_root)))

    monkeypatch.setattr(mgr, "load_library", original_load)
    saved = {v["file_path"]: v for v in mgr.load_library()}
    entry = saved[video_path]
    # 扫描不碰的字段必须留着
    assert entry.get("poster_downloaded") is True, "扫描把期间写入的字段回滚了"
    # 标准名归扫描管，但 tmdb 来源优先级高于 parsed，不该被降级覆盖
    assert entry.get("shadow_name") == "Iron Man (2008)"


def test_scan_managed_fields_cover_what_filler_writes():
    """SCAN_MANAGED_NAME_FIELDS 必须盖住填名逻辑实际写入的字段。

    这个白名单是合并规则的依据。填名逻辑加了新字段而这里没同步，
    新字段在合并时会被最新库的旧值盖掉，表现成"重扫没有生效"。
    """
    from clean_name_system import CleanNameResult, safe_update_clean_name
    from shadow_name_manager import apply_auto_fill

    probe: dict = {"file_path": "/x/a.mkv", "file_name": "a.mkv"}
    safe_update_clean_name(probe, CleanNameResult(
        display="片名 Title (2020)", cn="片名", en="Title",
        original="原名", year="2020", source="parsed",
    ))
    apply_auto_fill(probe, "Title (2020)", source="parsed")

    written = set(probe) - {"file_path", "file_name"}
    missing = written - SCAN_MANAGED_NAME_FIELDS
    assert not missing, f"填名写了但白名单没覆盖的字段: {sorted(missing)}"


def test_sibling_directory_with_shared_prefix_is_not_treated_as_child():
    """`D:\\影视2` 不是 `D:\\影视` 的子目录。

    直接用 `startswith` 判断"这条属于哪个路径"时，两个名字有共同前缀的
    平级目录会互相误判：扫描一个库会把另一个库的条目一起当成自己的、
    连带被覆盖或清理掉。
    """
    from shared import is_under_path

    assert is_under_path(r"D:\影视\电影\a.mkv", r"D:\影视")
    assert is_under_path(r"D:\影视\电影\a.mkv", "D:\\影视\\")     # 末尾分隔符不影响
    assert is_under_path(r"D:\影视", r"D:\影视")                  # 自己算在内
    assert is_under_path("/vol1/media/a.mkv", "/vol1/media")      # POSIX 分隔符

    assert not is_under_path(r"D:\影视2\电影\a.mkv", r"D:\影视")
    assert not is_under_path(r"D:\影视备份\a.mkv", r"D:\影视")
    assert not is_under_path("/vol1/media2/a.mkv", "/vol1/media")
    assert not is_under_path("", r"D:\影视")
    assert not is_under_path(r"D:\影视\a.mkv", "")
