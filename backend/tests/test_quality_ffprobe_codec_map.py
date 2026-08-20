"""ffprobe 编码名 → 质量评分表键的映射测试。

实际问题：库里 2622 条有 730 条 19 分、528 条 33 分，
拆开看是"只有分辨率和中字拿到分"。原因是评分表按发布命名写（x265 / AC3），
而 ffprobe 给的是 codec_name（hevc / ac3，小写），
文件名没有技术标签时回退到 ffprobe 值必然查不到，白丢音频 20 分 + 视频 10 分。
更讽刺的是我们自己的「标准结构 / 生成标准名」会清掉文件名里的技术标签，
整理得越规范，走的越是这条坏掉的回退路径。
"""

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from quality_parser import (  # noqa: E402
    compute_quality_score_from_video,
    normalize_ffprobe_audio_codec,
    normalize_ffprobe_video_codec,
)


class TestNormalizeVideoCodec:
    def test_known_codecs_mapped(self):
        assert normalize_ffprobe_video_codec("hevc") == "x265"
        assert normalize_ffprobe_video_codec("h264") == "x264"
        assert normalize_ffprobe_video_codec("av1") == "AV1"

    def test_case_insensitive(self):
        assert normalize_ffprobe_video_codec("HEVC") == "x265"
        assert normalize_ffprobe_video_codec(" H264 ") == "x264"

    def test_unknown_kept_as_is(self):
        """评不了的不硬给分：原样返回，查表得 0"""
        assert normalize_ffprobe_video_codec("vp9") == "vp9"
        assert normalize_ffprobe_video_codec("") == ""


class TestNormalizeAudioCodec:
    def test_known_codecs_mapped(self):
        assert normalize_ffprobe_audio_codec("ac3") == "AC3"
        assert normalize_ffprobe_audio_codec("eac3") == "EAC3"
        assert normalize_ffprobe_audio_codec("aac") == "AAC"
        assert normalize_ffprobe_audio_codec("dts") == "DTS"
        assert normalize_ffprobe_audio_codec("truehd") == "TrueHD"

    def test_unscoreable_codecs_get_nothing(self):
        """opus / flac 在评分表里没有对应档位，不编一个分数出来"""
        for codec in ("opus", "flac", "pcm_s16le", "vorbis", "mp3"):
            assert normalize_ffprobe_audio_codec(codec) == codec

    def test_atmos_not_inferred_from_eac3(self):
        """Atmos 是流内元数据，codec_name 只到 eac3，不能顺势提到 Atmos 档"""
        assert normalize_ffprobe_audio_codec("eac3") != "Atmos"


class TestScoreFromFfprobeFallback:
    def test_clean_filename_still_scores_codecs(self):
        """整理过的文件名没有技术标签，全靠 ffprobe 回退"""
        video = {
            "height": 1080,
            "file_name": "珍珠港 Pearl Harbor (2001).mkv",
            "codec": "h264",
            "audio_codec": "ac3",
            "subtitle_count": 1,
        }
        # 1080p(28) + 中字(5) + AC3(5) + x264(6) = 44；修复前只有 33
        assert compute_quality_score_from_video(video) == 44

    def test_unscoreable_audio_contributes_zero(self):
        video = {
            "height": 1080,
            "file_name": "Some Movie (2020).mkv",
            "codec": "hevc",
            "audio_codec": "opus",
        }
        # 1080p(28) + x265(10)，opus 不给分
        assert compute_quality_score_from_video(video) == 38

    def test_filename_tag_wins_over_ffprobe(self):
        """文件名信息更全（能区分 Remux/Atmos），不能被 ffprobe 值盖掉"""
        video = {
            "height": 2160,
            "file_name": "Movie.2020.2160p.Remux.TrueHD.Atmos.x265-GRP.mkv",
            "codec": "hevc",
            "audio_codec": "ac3",
        }
        # 音频应取文件名里的 Atmos(20)，而不是 ffprobe 的 ac3(5)
        assert compute_quality_score_from_video(video) == 45 + 20 + 20 + 10

    def test_missing_metadata_scores_zero(self):
        assert compute_quality_score_from_video({}) == 0
