from metadata_provider_adapter import build_metadata_provider_metadata
from metadata_provider_factory import (
    build_metadata_providers_from_metadata,
    get_metadata_provider_map,
)
from provider_builtin_metadata import METADATA_SOURCE_DEFAULTS, build_builtin_provider_metadata


class FakeMetadataSource:
    def search(self, request):
        return []

    def get_detail(self, external_id, media_type=""):
        return None


def test_build_metadata_providers_skips_missing_factories():
    providers = build_metadata_providers_from_metadata(
        [
            build_metadata_provider_metadata("tmdb", "TMDB"),
            build_metadata_provider_metadata("missing_metadata", "Missing Metadata"),
        ],
        source_factories={"tmdb": FakeMetadataSource},
    )

    assert [provider.metadata().id for provider in providers] == ["tmdb"]


def test_builtin_metadata_can_build_all_metadata_provider_adapters():
    metadata = build_builtin_provider_metadata()
    factories = {name: FakeMetadataSource for name in METADATA_SOURCE_DEFAULTS}

    providers = build_metadata_providers_from_metadata(metadata, source_factories=factories)

    assert {provider.metadata().id for provider in providers} == set(METADATA_SOURCE_DEFAULTS)


def test_get_metadata_provider_map_is_keyed_by_provider_id():
    providers = get_metadata_provider_map(
        metadata_items=[build_metadata_provider_metadata("tmdb", "TMDB")],
        source_factories={"tmdb": FakeMetadataSource},
    )

    assert list(providers) == ["tmdb"]
    assert providers["tmdb"].metadata().id == "tmdb"
