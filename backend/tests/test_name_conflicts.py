"""取名证据的冲突检测。

背景：每个取名来源都会错（下载来的文件名各式各样，NFO 也会刮削错），所以不能
靠"给来源排座次、位次高的说了算"。这里锁定的是可判定的矛盾检测 ——
只比对两边都拿到了值的项，冲突时打标而不是悄悄挑一个。
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from name_conflicts import (  # noqa: E402
    EPISODE_MISMATCH, SEASON_MISMATCH, SIBLING_MISMATCH, YEAR_MISMATCH,
    add_conflicts, annotate_group_conflicts, clear_conflicts, detect_item_conflicts,
)


def _episode_nfo(folder, file_name, *, title="第1话", showtitle="军火女王",
                 season=1, episode=1, year=""):
    video = os.path.join(folder, file_name)
    with open(video, "wb") as f:
        f.write(b"\x00")
    lines = ["<episodedetails>", f"  <title>{title}</title>",
             f"  <showtitle>{showtitle}</showtitle>",
             f"  <season>{season}</season>", f"  <episode>{episode}</episode>"]
    if year:
        lines.append(f"  <year>{year}</year>")
    lines.append("</episodedetails>")
    with open(os.path.join(folder, os.path.splitext(file_name)[0] + ".nfo"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return video


class TestSeasonConflict:
    def test_nfo_season_disagrees_with_folder(self, tmp_path):
        """实测军火女王 Season 02 目录里每集 NFO 都写着 season=1"""
        season = tmp_path / "Season 02"
        season.mkdir()
        video = _episode_nfo(str(season), "Jormungand [13].mkv", season=1, episode=13)
        assert SEASON_MISMATCH in detect_item_conflicts(video)

    def test_agreeing_season_is_not_a_conflict(self, tmp_path):
        season = tmp_path / "Season 01"
        season.mkdir()
        video = _episode_nfo(str(season), "Jormungand [01].mkv", season=1, episode=1)
        assert SEASON_MISMATCH not in detect_item_conflicts(video)

    def test_folder_without_season_number_is_not_a_conflict(self, tmp_path):
        """目录名给不出季号时不算矛盾 —— 缺失是常态，不是矛盾"""
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        video = _episode_nfo(str(work), "Jormungand [01].mkv", season=3, episode=1)
        assert SEASON_MISMATCH not in detect_item_conflicts(video)


class TestEpisodeConflict:
    def test_filename_number_disagrees_with_nfo(self, tmp_path):
        work = tmp_path / "某剧"
        work.mkdir()
        video = _episode_nfo(str(work), "Show - 05 [1080p].mkv", season=1, episode=7)
        assert EPISODE_MISMATCH in detect_item_conflicts(video)

    def test_agreeing_episode_is_clean(self, tmp_path):
        work = tmp_path / "某剧"
        work.mkdir()
        video = _episode_nfo(str(work), "Show - 05 [1080p].mkv", season=1, episode=5)
        assert detect_item_conflicts(video) == []


class TestYearConflict:
    def test_one_year_apart_is_tolerated(self, tmp_path):
        """上映年与发行年常差一年，实测「你好世界」NFO 2018 / 文件名 2019"""
        work = tmp_path / "动画电影"
        work.mkdir()
        video = _episode_nfo(str(work), "你好世界 helloworld (2019).mkv",
                             season=1, episode=1, year="2018")
        assert YEAR_MISMATCH not in detect_item_conflicts(video)

    def test_far_apart_year_is_a_conflict(self, tmp_path):
        work = tmp_path / "动画电影"
        work.mkdir()
        video = _episode_nfo(str(work), "某片 (2019).mkv", season=1, episode=1, year="2005")
        assert YEAR_MISMATCH in detect_item_conflicts(video)


class TestNoNfo:
    def test_no_nfo_means_no_conflict(self, tmp_path):
        work = tmp_path / "某剧"
        work.mkdir()
        video = work / "Show - 05.mkv"
        video.write_bytes(b"\x00")
        assert detect_item_conflicts(str(video)) == []


def _item(folder, name, cn, suffix="S01E01"):
    return {
        "file_path": os.path.join(folder, name),
        "file_name": name,
        "clean_name": f"{cn} {suffix}".strip(),
        "clean_name_cn": cn,
    }


class TestSiblingConsistency:
    def test_different_names_in_one_folder_are_all_marked(self):
        """实测军火女王一季 12 集拿到了「炎兔」「脉冲星」「奏出音乐的武器第一篇」"""
        folder = os.path.join("X:", "动画番", "军火女王", "Season 01")
        items = [
            _item(folder, "ep1.mkv", "炎兔", "S01E01"),
            _item(folder, "ep2.mkv", "脉冲星", "S01E02"),
            _item(folder, "ep3.mkv", "奏出音乐的武器第一篇", "S01E03"),
        ]
        assert annotate_group_conflicts(items) == 3
        for i in items:
            assert i["name_needs_review"] is True
            assert SIBLING_MISMATCH in i["name_conflicts"]

    def test_consistent_group_is_untouched(self):
        folder = os.path.join("X:", "动画番", "军火女王", "Season 01")
        items = [_item(folder, f"ep{n}.mkv", "军火女王", f"S01E{n:02d}") for n in range(1, 5)]
        assert annotate_group_conflicts(items) == 0
        for i in items:
            assert "name_needs_review" not in i

    def test_movie_pile_is_not_checked(self):
        """散装电影目录里每部名字本来就不同，不能拿一致性去说它错"""
        folder = os.path.join("X:", "动画电影")
        items = [
            _item(folder, "a.mkv", "你好世界", suffix=""),
            _item(folder, "b.mkv", "乔西的虎与鱼", suffix=""),
            _item(folder, "c.mkv", "你的名字。", suffix=""),
        ]
        assert annotate_group_conflicts(items) == 0

    def test_two_episodes_are_not_enough_to_judge(self):
        folder = os.path.join("X:", "动画番", "某剧", "Season 01")
        items = [_item(folder, "ep1.mkv", "甲", "S01E01"), _item(folder, "ep2.mkv", "乙", "S01E02")]
        assert annotate_group_conflicts(items) == 0

    def test_different_folders_are_independent(self):
        a = os.path.join("X:", "动画番", "剧甲", "Season 01")
        b = os.path.join("X:", "动画番", "剧乙", "Season 01")
        items = [_item(a, f"x{n}.mkv", "剧甲", f"S01E{n:02d}") for n in range(1, 4)]
        items += [_item(b, f"y{n}.mkv", "剧乙", f"S01E{n:02d}") for n in range(1, 4)]
        assert annotate_group_conflicts(items) == 0


class TestMarkerLifecycle:
    def test_clear_removes_stale_markers(self):
        item = {"name_conflicts": [SEASON_MISMATCH], "name_needs_review": True}
        clear_conflicts(item)
        assert "name_conflicts" not in item
        assert "name_needs_review" not in item

    def test_add_merges_and_dedupes(self):
        item = {}
        add_conflicts(item, [SEASON_MISMATCH])
        add_conflicts(item, [SEASON_MISMATCH, EPISODE_MISMATCH])
        assert item["name_conflicts"] == sorted({SEASON_MISMATCH, EPISODE_MISMATCH})

    def test_empty_list_does_not_create_fields(self):
        item = {}
        add_conflicts(item, [])
        assert item == {}


class TestScanFieldsCoverMarkers:
    def test_markers_are_scan_managed(self):
        """标记跟着名字一起重算，否则修好了标记还挂着"""
        from scan_name_filler import SCAN_MANAGED_NAME_FIELDS
        assert "name_conflicts" in SCAN_MANAGED_NAME_FIELDS
        assert "name_needs_review" in SCAN_MANAGED_NAME_FIELDS


class TestSeasonSourceIsConsistent:
    """季号只能有一个判据：详情里写 S01E16、整理预览写 S02E16 这种自相矛盾必须不出现"""

    def test_folder_name_beats_filename_and_nfo(self, tmp_path):
        from clean_name_system import build_search_index_name, season_from_folder_name
        from renamer import generate_shadow_name_from_nfo

        work = tmp_path / "军火女王 Jormungand"
        season = work / "Season 02"
        season.mkdir(parents=True)
        # 实测数据：第二季的分集 NFO 写的是 season=1、episode=16（整部剧连续编号），
        # 文件名里的 [16] 也是绝对集号，只有目录名说得对
        name = "[VCB-Studio] Jormungand PERFECT ORDER [16][Ma10p_1080p][x265_flac].mkv"
        video = _episode_nfo(str(season), name, title="第16话",
                             showtitle="军火女王", season=1, episode=16)

        assert season_from_folder_name("Season 02") == 2
        shadow = generate_shadow_name_from_nfo(video, str(season), "movie")
        index = build_search_index_name(video, name)
        assert shadow == "军火女王 S02E16"
        assert index is not None and index.suffix == "S02E16"
        # 两条路径必须给出同一个季集号
        assert index.suffix in shadow

    def test_no_season_in_folder_name_falls_back_to_nfo(self, tmp_path):
        from renamer import generate_shadow_name_from_nfo

        work = tmp_path / "某剧 Some Show"
        work.mkdir()
        video = _episode_nfo(str(work), "Some.Show.E05.mkv", title="第5话",
                             showtitle="某剧", season=3, episode=5)
        assert generate_shadow_name_from_nfo(video, str(work), "movie") == "某剧 S03E05"

    def test_chinese_season_names(self):
        from clean_name_system import season_from_folder_name
        assert season_from_folder_name("第二季") == 2
        assert season_from_folder_name("第十二季") == 12
        assert season_from_folder_name("S3") == 3
        assert season_from_folder_name("军火女王 Jormungand") is None
        assert season_from_folder_name("Specials") is None
