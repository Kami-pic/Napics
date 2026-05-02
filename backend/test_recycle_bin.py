"""recycle_bin 动态落盘行为测试。"""

import shutil
import uuid
from pathlib import Path

from recycle_bin import RecycleBin


def _touch(path: Path, content: bytes = b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _with_temp_dir(name, test_fn):
    tmp_dir = Path.cwd() / f"{name}_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir()
    try:
        test_fn(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_move_to_bin_falls_back_to_source_parent_when_path_is_outside_library_roots():
    def run(tmp_dir):
        download_dir = tmp_dir / "downloads" / "task-1"
        file_path = download_dir / "Show.S01E01.mkv"
        meta_path = tmp_dir / "backend-meta" / "recycle_bin.json"
        _touch(file_path)

        recycle_bin = RecycleBin(
            retention_days=7,
            library_roots=[str(tmp_dir / "media-root")],
            meta_path=str(meta_path),
        )
        entry = recycle_bin.move_to_bin(str(file_path), task_id="task-1")

        expected_dir = download_dir / ".recycle_bins"
        assert entry is not None
        assert expected_dir.exists()
        assert Path(entry.recycle_path).parent == expected_dir
        assert meta_path.exists()

    _with_temp_dir("recycle_bin_parent_fallback", run)


def test_move_to_bin_uses_hidden_sibling_recycle_dir_for_library_root():
    def run(tmp_dir):
        media_root = tmp_dir / "TV"
        file_path = media_root / "Show" / "Season 01" / "Show.S01E01.mkv"
        meta_path = tmp_dir / "backend-meta" / "recycle_bin.json"
        _touch(file_path)

        recycle_bin = RecycleBin(
            retention_days=7,
            library_roots=[str(media_root)],
            meta_path=str(meta_path),
        )
        entry = recycle_bin.move_to_bin(str(file_path), task_id="task-1")

        expected_dir = tmp_dir / ".recycle_bins" / "TV"
        assert entry is not None
        assert expected_dir.exists()
        assert Path(entry.recycle_path).parent == expected_dir
        assert meta_path.exists()

    _with_temp_dir("recycle_bin_hidden_sibling_root", run)


def test_cleanup_expired_removes_recycled_directory_entries():
    def run(tmp_dir):
        media_root = tmp_dir / "media-root"
        source_dir = media_root / "Show" / "Season 01"
        nested_video = source_dir / "Show.S01E01.mkv"
        meta_path = tmp_dir / "backend-meta" / "recycle_bin.json"
        _touch(nested_video)

        recycle_bin = RecycleBin(
            retention_days=-1,
            library_roots=[str(media_root)],
            meta_path=str(meta_path),
        )
        entry = recycle_bin.move_to_bin(str(source_dir), task_id="task-1")

        assert entry is not None
        recycled_dir = Path(entry.recycle_path)
        assert recycled_dir.exists()

        cleaned = recycle_bin.cleanup_expired()

        assert cleaned == 1
        assert not recycled_dir.exists()
        assert recycle_bin.list_entries() == []

    _with_temp_dir("recycle_bin_cleanup_directory", run)
