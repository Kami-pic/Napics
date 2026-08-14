"""分组搜索插件注册验证。

回归背景：search-bt-movie-tv / search-pan-github 等 8 个分组插件曾是空壳，
register() 只打日志不注册 provider，导致搜索链路 0 结果且前端静默"一闪而过"。
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)

# 分组插件 → 期望注册的 provider_id
BT_GROUPS = {
    "search-bt-movie-tv": ["yts", "eztv"],
    "search-bt-mirror": ["bitsearch", "1337x", "limetorrents"],
    "search-bt-anime-jp": ["nyaa", "bangumi_moe"],
    "search-bt-anime-cn": ["mikan", "acgrip", "dmhy"],
    "search-bt-cn": ["cilixiong", "xl720"],
}
PAN_GROUPS = {
    "search-pan-github": ["gogopanso", "github"],
    "search-pan-main": ["pansearch", "pansou"],
    "search-pan-resource": ["rrdynb", "ddys"],
}
ALL_GROUPS = {**BT_GROUPS, **PAN_GROUPS}

_PLUGINS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins"
)


def _has_sources(plugin_id: str) -> bool:
    """插件目录下是否有 scraper 源码。

    按 .gitignore 的既定约定，plugins/*/sources/ 由社区插件仓库独立分发，
    不进主仓库。所以在干净 clone 上这些用例应跳过而不是失败。
    """
    d = os.path.join(_PLUGINS_DIR, plugin_id, "sources")
    return os.path.isdir(d) and any(f.endswith(".py") for f in os.listdir(d))


pytestmark = pytest.mark.skipif(
    not any(_has_sources(p) for p in ALL_GROUPS),
    reason="plugins/*/sources/ 未随主仓库分发（见 .gitignore），跳过分组插件注册验证",
)


def _load(plugin_id: str):
    """用真实 PluginManager 加载插件，返回错误信息（None 表示成功）"""
    from plugin_manager import PluginManager

    pm = PluginManager()  # 构造时自动扫描 plugins/ 下的 manifest.json
    assert plugin_id in pm._manifests, f"{plugin_id} 的 manifest 未被发现"
    return pm._load_plugin_module(plugin_id)


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个用例前清空 registry，避免相互污染"""
    from plugin_context import _plugin_providers

    _plugin_providers.clear()
    yield
    _plugin_providers.clear()


@pytest.mark.parametrize("plugin_id,expected", ALL_GROUPS.items())
def test_group_plugin_registers_providers(plugin_id, expected):
    """每个分组插件必须把它 manifest 里声明的 provider 全部注册进 registry"""
    from plugin_context import _plugin_providers

    if not _has_sources(plugin_id):
        pytest.skip(f"{plugin_id}/sources 不存在")
    err = _load(plugin_id)
    assert err is None, f"{plugin_id} 加载失败: {err}"

    missing = [pid for pid in expected if pid not in _plugin_providers]
    assert not missing, f"{plugin_id} 未注册: {missing}（registry 实际有 {list(_plugin_providers)}）"


@pytest.mark.parametrize("plugin_id,expected", BT_GROUPS.items())
def test_bt_group_provides_scraper_class(plugin_id, expected):
    """BT 分组插件注册的 provider 必须带 scraper_class，否则工厂拿不到、搜索静默为空"""
    from plugin_context import _plugin_providers

    if not _has_sources(plugin_id):
        pytest.skip(f'{plugin_id}/sources 不存在')
    _load(plugin_id)
    for pid in expected:
        info = _plugin_providers[pid]
        assert info["type"] == "scraper_search", f"{pid} type 应为 scraper_search，实际 {info['type']}"
        assert info.get("scraper_class") is not None, f"{pid} 缺少 scraper_class"


@pytest.mark.parametrize("plugin_id,expected", PAN_GROUPS.items())
def test_pan_group_provides_scraper_class(plugin_id, expected):
    """网盘分组插件必须把 scraper_class 挂上，pan_search_service 依赖它构造 scraper"""
    from plugin_context import _plugin_providers

    if not _has_sources(plugin_id):
        pytest.skip(f'{plugin_id}/sources 不存在')
    _load(plugin_id)
    for pid in expected:
        info = _plugin_providers[pid]
        assert info["type"] == "pan_search", f"{pid} type 应为 pan_search，实际 {info['type']}"
        assert info.get("scraper_class") is not None, f"{pid} 缺少 scraper_class"


def test_bt_factory_not_empty_after_default_plugins():
    """默认预装的 BT 分组插件加载后，工厂映射必须非空（这是搜索能出结果的前提）"""
    _load("search-bt-movie-tv")

    from bt_search_provider_factory import get_direct_bt_scraper_factories

    factories = get_direct_bt_scraper_factories()
    assert factories, "BT 工厂为空 —— 搜索会返回 0 结果且前端无任何提示"
    assert "yts" in factories, f"yts 不在工厂里，实际 {list(factories)}"


def test_guard_allowed_sources_are_actually_registered():
    """插件守卫放行的源，必须真的在 registry 里注册了，不能只靠硬编码映射放行"""
    from plugin_context import _plugin_providers

    for plugin_id, expected in BT_GROUPS.items():
        if not _has_sources(plugin_id):
            continue
        _plugin_providers.clear()
        _load(plugin_id)
        registered = set(_plugin_providers)
        for pid in expected:
            assert pid in registered, f"守卫会放行 {pid}，但 {plugin_id} 并未注册它"
