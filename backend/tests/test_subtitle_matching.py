"""字幕结果相关性匹配测试。

锁定「搜索到的字幕是不是这部片」的判定。踩过的坑：
1. 中文逐字分词让 "信条" 在 "刺客信条" 里 100% 命中而拿到 60 分，
   占比 0.5 也高于 0.3 阈值 → 误匹配逃逸（靠 different_work 兜住）
2. 无包含关系但零散字符重合也能拿 60 分
   （"进击的巨人" vs "巨人族的花嫁" 共有 巨/人/的）→ 靠 weak_overlap 兜住
3. 但 "进击的巨人 最终季"、"进击的巨人 第3季" 是同一作品，不能一起过滤掉
4. assrt 的 native_name 是斜杠分隔的多别名，不拆开永远匹配不上
"""

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (_BACKEND, os.path.join(_BACKEND, "plugins", "subtitle-search")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from subtitle_matching import (  # noqa: E402
    build_match_candidates,
    build_match_targets,
    compute_junk_flags,
    compute_match_score,
)


def _judge(cn, en, native_name="", videoname=""):
    """返回 (match_score, is_junk, junk_reasons)"""
    candidates = build_match_candidates(cn_name=cn, en_name=en)
    targets = build_match_targets(native_name=native_name, videoname=videoname)
    score = compute_match_score(candidates, targets)
    flags = compute_junk_flags(match_score=score, candidates=candidates, targets=targets)
    return score, flags["is_junk"], flags["junk_reasons"]


class TestExactMatchKept:
    """正确结果必须保留"""

    def test_exact_cn_name(self):
        score, junk, _ = _judge("信条", "Tenet", native_name="信条")
        assert score == 90
        assert junk is False

    def test_slash_separated_aliases(self):
        """assrt 的 native_name 是 `信条/Tenet` 这种多别名，必须拆开匹配"""
        score, junk, _ = _judge("信条", "Tenet", native_name="信条/信条/Tenet/TENET天能")
        assert score == 90
        assert junk is False

    def test_release_style_videoname(self):
        """SubHD/SubDL 的 videoname 是 release 名，要剥掉技术标签再匹配"""
        score, junk, _ = _judge(
            "信条", "Tenet",
            native_name="信条",
            videoname="Tenet.2020.IMAX.2160p.BluRay.x265-SWTYBLZ",
        )
        assert score == 90
        assert junk is False

    def test_alias_with_trailing_year(self):
        score, junk, _ = _judge("刺客信条", "Assassin's Creed",
                                native_name="刺客教條/刺客信条/Assassin's Creed (2016)")
        assert score == 90
        assert junk is False


class TestModifierSuffixKept:
    """季/剧场版等修饰尾缀是同一作品，不能过滤"""

    def test_final_season(self):
        _, junk, reasons = _judge("进击的巨人", "Attack on Titan",
                                  native_name="进击的巨人 最终季")
        assert junk is False, reasons

    def test_numbered_season(self):
        _, junk, reasons = _judge("进击的巨人", "Attack on Titan",
                                  native_name="进击的巨人 第3季")
        assert junk is False, reasons

    def test_movie_edition(self):
        _, junk, reasons = _judge("你的名字", "Your Name",
                                  native_name="你的名字 剧场版")
        assert junk is False, reasons


class TestDifferentWorkFiltered:
    """片名被当成子串命中的误匹配必须过滤"""

    def test_prefix_extended_name(self):
        """刺客信条 / 秩序信条 / 弃子信条 都不是 信条"""
        for native in ("刺客信条", "秩序信条", "弃子信条"):
            score, junk, reasons = _judge("信条", "Tenet", native_name=native)
            assert junk is True, f"{native} score={score} reasons={reasons}"
            assert "different_work" in reasons

    def test_joker_variants(self):
        for native in ("小丑回魂", "小丑女"):
            _, junk, reasons = _judge("小丑", "Joker", native_name=native)
            assert junk is True, f"{native} reasons={reasons}"


class TestWeakOverlapFiltered:
    """只有零散字符重合的不同作品必须过滤"""

    def test_scattered_chars(self):
        """进击的巨人 vs 巨人族的花嫁：共有 巨/人/的，但不是同一作品"""
        score, junk, reasons = _judge("进击的巨人", "Attack on Titan",
                                      native_name="巨人族的花嫁")
        assert junk is True, f"score={score} reasons={reasons}"
        assert "weak_overlap" in reasons


class TestUnmatchedFiltered:
    def test_completely_unrelated(self):
        score, junk, reasons = _judge("信条", "Tenet",
                                      native_name="蜘蛛侠：崭新之日",
                                      videoname="Spider-Man.Brand.New.Day.2026")
        assert score == 0
        assert junk is True
        assert "unmatched" in reasons


class TestNoJunkRuleDependsOnBtFields:
    """字幕没有 seeders/size_gb，判定不能依赖 BT 特有字段"""

    def test_junk_flags_signature_is_bt_free(self):
        candidates = build_match_candidates(cn_name="信条", en_name="Tenet")
        targets = build_match_targets(native_name="信条")
        flags = compute_junk_flags(match_score=90, candidates=candidates, targets=targets)
        assert flags == {"is_junk": False, "junk_reasons": []}


class TestReleaseStyleNativeNameKept:
    """SubDL 的 native_name 直接是 release 名，不能被误判成不同作品。

    踩过的坑：`_is_different_work` 原先遍历目标时"碰到一个像不同作品的就返回 True"，
    而同一条结果会派生出多个目标（原始 release 名 + 剥完技术标签的短名），
    原始 release 名 normalize 后必然多出一堆内容 → 正确结果被全部误杀。
    正确语义是"任一对证据显示同作品就保留"。
    """

    def test_imax_edition_kept(self):
        native = "Tenet.2020.IMAX.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-FGT"
        score, junk, reasons = _judge("信条", "Tenet", native_name=native, videoname=native)
        assert junk is False, f"score={score} reasons={reasons}"

    def test_spaced_release_name_kept(self):
        native = "Tenet 2020 IMAX 720p BluRay HEVC x265 BONE"
        _, junk, reasons = _judge("信条", "Tenet", native_name=native, videoname=native)
        assert junk is False, reasons

    def test_release_version_suffix_kept(self):
        """V2 是发布版本号，不是另一部作品"""
        native = "Tenet.2020.V2.HDCAM.850MB.c1nem4.x264-SUNSCREEN"
        _, junk, reasons = _judge("信条", "Tenet", native_name=native, videoname=native)
        assert junk is False, reasons

    def test_different_film_in_release_name_still_filtered(self):
        """release 名里是另一部片时仍要过滤"""
        native = "刺客信条.Assassins.Creed.2016.2160p.WEB-DL"
        _, junk, reasons = _judge("信条", "Tenet", native_name=native, videoname=native)
        assert junk is True, reasons


class TestRegenerateCleanNames:
    """搜索索引名自动生成（前端「自动获取」按钮）"""

    def test_generates_cn_and_en(self):
        from clean_name_system import regenerate_clean_names

        library = [{
            "file_path": r"D:\media\Tenet.2020.1080p.BluRay.x264-WiKi.mkv",
            "file_name": "Tenet.2020.1080p.BluRay.x264-WiKi.mkv",
        }]
        result = regenerate_clean_names(library, library[0]["file_path"])
        assert result["updated"] == 1
        assert result["en"].lower().startswith("tenet")
        assert library[0]["clean_name_source"] == "parsed"

    def test_overwrites_manual_source(self):
        """用户显式点按钮，要能覆盖已有的 manual 名字，否则点了没反应"""
        from clean_name_system import regenerate_clean_names

        library = [{
            "file_path": r"D:\media\Tenet.2020.1080p.BluRay.x264-WiKi.mkv",
            "file_name": "Tenet.2020.1080p.BluRay.x264-WiKi.mkv",
            "clean_name": "随便写的",
            "clean_name_cn": "随便写的",
            "clean_name_source": "manual",
        }]
        result = regenerate_clean_names(library, library[0]["file_path"])
        assert result["updated"] == 1
        assert library[0]["clean_name"] != "随便写的"

    def test_missing_path_returns_zero(self):
        from clean_name_system import regenerate_clean_names

        result = regenerate_clean_names([], r"D:\nope.mkv")
        assert result["updated"] == 0
