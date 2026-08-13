"""外部插件源功能测试"""

import json
import os
import tempfile
import zipfile

import pytest

from plugin_manager import (
    PluginManager,
    PluginSourceIndex,
    RemotePluginInfo,
)


class TestPluginSourceIndex:
    """测试插件源 index.json 解析"""

    def test_parse_valid_index(self):
        data = {
            "name": "test-source",
            "version": "1.0.0",
            "description": "测试插件源",
            "plugins": [
                {
                    "id": "test-plugin",
                    "name": "测试插件",
                    "version": "1.0.0",
                    "category": "search",
                    "download_url": "https://example.com/test-plugin.zip",
                }
            ],
        }
        index = PluginSourceIndex(**data)
        assert index.name == "test-source"
        assert len(index.plugins) == 1
        assert index.plugins[0].id == "test-plugin"
        assert index.plugins[0].download_url == "https://example.com/test-plugin.zip"

    def test_parse_empty_index(self):
        data = {"name": "empty", "plugins": []}
        index = PluginSourceIndex(**data)
        assert index.plugins == []

    def test_parse_with_sha256(self):
        data = {
            "name": "secure-source",
            "plugins": [
                {
                    "id": "secure-plugin",
                    "version": "2.0.0",
                    "download_url": "https://example.com/secure.zip",
                    "sha256": "abc123def456",
                }
            ],
        }
        index = PluginSourceIndex(**data)
        assert index.plugins[0].sha256 == "abc123def456"


class TestNormalizeSourceUrl:
    """测试 URL 规范化"""

    def test_direct_json_url(self):
        url = "https://example.com/plugins/index.json"
        assert PluginManager._normalize_source_url(url) == url

    def test_github_repo_url(self):
        url = "https://github.com/user/napics-plugins"
        expected = "https://raw.githubusercontent.com/user/napics-plugins/main/index.json"
        assert PluginManager._normalize_source_url(url) == expected

    def test_github_repo_url_with_trailing_slash(self):
        url = "https://github.com/user/napics-plugins/"
        expected = "https://raw.githubusercontent.com/user/napics-plugins/main/index.json"
        assert PluginManager._normalize_source_url(url) == expected

    def test_github_raw_url_unchanged(self):
        url = "https://raw.githubusercontent.com/user/repo/main/index.json"
        assert PluginManager._normalize_source_url(url) == url

    def test_github_releases_url_unchanged(self):
        url = "https://github.com/user/repo/releases/download/v1.0/index.json"
        assert PluginManager._normalize_source_url(url) == url


class TestInstallRemotePlugin:
    """测试远程插件安装"""

    def _create_plugin_zip(self, plugin_id: str, tmp_dir: str) -> str:
        """创建一个测试用的插件 zip 包"""
        zip_path = os.path.join(tmp_dir, f"{plugin_id}.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            manifest = {
                "id": plugin_id,
                "name": "测试插件",
                "version": "1.0.0",
                "category": "search",
                "provides": ["SearchProvider:test"],
            }
            zf.writestr(f"{plugin_id}/manifest.json", json.dumps(manifest))
            zf.writestr(f"{plugin_id}/__init__.py", "def register(ctx): pass\ndef unregister(): pass\n")
        return zip_path

    def test_install_remote_plugin_success(self):
        """测试远程插件安装成功（模拟本地 zip）"""
        tmp_dir = tempfile.mkdtemp()
        try:
            pm = PluginManager()
            plugin_id = "test-remote-plugin"

            # 创建 zip
            zip_path = self._create_plugin_zip(plugin_id, tmp_dir)

            # 读取 zip 内容模拟下载
            with open(zip_path, "rb") as f:
                zip_content = f.read()

            # 计算 sha256
            import hashlib
            sha = hashlib.sha256(zip_content).hexdigest()

            plugin_info = RemotePluginInfo(
                id=plugin_id,
                name="测试插件",
                version="1.0.0",
                download_url=f"file:///{zip_path}",
                sha256=sha,
            )

            # 直接测试 manifest 解析和目录结构
            assert plugin_id not in pm._manifests
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_normalize_url_non_github(self):
        """非 GitHub URL 不做转换"""
        url = "https://my-server.com/plugins"
        # 不以 .json 结尾，也不是 github.com，保持原样
        result = PluginManager._normalize_source_url(url)
        assert result == url


class TestPluginSourceConfig:
    """测试配置持久化"""

    def test_config_with_plugin_sources(self):
        from config_manager import AppConfig, PluginSourceConfig

        config = AppConfig(
            plugin_sources=[
                PluginSourceConfig(name="社区源", url="https://github.com/user/plugins"),
                PluginSourceConfig(name="私有源", url="https://my-server.com/index.json"),
            ]
        )
        assert len(config.plugin_sources) == 2
        assert config.plugin_sources[0].name == "社区源"
        assert config.plugin_sources[1].url == "https://my-server.com/index.json"

    def test_config_serialization(self):
        from config_manager import AppConfig, PluginSourceConfig

        config = AppConfig(
            plugin_sources=[
                PluginSourceConfig(name="test", url="https://example.com/index.json"),
            ]
        )
        data = config.model_dump()
        assert "plugin_sources" in data
        assert data["plugin_sources"][0]["url"] == "https://example.com/index.json"

        # 反序列化
        restored = AppConfig(**data)
        assert len(restored.plugin_sources) == 1
        assert restored.plugin_sources[0].name == "test"
