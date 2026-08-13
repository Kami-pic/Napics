"""路径白名单验证

两个方向同等重要：
1. 挡住媒体库范围外的路径（防路径穿越）
2. 不能挡住正常功能会用到的路径 —— 回收站在库根的上一级、下载沙盒、
   海报缓存等都在 scan_paths 之外，一旦被误挡就是功能故障
"""
import os
import shutil
import tempfile

import pytest

from core.path_guard import is_within, is_within_any, find_matching_root


@pytest.fixture
def lib(monkeypatch):
    """构造一个临时媒体库结构，并接管配置"""
    base = tempfile.mkdtemp(prefix="napics_guard_")
    share = os.path.join(base, "share")
    library = os.path.join(share, "视频")
    os.makedirs(os.path.join(library, "电影"), exist_ok=True)
    os.makedirs(os.path.join(share, "#recycle"), exist_ok=True)

    import shared
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [library])
    monkeypatch.setattr(shared.config_m.config, "media_libraries", [])
    monkeypatch.setattr(shared.config_m.config, "recycle_bin_path", "")
    monkeypatch.setattr(shared.config_m.config, "download_watch_dirs", [])
    shared.invalidate_allowed_roots_cache()
    try:
        yield {"base": base, "share": share, "library": library, "shared": shared}
    finally:
        shared.invalidate_allowed_roots_cache()
        shutil.rmtree(base, ignore_errors=True)


# ── 必须放行：正常功能路径 ──

def test_allows_library_root(lib):
    assert lib["shared"].is_path_allowed(lib["library"]) is True


def test_allows_file_inside_library(lib):
    p = os.path.join(lib["library"], "电影", "阿凡达 (2009)", "movie.mkv")
    assert lib["shared"].is_path_allowed(p) is True


def test_allows_default_recycle_bin_beside_library(lib):
    """回收站默认在库根的上一级（share/#recycle），必须放行否则删除功能坏掉"""
    p = os.path.join(lib["share"], "#recycle", "视频", "电影", "old.mkv")
    assert lib["shared"].is_path_allowed(p) is True


def test_allows_download_sandbox(lib):
    """下载沙盒在 data_dir/downloads/{task_id}，在 scan_paths 之外"""
    p = os.path.join(lib["shared"].config_m.data_dir, "downloads", "abc123", "x.mkv")
    assert lib["shared"].is_path_allowed(p) is True


def test_allows_organize_snapshots(lib):
    p = os.path.join(lib["shared"].config_m.data_dir, "organize_snapshots", "snap.json")
    assert lib["shared"].is_path_allowed(p) is True


def test_allows_poster_cache(lib):
    p = os.path.join(os.getcwd(), "posters", "某电影.jpg")
    assert lib["shared"].is_path_allowed(p) is True


def test_allows_explicit_recycle_bin_path(lib, monkeypatch):
    custom = os.path.join(lib["base"], "my_recycle")
    monkeypatch.setattr(lib["shared"].config_m.config, "recycle_bin_path", custom)
    lib["shared"].invalidate_allowed_roots_cache()
    assert lib["shared"].is_path_allowed(os.path.join(custom, "a.mkv")) is True


def test_allows_media_libraries_paths(lib, monkeypatch):
    """分类媒体库模式：路径配在 media_libraries 而不是 scan_paths"""
    from config_manager import MediaLibraryConfig
    extra = os.path.join(lib["base"], "另一个库")
    os.makedirs(extra, exist_ok=True)
    monkeypatch.setattr(lib["shared"].config_m.config, "scan_paths", [])
    monkeypatch.setattr(
        lib["shared"].config_m.config, "media_libraries",
        [MediaLibraryConfig(name="动漫", paths=[extra], category_tag="tv")],
    )
    lib["shared"].invalidate_allowed_roots_cache()
    assert lib["shared"].is_path_allowed(os.path.join(extra, "x.mkv")) is True


