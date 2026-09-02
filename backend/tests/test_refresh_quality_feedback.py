"""/library/refresh-quality 的失败反馈与落盘条件。

这个端点原来不管成功失败都返回 {"status": "ok"}，前端 `catch {}`，于是三种
失败在界面上完全一样 —— 都是"点了检测质量没反应，编码还是空的"。用户只能
靠"把文件挪一下再重扫"来碰运气（挪动会触发重扫，走的是另一条代码路径）。
"""
import os
from types import SimpleNamespace

import pytest

import scanner
from routes import library_crud
from test_support.fake_library_store import LibraryMutationContract


class FakeConfigManager(LibraryMutationContract):
    def __init__(self, library):
        self.library = library
        self.saved_library = None

    def load_library(self):
        return self.library

    def save_library(self, data):
        self.saved_library = data


def _probed_info(file_path: str, **overrides):
    """一条 ffprobe 成功的结果。"""
    base = dict(
        file_path=file_path, file_name=os.path.basename(file_path), folder_name="",
        size_gb=4.59, duration_min=104.0, resolution="1080p", height=1080, width=1920,
        bitrate_kbps=6000.0, codec="hevc", container="mkv", audio_codec="eac3",
        audio_channels=6, subtitle_count=0, hdr_type="HDR10",
        has_poster=False, is_low_res=False,
    )
    base.update(overrides)
    return scanner.VideoInfo(**base)


@pytest.fixture
def existing_video(tmp_path):
    video = tmp_path / "某片.mkv"
    video.write_text("x", encoding="utf-8")
    return str(video)


def test_missing_file_is_reported(monkeypatch, tmp_path):
    """库里记的路径已经不在了 —— 原来是 os.path.exists 后一个静默 continue。

    「移动文件后就好了」说的就是这种：挪动触发重扫，用新路径重新入库。
    """
    gone = str(tmp_path / "已经不在了.mkv")
    fake = FakeConfigManager([{"file_path": gone, "quality_score": 10}])
    monkeypatch.setattr(library_crud, "config_m", fake)

    result = library_crud.refresh_quality_score([gone])

    assert result["failed"] == [{"path": gone, "reason": "missing"}]
    assert result["probed"] == 0
    # 分数仍会按库里现有字段重算（既有行为），但不能凭空写出元数据
    assert "codec" not in fake.library[0]


def test_probe_failure_is_reported(monkeypatch, existing_video):
    """ffprobe 读不了这个文件（损坏 / 后缀与实际格式不符）。

    height == 0 是 _fallback_info 的标记值，这种结果不能写进库（会把已有的
    分辨率覆盖成 0），但必须让用户知道原因。
    """
    fake = FakeConfigManager([{"file_path": existing_video, "quality_score": 10,
                               "height": 1080, "codec": "h264"}])
    monkeypatch.setattr(library_crud, "config_m", fake)
    monkeypatch.setattr(
        library_crud.scanner, "get_video_metadata",
        lambda fp: _probed_info(fp, height=0, width=0, codec="unknown", resolution="未知"),
    )

    result = library_crud.refresh_quality_score([existing_video])

    assert result["failed"] == [{"path": existing_video, "reason": "probe_failed"}]
    # 原有的 height / codec 不能被 fallback 的 0 / unknown 覆盖
    assert fake.library[0]["height"] == 1080
    assert fake.library[0]["codec"] == "h264"


def test_probe_exception_is_reported(monkeypatch, existing_video):
    fake = FakeConfigManager([{"file_path": existing_video, "quality_score": 10}])
    monkeypatch.setattr(library_crud, "config_m", fake)

    def _boom(fp):
        raise OSError("SMB 断了")

    monkeypatch.setattr(library_crud.scanner, "get_video_metadata", _boom)

    result = library_crud.refresh_quality_score([existing_video])

    assert result["failed"] == [{"path": existing_video, "reason": "probe_failed"}]


def test_path_not_in_library_is_reported(monkeypatch, existing_video):
    fake = FakeConfigManager([{"file_path": "另一条完全不同的路径.mkv"}])
    monkeypatch.setattr(library_crud, "config_m", fake)
    monkeypatch.setattr(library_crud.scanner, "get_video_metadata", _probed_info)

    result = library_crud.refresh_quality_score([existing_video])

    assert result["failed"] == [{"path": existing_video, "reason": "not_in_library"}]


