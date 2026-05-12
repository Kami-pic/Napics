from main import app
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind
from provider_registry import default_provider_registry
from providers import list_providers


def test_provider_api_returns_static_phase2_catalog():
    response = list_providers()
    payload = response.model_dump(by_alias=True)

    assert payload["metadata"] == []
    assert payload["download"] == []
    assert payload["storage"] == []
    assert payload["notification"] == []
    assert any(item["id"] == "prowlarr" for item in payload["search"])
    assert any(item["id"] == "pansearch" for item in payload["panSearch"])
    assert any(item["id"] == "rss_mikan" for item in payload["rss"])
    prowlarr = next(item for item in payload["search"] if item["id"] == "prowlarr")
    assert prowlarr["kind"] == "search"
    assert prowlarr["riskLevel"] == "user_configured"
    assert prowlarr["requires"] == ["api_url", "api_key"]
    assert prowlarr["supportsProxy"] is False


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
    )

    bitsearch = next(item for item in providers if item.id == "bitsearch")
    pansou = next(item for item in providers if item.id == "pansou")

    assert bitsearch.kind == ProviderKind.SEARCH
    assert bitsearch.enabled is False
    assert bitsearch.supports_proxy is False
    assert pansou.kind == ProviderKind.PAN_SEARCH
    assert pansou.enabled is True


def test_builtin_provider_metadata_keeps_legacy_source_counts():
    from search_service import BT_SOURCE_DEFAULTS, PAN_SOURCE_DEFAULTS

    providers = build_builtin_provider_metadata()
    search_count = sum(1 for item in providers if item.kind == ProviderKind.SEARCH)
    pan_count = sum(1 for item in providers if item.kind == ProviderKind.PAN_SEARCH)
    rss_count = sum(1 for item in providers if item.kind == ProviderKind.RSS)

    assert search_count == len(BT_SOURCE_DEFAULTS)
    assert pan_count == len(PAN_SOURCE_DEFAULTS)
    assert rss_count == 8


def test_root_route_keeps_existing_response():
    from main import read_root

    assert read_root() == {"message": "NAS Video Upgrader API is running"}
