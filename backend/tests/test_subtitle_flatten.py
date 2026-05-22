"""字幕文件扁平化 + 子目录提升 + 空目录清理测试。"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(__file__))

from organize_executor import _apply_action_plan_moves, _PLAN_SUBTITLE_EXTS


def _make_tree(base, structure: dict):
    """递归创建目录树。structure: {name: None(文件) | dict(子目录)}"""
    for name, content in structure.items():
        path = os.path.join(base, name)
        if content is None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write("")
        else:
            os.makedirs(path, exist_ok=True)
            _make_tree(path, content)


def test_subtitle_in_subdir_flattened_to_season():
    """字幕在 Subs 子目录中时，应被扁平化到 Season 01 下，而不是 Season 01/Subs/。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "[SubGroup] Hyouka - 02.mkv": None,
                "Subs": {
                    "[SubGroup] Hyouka - 01.chs.ass": None,
                    "[SubGroup] Hyouka - 02.chs.ass": None,
                },
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 02.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E02.mkv"),
                "mapped": {"season": 1, "episode": 2},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 02.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "Subs", "[SubGroup] Hyouka - 01.chs.ass"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "Subs", "[SubGroup] Hyouka - 02.chs.ass"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}

        assert os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv") in targets
        assert os.path.join(season_dir, "冰菓 Hyouka S01E02.mkv") in targets

        sub_targets = [t for t in targets if t.endswith(".ass")]
        for sub_target in sub_targets:
            parent = os.path.dirname(sub_target)
            assert os.path.normcase(parent) == os.path.normcase(season_dir), \
                f"字幕应在 Season 01 下，实际在: {parent}"

        sub_basenames = {os.path.basename(t) for t in sub_targets}
        assert "冰菓 Hyouka S01E01.chs.ass" in sub_basenames
        assert "冰菓 Hyouka S01E02.chs.ass" in sub_basenames


def test_subtitle_same_dir_still_works():
    """字幕和视频在同一目录下时，第一阶段的同名匹配应正常工作。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "[SubGroup] Hyouka - 01.chs.ass": None,
                "[SubGroup] Hyouka - 01.cht.ass": None,
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.chs.ass"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.cht.ass"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}
        sub_targets = [t for t in targets if t.endswith(".ass")]

        for sub_target in sub_targets:
            parent = os.path.dirname(sub_target)
            assert os.path.normcase(parent) == os.path.normcase(season_dir)


def test_sp_subdir_promoted_to_root():
    """SPs 子目录中的文件应被提升到剧集根目录下（和 Season 同级）。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "SPs": {
                    "SP01.mkv": None,
                    "SP02.mkv": None,
                },
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "SPs", "SP01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "SPs", "SP02.mkv"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}
        sp_targets = sorted([t for t in targets if "SP0" in os.path.basename(t)])

        # SPs 应在剧集根目录下（save_path/SPs/），不是 Season 01/SPs/
        expected_sp_dir = os.path.join(save_path, "SPs")
        for sp_target in sp_targets:
            parent = os.path.dirname(sp_target)
            assert os.path.normcase(parent) == os.path.normcase(expected_sp_dir), \
                f"SP 应在 {expected_sp_dir} 下，实际在: {parent}"


def test_cd_subdir_promoted_to_root():
    """CDs 子目录中的文件应被提升到剧集根目录下。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "CDs": {
                    "CD1": {
                        "01.flac": None,
                        "02.flac": None,
                    },
                },
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "CDs", "CD1", "01.flac"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "CDs", "CD1", "02.flac"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}
        flac_targets = sorted([t for t in targets if t.endswith(".flac")])

        # CDs/CD1 应在剧集根目录下
        expected_cd_dir = os.path.join(save_path, "CDs", "CD1")
        for flac_target in flac_targets:
            parent = os.path.dirname(flac_target)
            assert os.path.normcase(parent) == os.path.normcase(expected_cd_dir), \
                f"CD 文件应在 {expected_cd_dir} 下，实际在: {parent}"


def test_empty_torrent_dir_cleaned_up():
    """所有文件移走后，空的种子目录应被清理。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "Subs": {
                    "[SubGroup] Hyouka - 01.chs.ass": None,
                },
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "Subs", "[SubGroup] Hyouka - 01.chs.ass"), save_path),
        ]

        _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)

        # 种子目录和 Subs 子目录应该被清理
        assert not os.path.exists(torrent_dir), f"种子目录应被清理: {torrent_dir}"
        # Season 01 目录应该保留
        assert os.path.isdir(season_dir), "Season 01 目录应保留"


