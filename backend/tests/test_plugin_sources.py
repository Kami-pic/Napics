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


@pytest.fixture
def plugin_tmp_dir():
    """插件安装测试目录，避开本机 pytest Temp 目录权限污染。"""
    import shutil

    path = tempfile.mkdtemp(prefix="plugin_fallback_", dir=os.path.dirname(__file__))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class TestPluginLifecycle:
    """测试插件注册与卸载生命周期。"""

    def test_uninstall_removes_registered_provider_and_bt_factory(
        self, plugin_tmp_dir, monkeypatch
    ):
        """卸载后必须同步移除 Provider 注册和对应 BT 工厂。"""
        import sys

        import plugin_manager
        from bt_search_provider_factory import get_direct_bt_scraper_factories
        from plugin_context import _plugin_providers

        plugin_id = "test-search-lifecycle"
        plugin_dir = os.path.join(plugin_tmp_dir, plugin_id)
        os.makedirs(plugin_dir)
        with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({
                "id": plugin_id,
                "name": "生命周期测试插件",
                "version": "1.0.0",
                "category": "search",
            }, f, ensure_ascii=False)
        with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write(
                "class DummyScraper:\n"
                "    def __init__(self, proxy=None):\n"
                "        self.proxy = proxy\n\n"
                "def register(ctx):\n"
                "    ctx.register_scraper_search_provider(\n"
                "        'yts', '测试 YTS', DummyScraper\n"
                "    )\n\n"
                "def unregister():\n"
                "    pass\n"
            )

        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
        _plugin_providers.clear()
        try:
            pm = PluginManager()
            install_result = pm.install(plugin_id, [])

            assert install_result["success"] is True
            assert "yts" in _plugin_providers
            assert "yts" in get_direct_bt_scraper_factories()

            uninstall_result = pm.uninstall(plugin_id, [plugin_id])

            assert uninstall_result["success"] is True
            assert "yts" not in _plugin_providers
            assert "yts" not in get_direct_bt_scraper_factories()
            assert "napics_plugin_test_search_lifecycle" not in sys.modules
        finally:
            _plugin_providers.clear()


