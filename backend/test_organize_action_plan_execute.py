import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException

from routes.organize import (
    _apply_action_plan_moves,
    _find_duplicate_logical_targets,
    _find_duplicate_target_paths,
)


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _with_temp_dir(name, test_fn):
    tmp_dir = Path(os.getcwd()) / f"{name}_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir()
    try:
        test_fn(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_apply_action_plan_moves_renames_video_and_sidecars_into_target_dir():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        source_dir = save_path / "[Group] Show"
        original = source_dir / "[Group] Show - 01.mkv"
        subtitle = source_dir / "[Group] Show - 01.zh.srt"
        poster = source_dir / "[Group] Show - 01-poster.jpg"
        nfo = source_dir / "[Group] Show - 01.nfo"
        target = save_path / "Season 01" / "Show - S01E01.mkv"

        for path in [original, subtitle, poster, nfo]:
            _touch(path)

        ops = _apply_action_plan_moves([
            {
                "original_path": str(original),
                "target_path": str(target),
            }
        ])

        assert len(ops) == 4
        assert target.exists()
        assert (save_path / "Season 01" / "Show - S01E01.zh.srt").exists()
        assert (save_path / "Season 01" / "Show - S01E01-poster.jpg").exists()
        assert (save_path / "Season 01" / "Show - S01E01.nfo").exists()
        assert not original.exists()
        assert not subtitle.exists()
        assert not poster.exists()
        assert not nfo.exists()

    _with_temp_dir("organize_action_plan_move", run)


def test_apply_action_plan_moves_moves_single_season_extra_dirs_from_whitelist_into_target_season():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        source_dir = save_path / "[Group] Show"
        original = source_dir / "[Group] Show - 01.mkv"
        subtitle = source_dir / "Subs" / "[Group] Show - 01.zh.ass"
        font = source_dir / "Fonts" / "font.ttf"
        target = save_path / "Season 01" / "Show - S01E01.mkv"

        for path in [original, subtitle, font]:
            _touch(path)

        ops = _apply_action_plan_moves(
            [
                {
                    "original_path": str(original),
                    "target_path": str(target),
                    "mapped": {"season": 1, "episode": 1},
                }
            ],
            base_path=str(save_path),
            whitelist=[
                "[Group] Show/[Group] Show - 01.mkv",
                "[Group] Show/Subs/[Group] Show - 01.zh.ass",
                "[Group] Show/Fonts/font.ttf",
            ],
        )

        moved_targets = {Path(op["new"]) for op in ops}
        assert target in moved_targets
        assert (save_path / "Season 01" / "Subs" / "[Group] Show - 01.zh.ass").exists()
        assert (save_path / "Season 01" / "Fonts" / "font.ttf").exists()
        assert not subtitle.exists()
        assert not font.exists()

    _with_temp_dir("organize_action_plan_single_season_extras", run)


def test_apply_action_plan_moves_routes_multi_season_extra_dirs_by_source_season_folder():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        source_s1 = save_path / "[Group] Show" / "Season 1"
        source_s2 = save_path / "[Group] Show" / "Season 2"
        original_s1 = source_s1 / "Show - 01.mkv"
        original_s2 = source_s2 / "Show - 02.mkv"
        subtitle_s1 = source_s1 / "Subs" / "Show - 01.zh.ass"
        font_s2 = source_s2 / "Fonts" / "font.ttf"

        for path in [original_s1, original_s2, subtitle_s1, font_s2]:
            _touch(path)

        ops = _apply_action_plan_moves(
            [
                {
                    "original_path": str(original_s1),
                    "target_path": str(save_path / "Season 01" / "Show - S01E01.mkv"),
                    "mapped": {"season": 1, "episode": 1},
                },
                {
                    "original_path": str(original_s2),
                    "target_path": str(save_path / "Season 02" / "Show - S02E01.mkv"),
                    "mapped": {"season": 2, "episode": 1},
                },
            ],
            base_path=str(save_path),
            whitelist=[
                "[Group] Show/Season 1/Show - 01.mkv",
                "[Group] Show/Season 1/Subs/Show - 01.zh.ass",
                "[Group] Show/Season 2/Show - 02.mkv",
                "[Group] Show/Season 2/Fonts/font.ttf",
            ],
        )

        moved_targets = {Path(op["new"]) for op in ops}
        assert (save_path / "Season 01" / "Subs" / "Show - 01.zh.ass") in moved_targets
        assert (save_path / "Season 02" / "Fonts" / "font.ttf") in moved_targets
        assert (save_path / "Season 01" / "Subs" / "Show - 01.zh.ass").exists()
        assert (save_path / "Season 02" / "Fonts" / "font.ttf").exists()

    _with_temp_dir("organize_action_plan_multi_season_extras", run)


def test_apply_action_plan_moves_skips_missing_or_same_path_items():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        original = save_path / "Show - S01E01.mkv"
        _touch(original)

        ops = _apply_action_plan_moves([
            {"original_path": str(original), "target_path": str(original)},
            {"original_path": str(save_path / "missing.mkv"), "target_path": str(save_path / "Season 01" / "missing.mkv")},
        ])

        assert ops == []
        assert original.exists()

    _with_temp_dir("organize_action_plan_skip", run)


def test_find_duplicate_target_paths_returns_conflicting_targets_once():
    duplicates = _find_duplicate_target_paths([
        {"target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E02.mkv"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E02.mkv"},
    ])

    assert duplicates == [
        r"C:\library\Show\Season 01\Show - S01E01.mkv",
        r"C:\library\Show\Season 01\Show - S01E02.mkv",
    ]


def test_duplicate_target_paths_should_stop_execute_before_any_move():
    duplicates = _find_duplicate_target_paths([
        {"original_path": r"C:\source\a.mkv", "target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
        {"original_path": r"C:\source\b.mkv", "target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
    ])

    try:
        if duplicates:
            sample_targets = "\n".join(duplicates[:3])
            raise HTTPException(
                status_code=400,
                detail=(
                    f"action_plan 存在重复 target_path（{len(duplicates)} 个），已停止执行。\n"
                    f"{sample_targets}"
                ),
            )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "重复 target_path" in exc.detail
        assert "Show - S01E01.mkv" in exc.detail
    else:
        raise AssertionError("expected duplicate target_path guard to raise HTTPException")


def test_find_duplicate_logical_targets_ignores_extension_difference():
    duplicates = _find_duplicate_logical_targets([
        {"target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E01.mp4"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E02.mkv"},
        {"target_path": r"C:\library\Show\Season 01\Show - S01E02.ass"},
    ])

    assert duplicates == [
        r"C:\library\Show\Season 01\Show - S01E01",
        r"C:\library\Show\Season 01\Show - S01E02",
    ]


def test_duplicate_logical_targets_should_stop_execute_before_any_move():
    duplicates = _find_duplicate_logical_targets([
        {"original_path": r"C:\source\a.mkv", "target_path": r"C:\library\Show\Season 01\Show - S01E01.mkv"},
        {"original_path": r"C:\source\b.mp4", "target_path": r"C:\library\Show\Season 01\Show - S01E01.mp4"},
    ])

    try:
        if duplicates:
            sample_targets = "\n".join(duplicates[:3])
            raise HTTPException(
                status_code=400,
                detail=(
                    f"action_plan 存在重复逻辑目标（{len(duplicates)} 个），已停止执行。\n"
                    f"{sample_targets}"
                ),
            )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "重复逻辑目标" in exc.detail
        assert "Show - S01E01" in exc.detail
    else:
        raise AssertionError("expected duplicate logical target guard to raise HTTPException")
