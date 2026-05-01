"""file_relocator 冲突探测行为保护测试。"""

import os
import shutil
import uuid
import asyncio
from pathlib import Path

from file_relocator import CoexistPair, FileRelocator
from download_manager import DownloadTask
from recycle_bin import RecycleBin


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
        assert conflicts[0].old_file == os.path.abspath(str(old_file))
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
        old_folder_path = os.path.abspath(str(old_folder))
        old_file_path = os.path.abspath(str(old_file))
        assert old_folder_path in old_paths
        assert old_file_path in old_paths
        assert categories[old_folder_path] == "folder"
        assert categories[old_file_path] == "video"

    _with_temp_dir("relocator_conflict_folder", run)


def test_detect_conflicts_ignores_target_folder_created_by_current_plan():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        current_target_dir = save_path / "Season 01"
        current_target_file = current_target_dir / "Show - S01E02.mkv"
        _touch(current_target_file)

        plan = {
            "plan": [
                {
                    "target_path": str(current_target_file),
                    "mapped": {"season": 1, "episode": 2},
                }
            ]
        }

        conflicts = FileRelocator(recycle_bin=None)._detect_conflicts_v2(
            plan=plan,
            target_base=str(save_path),
            whitelist=["[Group] Show/Show.02.1080p.mkv"],
        )

        assert conflicts == []

    _with_temp_dir("relocator_current_plan_folder", run)


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


def test_recycle_old_files_moves_files_into_real_recycle_bin_and_persists_metadata():
    def run(tmp_dir):
        show_dir = tmp_dir / "Show"
        season_dir = show_dir / "Season 01"
        recycle_dir = tmp_dir / ".recycle"
        meta_path = tmp_dir / "backend-meta" / "recycle_bin.json"
        old_video = season_dir / "Show.S01E01.1080p.mkv"
        sidecar_nfo = season_dir / "Show.S01E01.1080p.nfo"
        season_nfo = season_dir / "season.nfo"

        for path in [old_video, sidecar_nfo, season_nfo]:
            _touch(path)

        recycle_bin = RecycleBin(str(recycle_dir), retention_days=7, meta_path=str(meta_path))
        relocator = FileRelocator(recycle_bin=recycle_bin)

        result = relocator._recycle_old_files(
            CoexistPair(
                new_file=str(show_dir / "Season 01" / "Show.S01E02.2160p.mkv"),
                old_file=str(old_video),
            ),
            task_id="task-1",
        )

        assert result is True
        assert not old_video.exists()
        assert not sidecar_nfo.exists()
        assert not season_nfo.exists()

        reloaded = RecycleBin(str(recycle_dir), retention_days=7, meta_path=str(meta_path))
        entries = {entry.original_path: entry for entry in reloaded.list_entries()}

        assert set(entries) == {str(old_video), str(sidecar_nfo), str(season_nfo)}
        for original_path, entry in entries.items():
            assert Path(entry.recycle_path).exists()
            assert Path(entry.recycle_path).parent == recycle_dir
            assert Path(entry.recycle_path).name.startswith("task-1_")
            assert Path(entry.recycle_path).name.endswith(Path(original_path).name)
            assert entry.task_id == "task-1"

        assert meta_path.exists()

    _with_temp_dir("relocator_real_recycle_bin", run)


def test_recycle_old_files_defaults_to_same_library_root_instead_of_backend_local_dir():
    def run(tmp_dir):
        media_root = tmp_dir / "media-root"
        show_dir = media_root / "Show"
        season_dir = show_dir / "Season 01"
        meta_path = tmp_dir / "backend-meta" / "recycle_bin.json"
        old_video = season_dir / "Show.S01E01.1080p.mkv"
        sidecar_nfo = season_dir / "Show.S01E01.1080p.nfo"
        season_nfo = season_dir / "season.nfo"

        for path in [old_video, sidecar_nfo, season_nfo]:
            _touch(path)

        recycle_bin = RecycleBin(
            retention_days=7,
            library_roots=[str(media_root)],
            meta_path=str(meta_path),
        )
        relocator = FileRelocator(recycle_bin=recycle_bin)

        result = relocator._recycle_old_files(
            CoexistPair(
                new_file=str(show_dir / "Season 01" / "Show.S01E02.2160p.mkv"),
                old_file=str(old_video),
            ),
            task_id="task-1",
        )

        recycle_dir = media_root / "#recycle_bin"
        reloaded = RecycleBin(
            retention_days=7,
            library_roots=[str(media_root)],
            meta_path=str(meta_path),
        )
        entries = {entry.original_path: entry for entry in reloaded.list_entries()}

        assert result is True
        assert recycle_dir.exists()
        assert set(entries) == {str(old_video), str(sidecar_nfo), str(season_nfo)}
        for entry in entries.values():
            assert Path(entry.recycle_path).parent == recycle_dir
        assert not (tmp_dir / "backend" / "recycle_bin").exists()
        assert meta_path.exists()

    _with_temp_dir("relocator_recycle_same_library_root", run)