def test_metadata_persists_even_when_score_is_unchanged(monkeypatch, existing_video):
    """探测成功但质量分恰好不变时，元数据也必须落盘。

    落盘条件原来只看 quality_score 变没变 —— 而质量分本来就能从文件名标签
    （1080p / HDR / x265）解析出来，探测前后一样是常见情况。于是刚探到的
    codec / height / container 被整批丢弃，用户点了没反应。
    """
    entry = {
        "file_path": existing_video, "file_name": "某片.mkv",
        "height": 0, "width": 0, "resolution": "未知",
        "codec": "unknown", "audio_codec": "unknown", "container": "mkv",
        "duration_min": 0.0, "quality_score": 65,
    }
    fake = FakeConfigManager([entry])
    monkeypatch.setattr(library_crud, "config_m", fake)
    monkeypatch.setattr(library_crud.scanner, "get_video_metadata", _probed_info)
    # 分数算出来和原来一样，模拟"探测前后同分"。
    # refresh_quality_score 内部是 `from quality_parser import ...`，每次调用都重新
    # 取一次，所以打模块属性就够。
    import quality_parser

    monkeypatch.setattr(quality_parser, "compute_quality_score_from_video", lambda v: 65)

    result = library_crud.refresh_quality_score([existing_video])

    assert result["failed"] == []
    assert result["probed"] == 1
    assert result["updated"] == 0, "分数没变，updated 就该是 0"
    assert fake.saved_library is not None, "元数据变了就必须落盘"
    assert entry["codec"] == "hevc"
    assert entry["height"] == 1080
    assert entry["resolution"] == "1080p"


def test_successful_probe_reports_no_failure(monkeypatch, existing_video):
    fake = FakeConfigManager([{"file_path": existing_video, "quality_score": 0}])
    monkeypatch.setattr(library_crud, "config_m", fake)
    monkeypatch.setattr(library_crud.scanner, "get_video_metadata", _probed_info)

    result = library_crud.refresh_quality_score([existing_video])

    assert result["failed"] == []
    assert result["probed"] == 1
    assert fake.saved_library is not None


def test_size_is_refreshed_even_when_probe_fails(monkeypatch, tmp_path):
    """文件大小不依赖 ffprobe —— 探测失败也要刷新对。

    大小是 os.stat 一次调用就能拿到的事实。原来它跟着 ffprobe 的 format.size 走，
    探测一失败整条元数据被丢弃，连大小都不更新。
    """
    video = tmp_path / "某片.mkv"
    video.write_bytes(b"x" * 2048)
    path = str(video)

    entry = {"file_path": path, "size_gb": 99.0, "height": 1080, "codec": "h264",
             "quality_score": 10}
    fake = FakeConfigManager([entry])
    monkeypatch.setattr(library_crud, "config_m", fake)
    # ffprobe 读不出来
    monkeypatch.setattr(
        library_crud.scanner, "get_video_metadata",
        lambda fp: _probed_info(fp, height=0, width=0, codec="unknown", resolution="未知"),
    )

    result = library_crud.refresh_quality_score([path])

    assert result["failed"] == [{"path": path, "reason": "probe_failed"}]
    # 大小按实际文件刷新了（2048 字节，四舍五入到 0.0 GB）
    assert entry["size_gb"] == round(2048 / (1024 ** 3), 2)
    # 而分辨率/编码没有被 fallback 的 0 / unknown 覆盖
    assert entry["height"] == 1080
    assert entry["codec"] == "h264"
    assert fake.saved_library is not None, "大小变了就该落盘"


def test_scanner_takes_size_from_filesystem_not_ffprobe():
    """扫描器的 size_gb 必须来自 os.path.getsize，不能是 ffprobe 的 format.size。"""
    import inspect

    import scanner

    src = inspect.getsource(scanner.get_video_metadata)
    assert "os.path.getsize" in src, "大小应该问操作系统"
    # ffprobe 的 format.size 只能作为拿不到时的退路
    idx_probe = src.find('format_info.get("size"')
    idx_os = src.find("os.path.getsize")
    assert idx_os < idx_probe, "os.path.getsize 应该是首选，ffprobe 的值只是退路"