def test_subtitle_no_episode_number_still_flattened():
    """字幕文件名中没有集号时，应直接扁平化到 Season 目录（保留原文件名）。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[SubGroup] Hyouka BDRip 1080p")

        _make_tree(save_path, {
            "[SubGroup] Hyouka BDRip 1080p": {
                "[SubGroup] Hyouka - 01.mkv": None,
                "Subs": {
                    "fonts.ass": None,
                },
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[SubGroup] Hyouka - 01.mkv"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "Subs", "fonts.ass"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}
        sub_targets = [t for t in targets if t.endswith(".ass")]

        for sub_target in sub_targets:
            parent = os.path.dirname(sub_target)
            assert os.path.normcase(parent) == os.path.normcase(season_dir)
            assert os.path.basename(sub_target) == "fonts.ass"


def test_realistic_zhushen_hyouka():
    """模拟真实场景：诸神字幕组冰菓种子，外挂字幕在独立子目录中。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_name = "【诸神字幕组】[冰菓 Hyouka][01-22合集+OAD][720P][外挂中日文字幕][BD-MP4]"
        torrent_dir = os.path.join(save_path, torrent_name)

        tree = {torrent_name: {"Subs": {}}}
        for i in range(1, 4):
            tree[torrent_name][f"[诸神字幕组][冰菓][{i:02d}][720P].mp4"] = None
            tree[torrent_name]["Subs"][f"[诸神字幕组][冰菓][{i:02d}].chs.srt"] = None
            tree[torrent_name]["Subs"][f"[诸神字幕组][冰菓][{i:02d}].jpn.srt"] = None

        _make_tree(save_path, tree)

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = []
        whitelist = []
        for i in range(1, 4):
            video_name = f"[诸神字幕组][冰菓][{i:02d}][720P].mp4"
            plan_items.append({
                "original_path": os.path.join(torrent_dir, video_name),
                "target_path": os.path.join(season_dir, f"冰菓 Hyouka S01E{i:02d}.mp4"),
                "mapped": {"season": 1, "episode": i},
            })
            whitelist.append(os.path.relpath(os.path.join(torrent_dir, video_name), save_path))
            whitelist.append(os.path.relpath(
                os.path.join(torrent_dir, "Subs", f"[诸神字幕组][冰菓][{i:02d}].chs.srt"), save_path))
            whitelist.append(os.path.relpath(
                os.path.join(torrent_dir, "Subs", f"[诸神字幕组][冰菓][{i:02d}].jpn.srt"), save_path))

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}
        sub_targets = sorted([t for t in targets if t.endswith(".srt")])

        for sub_target in sub_targets:
            parent = os.path.dirname(sub_target)
            assert os.path.normcase(parent) == os.path.normcase(season_dir)

        sub_basenames = {os.path.basename(t) for t in sub_targets}
        for i in range(1, 4):
            assert f"冰菓 Hyouka S01E{i:02d}.chs.srt" in sub_basenames
            assert f"冰菓 Hyouka S01E{i:02d}.jpn.srt" in sub_basenames

        # 种子目录应被清理
        assert not os.path.exists(torrent_dir), f"种子目录应被清理: {torrent_dir}"


def test_zip_file_same_dir_promoted_to_root():
    """和视频同目录的 zip 文件不应跟随视频进入 Season，应放在剧集根目录。"""
    with tempfile.TemporaryDirectory() as tmp:
        save_path = os.path.join(tmp, "冰菓 Hyouka")
        torrent_dir = os.path.join(save_path, "[Kamigami] Hyouka BDRip")

        _make_tree(save_path, {
            "[Kamigami] Hyouka BDRip": {
                "[Kamigami] Hyouka - 01.mp4": None,
                "[Kamigami] Hyouka - 01.Chs&Jap.ass": None,
                "[Kamigami] Hyouka - OAD.mp4": None,
                "[Kamigami] Hyouka - OAD.Chs&Jap.ass": None,
                "Fonts(字体包).zip": None,
            },
        })

        season_dir = os.path.join(save_path, "Season 01")
        plan_items = [
            {
                "original_path": os.path.join(torrent_dir, "[Kamigami] Hyouka - 01.mp4"),
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mp4"),
                "mapped": {"season": 1, "episode": 1},
            },
        ]
        whitelist = [
            os.path.relpath(os.path.join(torrent_dir, "[Kamigami] Hyouka - 01.mp4"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[Kamigami] Hyouka - 01.Chs&Jap.ass"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[Kamigami] Hyouka - OAD.mp4"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "[Kamigami] Hyouka - OAD.Chs&Jap.ass"), save_path),
            os.path.relpath(os.path.join(torrent_dir, "Fonts(字体包).zip"), save_path),
        ]

        ops = _apply_action_plan_moves(plan_items, base_path=save_path, whitelist=whitelist)
        targets = {op["new"] for op in ops}

        # zip 文件应在剧集根目录下，不在 Season 01 下
        zip_targets = [t for t in targets if t.endswith(".zip")]
        print(f"zip 目标路径: {zip_targets}")
        for zt in zip_targets:
            parent = os.path.dirname(zt)
            assert os.path.normcase(parent) == os.path.normcase(save_path), \
                f"zip 应在剧集根目录下，实际在: {parent}"

        # OAD 视频（不在 plan 中）也应在剧集根目录下
        oad_targets = [t for t in targets if "OAD" in os.path.basename(t) and t.endswith(".mp4")]
        print(f"OAD 目标路径: {oad_targets}")
        for ot in oad_targets:
            parent = os.path.dirname(ot)
            assert os.path.normcase(parent) == os.path.normcase(save_path), \
                f"OAD 应在剧集根目录下，实际在: {parent}"

        # 正片字幕应在 Season 01 下
        ep_sub_targets = [t for t in targets if "S01E01" in os.path.basename(t) and t.endswith(".ass")]
        print(f"正片字幕目标路径: {ep_sub_targets}")
        for st in ep_sub_targets:
            parent = os.path.dirname(st)
            assert os.path.normcase(parent) == os.path.normcase(season_dir), \
                f"正片字幕应在 Season 01 下，实际在: {parent}"
