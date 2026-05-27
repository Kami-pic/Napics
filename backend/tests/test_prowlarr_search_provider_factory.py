from bt_search_provider_adapter import build_direct_bt_search_metadata
from provider_builtin_metadata import build_builtin_provider_metadata
from prowlarr_search_provider_factory import (
    PROWLARR_PROVIDER_ID,
    build_prowlarr_provider_from_metadata,
    get_prowlarr_provider_map,
)


def test_build_prowlarr_provider_from_metadata_picks_only_prowlarr():
    metadata = [
        build_direct_bt_search_metadata("bitsearch", "Bitsearch"),
        build_direct_bt_search_metadata("prowlarr", "Prowlarr"),
    ]

    provider = build_prowlarr_provider_from_metadata(metadata, client_factory=lambda: object())

    assert provider is not None
    assert provider.metadata().id == PROWLARR_PROVIDER_ID
    assert provider.metadata().name == "Prowlarr"


def test_build_prowlarr_provider_from_metadata_returns_none_when_missing():
    metadata = [build_direct_bt_search_metadata("bitsearch", "Bitsearch")]

    provider = build_prowlarr_provider_from_metadata(metadata, client_factory=lambda: object())

    assert provider is None


def test_get_prowlarr_provider_map_is_keyed_by_provider_id():
    metadata = [build_direct_bt_search_metadata("prowlarr", "Prowlarr")]

    providers = get_prowlarr_provider_map(metadata_items=metadata, client_factory=lambda: object())

    assert list(providers) == ["prowlarr"]
    assert providers["prowlarr"].metadata().id == "prowlarr"


def test_builtin_metadata_can_build_prowlarr_provider_adapter():
    provider = build_prowlarr_provider_from_metadata(
        build_builtin_provider_metadata(),
        client_factory=lambda: object(),
    )

    assert provider is not None
    assert provider.metadata().id == "prowlarr"
    assert provider.metadata().requires == ["api_url", "api_key"]
