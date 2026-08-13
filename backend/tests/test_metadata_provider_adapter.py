from provider_context import ProviderContext
from provider_contracts import MetadataProvider
from provider_models import MetadataSearchRequest, ProviderHealthStatus
from metadata_provider_adapter import (
    MetadataProviderAdapter,
    build_metadata_provider_metadata,
    build_metadata_providers,
)


class FakeMetadataSource:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search(self, request):
        self.search_calls.append(request)
        return [
            {
                "external_id": "100",
                "title": "进击的巨人",
                "original_title": "進撃の巨人",
                "year": "2013",
                "media_type": "tv",
                "poster_url": "https://example.com/poster.jpg",
                "rating": 8.9,
            }
        ]

    def get_detail(self, external_id, media_type=""):
        self.detail_calls.append((external_id, media_type))
        return {
            "external_id": external_id,
            "title": "进击的巨人",
            "original_title": "進撃の巨人",
            "english_title": "Attack on Titan",
            "year": "2013",
            "media_type": media_type,
            "overview": "巨人题材动画",
            "runtime": 24,
            "rating": 8.9,
            "poster_url": "https://example.com/poster.jpg",
            "episodes": [{"season": 1, "episode": 1, "title": "致二千年后的你", "air_date": "2013-04-07"}],
        }


def test_metadata_adapter_satisfies_metadata_provider_protocol():
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("fake_metadata", "Fake Metadata"),
        FakeMetadataSource,
    )

    assert isinstance(provider, MetadataProvider)


def test_metadata_adapter_searches_candidates_from_legacy_source():
    source = FakeMetadataSource()
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("fake_metadata", "Fake Metadata"),
        lambda: source,
    )
    provider.initialize(ProviderContext())

    candidates = provider.search_metadata(MetadataSearchRequest(query="Attack on Titan", mediaType="tv", limit=5))

    assert len(candidates) == 1
    assert source.search_calls[0].query == "Attack on Titan"
    assert candidates[0].provider_id == "fake_metadata"
    assert candidates[0].external_id == "100"
    assert candidates[0].media_type == "tv"
    assert candidates[0].extra["title"] == "进击的巨人"


def test_metadata_adapter_gets_detail_from_legacy_source():
    source = FakeMetadataSource()
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("fake_metadata", "Fake Metadata"),
        lambda: source,
    )

    detail = provider.get_detail("100", "tv")

    assert source.detail_calls == [("100", "tv")]
    assert detail is not None
    assert detail.provider_id == "fake_metadata"
    assert detail.aliases.en == "Attack on Titan"
    assert detail.episodes[0].episode == 1
    assert detail.artwork[0].kind == "poster"
    assert detail.extra["title"] == "进击的巨人"


def test_metadata_adapter_health_follows_metadata_enabled():
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("fake_metadata", "Fake Metadata", enabled=False),
        FakeMetadataSource,
    )

    assert provider.health_check().status == ProviderHealthStatus.DISABLED


def test_build_metadata_providers_uses_matching_factories_only():
    providers = build_metadata_providers(
        [
            build_metadata_provider_metadata("fake_metadata", "Fake Metadata"),
            build_metadata_provider_metadata("missing_metadata", "Missing Metadata"),
        ],
        {"fake_metadata": FakeMetadataSource},
    )

    assert len(providers) == 1
    assert providers[0].metadata().id == "fake_metadata"
