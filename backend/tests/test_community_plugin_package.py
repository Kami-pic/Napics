"""社区插件发布包完整性验证。

回归背景：community-plugins/<id>/ 下只有 manifest + 空壳 __init__.py，
爬虫源码只在 backend/plugins/<id>/sources/。早期打包脚本直接 zip 前者，
用户从插件源装到的永远是空壳，搜索永远 0 结果。
"""

import os
import shutil
import sys
import tempfile
import zipfile

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
DIST_DIR = os.path.join(REPO_ROOT, "community-plugins", "dist")

sys.path.insert(0, BACKEND_DIR)

# 分组插件 → 期望注册的 provider_id
SEARCH_GROUPS = {
    "search-bt-mirror": (["bitsearch", "1337x", "limetorrents"], "scraper_class"),
    "search-bt-movie-tv": (["yts", "eztv"], "scraper_class"),
    "search-bt-anime-jp": (["nyaa", "bangumi_moe"], "scraper_class"),
    "search-bt-anime-cn": (["mikan", "acgrip", "dmhy"], "scraper_class"),
    "search-bt-cn": (["cilixiong", "xl720"], "scraper_class"),
    "search-pan-main": (["pansearch", "pansou"], "scraper_class"),
    "search-pan-github": (["gogopanso", "github"], "scraper_class"),
    "search-pan-resource": (["rrdynb", "ddys"], "scraper_class"),
}

RSS_GROUPS = {
    "rss-anime": (["rss_mikan", "rss_nyaa", "rss_acgrip", "rss_bangumi_moe", "rss_dmhy"], "source_class"),
    "rss-tv-movie": (["rss_eztv", "rss_yts", "rss_prowlarr"], "source_class"),
}

PLUGIN_GROUPS = {**SEARCH_GROUPS, **RSS_GROUPS}

pytestmark = pytest.mark.skipif(
    not os.path.isdir(DIST_DIR),
    reason="未生成 dist/，先运行 community-plugins/build_release.py",
)


@pytest.mark.parametrize("plugin_id", sorted(PLUGIN_GROUPS))
def test_release_zip_contains_sources(plugin_id):
    """发布包必须含 sources/ 下的爬虫源码，否则装出来是空壳"""
    zip_path = os.path.join(DIST_DIR, f"{plugin_id}.zip")
    assert os.path.isfile(zip_path), f"缺少发布包 {zip_path}"

    names = zipfile.ZipFile(zip_path).namelist()
    sources = [n for n in names if "/sources/" in n and n.endswith(".py")]
    assert sources, f"{plugin_id}.zip 不含任何 sources/*.py，实际内容: {names}"


@pytest.mark.parametrize("plugin_id,contract", sorted(PLUGIN_GROUPS.items()))
def test_installed_from_zip_registers_providers(plugin_id, contract):
    """把发布包解压到干净目录后加载，必须真正注册出 provider。"""
    expected, implementation_key = contract
    from plugin_context import _plugin_providers

    work = tempfile.mkdtemp(prefix="napics_pkg_", dir=os.path.dirname(os.path.abspath(__file__)))
    try:
        zipfile.ZipFile(os.path.join(DIST_DIR, f"{plugin_id}.zip")).extractall(work)
        init_path = os.path.join(work, plugin_id, "__init__.py")
        assert os.path.isfile(init_path)

        _plugin_providers.clear()
        # 按 PluginManager 的方式动态加载
        import importlib.util

        module_name = f"pkgtest_{plugin_id.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, init_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        from plugin_context import get_plugin_context

        module.register(get_plugin_context(plugin_id))

        missing = [p for p in expected if p not in _plugin_providers]
        assert not missing, f"{plugin_id} 从发布包装载后未注册: {missing}"
        for pid in expected:
            assert _plugin_providers[pid].get(implementation_key) is not None, \
                f"{pid} 缺少 {implementation_key}"
    finally:
        _plugin_providers.clear()
        sys.modules.pop(f"pkgtest_{plugin_id.replace('-', '_')}", None)
        shutil.rmtree(work, ignore_errors=True)


@pytest.mark.parametrize("plugin_id,contract", sorted(RSS_GROUPS.items()))
def test_rss_release_package_install_and_uninstall_lifecycle(plugin_id, contract, monkeypatch):
    """RSS 发布包经 PluginManager 安装后可用，卸载后不残留 Provider 或源模块。"""
    import plugin_manager
    from plugin_context import _plugin_providers

    expected, _ = contract
    work = tempfile.mkdtemp(prefix="napics_rss_lifecycle_", dir=os.path.dirname(__file__))
    module_prefix = f"napics_plugin_{plugin_id.replace('-', '_')}"
    try:
        zipfile.ZipFile(os.path.join(DIST_DIR, f"{plugin_id}.zip")).extractall(work)
        monkeypatch.setattr(plugin_manager, "PLUGINS_DIR", work)
        _plugin_providers.clear()
        manager = plugin_manager.PluginManager()

        assert manager.install(plugin_id, [])["success"] is True
        assert all(provider_id in _plugin_providers for provider_id in expected)
        assert any(name.startswith(f"{module_prefix}_rss_source_") for name in sys.modules)

        assert manager.uninstall(plugin_id, [plugin_id])["success"] is True
        assert all(provider_id not in _plugin_providers for provider_id in expected)
        assert not any(name.startswith(module_prefix) for name in sys.modules)
    finally:
        _plugin_providers.clear()
        for name in tuple(sys.modules):
            if name.startswith(module_prefix):
                sys.modules.pop(name, None)
        shutil.rmtree(work, ignore_errors=True)
