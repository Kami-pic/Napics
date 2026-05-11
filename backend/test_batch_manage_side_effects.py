"""批量管理入口的文件副作用基线测试。"""

import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from routes import tools as tools_route


class FakeConfigManager:
    def __init__(self, library, nas_root):
        self.library = library
        self.saved_library = None
        self.excluded_paths = None
        self.config = SimpleNamespace(nas_paths=[str(nas_root)])

    def load_library(self):
        return self.library

    def save_library(self, data):
        self.saved_library = data

    def add_excluded_paths(self, paths):
        self.excluded_paths = paths


class FakeRecycleBin:
    def __init__(self, recycle_root):
        self.recycle_root = recycle_root
        self.entries = []

    def move_to_bin(self, path, reason):
        source = Path(path)
        target = self.recycle_root / source.name
        shutil.move(str(source), str(target))
        entry = {"path": str(path), "reason": reason, "recycled_path": str(target)}
        self.entries.append(entry)
        return entry


def make_temp_root():
    root = Path(__file__).parent / f"_tmp_batch_manage_side_effects_{uuid4().hex}"
    root.mkdir()
    return root


def test_batch_move_loose_movie_wraps_video_sidecars_and_library(monkeypatch):
    temp_root = make_temp_root()
    try:
        source_dir = temp_root / "电影"
        target_dir = temp_root / "目标"
        source_dir.mkdir()
        video = source_dir / "Old Name.mkv"
        nfo = source_dir / "Old Name.nfo"
        poster = source_dir / "Old Name-poster.jpg"
        video.write_text("video", encoding="utf-8")
        nfo.write_text("nfo", encoding="utf-8")
        poster.write_bytes(b"poster")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": "电影",
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(tools_route, "config_m", fake_config)
        monkeypatch.setattr(tools_route, "_get_category_from_path", lambda _path: "movie")

        result = tools_route.batch_manage(
            tools_route.BatchRequest(action="move", paths=[str(video)], target_dir=str(target_dir))
        )

        moved_dir = target_dir / "Old Name"
        moved_video = moved_dir / "Old Name.mkv"
        assert result["failed"] == []
        assert result["success"] == [str(video)]
        assert moved_dir.exists()
        assert moved_video.exists()
        assert (moved_dir / "Old Name.nfo").exists()
        assert (moved_dir / "Old Name-poster.jpg").exists()
        assert not video.exists()
        assert not nfo.exists()
        assert not poster.exists()
        assert fake_config.saved_library[0]["file_path"] == str(moved_video)
        assert fake_config.saved_library[0]["file_name"] == "Old Name.mkv"
        assert fake_config.saved_library[0]["folder_name"] == str(Path("目标") / "Old Name")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_batch_move_loose_tv_video_keeps_flat_target_and_syncs_sidecars(monkeypatch):
    temp_root = make_temp_root()
    try:
        source_dir = temp_root / "动画番"
        target_dir = temp_root / "目标"
        source_dir.mkdir()
        video = source_dir / "Show S01E01.mkv"
        nfo = source_dir / "Show S01E01.nfo"
        poster = source_dir / "Show S01E01-poster.jpg"
        video.write_text("video", encoding="utf-8")
        nfo.write_text("nfo", encoding="utf-8")
        poster.write_bytes(b"poster")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": "动画番",
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(tools_route, "config_m", fake_config)
        monkeypatch.setattr(tools_route, "_get_category_from_path", lambda _path: "tv")

        result = tools_route.batch_manage(
            tools_route.BatchRequest(action="move", paths=[str(video)], target_dir=str(target_dir))
        )

        moved_video = target_dir / "Show S01E01.mkv"
        assert result["failed"] == []
        assert result["success"] == [str(video)]
        assert moved_video.exists()
        assert (target_dir / "Show S01E01.nfo").exists()
        assert (target_dir / "Show S01E01-poster.jpg").exists()
        assert not (target_dir / "Show S01E01").exists()
        assert not video.exists()
        assert not nfo.exists()
        assert not poster.exists()
        assert fake_config.saved_library[0]["file_path"] == str(moved_video)
        assert fake_config.saved_library[0]["file_name"] == "Show S01E01.mkv"
        assert fake_config.saved_library[0]["folder_name"] == "目标"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_batch_delete_loose_video_uses_recycle_bin_and_removes_library(monkeypatch):
    temp_root = make_temp_root()
    try:
        source_dir = temp_root / "电影"
        recycle_root = temp_root / "recycle"
        source_dir.mkdir()
        recycle_root.mkdir()
        video = source_dir / "Delete Me.mkv"
        video.write_text("video", encoding="utf-8")

        library = [
            {"file_path": str(video), "file_name": video.name, "folder_name": "电影"},
            {"file_path": str(source_dir / "Keep Me.mkv"), "file_name": "Keep Me.mkv", "folder_name": "电影"},
        ]
        fake_config = FakeConfigManager(library, temp_root)
        fake_recycle = FakeRecycleBin(recycle_root)
        monkeypatch.setattr(tools_route, "config_m", fake_config)
        monkeypatch.setattr(tools_route, "_get_recycle_bin", lambda: fake_recycle)

        result = tools_route.batch_manage(
            tools_route.BatchRequest(action="delete", paths=[str(video)])
        )

        assert result["failed"] == []
        assert str(video) in result["success"]
        assert not video.exists()
        assert (recycle_root / "Delete Me.mkv").exists()
        assert fake_recycle.entries == [
            {
                "path": str(video),
                "reason": "batch_delete",
                "recycled_path": str(recycle_root / "Delete Me.mkv"),
            }
        ]
        assert fake_config.saved_library == [library[1]]
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_batch_remove_only_updates_library_and_excluded_paths(monkeypatch):
    temp_root = make_temp_root()
    try:
        source_dir = temp_root / "电影"
        source_dir.mkdir()
        video = source_dir / "Remove Only.mkv"
        video.write_text("video", encoding="utf-8")

        library = [
            {"file_path": str(video), "file_name": video.name, "folder_name": "电影"},
            {"file_path": str(source_dir / "Keep Me.mkv"), "file_name": "Keep Me.mkv", "folder_name": "电影"},
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(tools_route, "config_m", fake_config)

        result = tools_route.batch_manage(
            tools_route.BatchRequest(action="remove", paths=[str(video)])
        )

        assert result["failed"] == []
        assert result["success"] == [str(video)]
        assert video.exists()
        assert fake_config.saved_library == [library[1]]
        assert set(fake_config.excluded_paths) == {str(video), str(source_dir)}
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_batch_copy_loose_video_copies_sidecars_and_keeps_library(monkeypatch):
    temp_root = make_temp_root()
    try:
        source_dir = temp_root / "电影"
        target_dir = temp_root / "目标"
        source_dir.mkdir()
        video = source_dir / "Copy Me.mkv"
        nfo = source_dir / "Copy Me.nfo"
        poster = source_dir / "Copy Me-poster.jpg"
        fanart = source_dir / "Copy Me-fanart.jpg"
        video.write_text("video", encoding="utf-8")
        nfo.write_text("nfo", encoding="utf-8")
        poster.write_bytes(b"poster")
        fanart.write_bytes(b"fanart")

        library = [{"file_path": str(video), "file_name": video.name, "folder_name": "电影"}]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(tools_route, "config_m", fake_config)

        result = tools_route.batch_manage(
            tools_route.BatchRequest(action="copy", paths=[str(video)], target_dir=str(target_dir))
        )

        assert result["failed"] == []
        assert result["success"] == [str(video)]
        assert video.exists()
        assert nfo.exists()
        assert poster.exists()
        assert fanart.exists()
        assert (target_dir / "Copy Me.mkv").exists()
        assert (target_dir / "Copy Me.nfo").exists()
        assert (target_dir / "Copy Me-poster.jpg").exists()
        assert (target_dir / "Copy Me-fanart.jpg").exists()
        assert fake_config.saved_library is None
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
