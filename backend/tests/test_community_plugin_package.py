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
    "search-bt-mirror": ["bitsearch", "1337x", "limetorrents"],
    "search-bt-movie-tv": ["yts", "eztv"],
    "search-bt-anime-jp": ["nyaa", "bangumi_moe"],
    "search-bt-anime-cn": ["mikan", "acgrip", "dmhy"],
    "search-bt-cn": ["cilixiong", "xl720"],
    "search-pan-main": ["pansearch", "pansou"],
    "search-pan-github": ["gogopanso", "github"],
    "search-pan-resource": ["rrdynb", "ddys"],
}

pytestmark = pytest.mark.skipif(
    not os.path.isdir(DIST_DIR),
    reason="未生成 dist/，先运行 community-plugins/build_release.py",
)


@pytest.mark.parametrize("plugin_id", sorted(SEARCH_GROUPS))
def test_release_zip_contains_sources(plugin_id):
    """发布包必须含 sources/ 下的爬虫源码，否则装出来是空壳"""
    zip_path = os.path.join(DIST_DIR, f"{plugin_id}.zip")
    assert os.path.isfile(zip_path), f"缺少发布包 {zip_path}"

    names = zipfile.ZipFile(zip_path).namelist()
    sources = [n for n in names if "/sources/" in n and n.endswith(".py")]
    assert sources, f"{plugin_id}.zip 不含任何 sources/*.py，实际内容: {names}"


@pytest.mark.parametrize("plugin_id,expected", sorted(SEARCH_GROUPS.items()))
def test_installed_from_zip_registers_providers(plugin_id, expected):
    """把发布包解压到干净目录后加载，必须真正注册出 provider"""
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
            assert _plugin_providers[pid].get("scraper_class") is not None, \
                f"{pid} 缺少 scraper_class"
    finally:
        _plugin_providers.clear()
        sys.modules.pop(f"pkgtest_{plugin_id.replace('-', '_')}", None)
        shutil.rmtree(work, ignore_errors=True)
