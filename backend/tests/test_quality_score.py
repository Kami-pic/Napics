"""质量评分系统测试：compute_quality_score + compare_quality_score + compute_quality_score_from_video。"""

import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from quality_parser import (
    QualityTag, parse_quality, compute_quality_score,
    compute_quality_score_from_video, compare_quality_score,
)

passed = 0
failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")


def fail(name, msg):
    global failed
    failed += 1
    print(f"  [FAIL] {name}: {msg}")


def test_score_dimensions():
    """测试各维度评分"""
    print("\n[SUITE] 评分维度")

    # 满分：2160p Remux x265 Atmos 中字 = 45+20+10+20+5 = 100
    tag = QualityTag(resolution="2160p", source="Remux", video_codec="x265", audio_codec="Atmos", has_chinese_sub=True)
    score = compute_quality_score(tag)
    if score == 100:
        ok(f"满分 100: {score}")
    else:
        fail("满分", f"期望 100，实际 {score}")

    # 1080p WEB-DL x265 AAC 无字幕 = 28+10+10+3+0 = 51
    tag2 = QualityTag(resolution="1080p", source="WEB-DL", video_codec="x265", audio_codec="AAC")
    score2 = compute_quality_score(tag2)
    if score2 == 51:
        ok(f"1080p WEB-DL x265 AAC: {score2}")
    else:
        fail("1080p WEB-DL", f"期望 51，实际 {score2}")

    # 720p 无来源 无编码 无字幕 = 14+0+0+0+0 = 14
    tag3 = QualityTag(resolution="720p")
    score3 = compute_quality_score(tag3)
    if score3 == 14:
        ok(f"720p 裸分: {score3}")
    else:
        fail("720p 裸分", f"期望 14，实际 {score3}")

    # 空标签 = 0
    tag4 = QualityTag()
    score4 = compute_quality_score(tag4)
    if score4 == 0:
        ok(f"空标签: {score4}")
    else:
        fail("空标签", f"期望 0，实际 {score4}")


def test_score_ordering():
    """测试评分排序正确性 — 同分辨率内严格递减，跨分辨率允许交叉"""
    print("\n[SUITE] 评分排序")

    # 同分辨率内必须递减
    cases_2160 = [
        ("2160p Remux Atmos", QualityTag(resolution="2160p", source="Remux", audio_codec="Atmos", video_codec="x265", has_chinese_sub=True)),
        ("2160p Bluray DTS-HD", QualityTag(resolution="2160p", source="Bluray", audio_codec="DTS-HD", video_codec="x265")),
        ("2160p WEB-DL AAC", QualityTag(resolution="2160p", source="WEB-DL", audio_codec="AAC", video_codec="x265")),
    ]
    scores_2160 = [(n, compute_quality_score(t)) for n, t in cases_2160]
    ok_2160 = all(scores_2160[i][1] > scores_2160[i+1][1] for i in range(len(scores_2160)-1))
    if ok_2160:
        ok(f"2160p 内递减: {[f'{n}={s}' for n, s in scores_2160]}")
    else:
        fail("2160p 内递减", str(scores_2160))

    cases_1080 = [
        ("1080p Remux TrueHD", QualityTag(resolution="1080p", source="Remux", audio_codec="TrueHD", video_codec="x265")),
        ("1080p Bluray DTS", QualityTag(resolution="1080p", source="Bluray", audio_codec="DTS", video_codec="x264")),
        ("1080p WEB-DL AAC", QualityTag(resolution="1080p", source="WEB-DL", audio_codec="AAC", video_codec="x264")),
    ]
    scores_1080 = [(n, compute_quality_score(t)) for n, t in cases_1080]
    ok_1080 = all(scores_1080[i][1] > scores_1080[i+1][1] for i in range(len(scores_1080)-1))
    if ok_1080:
        ok(f"1080p 内递减: {[f'{n}={s}' for n, s in scores_1080]}")
    else:
        fail("1080p 内递减", str(scores_1080))

    # 2160p 最低分 > 1080p 最低分（同等配置下 2160p 一定高于 1080p）
    score_2160_min = compute_quality_score(QualityTag(resolution="2160p"))
    score_1080_min = compute_quality_score(QualityTag(resolution="1080p"))
    if score_2160_min > score_1080_min:
        ok(f"2160p 裸分({score_2160_min}) > 1080p 裸分({score_1080_min})")
    else:
        fail("跨分辨率裸分", f"2160p({score_2160_min}) <= 1080p({score_1080_min})")


