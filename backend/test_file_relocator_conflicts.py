"""file_relocator 冲突探测行为保护测试。"""

import os
import shutil
import uuid
import asyncio
from pathlib import Path

from file_relocator import CoexistPair, FileRelocator
from download_manager import DownloadTask


class RecordingRecycleBin:
    def __init__(self):
        self.paths = []

    def move_to_bin(self, path, task_id):
        self.paths.append(path)
        return {"path": path, "task_id": task_id}


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _with_temp_dir(name, test_fn):
    tmp_dir = Path(os.getcwd()) / f"{name}_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir()
    try:
        test_fn(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_detect_conflicts_keeps_whitelisted_new_files_out_of_old_candidates():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        old_file = save_path / "Show.S01E01.1080p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        new_extra = save_path / "[Group] Show S01 2160p" / "SPs" / "Show.SP01.mkv"
        _touch(old_file)
        _touch(new_file)
        _touch(new_extra)

        plan = {
            "plan": [
                {
                    "target_path": str(save_path / "Season 01" / "Show.S01E02.2160p.mkv"),
                    "mapped": {"season": 1, "episode": 2},
                }
            ]
        }
        whitelist = [
            "[Group] Show S01 2160p/Show.S01E02.2160p.mkv",
            "[Group] Show S01 2160p/SPs/Show.SP01.mkv",
        ]

        conflicts = FileRelocator(recycle_bin=None)._detect_conflicts_v2(
            plan=plan,
            target_base=str(save_path),
            whitelist=whitelist,
        )

        assert len(conflicts) == 1
        assert conflicts[0].old_file == str(old_file.resolve())
        assert conflicts[0].category == "video"
        assert conflicts[0].is_folder is False

    _with_temp_dir("relocator_conflict_file", run)


def test_detect_conflicts_records_same_season_old_folder_and_inner_video():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        old_folder = save_path / "Season 01"
        old_file = old_folder / "Show.S01E01.720p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(old_file)
        _touch(new_file)

        plan = {
            "plan": [
                {
                    "target_path": str(save_path / "Season 01" / "Show.S01E02.2160p.mkv"),
                    "mapped": {"season": 1, "episode": 2},
                }
            ]
        }

        conflicts = FileRelocator(recycle_bin=None)._detect_conflicts_v2(
            plan=plan,
            target_base=str(save_path),
            whitelist=["[Group] Show S01 2160p/Show.S01E02.2160p.mkv"],
        )

        old_paths = {conflict.old_file for conflict in conflicts}
        categories = {conflict.old_file: conflict.category for conflict in conflicts}

        assert len(conflicts) == 2
        assert str(old_folder.resolve()) in old_paths
        assert str(old_file.resolve()) in old_paths
        assert categories[str(old_folder.resolve())] == "folder"
        assert categories[str(old_file.resolve())] == "video"

    _with_temp_dir("relocator_conflict_folder", run)


def test_recycle_old_files_records_video_sidecars_and_safe_dir_nfos():
    def run(tmp_dir):
        show_dir = tmp_dir / "Show"
        season_dir = show_dir / "Season 01"
        old_video = season_dir / "Show.S01E01.1080p.mkv"
        old_base = season_dir / "Show.S01E01.1080p"
        expected_files = [
            old_video,
            Path(str(old_base) + ".nfo"),
            season_dir / "Show.S01E01.1080p-poster.jpg",
            season_dir / "Show.S01E01.1080p-thumb.jpg",
            season_dir / "Show.S01E01.1080p-fanart.jpg",
            season_dir / "movie.nfo",
            season_dir / "season.nfo",
            show_dir / "season01-poster.jpg",
            show_dir / "season01-fanart.jpg",
            show_dir / "season01-thumb.jpg",
            show_dir / "season01-banner.jpg",
        ]
        protected_tvshow = season_dir / "tvshow.nfo"
        unused_clearlogo = season_dir / "Show.S01E01.1080p-clearlogo.png"

        for path in expected_files + [protected_tvshow, unused_clearlogo]:
            _touch(path)

        recycle_bin = RecordingRecycleBin()
        result = FileRelocator(recycle_bin=recycle_bin)._recycle_old_files(
            CoexistPair(new_file=str(show_dir / "Season 01" / "Show.S01E02.2160p.mkv"), old_file=str(old_video)),
            task_id="task-1",
        )

        moved_paths = set(recycle_bin.paths)
        assert result is True
        assert moved_paths == {str(path) for path in expected_files}
        assert str(protected_tvshow) not in moved_paths
        assert str(unused_clearlogo) not in moved_paths

    _with_temp_dir("relocator_recycle_sidecars", run)


def test_confirm_replace_falls_back_to_disk_scanned_whitelist_when_plan_missing_it():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        old_file = save_path / "Show.S01E01.1080p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(old_file)
        _touch(new_file)

        recycle_bin = RecordingRecycleBin()
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None):
            calls.append(
                {
                    "path": path,
                    "dry_run": dry_run,
                    "use_ai": use_ai,
                    "whitelist": list(whitelist) if whitelist else None,
                }
            )
            return {"steps": {"rename": 1}}

        relocator = FileRelocator(recycle_bin=recycle_bin, run_pipeline_fn=fake_run_pipeline)
        task = DownloadTask(
            id="task-1",
            save_path=str(save_path),
            download_dir=str(save_path / "[Group] Show S01 2160p"),
        )
        plan = {
            "plan": [
                {
                    "target_path": str(save_path / "Season 01" / "Show.S01E02.2160p.mkv"),
                    "mapped": {"season": 1, "episode": 2},
                }
            ]
        }

        result = asyncio.run(relocator.confirm_replace(task, plan))

        assert result.success is True
        assert result.status == "archived"
        assert calls == [
            {
                "path": str(task.download_dir),
                "dry_run": False,
                "use_ai": False,
                "whitelist": None,
            }
        ]
        assert recycle_bin.paths == [str(old_file)]

    _with_temp_dir("relocator_confirm_replace_fallback", run)
