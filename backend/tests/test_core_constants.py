"""规则中心常量回归测试。"""

from core.constants import (
    MEDIA_EXTS,
    MOVIE_TV_NFO_NAMES,
    SIDE_CAR_SUFFIXES,
    STANDARD_NFO_NAMES,
    SUBTITLE_EXTS,
    VIDEO_EXTS,
)


def test_video_exts_cover_existing_media_formats():
    assert {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"} <= VIDEO_EXTS


def test_media_exts_include_video_subtitle_and_metadata():
    assert VIDEO_EXTS <= MEDIA_EXTS
    assert SUBTITLE_EXTS <= MEDIA_EXTS
    assert {".nfo", ".jpg", ".png", ".tmp"} <= MEDIA_EXTS


def test_nfo_and_sidecar_names_keep_existing_order():
    assert STANDARD_NFO_NAMES == ("movie.nfo", "tvshow.nfo", "season.nfo")
    assert MOVIE_TV_NFO_NAMES == ("movie.nfo", "tvshow.nfo")
    assert SIDE_CAR_SUFFIXES[0] == ".nfo"
