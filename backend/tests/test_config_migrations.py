"""配置一次性迁移验证。

回归背景：metadata-bangumi 不在默认 installed_plugins 里，providers.py 按
f"metadata-{id}" in installed 过滤后前端完全看不到 Bangumi，功能整体不可用。
已落盘的旧配置必须被补齐，且补齐只能发生一次（否则用户卸载后会被装回）。
"""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_manager import AppConfig, ConfigManager


@pytest.fixture
def tmp_dir():
    """自建临时目录（pytest 内置 tmp_dir 在本机 Temp 上有权限问题）"""
    # 放在工作区内：本机系统 Temp 目录对 os.replace 有权限限制
    d = tempfile.mkdtemp(prefix="napics_cfg_", dir=os.path.dirname(os.path.abspath(__file__)))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _write(tmp_dir, data: dict) -> str:
    p = os.path.join(tmp_dir, "config.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return p


def test_default_includes_bangumi():
    """默认预装列表必须含 metadata-bangumi"""
    assert "metadata-bangumi" in AppConfig().installed_plugins


def test_existing_config_gets_bangumi_appended(tmp_dir):
    """已落盘的旧配置（非空插件列表）应被补齐 bangumi"""
    p = _write(tmp_dir, {"installed_plugins": ["metadata-tmdb", "metadata-douban"]})
    cm = ConfigManager(config_path=p)

    assert "metadata-bangumi" in cm.config.installed_plugins
    assert "add_bangumi_metadata" in cm.config.config_migrations


def test_migration_is_persisted(tmp_dir):
    """迁移结果必须写回磁盘，而不是只存在于内存"""
    p = _write(tmp_dir, {"installed_plugins": ["metadata-tmdb"]})
    ConfigManager(config_path=p)

    with open(p, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "metadata-bangumi" in saved["installed_plugins"]
    assert "add_bangumi_metadata" in saved["config_migrations"]


def test_migration_runs_only_once(tmp_dir):
    """迁移标记存在时不再补齐 —— 用户主动卸载 bangumi 后重启不会被装回"""
    p = _write(tmp_dir, {
        "installed_plugins": ["metadata-tmdb"],
        "config_migrations": ["add_bangumi_metadata"],
    })
    cm = ConfigManager(config_path=p)

    assert "metadata-bangumi" not in cm.config.installed_plugins


def test_empty_plugin_list_falls_back_to_defaults(tmp_dir):
    """插件列表为空的旧配置走默认注入，默认里已含 bangumi"""
    p = _write(tmp_dir, {"installed_plugins": []})
    cm = ConfigManager(config_path=p)

    assert "metadata-bangumi" in cm.config.installed_plugins


def test_migration_preserves_other_plugins(tmp_dir):
    """迁移不能动其他已安装插件"""
    original = ["metadata-tmdb", "search-bt-movie-tv", "download-qbittorrent"]
    p = _write(tmp_dir, {"installed_plugins": list(original)})
    cm = ConfigManager(config_path=p)

    for pid in original:
        assert pid in cm.config.installed_plugins
