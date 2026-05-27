"""跨模块共享的静态规则常量。"""

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}

STANDARD_NFO_NAMES = ("movie.nfo", "tvshow.nfo", "season.nfo")
MOVIE_TV_NFO_NAMES = ("movie.nfo", "tvshow.nfo")

SIDE_CAR_SUFFIXES = (".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg")
RECYCLE_DIR_NFO_AND_ART = ("movie.nfo", "season.nfo", "poster.jpg", "fanart.jpg", "banner.jpg")

MEDIA_EXTS = VIDEO_EXTS | SUBTITLE_EXTS | {".nfo", ".jpg", ".png", ".tmp"}