def test_confirm_replace_falls_back_to_disk_scanned_whitelist_when_plan_missing_it():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        old_file = save_path / "Show.S01E01.1080p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(old_file)
        _touch(new_file)

        recycle_bin = RecordingRecycleBin()
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(
                {
                    "path": path,
                    "dry_run": dry_run,
                    "use_ai": use_ai,
                    "whitelist": list(whitelist) if whitelist else None,
                    "action_plan": action_plan,
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
                "path": str(task.save_path),
                "dry_run": False,
                "use_ai": False,
                "whitelist": None,
                "action_plan": plan,
            }
        ]
        assert recycle_bin.paths == [str(old_file)]

    _with_temp_dir("relocator_confirm_replace_fallback", run)


def test_confirm_replace_prefers_save_path_for_execute_plan():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        download_dir = tmp_dir / "downloads" / "task-1"
        old_file = save_path / "Show.S01E01.1080p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(old_file)
        _touch(new_file)
        download_dir.mkdir(parents=True, exist_ok=True)

        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(
                {
                    "path": path,
                    "dry_run": dry_run,
                    "use_ai": use_ai,
                    "whitelist": list(whitelist) if whitelist else None,
                    "action_plan": action_plan,
                }
            )
            return {"steps": {"rename": 1}}

        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)
        task = DownloadTask(
            id="task-1",
            save_path=str(save_path),
            download_dir=str(download_dir),
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
        assert calls == [
            {
                "path": str(save_path),
                "dry_run": False,
                "use_ai": False,
                "whitelist": None,
                "action_plan": plan,
            }
        ]

    _with_temp_dir("relocator_execute_save_path", run)


def test_relocate_fails_when_pipeline_is_not_ready():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        save_path.mkdir(parents=True, exist_ok=True)
        task = DownloadTask(id="task-1", save_path=str(save_path))

        result = asyncio.run(FileRelocator(recycle_bin=RecordingRecycleBin()).relocate(task))

        assert result.success is False
        assert result.status == "failed"
        assert result.error == "整理引擎未就绪"

    _with_temp_dir("relocator_no_pipeline", run)


def test_relocate_fails_when_save_path_is_not_ready():
    def run(tmp_dir):
        save_path = tmp_dir / "missing"
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(path)
            return {"plan": []}

        task = DownloadTask(id="task-1", save_path=str(save_path))
        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)

        result = asyncio.run(relocator.relocate(task))

        assert result.success is False
        assert result.status == "failed"
        assert result.error == f"下载目录尚未就绪: {save_path}"
        assert calls == []

    _with_temp_dir("relocator_missing_save_path", run)


def test_relocate_fails_when_dry_run_returns_empty_plan():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(new_file)
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(
                {
                    "path": path,
                    "dry_run": dry_run,
                    "use_ai": use_ai,
                    "whitelist": list(whitelist) if whitelist else None,
                    "action_plan": action_plan,
                }
            )
            return {}

        task = DownloadTask(id="task-1", save_path=str(save_path))
        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)

        result = asyncio.run(relocator.relocate(task))

        assert result.success is False
        assert result.status == "failed"
        assert result.error == "无法识别新下载的文件结构"
        assert calls == [
            {
                "path": str(save_path),
                "dry_run": True,
                "use_ai": True,
                "whitelist": [os.path.join("[Group] Show S01 2160p", "Show.S01E02.2160p.mkv")],
                "action_plan": None,
            }
        ]

    _with_temp_dir("relocator_empty_plan", run)


def test_confirm_replace_stops_when_recycle_old_files_fails():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        old_file = save_path / "Show.S01E01.1080p.mkv"
        new_file = save_path / "[Group] Show S01 2160p" / "Show.S01E02.2160p.mkv"
        _touch(old_file)
        _touch(new_file)
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(path)
            return {"steps": {"rename": 1}}

        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)
        relocator._recycle_old_files = lambda pair, task_id: False
        task = DownloadTask(id="task-1", save_path=str(save_path))
        plan = {
            "plan": [
                {
                    "target_path": str(save_path / "Season 01" / "Show.S01E02.2160p.mkv"),
                    "mapped": {"season": 1, "episode": 2},
                }
            ]
        }

        result = asyncio.run(relocator.confirm_replace(task, plan))

        assert result.success is False
        assert result.status == "failed"
        assert result.error == f"旧资源入回收站失败: {old_file}"
        assert calls == []

    _with_temp_dir("relocator_confirm_replace_recycle_fail", run)


def test_cancel_replace_recycles_all_files_under_sandbox():
    def run(tmp_dir):
        sandbox = tmp_dir / "downloads" / "task-1"
        nested_file = sandbox / "subdir" / "new-file.srt"
        video_file = sandbox / "new-file.mkv"
        _touch(nested_file)
        _touch(video_file)

        recycle_bin = RecordingRecycleBin()
        task = DownloadTask(id="task-1", download_dir=str(sandbox))

        result = FileRelocator(recycle_bin=recycle_bin).cancel_replace(task)

        assert result.success is True
        assert result.status == "cancelled"
        assert result.relocated_count == 2
        assert set(recycle_bin.paths) == {str(video_file), str(nested_file)}

    _with_temp_dir("relocator_cancel_replace", run)


