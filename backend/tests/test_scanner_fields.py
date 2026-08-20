"""扫描器字段契约测试。

存量 media_library.json 用的是 codec / duration_min / container，
任何一处写成 video_codec / duration 都会让前端显示为空 —— 这个坑踩过一次：
refresh-quality 端点改了名，导致"点过检测质量的条目才显示编码"。
"""
import os
import shutil
import subprocess
import sys

import pytest

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import scanner

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="需要 ffmpeg/ffprobe")


def test_videoinfo_field_names_are_canonical():
    """字段名以存量数据为准，不要改成 video_codec / duration"""
    fields = set(scanner.VideoInfo.model_fields.keys())
    assert "codec" in fields
    assert "duration_min" in fields
    assert "container" in fields, "容器格式字段缺失"
    assert "video_codec" not in fields, "别引入 video_codec，存量数据用的是 codec"
    assert "duration" not in fields, "别引入 duration，存量数据用的是 duration_min"


def test_refresh_quality_writes_canonical_names():
    """refresh-quality 必须写 codec/duration_min，不能写 video_codec/duration"""
    src = open(os.path.join(_BACKEND, "routes", "library_crud.py"), encoding="utf-8").read()
    start = src.index("def refresh_quality_score(")
    end = src.index("@router.post(\"/library/folder-type\")")
    body = src[start:end]

    assert 'v["codec"]' in body, "应写 codec"
    assert 'v["duration_min"]' in body, "应写 duration_min"
    assert 'v["video_codec"]' not in body, "不能写 video_codec，会造成同条记录双字段名"
    assert 'v["duration"]' not in body, "不能写 duration，会造成同条记录双字段名"


@pytest.fixture
def sample_mkv(tmp_path):
    out = tmp_path / "probe.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")
    return str(out)


@requires_ffmpeg
def test_get_video_metadata_fills_codec_and_container(sample_mkv):
    info = scanner.get_video_metadata(sample_mkv)
    assert info is not None
    assert info.codec == "h264", f"视频编码应为 h264，实际 {info.codec}"
    assert info.audio_codec == "aac"
    assert info.container, "容器格式不能为空"
    assert "matroska" in info.container or "mkv" in info.container, \
        f"mkv 的 container 应含 matroska，实际 {info.container}"
    assert info.duration_min > 0


@requires_ffmpeg
def test_container_is_single_value_not_comma_list(tmp_path):
    """ffprobe 的 format_name 常是逗号分隔候选列表，必须只取第一项"""
    out = tmp_path / "probe.mp4"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    if r.returncode != 0:
        pytest.skip("造样本失败")
    info = scanner.get_video_metadata(str(out))
    assert info is not None
    assert "," not in info.container, f"container 不应是列表: {info.container}"


def test_fallback_info_uses_extension_as_container(tmp_path):
    """ffprobe 失败时容器格式退化为扩展名，不能留空"""
    p = tmp_path / "broken.mkv"
    p.write_bytes(b"not a real video")
    info = scanner._fallback_info(str(p))
    assert info is not None
    assert info.container == "mkv"
    assert info.codec == "unknown"