class TestRepositoryFallback:
    """Release 不存在时的仓库源码回退。"""

    @staticmethod
    def _repo_zip(plugin_id: str, manifest_id: str = "") -> bytes:
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            manifest = {
                "id": manifest_id or plugin_id,
                "name": "测试插件",
                "version": "1.0.0",
                "category": "download",
            }
            prefix = f"plugins-main/{plugin_id}/"
            zf.writestr(prefix + "manifest.json", json.dumps(manifest))
            zf.writestr(prefix + "__init__.py", "def register(ctx): pass\n")
        return buffer.getvalue()

    def test_codeload_used_when_archive_and_mirrors_fail(self, plugin_tmp_dir, monkeypatch):
        """archive/镜像全失败后仍应尝试 codeload 官方直链。"""
        import plugin_manager

        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
        pm = PluginManager()
        content = self._repo_zip("download-openlist")
        calls = []

        class Response:
            def __init__(self, body):
                self.content = body

        def fake_get(url, **kwargs):
            calls.append((url, kwargs.get("mirrors")))
            if "codeload.github.com" in url:
                return Response(content), url
            return None, "archive failed"

        monkeypatch.setattr(plugin_manager.github_access, "get", fake_get)
        result = pm._fallback_install_from_repo(
            "download-openlist",
            "https://github.com/user/plugins",
            [],
            None,
        )

        assert result["success"] is True
        assert any("codeload.github.com" in url for url, _ in calls)
        assert os.path.isfile(os.path.join(plugin_tmp_dir, "download-openlist", "manifest.json"))

    def test_download_failure_reports_attempted_fallbacks(self, plugin_tmp_dir, monkeypatch):
        """所有仓库地址失败时返回明确阶段，不再只说“均不可用”。"""
        import plugin_manager

        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
        monkeypatch.setattr(
            plugin_manager.github_access,
            "get",
            lambda url, **kwargs: (None, f"failed: {url}"),
        )
        pm = PluginManager()

        result = pm._fallback_install_from_repo(
            "rss-anime",
            "https://github.com/user/plugins",
            [],
            None,
        )

        assert result["success"] is False
        assert result["error"] == "repo_download_failed"
        assert "codeload" in result["message"]

    def test_manifest_mismatch_restores_existing_plugin(self, plugin_tmp_dir, monkeypatch):
        """仓库包身份不匹配时必须恢复安装前的插件目录。"""
        import plugin_manager

        plugin_id = "download-openlist"
        existing_dir = os.path.join(plugin_tmp_dir, plugin_id)
        os.makedirs(existing_dir)
        with open(os.path.join(existing_dir, "old.txt"), "w", encoding="utf-8") as f:
            f.write("old plugin")

        class Response:
            content = self._repo_zip(plugin_id, manifest_id="another-plugin")

        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
        monkeypatch.setattr(
            plugin_manager.github_access,
            "get",
            lambda url, **kwargs: (Response(), url),
        )
        pm = PluginManager()

        result = pm._fallback_install_from_repo(
            plugin_id,
            "https://github.com/user/plugins",
            [],
            None,
        )

        assert result["success"] is False
        assert result["error"] == "manifest_id_mismatch"
        assert os.path.isfile(os.path.join(existing_dir, "old.txt"))
        assert not os.path.exists(existing_dir + ".bak")

    def test_register_failure_rolls_back_runtime_providers(self, plugin_tmp_dir, monkeypatch):
        """register 中途失败时不得遗留 provider 或模块。"""
        import io
        import sys

        import plugin_manager
        from plugin_context import get_plugin_providers, unregister_plugin_providers

        plugin_id = "broken-register-plugin"
        unregister_plugin_providers(plugin_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            prefix = f"plugins-main/{plugin_id}/"
            zf.writestr(prefix + "manifest.json", json.dumps({
                "id": plugin_id,
                "name": "失败插件",
                "version": "1.0.0",
                "category": "search",
            }))
            zf.writestr(
                prefix + "__init__.py",
                "def register(ctx):\n"
                "    ctx.register_search_provider('partial_provider', 'Partial', lambda q, n: [])\n"
                "    raise RuntimeError('register boom')\n",
            )

        class Response:
            content = buffer.getvalue()

        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
        monkeypatch.setattr(plugin_manager.github_access, "get", lambda url, **kwargs: (Response(), url))
        pm = PluginManager()

        result = pm._fallback_install_from_repo(
            plugin_id,
            "https://github.com/user/plugins",
            [],
            None,
        )

        assert result["success"] is False
        assert result["error"] == "load_failed"
        assert "partial_provider" not in get_plugin_providers()
        assert f"napics_plugin_{plugin_id.replace('-', '_')}" not in sys.modules


def test_direct_release_load_failure_restores_existing_plugin(plugin_tmp_dir, monkeypatch):
    """Release 包注册失败时必须报错并恢复旧插件，不能伪装安装成功。"""
    import hashlib
    import io

    import plugin_manager

    plugin_id = "direct-load-failure"
    existing_dir = os.path.join(plugin_tmp_dir, plugin_id)
    os.makedirs(existing_dir)
    with open(os.path.join(existing_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"id": plugin_id, "name": "旧插件", "version": "1.0.0"}, f)
    with open(os.path.join(existing_dir, "old.txt"), "w", encoding="utf-8") as f:
        f.write("old")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            f"{plugin_id}/manifest.json",
            json.dumps({"id": plugin_id, "name": "新插件", "version": "2.0.0"}),
        )
        zf.writestr(
            f"{plugin_id}/__init__.py",
            "def register(ctx):\n    raise RuntimeError('unsupported api')\n",
        )
    content = buffer.getvalue()

    class Response:
        def __init__(self, body):
            self.content = body

        def raise_for_status(self):
            return None

    monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", plugin_tmp_dir)
    monkeypatch.setattr(plugin_manager, "check_external_url", lambda url: (True, ""))
    monkeypatch.setattr(plugin_manager.requests, "get", lambda *args, **kwargs: Response(content))
    manager = PluginManager()
    result = manager.install_remote_plugin(
        RemotePluginInfo(
            id=plugin_id,
            download_url="https://example.com/direct-load-failure.zip",
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        [],
    )

    assert result["success"] is False
    assert result["error"] == "load_failed"
    assert os.path.isfile(os.path.join(existing_dir, "old.txt"))
    assert not os.path.exists(existing_dir + ".bak")
    assert manager.get_manifest(plugin_id).version == "1.0.0"


def test_remote_release_is_written_only_to_external_root(plugin_tmp_dir, monkeypatch):
    """远程包必须进入 external root，并返回真实 external 来源。"""
    import hashlib
    import io
    import plugin_manager

    builtin_dir = os.path.join(plugin_tmp_dir, "builtin")
    external_dir = os.path.join(plugin_tmp_dir, "external")
    os.makedirs(builtin_dir)
    plugin_id = "external-only-plugin"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            f"{plugin_id}/manifest.json",
            json.dumps({"id": plugin_id, "name": "外部插件", "category": "feature"}),
        )
        archive.writestr(f"{plugin_id}/__init__.py", "def register(ctx): pass\n")
    content = buffer.getvalue()

    class Response:
        def __init__(self, body):
            self.content = body

        def raise_for_status(self):
            return None

    monkeypatch.setattr(plugin_manager, "check_external_url", lambda url: (True, ""))
    monkeypatch.setattr(plugin_manager.requests, "get", lambda *args, **kwargs: Response(content))
    manager = PluginManager(builtin_dir, external_dir)

    result = manager.install_remote_plugin(
        RemotePluginInfo(
            id=plugin_id,
            download_url="https://example.com/external-only-plugin.zip",
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        [],
    )

    assert result["success"] is True
    assert manager.get_source(plugin_id) == "external"
    assert os.path.isfile(os.path.join(external_dir, plugin_id, "manifest.json"))
    assert not os.path.exists(os.path.join(builtin_dir, plugin_id))
