"""网页版文件夹选择器的目录列举与路径校验

这套接口替代了原来在服务端弹系统对话框的做法（Docker / NAS 上弹不出来）。
"""
import os
import shutil
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def tree():
    """造一个有层级的临时目录"""
    base = tempfile.mkdtemp(prefix="napics_fs_")
    os.makedirs(os.path.join(base, "电影", "阿凡达 (2009)"), exist_ok=True)
    os.makedirs(os.path.join(base, "电视剧"), exist_ok=True)
    os.makedirs(os.path.join(base, ".hidden"), exist_ok=True)
    os.makedirs(os.path.join(base, "@eaDir"), exist_ok=True)
    with open(os.path.join(base, "note.txt"), "w", encoding="utf-8") as f:
        f.write("x")
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ── 目录列举 ──

def test_empty_path_returns_roots(client):
    """不传路径时返回根（Windows 是盘符，Unix 是 /）"""
    r = client.get("/fs/list")
    assert r.status_code == 200
    data = r.json()
    assert data["is_root_list"] is True
    assert len(data["dirs"]) >= 1
    if sys.platform == "win32":
        assert any(d["name"].endswith(":\\") for d in data["dirs"])
    else:
        assert any(d["path"] == "/" for d in data["dirs"])


def test_lists_subdirectories(client, tree):
    r = client.get("/fs/list", params={"path": tree})
    assert r.status_code == 200
    data = r.json()
    names = [d["name"] for d in data["dirs"]]
    assert "电影" in names
    assert "电视剧" in names


def test_hides_dotfiles_and_system_dirs(client, tree):
    """隐藏目录与 NAS 系统目录不应出现在列表里"""
    data = client.get("/fs/list", params={"path": tree}).json()
    names = [d["name"] for d in data["dirs"]]
    assert ".hidden" not in names
    assert "@eaDir" not in names


def test_does_not_list_files(client, tree):
    """只返回目录，不返回文件（减少信息暴露）"""
    data = client.get("/fs/list", params={"path": tree}).json()
    names = [d["name"] for d in data["dirs"]]
    assert "note.txt" not in names


def test_parent_allows_going_up(client, tree):
    child = os.path.join(tree, "电影")
    data = client.get("/fs/list", params={"path": child}).json()
    assert os.path.normcase(data["parent"]) == os.path.normcase(tree)


def test_can_navigate_into_child(client, tree):
    data = client.get("/fs/list", params={"path": os.path.join(tree, "电影")}).json()
    names = [d["name"] for d in data["dirs"]]
    assert "阿凡达 (2009)" in names


def test_nonexistent_path_returns_error_not_crash(client):
    data = client.get("/fs/list", params={"path": "/definitely/not/here/xyz"}).json()
    assert data["error"]
    assert data["dirs"] == []


def test_separator_matches_platform(client, tree):
    data = client.get("/fs/list", params={"path": tree}).json()
    assert data["separator"] == os.sep


# ── 路径校验（Docker 场景的核心提示） ──

def test_check_existing_dir(client, tree):
    data = client.get("/fs/check", params={"path": tree}).json()
    assert data["exists"] is True
    assert data["is_dir"] is True
    assert data["readable"] is True
    assert data["hint"] == ""


def test_check_host_path_not_mounted_in_container(client):
    """还原用户的真实问题：填了宿主机路径，容器内不存在，必须给出明确提示"""
    data = client.get("/fs/check", params={"path": "/vol2/1000/video"}).json()
    if not os.path.isdir("/vol2/1000/video"):
        assert data["exists"] is False
        assert "挂载" in data["hint"], "提示里应说明 Docker 挂载问题"


def test_check_file_is_not_dir(client, tree):
    data = client.get("/fs/check", params={"path": os.path.join(tree, "note.txt")}).json()
    assert data["exists"] is True
    assert data["is_dir"] is False
    assert data["hint"]


def test_check_empty_path(client):
    data = client.get("/fs/check", params={"path": ""}).json()
    assert data["exists"] is False
    assert data["hint"]


# ── 旧接口已移除 ──

def test_old_browse_folder_endpoint_removed(client):
    """服务端弹窗方案已删除，不应再存在"""
    r = client.get("/config/browse-folder")
    assert r.status_code == 404
