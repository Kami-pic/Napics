import pytest

from main import app
import providers as providers_module
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata
from provider_registry import default_provider_registry
from providers import list_providers


@pytest.fixture(autouse=True)
def _isolate_private_provider_env(monkeypatch):
    """测试默认使用 open-core catalog，显式开启用例自行覆盖。"""
    monkeypatch.delenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", raising=False)


def _fake_installed(monkeypatch, plugin_ids):
    """固定已安装插件列表，避免结果随本机 config.json 变化。"""
    import plugin_guard

    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: list(plugin_ids))


def test_provider_api_returns_static_provider_catalog(monkeypatch):
    _fake_installed(monkeypatch, [
        "search-prowlarr",
        "download-qbittorrent",
        "download-openlist",
        "storage-openlist",
        "rss-anime",
        "metadata-tmdb",
        "metadata-douban",
        "metadata-bangumi",
    ])

    response = list_providers()
    payload = response.model_dump(by_alias=True)

    assert any(item["id"] == "qbittorrent" for item in payload["download"])
    assert any(item["id"] == "openlist" for item in payload["download"])
    assert any(item["id"] == "openlist_storage" for item in payload["storage"])
    assert payload["notification"] == []
    assert any(item["id"] == "prowlarr" for item in payload["search"])
    assert payload["panSearch"] == []
    assert any(item["id"] == "tmdb" for item in payload["metadata"])
    assert any(item["id"] == "douban" for item in payload["metadata"])
    assert any(item["id"] == "bangumi" for item in payload["metadata"])
    assert any(item["id"] == "rss_mikan" for item in payload["rss"])
    prowlarr = next(item for item in payload["search"] if item["id"] == "prowlarr")
    tmdb = next(item for item in payload["metadata"] if item["id"] == "tmdb")
    qbittorrent = next(item for item in payload["download"] if item["id"] == "qbittorrent")
    openlist_storage = next(item for item in payload["storage"] if item["id"] == "openlist_storage")
    assert prowlarr["kind"] == "search"
    assert prowlarr["riskLevel"] == "user_configured"
    assert prowlarr["requires"] == ["api_url", "api_key"]
    assert prowlarr["supportsProxy"] is False
    assert "seeders" in prowlarr["capabilities"]
    assert tmdb["kind"] == "metadata"
    assert tmdb["requires"] == ["api_key"]
    assert qbittorrent["kind"] == "download"
    assert qbittorrent["riskLevel"] == "user_configured"
    assert openlist_storage["kind"] == "storage"
    assert openlist_storage["capabilities"] == ["list_mounts", "list_dir", "exists"]


def test_provider_api_does_not_register_static_metadata_globally():
    before = default_provider_registry.catalog().model_dump(by_alias=True)

    list_providers()

    assert default_provider_registry.catalog().model_dump(by_alias=True) == before


def test_provider_api_route_is_registered():
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/providers" in paths


def test_builtin_provider_metadata_applies_config_overrides():
    providers = build_builtin_provider_metadata(
        bt_overrides={"bitsearch": {"enabled": False, "proxy": False}},
        pan_overrides={"pansou": True},
        include_private_pan=True,
    )

    bitsearch = next(item for item in providers if item.id == "bitsearch")
    pansou = next(item for item in providers if item.id == "pansou")

    assert bitsearch.kind == ProviderKind.SEARCH
    assert bitsearch.enabled is False
    assert bitsearch.supports_proxy is False
    assert pansou.kind == ProviderKind.PAN_SEARCH
    assert pansou.enabled is True


def test_builtin_provider_metadata_keeps_open_core_source_counts():
    from search_service import BT_SOURCE_DEFAULTS, PAN_SOURCE_DEFAULTS

    providers = build_builtin_provider_metadata()
    search_count = sum(1 for item in providers if item.kind == ProviderKind.SEARCH)
    pan_count = sum(1 for item in providers if item.kind == ProviderKind.PAN_SEARCH)
    metadata_count = sum(1 for item in providers if item.kind == ProviderKind.METADATA)
    rss_count = sum(1 for item in providers if item.kind == ProviderKind.RSS)
    download_count = sum(1 for item in providers if item.kind == ProviderKind.DOWNLOAD)
    storage_count = sum(1 for item in providers if item.kind == ProviderKind.STORAGE)

    assert search_count == len(BT_SOURCE_DEFAULTS)
    assert pan_count == 0
    assert metadata_count == 3
    assert rss_count == 8
    assert download_count == 2
    assert storage_count == 1


def test_builtin_provider_metadata_marks_sources_without_seeder_info():
    providers = build_builtin_provider_metadata()
    mikan = next(item for item in providers if item.id == "mikan")
    bitsearch = next(item for item in providers if item.id == "bitsearch")

    assert "seeders" not in mikan.capabilities
    assert "seeders" in bitsearch.capabilities


def test_builtin_provider_metadata_exposes_keyword_preferences():
    providers = build_builtin_provider_metadata()
    nyaa = next(item for item in providers if item.id == "nyaa")
    mikan = next(item for item in providers if item.id == "mikan")
    prowlarr = next(item for item in providers if item.id == "prowlarr")

    assert nyaa.capabilities[:4] == ["search", "magnet", "torrent", "size"]
    assert "keyword_original" in nyaa.capabilities
    assert "season_en" in nyaa.capabilities
    assert "keyword_cn" in mikan.capabilities
    assert "season_cn" in mikan.capabilities
    assert "keyword_en" in prowlarr.capabilities
    assert "indexers" in prowlarr.capabilities


