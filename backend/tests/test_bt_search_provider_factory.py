from bt_search_provider_adapter import build_direct_bt_search_metadata
from bt_search_provider_factory import (
    DIRECT_BT_SOURCE_ORDER,
    LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES,
    build_direct_bt_providers_from_metadata,
    get_direct_bt_provider_map,
    get_direct_bt_scraper_factories,
)
from provider_builtin_metadata import build_builtin_provider_metadata
from search_service import BT_SOURCE_DEFAULTS

# 确保 search-bt-direct 插件已加载（测试环境无 startup_event）
import plugin_context
if not plugin_context.get_plugin_providers():
    from plugin_manager import PluginManager
    _pm = PluginManager()
    _pm._load_plugin_module("search-bt-direct")


def test_build_direct_bt_providers_skips_prowlarr_and_missing_factories():
    metadata = [
        build_direct_bt_search_metadata("prowlarr", "Prowlarr"),
        build_direct_bt_search_metadata("bitsearch", "Bitsearch"),
        build_direct_bt_search_metadata("missing", "Missing"),
    ]

    providers = build_direct_bt_providers_from_metadata(
        metadata,
        scraper_factories={"bitsearch": lambda: object()},
    )

    assert [provider.metadata().id for provider in providers] == ["bitsearch"]


def test_builtin_metadata_can_build_all_direct_bt_provider_adapters():
    metadata = build_builtin_provider_metadata()
    factories = {name: (lambda: object()) for name in BT_SOURCE_DEFAULTS if name != "prowlarr"}

    providers = build_direct_bt_providers_from_metadata(metadata, scraper_factories=factories)

    assert {provider.metadata().id for provider in providers} == set(factories)
    assert "prowlarr" not in {provider.metadata().id for provider in providers}


def test_get_direct_bt_provider_map_is_keyed_by_provider_id():
    metadata = [
        build_direct_bt_search_metadata("prowlarr", "Prowlarr"),
        build_direct_bt_search_metadata("bitsearch", "Bitsearch"),
    ]

    providers = get_direct_bt_provider_map(
        metadata_items=metadata,
        scraper_factories={"bitsearch": lambda: object()},
    )

    assert list(providers) == ["bitsearch"]
    assert providers["bitsearch"].metadata().id == "bitsearch"


def test_factory_keys_match_legacy_direct_bt_sources():
    expected = {name for name in BT_SOURCE_DEFAULTS if name != "prowlarr"}

    assert set(get_direct_bt_scraper_factories()) == expected


def test_direct_bt_source_order_matches_legacy_defaults():
    assert DIRECT_BT_SOURCE_ORDER == tuple(name for name in BT_SOURCE_DEFAULTS if name != "prowlarr")


def test_skip_filter_source_subset_keeps_legacy_fast_merge_scope():
    assert LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES == (
        "bitsearch",
        "cilixiong",
        "xl720",
        "nyaa",
        "mikan",
        "yts",
        "limetorrents",
        "acgrip",
        "bangumi_moe",
    )
