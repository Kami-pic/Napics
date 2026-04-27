import os
import shutil
import uuid
from pathlib import Path

from routes.organize import _apply_action_plan_moves


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