def test_builtin_provider_metadata_can_include_private_pan_sources():
    from search_service import PAN_SOURCE_DEFAULTS

    providers = build_builtin_provider_metadata(include_private_pan=True)
    pan_count = sum(1 for item in providers if item.kind == ProviderKind.PAN_SEARCH)

    assert pan_count == len(PAN_SOURCE_DEFAULTS)


def test_provider_api_can_expose_private_pan_sources_with_explicit_env(monkeypatch):
    monkeypatch.setenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", "true")
    _fake_installed(monkeypatch, ["search-pan-main"])

    payload = providers_module.list_providers().model_dump(by_alias=True)

    assert any(item["id"] == "pansearch" for item in payload["panSearch"])


def test_root_route_keeps_existing_response():
    from main import read_root

    assert read_root() == {"message": "NAS Video Upgrader API is running"}


def test_provider_api_marks_installed_provider_without_runtime_registration(monkeypatch):
    import plugin_guard

    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: ["search-bt-anime-cn"])
    monkeypatch.setattr(plugin_guard, "get_allowed_bt_sources", lambda: {"mikan"})
    monkeypatch.setattr(plugin_guard, "is_pan_search_allowed", lambda: False)
    monkeypatch.setattr(
        providers_module,
        "_get_registered_provider_ids",
        lambda: {kind: set() for kind in ProviderKind},
    )

    payload = providers_module.list_providers().model_dump(by_alias=True)
    mikan = next(item for item in payload["search"] if item["id"] == "mikan")

    assert mikan["installed"] is True
    assert mikan["registered"] is False
    assert mikan["available"] is False
    assert mikan["loadError"] == "插件已安装，但运行时未注册该 Provider"


def test_provider_api_marks_runtime_registered_provider_available(monkeypatch):
    import plugin_guard

    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: ["search-bt-anime-cn"])
    monkeypatch.setattr(plugin_guard, "get_allowed_bt_sources", lambda: {"mikan"})
    monkeypatch.setattr(plugin_guard, "is_pan_search_allowed", lambda: False)
    runtime_ids = {kind: set() for kind in ProviderKind}
    runtime_ids[ProviderKind.SEARCH].add("mikan")
    monkeypatch.setattr(providers_module, "_get_registered_provider_ids", lambda: runtime_ids)

    payload = providers_module.list_providers().model_dump(by_alias=True)
    mikan = next(item for item in payload["search"] if item["id"] == "mikan")

    assert mikan["registered"] is True
    assert mikan["available"] is True
    assert mikan["loadError"] == ""


def test_provider_api_includes_registered_third_party_metadata(monkeypatch):
    import plugin_context
    import plugin_guard

    metadata = ProviderMetadata(
        id="custom_search",
        name="Custom Search",
        kind=ProviderKind.SEARCH,
        type="bt",
        enabled=True,
    )
    runtime = {
        "custom_search": {
            "type": "search",
            "metadata": metadata,
            "search_fn": lambda *_: [],
            "plugin_id": "search-custom",
        }
    }
    monkeypatch.setattr(plugin_context, "get_plugin_providers", lambda: runtime)
    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: ["search-custom"])

    payload = providers_module.list_providers().model_dump(by_alias=True)
    custom = next(item for item in payload["search"] if item["id"] == "custom_search")

    assert custom["installed"] is True
    assert custom["registered"] is True
    assert custom["available"] is True


def test_provider_api_filters_rss_by_installed_package(monkeypatch):
    import plugin_guard

    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: ["rss-anime"])
    runtime_ids = {kind: set() for kind in ProviderKind}
    runtime_ids[ProviderKind.RSS].add("rss_mikan")
    monkeypatch.setattr(providers_module, "_get_registered_provider_ids", lambda: runtime_ids)

    payload = providers_module.list_providers().model_dump(by_alias=True)

    assert {item["id"] for item in payload["rss"]} == {
        "rss_mikan", "rss_nyaa", "rss_acgrip", "rss_bangumi_moe", "rss_dmhy",
    }
    mikan = next(item for item in payload["rss"] if item["id"] == "rss_mikan")
    nyaa = next(item for item in payload["rss"] if item["id"] == "rss_nyaa")
    assert mikan["available"] is True
    assert nyaa["available"] is False


def test_private_pan_guard_matches_runtime_policy(monkeypatch):
    import plugin_context
    import plugin_guard

    monkeypatch.setattr(plugin_guard, "get_installed_plugins", lambda: ["search-pan-main"])
    monkeypatch.setattr(plugin_context, "get_plugin_providers", lambda: {})
    monkeypatch.delenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", raising=False)

    assert plugin_guard.is_pan_search_allowed() is False
    assert plugin_guard.get_allowed_pan_sources() == set()

    monkeypatch.setenv("NAPICS_ALLOW_PRIVATE_PROVIDERS", "true")

    assert plugin_guard.is_pan_search_allowed() is True
    assert plugin_guard.get_allowed_pan_sources() == {"pansearch", "pansou"}
