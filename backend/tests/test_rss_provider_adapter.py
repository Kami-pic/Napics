from provider_context import ProviderContext
from provider_contracts import RSSProvider
from provider_models import ProviderHealthStatus, RSSFetchRequest
from rss_provider_adapter import RSSProviderAdapter, build_rss_provider_metadata, build_rss_providers
from rss_source_base import RSSItem


class FakeRSSSource:
    name = "fake"
    display_name = "Fake RSS"
    enabled = True

    def __init__(self):
        self.calls = []

    def fetch(self, subscription):
        self.calls.append(subscription)
        return [
            RSSItem(
                title=f"{subscription.title} S01E01",
                download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                info_url="https://example.com/rss",
                size_gb=1.2,
                info_hash="ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                quality_tag="WEB-1080p",
                resolution="1080p",
                episode=1,
                season=1,
                source_name="fake",
                seeders=10,
                indexer="fake",
            )
        ]

    def can_download(self, item):
        return bool(item.download_url)


def test_rss_adapter_satisfies_rss_provider_protocol():
    provider = RSSProviderAdapter(
        build_rss_provider_metadata("rss_fake", "Fake RSS"),
        FakeRSSSource,
    )

    assert isinstance(provider, RSSProvider)


def test_rss_adapter_fetches_candidates_from_legacy_source():
    source = FakeRSSSource()
    provider = RSSProviderAdapter(
        build_rss_provider_metadata("rss_fake", "Fake RSS"),
        lambda: source,
    )
    provider.initialize(ProviderContext())

    candidates = provider.fetch(RSSFetchRequest(title="Attack on Titan", mediaType="tv", limit=5))

    assert len(candidates) == 1
    assert source.calls[0].title == "Attack on Titan"
    assert source.calls[0].type == "tv"
    assert candidates[0].provider_id == "rss_fake"
    assert candidates[0].download_url.startswith("magnet:")
    assert candidates[0].episode == 1
    assert provider.can_download(candidates[0]) is True


def test_rss_adapter_health_follows_metadata_enabled():
    provider = RSSProviderAdapter(
        build_rss_provider_metadata("rss_fake", "Fake RSS", enabled=False),
        FakeRSSSource,
    )

    assert provider.health_check().status == ProviderHealthStatus.DISABLED


def test_build_rss_providers_uses_matching_factories_only():
    providers = build_rss_providers(
        [
            build_rss_provider_metadata("rss_fake", "Fake RSS"),
            build_rss_provider_metadata("rss_missing", "Missing RSS"),
        ],
        {"fake": FakeRSSSource},
    )

    assert len(providers) == 1
    assert providers[0].metadata().id == "rss_fake"
