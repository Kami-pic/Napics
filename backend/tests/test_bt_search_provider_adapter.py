from provider_context import ProviderContext
from provider_contracts import SearchProvider
from provider_models import ProviderHealthStatus, SearchRequest
from searcher import SearchResult

from bt_search_provider_adapter import (
    DirectBTSearchProviderAdapter,
    build_direct_bt_search_providers,
    build_direct_bt_search_metadata,
)


class FakeScraper:
    def __init__(self):
        self.calls = []

    def search_as_search_results(self, keyword: str, max_results: int = 40):
        self.calls.append((keyword, max_results))
        return [
            SearchResult(
                title="Attack on Titan S01E01 1080p",
                size_gb=1.5,
                indexer="fake_bt",
                seeders=12,
                leechers=3,
                download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                info_url="https://example.test/torrent",
                quality_tag="WEB-1080p",
            )
        ]


def test_direct_bt_adapter_satisfies_search_provider_protocol():
    provider = DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata("fake_bt", "Fake BT"),
        scraper_factory=FakeScraper,
    )

    assert isinstance(provider, SearchProvider)


def test_direct_bt_adapter_converts_search_results_to_candidates():
    scraper = FakeScraper()
    provider = DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata("fake_bt", "Fake BT"),
        scraper_factory=lambda: scraper,
    )

    provider.initialize(ProviderContext())
    candidates = provider.search(SearchRequest(query="Attack on Titan", limit=7))

    assert scraper.calls == [("Attack on Titan", 7)]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.provider_id == "fake_bt"
    assert candidate.title == "Attack on Titan S01E01 1080p"
    assert candidate.download_url.startswith("magnet:")
    assert candidate.size_gb == 1.5
    assert candidate.seeders == 12
    assert candidate.leechers == 3
    assert candidate.raw_quality == "WEB-1080p"
    assert candidate.info_hash == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"


def test_direct_bt_adapter_metadata_and_health_follow_enabled_state():
    provider = DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata("fake_bt", "Fake BT", enabled=False),
        scraper_factory=FakeScraper,
    )

    assert provider.metadata().id == "fake_bt"
    assert provider.metadata().name == "Fake BT"
    assert provider.health_check().status == ProviderHealthStatus.DISABLED


def test_build_direct_bt_search_providers_uses_matching_factories_only():
    metadata = [
        build_direct_bt_search_metadata("fake_bt", "Fake BT"),
        build_direct_bt_search_metadata("missing_bt", "Missing BT"),
    ]

    providers = build_direct_bt_search_providers(
        metadata,
        scraper_factories={"fake_bt": FakeScraper},
    )

    assert len(providers) == 1
    assert providers[0].metadata().id == "fake_bt"
