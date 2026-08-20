"""播放器内嵌字幕提取与分类测试。

覆盖之前完全没有测试的区域：codec 分类、语言归一化、内嵌字幕检测、
提取落盘缓存。带 ffmpeg 的用例会在没有 ffmpeg 时自动跳过。
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _load_playback_module():
    """插件不在包路径里，按文件路径加载"""
    init_dir = os.path.join(_BACKEND, "plugins", "feature-player")
    if init_dir not in sys.path:
        sys.path.insert(0, init_dir)
    path = os.path.join(init_dir, "playback_routes.py")
    spec = importlib.util.spec_from_file_location("playback_routes_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pb = _load_playback_module()

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="需要 ffmpeg/ffprobe")


# ── codec 分类 ──

@pytest.mark.parametrize("codec", ["subrip", "ass", "ssa", "mov_text", "webvtt"])
def test_text_codecs_supported(codec):
    supported, reason = pb._classify_subtitle_codec(codec)
    assert supported is True
    assert reason == ""


@pytest.mark.parametrize("codec", ["hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"])
def test_graphic_codecs_unsupported_with_reason(codec):
    """图形字幕必须被标记为不可用，且给出原因（而不是静默丢弃）"""
    supported, reason = pb._classify_subtitle_codec(codec)
    assert supported is False
    assert "OCR" in reason or "图形" in reason


@pytest.mark.parametrize("codec", ["dvb_teletext", "arib_caption", "eia_608", "eia_708"])
def test_unconvertible_codecs_rejected_early(codec):
    """这些 codec 过去能通过过滤，然后在提取阶段静默 500"""
    supported, reason = pb._classify_subtitle_codec(codec)
    assert supported is False
    assert reason


def test_unknown_codec_is_optimistically_supported():
    """未知 codec 不应误杀，交给提取阶段判定"""
    supported, _ = pb._classify_subtitle_codec("some_future_codec")
    assert supported is True


# ── 语言归一化 ──

@pytest.mark.parametrize("raw,expected", [
    ("chi", "zh"), ("zho", "zh"), ("chs", "zh"), ("cht", "zh"),
    ("cmn", "zh"),          # 普通话，Netflix 片源常见
    ("yue", "zh"),          # 粤语
    ("zh-Hans", "zh"), ("zh-Hant", "zh"), ("zh_TW", "zh"), ("zh-CN", "zh"),
    ("eng", "en"), ("en-US", "en"),
    ("jpn", "ja"), ("kor", "ko"),
    ("fra", "fr"), ("ger", "de"), ("spa", "es"), ("por", "pt"),
])
def test_normalize_lang(raw, expected):
    assert pb._normalize_lang(raw) == expected


def test_normalize_lang_passthrough_and_empty():
    assert pb._normalize_lang("") == ""
    assert pb._normalize_lang(None) == ""
    assert pb._normalize_lang("xyz") == "xyz"   # 未知码原样返回，不猜


# ── 内嵌字幕检测（真实 ffmpeg 造样本） ──

@pytest.fixture
def mkv_with_subs(tmp_path):
    """造一个含 2 条 subrip 字幕轨的 mkv（1 视频 + 1 音频 + 2 字幕）"""
    srt_zh = tmp_path / "zh.srt"
    srt_zh.write_text(
        "1\n00:00:00,500 --> 00:00:02,000\n中文字幕测试\n\n"
        "2\n00:00:02,500 --> 00:00:04,000\n第二句\n",
        encoding="utf-8",
    )
    srt_en = tmp_path / "en.srt"
    srt_en.write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nEnglish subtitle\n\n"
        "2\n00:00:02,500 --> 00:00:04,000\nSecond line\n",
        encoding="utf-8",
    )
    out = tmp_path / "sample.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=5:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-i", str(srt_zh),
        "-i", str(srt_en),
        "-map", "0:v", "-map", "1:a", "-map", "2:s", "-map", "3:s",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-c:s", "srt",
        "-metadata:s:s:0", "language=chi",
        "-metadata:s:s:1", "language=eng",
        str(out),
    ]
    r = subprocess.run(
        cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=120,
    )
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")
    return str(out)


@requires_ffmpeg
def test_detect_embedded_subtitles_returns_both_tracks(mkv_with_subs):
    subs = pb._detect_embedded_subtitles(mkv_with_subs)
    assert len(subs) == 2
    assert all(s["embedded"] is True for s in subs)
    assert all(s["unsupported"] is False for s in subs)
    assert {s["lang"] for s in subs} == {"zh", "en"}
    assert all(s["codec"] == "subrip" for s in subs)


@requires_ffmpeg
def test_detect_embedded_subtitles_url_carries_absolute_stream_index(mkv_with_subs):
    """URL 里的 index 必须是文件内绝对流索引，才能和 ffmpeg -map 0:<n> 对上。

    样本是 1 视频 + 1 音频 + 2 字幕，所以字幕的绝对索引是 2 和 3。
    """
    subs = pb._detect_embedded_subtitles(mkv_with_subs)
    indices = sorted(int(s["url"].rsplit("index=", 1)[1]) for s in subs)
    assert indices == [2, 3]


@requires_ffmpeg
def test_extract_all_text_subtitles_writes_vtt(mkv_with_subs):
    """一次调用应把两条字幕轨都提取落盘，且内容是有效 VTT"""
    fp = pb._video_fingerprint(mkv_with_subs)
    result = pb._extract_all_text_subtitles(mkv_with_subs, fp)
    assert len(result) == 2
    for idx, vtt_path in result.items():
        assert os.path.isfile(vtt_path)
        content = open(vtt_path, encoding="utf-8").read()
        assert content.startswith("WEBVTT")
        assert "-->" in content
    # 清理
    for vtt_path in result.values():
        os.remove(vtt_path)


@requires_ffmpeg
def test_extract_skips_unsupported_tracks(tmp_path, monkeypatch, mkv_with_subs):
    """被标记 unsupported 的轨不应进入提取命令"""
    real_detect = pb._detect_embedded_subtitles

    def fake_detect(path):
        subs = real_detect(path)
        # 把第一条伪装成 PGS
        if subs:
            subs[0] = {**subs[0], "unsupported": True, "codec": "hdmv_pgs_subtitle"}
        return subs

    monkeypatch.setattr(pb, "_detect_embedded_subtitles", fake_detect)
    fp = pb._video_fingerprint(mkv_with_subs) + "_skip"
    result = pb._extract_all_text_subtitles(mkv_with_subs, fp)
    assert len(result) == 1   # 只提取剩下那条文本轨
    for vtt_path in result.values():
        os.remove(vtt_path)


@requires_ffmpeg
def test_external_and_embedded_share_same_field_shape(tmp_path, mkv_with_subs, monkeypatch):
    """外挂与内嵌字幕必须有相同的字段集合。

    曾经只给内嵌字幕加了 unsupported/codec，消费端对外挂字幕取这些键会 KeyError。
    """
    # 在视频同目录放一个外挂 srt，让 list_subtitles 同时返回两类
    video_dir = os.path.dirname(mkv_with_subs)
    external = os.path.join(video_dir, "sample.chs.srt")
    with open(external, "w", encoding="utf-8") as f:
        f.write("1\n00:00:01,000 --> 00:00:02,000\n外挂字幕\n")

    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    result = pb.list_subtitles(path=mkv_with_subs)
    subs = result["subtitles"]

    external_items = [s for s in subs if not s["embedded"]]
    embedded_items = [s for s in subs if s["embedded"]]
    assert external_items, "应检测到外挂字幕"
    assert embedded_items, "应检测到内嵌字幕"

    required = {"name", "format", "codec", "lang", "url",
                "embedded", "unsupported", "unsupported_reason", "forced"}
    for item in subs:
        missing = required - set(item)
        assert not missing, f"字幕项缺字段 {missing}: {item.get('name')}"


@requires_ffmpeg
def test_fingerprint_changes_when_file_changes(tmp_path, mkv_with_subs):
    """指纹要跟大小/mtime 绑定，文件被替换后缓存必须失效"""
    fp1 = pb._video_fingerprint(mkv_with_subs)
    with open(mkv_with_subs, "ab") as f:
        f.write(b"\x00" * 1024)
    fp2 = pb._video_fingerprint(mkv_with_subs)
    assert fp1 != fp2


def test_fingerprint_stable_for_same_file(tmp_path):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"data")
    assert pb._video_fingerprint(str(p)) == pb._video_fingerprint(str(p))


# ── VTT 转换 ──

def test_srt_to_vtt_converts_comma_to_dot():
    srt = "1\n00:00:01,500 --> 00:00:03,200\n测试\n"
    vtt = pb._srt_to_vtt(srt)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.500 --> 00:00:03.200" in vtt
    assert "," not in vtt.split("-->")[0].split("\n")[-1]


def test_ass_to_vtt_strips_style_tags():
    ass = (
        "[Events]\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\pos(100,200)}带样式的字幕\n"
    )
    vtt = pb._ass_to_vtt(ass)
    assert "带样式的字幕" in vtt
    assert "\\pos" not in vtt
    assert "{" not in vtt


# ── 转码 seek 关键帧对齐 ──

@pytest.fixture
def mkv_long_gop(tmp_path):
    """造一个 GOP 为 5 秒的 20 秒视频，关键帧在 0/5/10/15s"""
    out = tmp_path / "gop.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=20:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-g", "50", "-keyint_min", "50", "-sc_threshold", "0",  # 固定 5s GOP
        "-c:a", "aac",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")
    return str(out)


@requires_ffmpeg
def test_keyframe_time_snaps_backward(mkv_long_gop, monkeypatch):
    """请求 7s（非关键帧）应返回 5s，即 <= 请求值的最近关键帧。

    这是字幕对齐的核心：前端必须拿到 ffmpeg 真实落点而不是用户点击的时间。
    """
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    result = pb.get_keyframe_time(path=mkv_long_gop, time=7.0)
    actual = result["actual_start"]
    assert result["requested"] == 7.0
    assert actual <= 7.0, "落点不能晚于请求时间"
    assert 4.5 <= actual <= 5.5, f"应 snap 到 5s 附近的关键帧，实际 {actual}"


@requires_ffmpeg
def test_keyframe_time_exact_on_keyframe(mkv_long_gop, monkeypatch):
    """请求正好落在关键帧上时应原样返回，不再往前跳一个 GOP"""
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    actual = pb.get_keyframe_time(path=mkv_long_gop, time=10.0)["actual_start"]
    assert 9.5 <= actual <= 10.5, f"应保持在 10s，实际 {actual}"


@requires_ffmpeg
def test_keyframe_time_zero_short_circuits(mkv_long_gop, monkeypatch):
    """time=0 不需要起 ffmpeg，直接返回 0"""
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    assert pb.get_keyframe_time(path=mkv_long_gop, time=0)["actual_start"] == 0.0


@requires_ffmpeg
def test_keyframe_time_cleans_temp_file(mkv_long_gop, monkeypatch):
    """临时 mp4 必须删掉，不能在 tempdir 里堆积"""
    import glob
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    pattern = os.path.join(tempfile.gettempdir(), "napics_kf_*.mp4")
    before = set(glob.glob(pattern))
    pb.get_keyframe_time(path=mkv_long_gop, time=7.0)
    assert set(glob.glob(pattern)) == before, "临时文件未清理"


def test_transcode_uses_input_seek():
    """-ss 必须在 -i 之前（input seek）。

    放在 -i 之后是 output seek，要从文件头 demux，实测 1800s 处要 4.58s
    而 input seek 恒定 0.1s。
    """
    src = open(
        os.path.join(_BACKEND, "plugins", "feature-player", "playback_routes.py"),
        encoding="utf-8",
    ).read()
    # 截取 transcode_file 函数体
    start = src.index("def transcode_file(")
    end = src.index("@router.get(\"/playback/keyframe-time\")")
    body = src[start:end]

    ss_pos = body.index('"-ss"')
    i_pos = body.index('"-i", path')
    assert ss_pos < i_pos, "-ss 必须在 -i 之前，否则退化成 output seek"
