"""手动重命名入口的文件副作用基线测试。"""

import shutil
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

import pytest

import shared
from routes import rename as rename_route
from test_support.fake_library_store import LibraryMutationContract


@pytest.fixture(autouse=True)
def _allow_fixture_dir(monkeypatch):
    """把夹具所在目录声明进路径白名单（理由见 test_batch_manage_side_effects）"""
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [str(Path(__file__).parent)])
    shared.invalidate_allowed_roots_cache()
    yield
    shared.invalidate_allowed_roots_cache()


class FakeConfigManager(LibraryMutationContract):
    def __init__(self, library, nas_root):
        self.library = library
        self.saved_library = None
        self.config = SimpleNamespace(scan_paths=[str(nas_root)])

    def load_library(self):
        return self.library

    def save_library(self, data):
        self.saved_library = data


def make_temp_root():
    root = Path(__file__).parent / f"_tmp_rename_side_effects_{uuid4().hex}"
    root.mkdir()
    return root


def test_rename_video_file_syncs_sidecars_and_library(monkeypatch):
    temp_root = make_temp_root()
    try:
        video = temp_root / "Old Name.mkv"
        nfo = temp_root / "Old Name.nfo"
        poster = temp_root / "Old Name-poster.jpg"
        video.write_text("video", encoding="utf-8")
        nfo.write_text("nfo", encoding="utf-8")
        poster.write_bytes(b"poster")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_type": "season",
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        result = rename_route.rename_item(str(video), "New Name.mkv")

        new_video = temp_root / "New Name.mkv"
        assert result["new_path"] == str(new_video)
        assert new_video.exists()
        assert not video.exists()
        assert (temp_root / "New Name.nfo").exists()
        assert (temp_root / "New Name-poster.jpg").exists()
        assert not nfo.exists()
        assert not poster.exists()
        assert fake_config.saved_library[0]["file_path"] == str(new_video)
        assert fake_config.saved_library[0]["file_name"] == "New Name.mkv"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_rename_single_video_movie_folder_syncs_video_sidecars_and_library(monkeypatch):
    temp_root = make_temp_root()
    try:
        folder = temp_root / "Old Movie"
        folder.mkdir()
        video = folder / "source.mkv"
        nfo = folder / "source.nfo"
        poster = folder / "source-poster.jpg"
        video.write_text("video", encoding="utf-8")
        nfo.write_text("nfo", encoding="utf-8")
        poster.write_bytes(b"poster")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": folder.name,
                "folder_type": "movie",
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        result = rename_route.rename_item(str(folder), "New Movie")

        new_folder = temp_root / "New Movie"
        new_video = new_folder / "New Movie.mkv"
        assert result["new_path"] == str(new_folder)
        assert new_folder.exists()
        assert not folder.exists()
        assert new_video.exists()
        assert (new_folder / "New Movie.nfo").exists()
        assert (new_folder / "New Movie-poster.jpg").exists()
        assert not (new_folder / "source.nfo").exists()
        assert not (new_folder / "source-poster.jpg").exists()
        assert fake_config.saved_library[0]["file_path"] == str(new_video)
        assert fake_config.saved_library[0]["file_name"] == "New Movie.mkv"
        assert fake_config.saved_library[0]["folder_name"] == "New Movie"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
