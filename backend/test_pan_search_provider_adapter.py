from pan_models import PanResult, PanType
from pan_search_provider_adapter import (
    PanSearchProviderAdapter,
    build_pan_search_metadata,
    build_pan_search_providers,
)
from pan_search_provider_factory import (
    build_pan_search_providers_from_metadata,
    get_pan_search_provider_map,
)
from provider_context import ProviderContext
from provider_contracts import PanSearchProvider
from provider_models import ProviderHealthStatus, ProviderKind, ProviderMetadata, SearchRequest


class FakePanScraper:
    def __init__(self):
        self.calls = []

    def search(self, keyword: str):
        self.calls.append(keyword)
        return [
            PanResult(
                title="流浪地球2 2160p",
                pan_type=PanType.QUARK,
                share_url="https://pan.quark.cn/s/abc",
                password="1234",
                source="fake_pan",
                size_gb=12.5,
            ),
            PanResult(
                title="流浪地球2 1080p",
                pan_type=PanType.ALIYUN,
                share_url="https://www.alipan.com/s/def",
                source="fake_pan",
                size_gb=8,
            ),
        ]


def test_pan_search_adapter_satisfies_provider_protocol():
    provider = PanSearchProviderAdapter(
        build_pan_search_metadata("fake_pan", "Fake Pan"),
        scraper_factory=FakePanScraper,
    )

    assert isinstance(provider, PanSearchProvider)


def test_pan_search_adapter_converts_pan_results_to_candidates():
    scraper = FakePanScraper()
    provider = PanSearchProviderAdapter(
        build_pan_search_metadata("fake_pan", "Fake Pan"),
        scraper_factory=lambda: scraper,
    )

    provider.initialize(ProviderContext())
    candidates = provider.search_pan(SearchRequest(query="流浪地球2", limit=1))

    assert scraper.calls == ["流浪地球2"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_provider_id == "fake_pan"
    assert candidate.title == "流浪地球2 2160p"
    assert candidate.clean_title == "流浪地球2 2160p"
    assert candidate.share_url == "https://pan.quark.cn/s/abc"
    assert candidate.pan_type == "quark"
    assert candidate.password == "1234"
    assert candidate.file_size == "12.5 GB"
    assert candidate.resolution == "2160p"


def test_pan_search_adapter_metadata_and_health_follow_enabled_state():
    provider = PanSearchProviderAdapter(
        build_pan_search_metadata("fake_pan", "Fake Pan", enabled=False),
        scraper_factory=FakePanScraper,
    )

    assert provider.metadata().id == "fake_pan"
    assert provider.metadata().name == "Fake Pan"
    assert provider.health_check().status == ProviderHealthStatus.DISABLED


def test_build_pan_search_providers_uses_matching_factories_only():
    metadata = [
        build_pan_search_metadata("fake_pan", "Fake Pan"),
        build_pan_search_metadata("missing_pan", "Missing Pan"),
        ProviderMetadata(id="tmdb", name="TMDB", kind=ProviderKind.METADATA),
    ]

    providers = build_pan_search_providers(
        metadata,
        scraper_factories={"fake_pan": FakePanScraper},
    )

    assert len(providers) == 1
    assert providers[0].metadata().id == "fake_pan"


def test_pan_search_provider_factory_filters_pan_metadata_only():
    metadata = [
        build_pan_search_metadata("fake_pan", "Fake Pan"),
        ProviderMetadata(id="tmdb", name="TMDB", kind=ProviderKind.METADATA),
    ]

    providers = build_pan_search_providers_from_metadata(
        metadata,
        scraper_factories={"fake_pan": FakePanScraper},
    )

    assert [provider.metadata().id for provider in providers] == ["fake_pan"]


def test_pan_search_provider_map_keeps_provider_id_keys():
    providers = get_pan_search_provider_map(
        metadata_items=[build_pan_search_metadata("fake_pan", "Fake Pan")],
        scraper_factories={"fake_pan": FakePanScraper},
    )

    assert list(providers.keys()) == ["fake_pan"]
