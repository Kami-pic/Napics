"""扫描器字段契约测试。

存量 media_library.json 用的是 codec / duration_min / container，
任何一处写成 video_codec / duration 都会让前端显示为空 —— 这个坑踩过一次：
refresh-quality 端点改了名，导致"点过检测质量的条目才显示编码"。
"""
import os
import shutil
import subprocess
import sys
import time

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


def _make_sample(out, extra_args=None):
    """造测试样本。ffmpeg 退出后文件可能还没完全可读，需要等落盘。"""
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
    ] + (extra_args or []) + [str(out)]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")

    # 等到 ffprobe 能真正读出视频流为止：刚写完就 probe 会间歇性拿到
    # unknown（文件尚未完全可读），导致测试随机失败
    for _ in range(20):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30,
        )
        if probe.returncode == 0 and (probe.stdout or "").strip():
            return str(out)
        time.sleep(0.1)
    pytest.skip("样本写出后 ffprobe 仍读不到视频流")


@pytest.fixture
def sample_mkv(tmp_path):
    return _make_sample(tmp_path / "probe.mkv")


@requires_ffmpeg
def test_get_video_metadata_fills_codec_and_container(sample_mkv):
    info = scanner.get_video_metadata(sample_mkv)
    assert info is not None
    assert info.codec == "h264", f"视频编码应为 h264，实际 {info.codec}"
    assert info.audio_codec == "aac"
    assert info.duration_min > 0
    # 容器要是用户认知里的名字（mkv），不是 ffprobe 的 format_name（matroska）
    assert info.container == "mkv", f"应为 mkv，实际 {info.container}"


@requires_ffmpeg
def test_container_is_user_facing_extension(tmp_path):
    """mp4 的 container 必须是 mp4，不能是 ffprobe format_name 里的 mov"""
    sample = _make_sample(tmp_path / "probe.mp4")
    info = scanner.get_video_metadata(sample)
    assert info is not None
    assert info.container == "mp4", f"应为 mp4，实际 {info.container}"
    assert "," not in info.container


def test_fallback_info_uses_extension_as_container(tmp_path):
    """ffprobe 失败时容器格式退化为扩展名，不能留空"""
    p = tmp_path / "broken.mkv"
    p.write_bytes(b"not a real video")
    info = scanner._fallback_info(str(p))
    assert info is not None
    assert info.container == "mkv"
    assert info.codec == "unknown"


def test_ffprobe_call_isolates_stdin():
    """ffprobe 调用必须显式 stdin=DEVNULL。

    不指定的话，uvicorn / pytest 下父进程 stdin 已被替换，
    继承句柄抛 OSError 被 except 吞掉走 fallback，整库 codec 变成 unknown。
    这个 bug 表现为"编码格式扫不出来"，且只在特定运行环境下出现，极难排查。
    """
    src = open(os.path.join(_BACKEND, "scanner.py"), encoding="utf-8").read()
    start = src.index("def get_video_metadata(")
    end = src.index("def _fallback_info(")
    body = src[start:end]

    assert "subprocess.run(" in body
    assert "stdin=subprocess.DEVNULL" in body, \
        "ffprobe 调用缺少 stdin=subprocess.DEVNULL"


@requires_ffmpeg
def test_subtitle_counts_split_text_and_graphic(tmp_path):
    """内封字幕要拆成文本/图形两个计数，混合片源才能如实体现"""
    srt = tmp_path / "s.srt"
    srt.write_text("1\n00:00:00,500 --> 00:00:02,000\nhello\n", encoding="utf-8")
    out = tmp_path / "mix.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-i", str(srt),
        "-map", "0:v", "-map", "1:a", "-map", "2:s",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-c:s", "srt",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip("造样本失败")

    info = scanner.get_video_metadata(str(out))
    assert info is not None
    assert info.subtitle_count == 1
    assert info.subtitle_text_count == 1, "srt 应计为文本字幕"
    assert info.subtitle_graphic_count == 0


def test_videoinfo_has_subtitle_split_fields():
    fields = set(scanner.VideoInfo.model_fields.keys())
    assert "subtitle_text_count" in fields
    assert "subtitle_graphic_count" in fields
