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
        """核心插件全部被发现，第三方插件也被发现（标记为 external）。"""
        pm = PluginManager()
        core_ids = {
            "metadata-tmdb", "metadata-douban", "metadata-bangumi",
            "search-prowlarr", "download-qbittorrent", "storage-openlist",
            "feature-completeness", "feature-discover",
            "feature-local-match", "feature-subscribe",
        }
        # 核心插件必须全部存在且标记为 builtin
        assert core_ids.issubset(set(pm._manifests))
        for cid in core_ids:
            assert pm._plugin_sources[cid] == "builtin"

    def test_list_all_no_installed(self):
        """无已安装插件时，所有发现的插件均未安装。"""
        pm = PluginManager()
        plugins = pm.list_all([])
        assert len(plugins) >= 10
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
        assert "storage" in categories

    def test_reload(self):
        """reload 不报错"""
        pm = PluginManager()
        count_before = len(pm._manifests)
        pm.reload()
        assert len(pm._manifests) == count_before


class TestPluginRoots:
    """内置与外部插件目录必须物理隔离。"""

    @staticmethod
    def _write_manifest(root: str, plugin_id: str, name: str) -> str:
        plugin_dir = os.path.join(root, plugin_id)
        os.makedirs(plugin_dir, exist_ok=True)
        with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as file:
            json.dump({"id": plugin_id, "name": name, "category": "feature"}, file)
        return plugin_dir

    def test_merges_roots_and_reports_real_source(self):
        with tempfile.TemporaryDirectory() as builtin, tempfile.TemporaryDirectory() as external:
            self._write_manifest(builtin, "builtin-test", "内置")
            self._write_manifest(external, "external-test", "外部")

            manager = PluginManager(builtin, external)
            plugins = {plugin.id: plugin for plugin in manager.list_all([])}

            assert plugins["builtin-test"].source == "builtin"
            assert plugins["external-test"].source == "external"

    def test_builtin_wins_when_external_uses_same_id(self):
        with tempfile.TemporaryDirectory() as builtin, tempfile.TemporaryDirectory() as external:
            self._write_manifest(builtin, "same-id", "内置版本")
            self._write_manifest(external, "same-id", "外部版本")

            manager = PluginManager(builtin, external)

            assert manager.get_manifest("same-id").name == "内置版本"
            assert manager.get_source("same-id") == "builtin"


def test_core_plugin_config_schema_is_manifest_driven():
    manager = PluginManager()
    tmdb = manager.get_manifest("metadata-tmdb")
    prowlarr = manager.get_manifest("search-prowlarr")

    assert [field.key for field in tmdb.config_schema] == ["tmdb_api_key"]
    assert [field.key for field in prowlarr.config_schema] == [
        "prowlarr_url", "prowlarr_api_key",
    ]
    assert all(field.label for field in tmdb.config_schema + prowlarr.config_schema)


def test_builtin_plugin_files_cannot_be_removed():
    manager = PluginManager()
    result = manager.uninstall_remote_plugin("metadata-tmdb", ["metadata-tmdb"])

    assert result["success"] is False
    assert result["error"] == "not_external_plugin"
    assert manager.get_manifest("metadata-tmdb") is not None
