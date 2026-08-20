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


# ── 真实片源场景回归 ──

@requires_ffmpeg
def test_detects_both_when_external_name_differs_from_video(tmp_path, monkeypatch):
    """外挂字幕文件名与视频名完全不同时也要检测到。

    真实场景（克洛伊）：视频叫「克洛伊 (2010).mkv」，
    外挂字幕叫「Chloe.2009.Bluray.1080p.DTS-HD.x264-Grym R3.srt」，
    同目录还混着 nfo / jpg / txt。内封另有 1 条 subrip。
    期望结果：2 条字幕，一条 external 一条 embedded。
    """
    srt_embed = tmp_path / "embed.srt"
    srt_embed.write_text("1\n00:00:00,500 --> 00:00:02,000\nembedded\n", encoding="utf-8")

    video = tmp_path / "克洛伊 (2010).mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-i", str(srt_embed),
        "-map", "0:v", "-map", "1:a", "-map", "2:s",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-c:s", "srt",
        "-metadata:s:s:0", "language=eng",
        str(video),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180)
    if r.returncode != 0:
        pytest.skip(f"造样本失败: {r.stderr[:200]}")
    srt_embed.unlink()   # 这个只是制作素材，不能留在目录里当外挂字幕

    # 异名外挂字幕 + 一堆干扰文件
    (tmp_path / "Chloe.2009.Bluray.1080p.DTS-HD.x264-Grym R3.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nexternal\n", encoding="utf-8")
    (tmp_path / "movie.nfo").write_text("<movie/>", encoding="utf-8")
    (tmp_path / "poster.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "source.txt").write_text("", encoding="utf-8")

    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    result = pb.list_subtitles(path=str(video))
    subs = result["subtitles"]

    external = [s for s in subs if s["kind"] == "external"]
    embedded = [s for s in subs if s["kind"] == "embedded"]

    assert len(external) == 1, f"应检测到 1 条外挂字幕，实际 {len(external)}: {[s['name'] for s in subs]}"
    assert len(embedded) == 1, f"应检测到 1 条内封字幕，实际 {len(embedded)}"
    assert len(subs) == 2, f"总数应为 2，实际 {len(subs)}"

    summary = result["summary"]
    assert summary["external"] == 1
    assert summary["embedded"] == 1
    assert summary["graphic"] == 0
    assert summary["maybe_hardcoded"] is False


@requires_ffmpeg
def test_non_subtitle_files_not_picked_up(tmp_path, monkeypatch):
    """nfo/jpg/txt 等不能被当成字幕文件"""
    video = tmp_path / "v.mkv"
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", str(video),
    ]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
    if r.returncode != 0:
        pytest.skip("造样本失败")

    for name in ("movie.nfo", "poster.jpg", "fanart.jpg", "source.txt", "readme.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    subs = pb.list_subtitles(path=str(video))["subtitles"]
    assert subs == [], f"不该把非字幕文件当字幕: {[s['name'] for s in subs]}"
