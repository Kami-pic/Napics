"""插件管理器单元测试"""

import json
import os
import sys
import tempfile

import pytest

# 确保 backend 在 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugin_manager import PluginManager, PluginManifest, PLUGINS_DIR


class TestPluginManager:
    """测试 PluginManager 核心逻辑"""

    def test_load_manifests(self):
        """应能加载 plugins/ 目录下的所有 manifest"""
        pm = PluginManager()
        # 至少应该加载到我们创建的 16 个插件
        assert len(pm._manifests) >= 16

    def test_list_all_no_installed(self):
        """无已安装插件时，所有插件 installed=False"""
        pm = PluginManager()
        plugins = pm.list_all([])
        assert len(plugins) >= 16
        for p in plugins:
            assert p.installed is False

    def test_list_all_with_installed(self):
        """已安装插件正确标记"""
        pm = PluginManager()
        plugins = pm.list_all(["metadata-tmdb", "search-prowlarr"])
        tmdb = next(p for p in plugins if p.id == "metadata-tmdb")
        prowlarr = next(p for p in plugins if p.id == "search-prowlarr")
        douban = next(p for p in plugins if p.id == "metadata-douban")
        assert tmdb.installed is True
        assert prowlarr.installed is True
        assert douban.installed is False

    def test_get_manifest(self):
        """获取单个插件 manifest"""
        pm = PluginManager()
        m = pm.get_manifest("metadata-tmdb")
        assert m is not None
        assert m.id == "metadata-tmdb"
        assert m.name == "TMDB"
        assert m.category == "metadata"
        assert "tmdb_api_key" in m.requires_config

    def test_get_manifest_not_found(self):
        """不存在的插件返回 None"""
        pm = PluginManager()
        assert pm.get_manifest("nonexistent") is None

    def test_install_success(self):
        """正常安装"""
        pm = PluginManager()
        result = pm.install("metadata-tmdb", [])
        assert result["success"] is True
        assert result["plugin_id"] == "metadata-tmdb"

    def test_install_already_installed(self):
        """重复安装失败"""
        pm = PluginManager()
        result = pm.install("metadata-tmdb", ["metadata-tmdb"])
        assert result["success"] is False
        assert result["error"] == "already_installed"

    def test_install_not_found(self):
        """安装不存在的插件"""
        pm = PluginManager()
        result = pm.install("nonexistent", [])
        assert result["success"] is False
        assert result["error"] == "plugin_not_found"

    def test_install_missing_dependency(self):
        """依赖未满足时安装失败"""
        pm = PluginManager()
        # feature-completeness 依赖 metadata-tmdb
        result = pm.install("feature-completeness", [])
        assert result["success"] is False
        assert result["error"] == "missing_dependencies"
        assert "metadata-tmdb" in result["missing_dependencies"]

    def test_install_dependency_satisfied(self):
        """依赖满足时安装成功"""
        pm = PluginManager()
        result = pm.install("feature-completeness", ["metadata-tmdb"])
        assert result["success"] is True

    def test_uninstall_success(self):
        """正常卸载"""
        pm = PluginManager()
        result = pm.uninstall("metadata-tmdb", ["metadata-tmdb"])
        assert result["success"] is True

    def test_uninstall_not_installed(self):
        """卸载未安装的插件"""
        pm = PluginManager()
        result = pm.uninstall("metadata-tmdb", [])
        assert result["success"] is False
        assert result["error"] == "not_installed"

    def test_uninstall_has_dependents(self):
        """有依赖此插件的已安装插件时卸载失败"""
        pm = PluginManager()
        result = pm.uninstall("metadata-tmdb", ["metadata-tmdb", "feature-completeness"])
        assert result["success"] is False
        assert result["error"] == "has_dependents"
        assert "feature-completeness" in result["dependents"]

    def test_check_dependencies(self):
        """检查依赖"""
        pm = PluginManager()
        missing = pm.check_dependencies("feature-completeness", [])
        assert "metadata-tmdb" in missing

        missing = pm.check_dependencies("feature-completeness", ["metadata-tmdb"])
        assert missing == []

    def test_get_dependents(self):
        """获取依赖此插件的已安装插件"""
        pm = PluginManager()
        deps = pm.get_dependents("metadata-tmdb", ["metadata-tmdb", "feature-completeness"])
        assert "feature-completeness" in deps

    def test_categories(self):
        """验证插件分类正确"""
        pm = PluginManager()
        plugins = pm.list_all([])
        categories = set(p.category for p in plugins)
        assert "metadata" in categories
        assert "search" in categories
        assert "download" in categories
        assert "feature" in categories
        assert "rss" in categories
        assert "storage" in categories

    def test_reload(self):
        """reload 不报错"""
        pm = PluginManager()
        count_before = len(pm._manifests)
        pm.reload()
        assert len(pm._manifests) == count_before