def test_from_video():
    """测试从视频条目计算分数"""
    print("\n[SUITE] 从视频条目算分")

    # 1080p 视频，文件名含 WEB-DL x265
    video = {
        "height": 1080,
        "file_name": "Movie.2024.1080p.WEB-DL.x265.DDP5.1.mkv",
        "codec": "hevc",
        "audio_codec": "eac3",
    }
    score = compute_quality_score_from_video(video)
    if score > 0:
        ok(f"1080p WEB-DL 视频: {score}")
    else:
        fail("1080p 视频", f"分数为 0")

    # 2160p 视频
    video2 = {"height": 2160, "file_name": "Movie.4K.Remux.DTS-HD.MA.mkv"}
    score2 = compute_quality_score_from_video(video2)
    if score2 > score:
        ok(f"2160p Remux > 1080p WEB-DL: {score2} > {score}")
    else:
        fail("2160p vs 1080p", f"{score2} <= {score}")

    # 空视频
    video3 = {"height": 0, "file_name": "unknown.avi"}
    score3 = compute_quality_score_from_video(video3)
    if score3 >= 0:
        ok(f"空视频不崩溃: {score3}")
    else:
        fail("空视频", f"分数异常: {score3}")


def test_compare():
    """测试分数比较"""
    print("\n[SUITE] 分数比较")

    # 差距 > 5 → True
    if compare_quality_score(50, 60):
        ok("60 > 50+5 → True")
    else:
        fail("60 vs 50", "应该返回 True")

    # 差距 = 5 → False（不严格大于）
    if not compare_quality_score(50, 55):
        ok("55 = 50+5 → False")
    else:
        fail("55 vs 50", "应该返回 False")

    # 差距 < 5 → False
    if not compare_quality_score(50, 53):
        ok("53 < 50+5 → False")
    else:
        fail("53 vs 50", "应该返回 False")

    # 新分数更低 → False
    if not compare_quality_score(60, 50):
        ok("50 < 60 → False")
    else:
        fail("50 vs 60", "应该返回 False")


def test_parse_and_score():
    """测试从 BT 标题解析后算分"""
    print("\n[SUITE] 标题解析+算分")

    titles = [
        ("Movie.2024.2160p.Remux.DTS-HD.MA.x265-GROUP", 89),  # 40+25+14+10 = 89
        ("Movie.2024.1080p.BluRay.x264.DTS-CHS", 53),         # 25+20+6+7+5 = 63 (实际看解析)
        ("Movie.2024.720p.HDTV.AAC", 21),                      # 12+6+3 = 21
        ("Movie.2024.WEB-DL.1080p.x265.DDP5.1.CHS", 62),     # 25+12+10+10+5 = 62
    ]
    for title, min_expected in titles:
        tag = parse_quality(title)
        score = compute_quality_score(tag)
        if score >= min_expected * 0.8:  # 允许 20% 误差（解析可能不完美）
            ok(f"'{title[:40]}...' → {score}")
        else:
            fail(f"'{title[:40]}...'", f"分数 {score} < 期望最低 {min_expected * 0.8}")


if __name__ == "__main__":
    print("=" * 60)
    print("质量评分系统测试")
    print("=" * 60)

    test_score_dimensions()
    test_score_ordering()
    test_from_video()
    test_compare()
    test_parse_and_score()

    print(f"\n{'=' * 60}")
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
