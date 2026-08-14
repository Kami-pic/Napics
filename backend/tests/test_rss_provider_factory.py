from provider_builtin_metadata import RSS_SOURCE_DEFAULTS, build_builtin_provider_metadata
from rss_provider_adapter import build_rss_provider_metadata
from rss_provider_factory import (
    RSS_SOURCE_ORDER,
    build_rss_providers_from_metadata,
    get_rss_provider_map,
    get_rss_source_factories,
)


def test_build_rss_providers_skips_missing_factories():
    providers = build_rss_providers_from_metadata(
        [
            build_rss_provider_metadata("rss_mikan", "Mikan"),
            build_rss_provider_metadata("rss_missing", "Missing"),
        ],
        source_factories={"mikan": lambda: object()},
    )

    assert [provider.metadata().id for provider in providers] == ["rss_mikan"]


def test_builtin_metadata_can_build_all_rss_provider_adapters():
    metadata = build_builtin_provider_metadata()
    factories = {name: (lambda: object()) for name in RSS_SOURCE_DEFAULTS}

    providers = build_rss_providers_from_metadata(metadata, source_factories=factories)

    assert {provider.metadata().id for provider in providers} == {f"rss_{name}" for name in factories}


def test_factory_keys_match_builtin_rss_sources(monkeypatch):
    import plugin_guard
    from plugin_context import (
        _plugin_providers,
        get_plugin_context,
        unregister_plugin_providers,
    )

    class FakeRSSSource:
        pass

    _plugin_providers.clear()
    try:
        ctx = get_plugin_context("test-rss-package")
        for source_id, info in RSS_SOURCE_DEFAULTS.items():
            ctx.register_rss_source_provider(
                source_id,
                info["label"],
                FakeRSSSource,
            )
        monkeypatch.setattr(
            plugin_guard,
            "get_allowed_rss_sources",
            lambda: set(RSS_SOURCE_DEFAULTS),
        )

        assert set(get_rss_source_factories()) == set(RSS_SOURCE_DEFAULTS)
        assert _plugin_providers["rss_mikan"]["type"] == "rss_source"
        assert _plugin_providers["rss_mikan"]["metadata"].id == "rss_mikan"
    finally:
        unregister_plugin_providers("test-rss-package")


def test_rss_source_order_matches_builtin_defaults():
    assert RSS_SOURCE_ORDER == tuple(RSS_SOURCE_DEFAULTS)


def test_get_rss_provider_map_is_keyed_by_provider_id():
    providers = get_rss_provider_map(
        metadata_items=[build_rss_provider_metadata("rss_mikan", "Mikan")],
        source_factories={"mikan": lambda: object()},
    )

    assert list(providers) == ["rss_mikan"]
    assert providers["rss_mikan"].metadata().id == "rss_mikan"
