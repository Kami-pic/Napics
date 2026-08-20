"""外挂字幕匹配规则测试。

两级匹配：同名前缀优先；同名一个都没有且目录里只有一个视频文件时，
把目录内字幕都归给它。

真实案例（克洛伊）：视频「克洛伊 (2010).mkv」，
字幕「Chloe.2009.Bluray.1080p.DTS-HD.x264-Grym R3.srt」，
只按同名匹配会返回空 —— 详情面板因此一直显示不出外挂字幕。
反过来，整季剧集目录必须严格同名，否则第 1 集会带上全季的字幕。
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from core.file_ops.sidecars import list_subtitle_files


def _touch(p, content="x"):
    p.write_text(content, encoding="utf-8")


def test_same_stem_exact(tmp_path):
    _touch(tmp_path / "movie.mkv")
    _touch(tmp_path / "movie.srt")
    assert list_subtitle_files(str(tmp_path / "movie.mkv")) == ["movie.srt"]


def test_same_stem_with_lang_suffix(tmp_path):
    _touch(tmp_path / "movie.mkv")
    _touch(tmp_path / "movie.chs.srt")
    _touch(tmp_path / "movie.eng.ass")
    got = list_subtitle_files(str(tmp_path / "movie.mkv"))
    assert sorted(got) == ["movie.chs.srt", "movie.eng.ass"]


def test_different_name_single_video_dir(tmp_path):
    """克洛伊场景：字幕名与视频名完全不同，但目录里只有一个视频"""
    _touch(tmp_path / "克洛伊 (2010).mkv")
    _touch(tmp_path / "Chloe.2009.Bluray.1080p.DTS-HD.x264-Grym R3.srt")
    _touch(tmp_path / "movie.nfo")
    _touch(tmp_path / "poster.jpg")
    _touch(tmp_path / "source.txt")

    got = list_subtitle_files(str(tmp_path / "克洛伊 (2010).mkv"))
    assert got == ["Chloe.2009.Bluray.1080p.DTS-HD.x264-Grym R3.srt"], \
        f"单视频目录应放宽匹配，实际 {got}"


def test_multi_video_dir_requires_same_stem(tmp_path):
    """整季剧集目录：必须严格同名，不能把别集的字幕算进来"""
    for i in (1, 2, 3):
        _touch(tmp_path / f"Show.S01E0{i}.mkv")
    _touch(tmp_path / "Show.S01E01.chs.srt")
    _touch(tmp_path / "Show.S01E02.chs.srt")
    _touch(tmp_path / "Random.Release.Group.srt")

    got = list_subtitle_files(str(tmp_path / "Show.S01E01.mkv"))
    assert got == ["Show.S01E01.chs.srt"], f"不该串到别集或异名字幕，实际 {got}"

    got2 = list_subtitle_files(str(tmp_path / "Show.S01E03.mkv"))
    assert got2 == [], f"没有同名字幕的那集应返回空，实际 {got2}"


def test_no_subtitle_files(tmp_path):
    _touch(tmp_path / "movie.mkv")
    _touch(tmp_path / "movie.nfo")
    assert list_subtitle_files(str(tmp_path / "movie.mkv")) == []


def test_non_subtitle_extensions_ignored(tmp_path):
    _touch(tmp_path / "movie.mkv")
    for name in ("movie.nfo", "movie.jpg", "movie.txt", "movie.md"):
        _touch(tmp_path / name)
    assert list_subtitle_files(str(tmp_path / "movie.mkv")) == []


def test_missing_directory(tmp_path):
    assert list_subtitle_files(str(tmp_path / "nope" / "movie.mkv")) == []


def test_same_stem_wins_over_loose_match(tmp_path):
    """有同名字幕时不应把目录里其他字幕也带上"""
    _touch(tmp_path / "movie.mkv")
    _touch(tmp_path / "movie.srt")
    _touch(tmp_path / "OtherRelease.srt")
    assert list_subtitle_files(str(tmp_path / "movie.mkv")) == ["movie.srt"]