def test_execute_plan_falls_back_to_download_dir_when_save_path_is_empty():
    def run(tmp_dir):
        download_dir = tmp_dir / "downloads" / "task-1"
        download_dir.mkdir(parents=True, exist_ok=True)
        calls = []

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            calls.append(
                {
                    "path": path,
                    "dry_run": dry_run,
                    "use_ai": use_ai,
                    "whitelist": whitelist,
                    "action_plan": action_plan,
                }
            )
            return {"steps": {"rename": 2, "nfo": {"nfo_written": 1}, "skip": "ignored"}}

        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)
        task = DownloadTask(id="task-1", save_path="", download_dir=str(download_dir))
        plan = {"plan": [{"target_path": str(download_dir / "Season 01" / "Show.S01E02.2160p.mkv")}]}

        result = asyncio.run(relocator._execute_plan(task, plan))

        assert result.success is True
        assert result.status == "archived"
        assert result.relocated_count == 3
        assert calls == [
            {
                "path": str(download_dir),
                "dry_run": False,
                "use_ai": False,
                "whitelist": None,
                "action_plan": plan,
            }
        ]

    _with_temp_dir("relocator_execute_download_dir_fallback", run)


def test_execute_plan_returns_failed_when_pipeline_raises():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        save_path.mkdir(parents=True, exist_ok=True)

        async def fake_run_pipeline(path, dry_run, use_ai, whitelist=None, action_plan=None):
            raise RuntimeError("boom")

        relocator = FileRelocator(recycle_bin=RecordingRecycleBin(), run_pipeline_fn=fake_run_pipeline)
        task = DownloadTask(id="task-1", save_path=str(save_path))

        result = asyncio.run(relocator._execute_plan(task, {"plan": []}))

        assert result.success is False
        assert result.status == "failed"
        assert result.error == "整理执行失败: boom"

    _with_temp_dir("relocator_execute_fail", run)


def test_archive_both_returns_archived_when_conflicts_are_empty():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        save_path.mkdir(parents=True, exist_ok=True)
        task = DownloadTask(id="task-1", save_path=str(save_path))

        result = asyncio.run(FileRelocator(recycle_bin=RecordingRecycleBin()).archive_both(task, []))

        assert result.success is True
        assert result.status == "archived"
        assert result.relocated_count == 0

    _with_temp_dir("relocator_archive_both_empty", run)


def test_archive_both_renames_old_files_into_backup_dir_and_avoids_name_collision():
    def run(tmp_dir):
        save_path = tmp_dir / "Show"
        save_path.mkdir(parents=True, exist_ok=True)
        old_file = save_path / "Show.S01E01.1080p.mkv"
        backup_dir = save_path / f"[旧资源备份] - {save_path.name}"
        existing_backup = backup_dir / old_file.name
        _touch(old_file)
        _touch(existing_backup)

        task = DownloadTask(id="task-1", save_path=str(save_path))
        conflicts = [CoexistPair(new_file=str(save_path / "Season 01" / "Show.S01E02.2160p.mkv"), old_file=str(old_file))]

        result = asyncio.run(FileRelocator(recycle_bin=RecordingRecycleBin()).archive_both(task, conflicts))

        moved_files = list(backup_dir.glob("Show.S01E01.1080p*"))
        moved_names = {path.name for path in moved_files}

        assert result.success is True
        assert result.status == "archived"
        assert old_file.exists() is False
        assert old_file.name in moved_names
        assert any(name.startswith("Show.S01E01.1080p_") and name.endswith(".mkv") for name in moved_names)

    _with_temp_dir("relocator_archive_both_collision", run)


def test_cancel_replace_fails_when_sandbox_directory_is_missing():
    def run(tmp_dir):
        sandbox = tmp_dir / "downloads" / "task-1"
        task = DownloadTask(id="task-1", download_dir=str(sandbox))

        result = FileRelocator(recycle_bin=RecordingRecycleBin()).cancel_replace(task)

        assert result.success is False
        assert result.status == "failed"
        assert result.error == "沙盒目录不存在"

    _with_temp_dir("relocator_cancel_replace_missing", run)


def test_recycle_old_files_treats_missing_old_file_as_success_without_recycling():
    def run(tmp_dir):
        missing_old = tmp_dir / "Show" / "Show.S01E01.1080p.mkv"
        recycle_bin = RecordingRecycleBin()

        result = FileRelocator(recycle_bin=recycle_bin)._recycle_old_files(
            CoexistPair(new_file=str(tmp_dir / "Show" / "Season 01" / "Show.S01E02.2160p.mkv"), old_file=str(missing_old)),
            task_id="task-1",
        )

        assert result is True
        assert recycle_bin.paths == []

    _with_temp_dir("relocator_recycle_missing_old", run)
