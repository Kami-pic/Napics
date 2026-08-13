"""原子写入与 ConfigManager 落盘行为验证"""
import json
import os
import shutil
import tempfile

import pytest

from core.json_store import atomic_write_json


@pytest.fixture
def workdir():
    """自管理临时目录（不用 pytest tmp_path，规避本机 Temp 目录权限问题）"""
    d = tempfile.mkdtemp(prefix="napics_test_")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_atomic_write_creates_valid_json(workdir):
    target = os.path.join(workdir, "data.json")
    atomic_write_json(target, [{"name": "测试影片", "n": 1}])

    with open(target, "r", encoding="utf-8") as f:
        assert json.load(f) == [{"name": "测试影片", "n": 1}]
    # 临时文件必须被清理
    assert not os.path.exists(target + ".tmp")


def test_atomic_write_keeps_chinese_readable(workdir):
    target = os.path.join(workdir, "data.json")
    atomic_write_json(target, {"title": "权力的游戏"})

    with open(target, "r", encoding="utf-8") as f:
        raw = f.read()
    assert "权力的游戏" in raw  # 不应被转义成 \uXXXX


def test_compact_mode_is_smaller(workdir):
    data = [{"file_path": f"/media/v{i}.mkv", "clean_name": "测试"} for i in range(100)]
    indented = os.path.join(workdir, "a.json")
    compact = os.path.join(workdir, "b.json")

    atomic_write_json(indented, data, indent=4)
    atomic_write_json(compact, data, compact=True)

    assert os.path.getsize(compact) < os.path.getsize(indented)
    # 两种格式解析结果必须完全一致
    with open(indented, encoding="utf-8") as f1, open(compact, encoding="utf-8") as f2:
        assert json.load(f1) == json.load(f2)


def test_original_file_intact_when_write_fails(workdir):
    """写入失败时原文件必须保持完整（原子性的核心价值）"""
    target = os.path.join(workdir, "data.json")
    atomic_write_json(target, {"good": True})

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": Unserializable()})

    with open(target, encoding="utf-8") as f:
        assert json.load(f) == {"good": True}
    assert not os.path.exists(target + ".tmp")


def test_config_manager_roundtrip(workdir, monkeypatch):
    """ConfigManager 保存后能原样读回，且 media_library 紧凑写入可解析"""
    monkeypatch.setenv("NAPICS_DATA_DIR", workdir)
    import config_manager as cm_module

    mgr = cm_module.ConfigManager()
    conf = mgr.config
    conf.tmdb_api_key = "test-key-123"
    conf.scan_paths = ["/media/电影"]
    mgr.save(conf)

    reloaded = cm_module.ConfigManager()
    assert reloaded.config.tmdb_api_key == "test-key-123"
    assert reloaded.config.scan_paths == ["/media/电影"]

    lib = [{"file_path": "/media/电影/a.mkv", "file_name": "a.mkv", "height": 1080}]
    mgr.save_library(lib)
    got = mgr.load_library()
    assert len(got) == 1
    assert got[0]["file_path"] == "/media/电影/a.mkv"
