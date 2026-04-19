"""
Unit tests for ShadowNameManager
"""
import json
import os
import tempfile
import xml.etree.ElementTree as ET

import pytest

from shadow_name_manager import ShadowNameManager, ShadowNameEntry


@pytest.fixture
def tmp_library(tmp_path):
    """Create a temp media_library.json with sample data"""
    lib_path = str(tmp_path / "media_library.json")
    data = [
        {
            "file_path": "/videos/movie_a.mkv",
            "file_name": "movie_a.mkv",
            "folder_name": "videos",
        },
        {
            "file_path": "/videos/movie_b.mp4",
            "file_name": "movie_b.mp4",
            "folder_name": "videos",
        },
    ]
    with open(lib_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return lib_path


@pytest.fixture
def manager(tmp_library):
    return ShadowNameManager(library_path=tmp_library)


class TestGet:
    def test_returns_none_when_no_shadow_name(self, manager):
        result = manager.get("/videos/movie_a.mkv")
        assert result is None

    def test_returns_none_for_nonexistent_path(self, manager):
        result = manager.get("/nonexistent/path.mkv")
        assert result is None

    def test_returns_entry_after_set(self, manager):
        manager.set("/videos/movie_a.mkv", "Test Movie (2023)", "tmdb", 12345)
        entry = manager.get("/videos/movie_a.mkv")
        assert entry is not None
        assert entry.shadow_name == "Test Movie (2023)"
        assert entry.source == "tmdb"
        assert entry.tmdb_id == 12345


class TestSet:
    def test_set_shadow_name(self, manager):
        manager.set("/videos/movie_a.mkv", "My Movie", "manual", 100)
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "My Movie"
        assert entry.source == "manual"
        assert entry.tmdb_id == 100

    def test_set_overwrites_existing(self, manager):
        manager.set("/videos/movie_a.mkv", "First", "tmdb", 1)
        manager.set("/videos/movie_a.mkv", "Second", "manual", 2)
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "Second"
        assert entry.source == "manual"

    def test_set_nonexistent_path_does_nothing(self, manager):
        manager.set("/nonexistent.mkv", "Name", "manual")
        # Should not raise, just silently skip

    def test_set_persists_to_file(self, manager, tmp_library):
        manager.set("/videos/movie_a.mkv", "Persisted", "tmdb", 42)
        # Read raw JSON to verify persistence
        with open(tmp_library, "r", encoding="utf-8") as f:
            data = json.load(f)
        item = next(i for i in data if i["file_path"] == "/videos/movie_a.mkv")
        assert item["shadow_name"] == "Persisted"
        assert item["shadow_name_source"] == "tmdb"
        assert item["shadow_tmdb_id"] == 42


class TestAutoFill:
    def test_auto_fill_succeeds_when_no_shadow(self, manager):
        result = manager.auto_fill("/videos/movie_a.mkv", "Auto Name", "nfo", 99)
        assert result is True
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "Auto Name"
        assert entry.source == "nfo"

    def test_auto_fill_blocked_by_manual(self, manager):
        manager.set("/videos/movie_a.mkv", "Manual Name", "manual", 1)
        result = manager.auto_fill("/videos/movie_a.mkv", "Auto Name", "tmdb", 2)
        assert result is False
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "Manual Name"
        assert entry.source == "manual"

    def test_auto_fill_overwrites_non_manual(self, manager):
        manager.set("/videos/movie_a.mkv", "Old Auto", "nfo", 1)
        result = manager.auto_fill("/videos/movie_a.mkv", "New Auto", "tmdb", 2)
        assert result is True
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "New Auto"
        assert entry.source == "tmdb"

    def test_auto_fill_blocked_by_higher_priority(self, manager):
        """nfo(3) 不被 parsed(1) 覆盖"""
        manager.set("/videos/movie_a.mkv", "NFO Name", "nfo", 1)
        result = manager.auto_fill("/videos/movie_a.mkv", "Parsed Name", "parsed", 2)
        assert result is False
        entry = manager.get("/videos/movie_a.mkv")
        assert entry.shadow_name == "NFO Name"
        assert entry.source == "nfo"

    def test_auto_fill_nonexistent_path_returns_false(self, manager):
        result = manager.auto_fill("/nonexistent.mkv", "Name", "tmdb")
        assert result is False


class TestClear:
    def test_clear_removes_shadow_fields(self, manager, tmp_library):
        manager.set("/videos/movie_a.mkv", "To Clear", "tmdb", 10)
        manager.clear("/videos/movie_a.mkv")
        assert manager.get("/videos/movie_a.mkv") is None
        # Verify raw JSON has no shadow fields
        with open(tmp_library, "r", encoding="utf-8") as f:
            data = json.load(f)
        item = next(i for i in data if i["file_path"] == "/videos/movie_a.mkv")
        assert "shadow_name" not in item
        assert "shadow_name_source" not in item
        assert "shadow_tmdb_id" not in item

    def test_clear_nonexistent_path_does_nothing(self, manager):
        manager.clear("/nonexistent.mkv")
        # Should not raise


class TestGetSearchName:
    def test_returns_shadow_name_when_present(self, manager):
        manager.set("/videos/movie_a.mkv", "Shadow", "tmdb")
        assert manager.get_search_name("/videos/movie_a.mkv") == "Shadow"

    def test_returns_file_name_when_no_shadow(self, manager):
        assert manager.get_search_name("/videos/movie_a.mkv") == "movie_a.mkv"

    def test_returns_empty_for_nonexistent_path(self, manager):
        assert manager.get_search_name("/nonexistent.mkv") == ""


class TestBatchGenerate:
    def test_batch_with_nfo_files(self, tmp_path):
        """Test batch_generate extracts originaltitle from NFO files"""
        # Create a video file path and corresponding NFO
        video_dir = tmp_path / "movies"
        video_dir.mkdir()
        video_path = str(video_dir / "test_movie.mkv")
        nfo_path = str(video_dir / "test_movie.nfo")

        # Write a minimal NFO
        root = ET.Element("movie")
        ET.SubElement(root, "originaltitle").text = "The Test Movie"
        ET.SubElement(root, "year").text = "2023"
        uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uid.text = "555"
        tree = ET.ElementTree(root)
        tree.write(nfo_path, encoding="unicode")

        # Create library JSON
        lib_path = str(tmp_path / "media_library.json")
        data = [
            {"file_path": video_path, "file_name": "test_movie.mkv", "folder_name": "movies"},
        ]
        with open(lib_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        mgr = ShadowNameManager(library_path=lib_path)
        stats = mgr.batch_generate()
        assert stats["generated"] == 1
        assert stats["skipped"] == 0
        assert stats["failed"] == 0

        entry = mgr.get(video_path)
        assert entry is not None
        assert entry.shadow_name == "The Test Movie (2023)"
        assert entry.source == "nfo"
        assert entry.tmdb_id == 555

    def test_batch_skips_manual(self, tmp_path):
        """Manual shadow names are never overwritten by batch_generate"""
        lib_path = str(tmp_path / "media_library.json")
        data = [
            {
                "file_path": "/videos/manual.mkv",
                "file_name": "manual.mkv",
                "shadow_name": "My Manual Name",
                "shadow_name_source": "manual",
                "shadow_tmdb_id": 1,
            },
        ]
        with open(lib_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        mgr = ShadowNameManager(library_path=lib_path)
        stats = mgr.batch_generate()
        assert stats["skipped"] == 1
        entry = mgr.get("/videos/manual.mkv")
        assert entry.shadow_name == "My Manual Name"

    def test_batch_fails_when_no_nfo(self, tmp_path):
        """Items without NFO files count as failed"""
        lib_path = str(tmp_path / "media_library.json")
        data = [
            {"file_path": "/nonexistent/video.mkv", "file_name": "video.mkv"},
        ]
        with open(lib_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        mgr = ShadowNameManager(library_path=lib_path)
        stats = mgr.batch_generate()
        assert stats["failed"] == 1
        assert stats["generated"] == 0

    def test_batch_empty_library(self, tmp_path):
        lib_path = str(tmp_path / "media_library.json")
        with open(lib_path, "w") as f:
            json.dump([], f)
        mgr = ShadowNameManager(library_path=lib_path)
        stats = mgr.batch_generate()
        assert stats == {"generated": 0, "skipped": 0, "failed": 0}
