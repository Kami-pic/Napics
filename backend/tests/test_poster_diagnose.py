"""封面诊断接口：定位「本地有刮削文件但封面还是走外网」的原因"""
import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def media(monkeypatch):
    """构造三种目录：命中本地海报、命名不被识别、路径不可达"""
    base = tempfile.mkdtemp(prefix="napics_pd_")

    ok_dir = os.path.join(base, "命中", "阿凡达 (2009)")
    os.makedirs(ok_dir, exist_ok=True)
    open(os.path.join(ok_dir, "poster.jpg"), "wb").write(b"\xff\xd8\xff\xe0")
    open(os.path.join(ok_dir, "movie.nfo"), "w", encoding="utf-8").write("<movie/>")

    miss_dir = os.path.join(base, "未命中", "星际穿越 (2014)")
    os.makedirs(miss_dir, exist_ok=True)
    # 故意用不在识别列表里的命名
    open(os.path.join(miss_dir, "fanart.jpg"), "wb").write(b"\xff\xd8\xff\xe0")
    open(os.path.join(miss_dir, "landscape.png"), "wb").write(b"\x89PNG")
    open(os.path.join(miss_dir, "movie.nfo"), "w", encoding="utf-8").write("<movie/>")

    gone_dir = os.path.join(base, "已不存在")

    fake_lib = [
        {"file_path": os.path.join(ok_dir, "a.mkv")},
        {"file_path": os.path.join(miss_dir, "b.mkv")},
        {"file_path": os.path.join(gone_dir, "c.mkv")},
    ]

    import shared
    monkeypatch.setattr(shared.config_m, "load_library", lambda: list(fake_lib))
    try:
        yield {"ok": ok_dir, "miss": miss_dir}
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _get(client):
    r = client.get("/scrape/poster-diagnose", params={"limit": 50})
    assert r.status_code == 200
    return r.json()


def test_counts_hit_miss_and_unreachable(media):
    from main import app
    data = _get(TestClient(app))

    assert data["checked"] == 3
    assert data["local_poster_hit"] == 1, "有 poster.jpg 的目录应算命中"
    assert data["local_poster_miss"] == 1, "命名不被识别的目录应算未命中"
    assert data["folder_unreachable"] == 1, "不存在的目录应算不可达"


def test_miss_sample_lists_actual_image_files(media):
    """未命中的样本要列出该目录真实存在的图片名，便于判断是不是命名问题"""
    from main import app
    data = _get(TestClient(app))

    assert data["miss_samples"], "应给出未命中的样本"
    sample = data["miss_samples"][0]
    names = sample["image_files_found"]
    assert "fanart.jpg" in names
    assert "landscape.png" in names
    assert sample["has_nfo"] is True, "有 NFO 说明刮削过，只是海报命名不匹配"


def test_reports_recognized_names(media):
    from main import app
    data = _get(TestClient(app))
    assert "poster.jpg" in data["recognized_folder_names"]
    assert "-poster.jpg" in data["recognized_suffixes"]


def test_hint_points_to_naming_when_miss_exists(media):
    from main import app
    data = _get(TestClient(app))
    assert "proxy/image" in data["hint"] or "命名" in data["hint"]