def test_allows_download_watch_dirs(lib, monkeypatch):
    watch = os.path.join(lib["base"], "watch")
    monkeypatch.setattr(lib["shared"].config_m.config, "download_watch_dirs", [watch])
    lib["shared"].invalidate_allowed_roots_cache()
    assert lib["shared"].is_path_allowed(os.path.join(watch, "new.mkv")) is True


# ── 必须拒绝：范围外路径 ──

@pytest.mark.parametrize("evil", [
    "/etc/passwd",
    "/root/.ssh/authorized_keys",
    "C:\\Windows\\System32\\drivers\\etc\\hosts",
    "C:\\Users\\Administrator\\Desktop",
])
def test_rejects_system_paths(lib, evil):
    assert lib["shared"].is_path_allowed(evil) is False


def test_rejects_parent_of_library(lib):
    """库的上级目录本身不能操作（否则等于能动整个共享盘）"""
    assert lib["shared"].is_path_allowed(lib["base"]) is False


def test_rejects_traversal_out_of_library(lib):
    evil = os.path.join(lib["library"], "..", "..", "secret.txt")
    assert lib["shared"].is_path_allowed(evil) is False


def test_rejects_sibling_prefix_directory(lib):
    """视频2 不能因为前缀像 视频 就被放行"""
    sibling = lib["library"] + "2"
    assert lib["shared"].is_path_allowed(os.path.join(sibling, "x.mkv")) is False


def test_rejects_empty_path(lib):
    assert lib["shared"].is_path_allowed("") is False


def test_rejects_everything_when_no_library_configured(lib, monkeypatch):
    """未配置任何媒体库时，媒体路径应全部拒绝（此时也无正常操作对象）"""
    monkeypatch.setattr(lib["shared"].config_m.config, "scan_paths", [])
    monkeypatch.setattr(lib["shared"].config_m.config, "media_libraries", [])
    lib["shared"].invalidate_allowed_roots_cache()
    assert lib["shared"].is_path_allowed("/etc/passwd") is False
    assert lib["shared"].is_path_allowed(os.path.join(lib["library"], "x.mkv")) is False


# ── 缓存行为 ──

def test_config_change_takes_effect_after_invalidate(lib, monkeypatch):
    new_root = os.path.join(lib["base"], "新库")
    os.makedirs(new_root, exist_ok=True)
    target = os.path.join(new_root, "a.mkv")

    assert lib["shared"].is_path_allowed(target) is False

    monkeypatch.setattr(lib["shared"].config_m.config, "scan_paths", [new_root])
    lib["shared"].invalidate_allowed_roots_cache()
    assert lib["shared"].is_path_allowed(target) is True


# ── 路由层集成 ──

def test_route_rejects_outside_path_403(lib):
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.get("/scrape/poster", params={"path": "C:\\Windows\\System32"})
    assert resp.status_code == 403


def test_route_allows_inside_path(lib):
    """库内路径不应被 403（没有海报时返回 404 是正常的）"""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.get("/scrape/poster", params={"path": os.path.join(lib["library"], "电影")})
    assert resp.status_code != 403


def test_upload_poster_rejects_outside_path(lib):
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.post(
        "/scrape/upload-poster",
        params={"path": "C:\\Windows\\Temp"},
        files={"file": ("evil.jpg", b"\xff\xd8\xff\xe0data", "image/jpeg")},
    )
    assert resp.status_code == 403


def test_upload_poster_rejects_non_image_extension(lib):
    """路径合法但扩展名非图片，也要拒绝"""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.post(
        "/scrape/upload-poster",
        params={"path": os.path.join(lib["library"], "电影")},
        files={"file": ("payload.py", b"import os", "text/x-python")},
    )
    assert resp.status_code == 400


def test_batch_manage_rejects_outside_target(lib):
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.post("/batch_manage", json={
        "action": "move",
        "paths": [os.path.join(lib["library"], "电影")],
        "target_dir": "C:\\Windows\\Temp",
    })
    assert resp.status_code == 403


def test_play_rejects_outside_path(lib):
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.get("/play", params={"path": "C:\\Windows\\System32\\calc.exe"})
    assert resp.status_code == 403
