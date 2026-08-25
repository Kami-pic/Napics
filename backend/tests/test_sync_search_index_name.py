"""/sync 必须把新增视频的检索名一起落盘。

原实现顺序是「落盘 → 填名 → 只有影子名被填过才二次落盘」，
于是"有检索名、无影子名"（没有 NFO 的普通文件）的新增视频，
检索名算出来了却只活在内存里，用户看到的仍是没有名字的条目，
要等目录树自愈那条路径才补上。
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


def _consume(response) -> list:
    """把 StreamingResponse 的 SSE 事件收成 dict 列表。

    starlette 会把同步 generator 包成 async_generator，所以只能异步消费。
    """
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
def sync_env(tmp_path, monkeypatch):
    """临时数据目录 + 临时媒体目录，里面放一个真实的假视频文件"""
    data_dir = tmp_path / "data"
    media_dir = tmp_path / "media" / "钢铁侠 Iron Man (2008)"
    data_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)

    video = media_dir / "钢铁侠 Iron Man (2008).mkv"
    video.write_bytes(b"\x00" * 2048)

    monkeypatch.setenv("NAPICS_DATA_DIR", str(data_dir))
    mgr = config_manager.ConfigManager()
    # 直接改内存配置，不去动 NAPICS_DATA_DIR 下的 config.json 文件
    mgr._config.scan_paths = [str(tmp_path / "media")]
    mgr._config.media_libraries = []
    mgr._config.exclude_dirs = ""
    mgr.save_library([])

    monkeypatch.setattr(library_routes, "config_m", mgr)
    # 本机 / CI 都没有 ffmpeg，走 scanner 的兜底元数据
    monkeypatch.setattr(library_routes.scanner, "get_video_metadata", scanner._fallback_info)
    # 无 NFO：影子名填不上，这正是暴露该 bug 的条件
    monkeypatch.setattr(
        library_routes.shadow_m, "_read_nfo_originaltitle", lambda fp: None,
    )
    monkeypatch.setattr(library_routes, "_tmdb_client", lambda: None)

    return mgr, str(video)


def test_sync_persists_search_index_name_without_shadow_name(sync_env):
    mgr, video_path = sync_env

    events = _consume(library_routes.quick_sync())

    assert any(e.get("type") == "done" for e in events), f"同步没跑完: {events}"

    saved = mgr.load_library()
    assert len(saved) == 1, f"新增视频没入库: {saved}"
    item = saved[0]
    assert item["file_path"] == video_path
    # 检索名必须已经在盘上，不能只活在内存里等目录树自愈
    assert item.get("clean_name"), f"检索名没落盘: {item}"
    # 前提确认：这条确实没有影子名，否则这个用例就测不到目标场景了
    assert not item.get("shadow_name"), "夹具失效：这条不该有影子名"


def test_sync_writes_library_once(sync_env, monkeypatch):
    """两次落盘已合并成一次：整库序列化对大媒体库不便宜。

    注意这条在修复前也是绿的（旧代码在 shadow_filled == 0 时本来就只写一次），
    它的作用是防止以后又把二次落盘加回来，不是本次 bug 的回归证据。
    """
    mgr, _ = sync_env
    writes = []
    original = mgr.save_library
    monkeypatch.setattr(
        mgr, "save_library", lambda data: (writes.append(len(data)), original(data))[1],
    )

    _consume(library_routes.quick_sync())

    assert len(writes) == 1, f"落盘次数应为 1，实际 {len(writes)}"


def test_sync_keeps_entries_added_by_others_while_scanning(sync_env, monkeypatch):
    """同步期间别处写进来的条目不能被抹掉。

    下载归位后的局部刷新就是这个场景：文件在同步开始之后才出现，
    既不在库快照里、也不在文件系统遍历结果里。
    """
    mgr, video_path = sync_env
    concurrent_entry = {"file_path": "/other/新片.mkv", "file_name": "新片.mkv", "height": 1080}

    real_scan_folder = None  # 占位，保持结构清晰
    original_load = mgr.load_library
    injected = {"done": False}

    def load_with_injection():
        data = original_load()
        # 第二次读库（落盘阶段的锁内重读）时，模拟别处刚写入了一条
        if injected["done"]:
            return data + [concurrent_entry]
        injected["done"] = True
        return data

    monkeypatch.setattr(mgr, "load_library", load_with_injection)

    _consume(library_routes.quick_sync())

    monkeypatch.setattr(mgr, "load_library", original_load)
    paths = {v["file_path"] for v in mgr.load_library()}
    assert video_path in paths
    assert "/other/新片.mkv" in paths, "同步把并发写入的条目删掉了"


def test_sync_does_not_resurrect_entries_deleted_elsewhere(sync_env, monkeypatch):
    """同步期间用户删掉的条目不能被写回来。

    current_lib 是从同步开始时的快照派生的。如果文件系统遍历发生在删除之前，
    该路径既在 fs_files 里、也不在 removed 里，会被当成"还存在"写回去 ——
    用户看到刚删掉的东西自己回来了。
    """
    mgr, video_path = sync_env
    # 库里先有这条（同步开始时的快照会读到它）
    mgr.save_library([{"file_path": video_path, "file_name": "钢铁侠 Iron Man (2008).mkv", "height": 1080}])

    original_load = mgr.load_library
    calls = {"n": 0}

    def load_with_concurrent_delete():
        calls["n"] += 1
        data = original_load()
        # 第二次读库（落盘阶段的锁内重读）时，模拟别处已经把这条删掉了
        if calls["n"] >= 2:
            return [v for v in data if v.get("file_path") != video_path]
        return data

    monkeypatch.setattr(mgr, "load_library", load_with_concurrent_delete)

    _consume(library_routes.quick_sync())

    monkeypatch.setattr(mgr, "load_library", original_load)
    paths = {v["file_path"] for v in mgr.load_library()}
    assert video_path not in paths, "同步把别处删掉的条目复活了"


def test_sync_keeps_fields_written_by_others(sync_env, monkeypatch):
    """同步期间刮削写进已有条目的字段不能被回滚。

    同步不修改已有条目的任何字段，所以保留下来的条目必须用锁内重读到的版本，
    而不是几分钟前的快照对象。
    """
    mgr, video_path = sync_env
    mgr.save_library([{"file_path": video_path, "file_name": "钢铁侠 Iron Man (2008).mkv", "height": 1080}])

    original_load = mgr.load_library
    calls = {"n": 0}

    def load_with_concurrent_scrape():
        calls["n"] += 1
        data = original_load()
        if calls["n"] >= 2:
            # 模拟刮削在同步期间给这条写了标准名
            for item in data:
                if item.get("file_path") == video_path:
                    item["shadow_name"] = "Iron Man (2008)"
                    item["shadow_name_source"] = "tmdb"
            return data
        return data

    monkeypatch.setattr(mgr, "load_library", load_with_concurrent_scrape)

    _consume(library_routes.quick_sync())

    monkeypatch.setattr(mgr, "load_library", original_load)
    saved = {v["file_path"]: v for v in mgr.load_library()}
    assert saved[video_path].get("shadow_name") == "Iron Man (2008)", "刮削结果被同步回滚了"
