"""验证 keyframe-time 端点返回的落点，与转码实际使用的 output seek 落点一致。

背景：转码用 output seek（-ss 在 -i 之后）保证音画同步。
字幕 offset 必须等于**转码流的真实起点**，否则字幕整体偏移。
keyframe-time 端点若用 input seek 探测，两者落点可能不同，offset 就是错的。
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _load():
    init_dir = os.path.join(_BACKEND, "plugins", "feature-player")
    if init_dir not in sys.path:
        sys.path.insert(0, init_dir)
    spec = importlib.util.spec_from_file_location(
        "pb_seek_under_test", os.path.join(init_dir, "playback_routes.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pb = _load()
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="需要 ffmpeg/ffprobe")


@pytest.fixture
def mkv_gop5(tmp_path):
    """30 秒视频，固定 5 秒 GOP → 关键帧在 0/5/10/15/20/25s"""
    out = tmp_path / "gop5.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=30:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-g", "50", "-keyint_min", "50", "-sc_threshold", "0",
        "-c:a", "aac",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")
    return str(out)


def _media_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60,
    )
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def _transcode_first_pts_absolute(path, start):
    """测 output seek 转码流的真实起点（原始绝对时间）。

    不能用 -copyts 探测：它和 output seek 的 -ss 交互行为不可靠
    （实测 -ss 23 -copyts 会得到 2.0 这种明显错误的值）。

    改用时长反推：output seek 输出的是 [落点, 文件尾]，
    所以 落点 = 总时长 - 输出时长。
    """
    total = _media_duration(path)
    if total <= 0:
        return None
    out = os.path.join(tempfile.gettempdir(), f"osk_{os.getpid()}.mp4")
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-probesize", "5000000", "-analyzeduration", "3000000",
        "-i", path,
        "-ss", str(start),          # output seek，与线上一致
        "-map", "0:v:0",
        "-c:v", "copy",
        "-f", "mp4", out,           # 普通 mp4，时长信息完整
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=300)
    if r.returncode != 0 or not os.path.isfile(out):
        return None
    produced = _media_duration(out)
    os.remove(out)
    if produced <= 0:
        return None
    return total - produced


@requires_ffmpeg
@pytest.mark.parametrize("seek", [7.0, 12.0, 23.0])
def test_keyframe_endpoint_matches_transcode_landing(mkv_gop5, monkeypatch, seek):
    """端点返回值必须等于转码流的真实起点，误差 < 0.15s。

    这是字幕对齐的唯一依据：前端拿这个值当 seekOffset。
    """
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    endpoint = pb.get_keyframe_time(path=mkv_gop5, time=seek)["actual_start"]
    real = _transcode_first_pts_absolute(mkv_gop5, seek)
    assert real is not None, "无法测出转码真实落点"
    assert abs(endpoint - real) < 0.15, (
        f"seek={seek}: 端点返回 {endpoint:.3f}s 但转码实际从 {real:.3f}s 开始，"
        f"差 {abs(endpoint - real):.3f}s → 字幕会偏这么多"
    )


@requires_ffmpeg
def test_transcode_keeps_output_seek(mkv_gop5):
    """-ss 必须在 -i 之后（output seek）。

    input seek 快但破坏音画同步，commit 011ffdf 专门改成 output seek 修过这个问题。
    """
    src = open(
        os.path.join(_BACKEND, "plugins", "feature-player", "playback_routes.py"),
        encoding="utf-8",
    ).read()
    start = src.index("def transcode_file(")
    end = src.index('@router.get("/playback/keyframe-time")')
    body = src[start:end]

    i_pos = body.index('"-i", path')
    ss_pos = body.index('"-ss"', i_pos - 400)  # 从 -i 附近往后找实际的 -ss 参数
    # 取 -i 之后出现的第一个 -ss
    ss_after = body.index('"-ss"', i_pos)
    assert ss_after > i_pos, "-ss 必须在 -i 之后，input seek 会破坏音画同步"


@requires_ffmpeg
def test_audio_video_start_aligned_under_output_seek(mkv_gop5):
    """output seek 下音视频起始时间戳应对齐（差 < 0.2s）"""
    out = os.path.join(tempfile.gettempdir(), f"av_{os.getpid()}.mp4")
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-probesize", "5000000", "-analyzeduration", "3000000",
        "-i", mkv_gop5, "-ss", "12.0",
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "aac", "-ac", "2",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-frames:v", "30",
        "-f", "mp4", out,
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=300)
    if r.returncode != 0:
        pytest.skip("转码失败")
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_packets",
         "-show_entries", "packet=codec_type,pts_time", out],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60,
        encoding="utf-8",
    )
    os.remove(out)
    packets = json.loads(p.stdout).get("packets", [])
    v = [float(x["pts_time"]) for x in packets if x.get("codec_type") == "video"]
    a = [float(x["pts_time"]) for x in packets if x.get("codec_type") == "audio"]
    assert v and a, "缺少音频或视频包"
    assert abs(v[0] - a[0]) < 0.2, f"音视频起始差 {abs(v[0]-a[0]):.3f}s 过大"
