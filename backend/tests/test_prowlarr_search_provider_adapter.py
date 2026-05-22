from types import SimpleNamespace

from provider_contracts import SearchProvider
from provider_models import ProviderKind, ProviderMetadata, ProviderRiskLevel, SearchRequest
from prowlarr_search_provider_adapter import ProwlarrSearchProviderAdapter


class FakeProwlarrClient:
    def __init__(self):
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        return [
            SimpleNamespace(
                title="进击的巨人 S01 1080p",
                size_gb=12.34,
                indexer="Nyaa",
                seeders=88,
                leechers=3,
                download_url="magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
                info_url="https://example.com/info",
                quality_tag="1080p",
            ),
            SimpleNamespace(
                title="进击的巨人 S01 720p",
                size_gb=6.78,
                indexer="Indexer2",
                seeders=12,
                leechers=1,
                download_url="https://prowlarr/download/2",
                info_url="",
                quality_tag="720p",
            ),
        ]


def _metadata(enabled=True):
    return ProviderMetadata(
        id="prowlarr",
        name="Prowlarr",
        kind=ProviderKind.SEARCH,
        type="bt",
        enabled=enabled,
        defaultEnabled=True,
        capabilities=["search", "magnet", "torrent", "size", "seeders"],
        riskLevel=ProviderRiskLevel.USER_CONFIGURED,
        requires=["api_url", "api_key"],
    )


def test_prowlarr_adapter_satisfies_search_provider_protocol():
    provider = ProwlarrSearchProviderAdapter(_metadata(), FakeProwlarrClient)

    assert isinstance(provider, SearchProvider)


def test_prowlarr_adapter_search_outputs_search_candidates():
    client = FakeProwlarrClient()
    provider = ProwlarrSearchProviderAdapter(_metadata(), lambda: client)

    candidates = provider.search(SearchRequest(query="进击的巨人", limit=1))

    assert client.calls == ["进击的巨人"]
    assert len(candidates) == 1
    assert candidates[0].provider_id == "prowlarr"
    assert candidates[0].title == "进击的巨人 S01 1080p"
    assert candidates[0].download_url.startswith("magnet:")
    assert candidates[0].info_url == "https://example.com/info"
    assert candidates[0].size_gb == 12.34
    assert candidates[0].seeders == 88
    assert candidates[0].leechers == 3
    assert candidates[0].raw_quality == "1080p"
    assert candidates[0].indexer == "Nyaa"
    assert candidates[0].info_hash == "0123456789ABCDEF0123456789ABCDEF01234567"


def test_prowlarr_adapter_health_reflects_metadata_enabled():
    enabled = ProwlarrSearchProviderAdapter(_metadata(enabled=True), FakeProwlarrClient)
    disabled = ProwlarrSearchProviderAdapter(_metadata(enabled=False), FakeProwlarrClient)

    assert enabled.health_check().status == "ok"
    assert disabled.health_check().status == "disabled"
