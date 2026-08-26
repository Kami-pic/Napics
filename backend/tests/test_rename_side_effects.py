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


def test_rename_folder_keeps_video_inside_when_frontend_sends_full_path(monkeypatch):
    """前端改文件夹名时传的是**整条新路径**，视频不能因此被搬出封装夹。

    ShadowNameSection 的文件夹分支拼的是 `parentDir + "\\" + newName`，
    所以 new_name 到后端手里长这样：`…\\合集\\新片名`。
    后端拿它去 `os.path.join(new_path, new_name + ext)` 算新视频路径时，
    Windows 的 join 遇到绝对路径会直接返回后者 —— 视频于是被 rename 到
    `…\\合集\\新片名.mkv`，脱离封装夹落到合集目录里，封装夹变成空壳。
    这就是「合集聚合文件夹下改名后封装文件夹名会出乱码」看到的结构错乱。
    """
    temp_root = make_temp_root()
    try:
        collection = temp_root / "某某合集"
        collection.mkdir()
        folder = collection / "旧片名"
        folder.mkdir()
        video = folder / "旧片名.某发布组.1080p.mkv"
        video.write_text("video", encoding="utf-8")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": str(Path("某某合集") / "旧片名"),
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        # 前端传的就是这个形状
        new_name_from_frontend = str(collection / "新片名")
        rename_route.rename_item(str(folder), new_name_from_frontend)

        new_folder = collection / "新片名"
        assert new_folder.is_dir(), "封装夹应该被改名"
        assert not folder.exists()
        # 视频必须还在封装夹里，而不是被搬到合集目录下
        assert not (collection / "新片名.mkv").exists(), "视频被搬出了封装夹"
        assert (new_folder / "新片名.mkv").exists(), "视频应留在封装夹内并跟着改名"

        saved = fake_config.saved_library[0]
        assert saved["file_path"] == str(new_folder / "新片名.mkv")
        assert saved["folder_name"] == str(Path("某某合集") / "新片名")


    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_rename_folder_name_uses_owning_scan_root_not_the_first(monkeypatch):
    """folder_name 要按该文件真正所属的扫描根算，不是写死 scan_paths[0]。

    写死第一个的后果是 `os.path.relpath` 算出 `..\\..\\` 开头的相对路径，
    建树时 `..` 会变成一个节点名 —— 用户看到的就是外层文件夹名变成一串
    看不懂的东西。
    """
    temp_root = make_temp_root()
    try:
        first_root = temp_root / "第一个扫描路径"
        second_root = temp_root / "第二个扫描路径"
        first_root.mkdir()
        second_root.mkdir()
        folder = second_root / "电影" / "旧片名"
        folder.mkdir(parents=True)
        video = folder / "旧片名.mkv"
        video.write_text("video", encoding="utf-8")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": str(Path("电影") / "旧片名"),
            }
        ]
        fake_config = FakeConfigManager(library, first_root)
        # 两个扫描路径，目标文件在第二个下面
        fake_config.config = SimpleNamespace(
            scan_paths=[str(first_root), str(second_root)], media_libraries=[]
        )
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        rename_route.rename_item(str(folder), "新片名")

        saved = fake_config.saved_library[0]
        assert saved["folder_name"] == str(Path("电影") / "新片名")
        assert ".." not in saved["folder_name"]
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_rename_episode_does_not_rename_season_folder(monkeypatch):
    """只有 1 集的季目录不能被联动改名。

    「目录内 1 个视频 0 个子目录」这个判据本来是用来识别 movie 单片封装夹的，
    但新番刚下第一集时季目录同样满足它，于是 `Season 01` 会被改成集文件名。
    原来唯一的保护是读库里的 folder_type，而那个字段从来没被写进库。
    """
    temp_root = make_temp_root()
    try:
        season = temp_root / "某剧" / "Season 01"
        season.mkdir(parents=True)
        video = season / "raw.mkv"
        video.write_text("video", encoding="utf-8")

        library = [{"file_path": str(video), "file_name": video.name}]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        rename_route.rename_item(str(video), "某剧 - S01E01.mkv")

        assert season.is_dir(), "季目录不该被改名"
        assert (season / "某剧 - S01E01.mkv").exists()
        assert not (temp_root / "某剧" / "某剧 - S01E01").exists()
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def test_rename_movie_in_wrapper_folder_still_renames_folder(monkeypatch):
    """movie 单片封装夹的联动改名必须照旧生效 —— 这是这段逻辑的本来用途。"""
    temp_root = make_temp_root()
    try:
        folder = temp_root / "旧片名"
        folder.mkdir()
        video = folder / "旧片名.mkv"
        video.write_text("video", encoding="utf-8")

        library = [
            {
                "file_path": str(video),
                "file_name": video.name,
                "folder_name": "旧片名",
            }
        ]
        fake_config = FakeConfigManager(library, temp_root)
        monkeypatch.setattr(rename_route, "config_m", fake_config)

        rename_route.rename_item(str(video), "新片名 (2024).mkv")

        new_folder = temp_root / "新片名 (2024)"
        assert new_folder.is_dir()
        assert (new_folder / "新片名 (2024).mkv").exists()
        assert fake_config.saved_library[0]["folder_name"] == "新片名 (2024)"
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
