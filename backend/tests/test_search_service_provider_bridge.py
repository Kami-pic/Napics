import search_service
from bt_search_provider_adapter import DirectBTSearchProviderAdapter, build_direct_bt_search_metadata
from searcher import SearchResult


class FakeDirectScraper:
    def __init__(self, results=None):
        self.calls = []
        self.results = results or []

    def search_as_search_results(self, keyword, max_results=40):
        self.calls.append((keyword, max_results))
        return list(self.results)


def _provider(name, scraper):
    return DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata(name, name),
        lambda: scraper,
    )


def test_search_service_provider_list_uses_provider_factory_order(monkeypatch):
    providers = {
        "bitsearch": lambda: object(),
        "cilixiong": lambda: object(),
        "xl720": lambda: object(),
        "nyaa": lambda: object(),
        "mikan": lambda: object(),
        "yts": lambda: object(),
        "limetorrents": lambda: object(),
        "acgrip": lambda: object(),
        "bangumi_moe": lambda: object(),
        "eztv": lambda: object(),
        "dmhy": lambda: object(),
        "1337x": lambda: object(),
    }
    provider_map = {name: _provider(name, scraper()) for name, scraper in providers.items()}

    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_provider_map",
        lambda: provider_map,
    )

    names = [name for name, _ in search_service._get_provider_list()]

    assert names == [name for name in search_service.BT_SOURCE_DEFAULTS if name != "prowlarr"]


def test_enabled_sources_keeps_legacy_override_behavior(monkeypatch):
    providers = {
        name: _provider(name, object())
        for name in search_service.BT_SOURCE_DEFAULTS
        if name != "prowlarr"
    }
    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_provider_map",
        lambda: providers,
    )

    prowlarr_enabled, enabled_providers = search_service._get_enabled_sources(
        {
            "prowlarr": False,
            "bitsearch": {"enabled": False, "proxy": True},
            "limetorrents": True,
        }
    )

    enabled_names = [name for name, _ in enabled_providers]
    assert prowlarr_enabled is False
    assert "bitsearch" not in enabled_names
    assert "limetorrents" in enabled_names


def test_search_direct_uses_provider_adapter_and_keeps_result_shape():
    scraper = FakeDirectScraper(
        [
            SearchResult(
                title="Attack on Titan S01E01",
                size_gb=1.5,
                indexer="bitsearch",
                seeders=8,
                leechers=2,
                download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                info_url="https://example.com/aot",
                quality_tag="WEB-1080p",
            )
        ]
    )

    name, results, err, searched, hit_kw = search_service.search_direct(
        "bitsearch",
        _provider("bitsearch", scraper),
        search_service.build_keywords("Attack on Titan"),
    )

    assert name == "bitsearch"
    assert err is None
    assert searched == ["Attack on Titan"]
    assert hit_kw == "Attack on Titan"
    assert scraper.calls == [("Attack on Titan", 40)]
    assert isinstance(results[0], SearchResult)
    assert results[0].indexer == "bitsearch"


class FakeProwlarrClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search(self, keyword):
        self.calls.append(keyword)
        return list(self.responses.get(keyword, []))


def test_search_prowlarr_uses_provider_adapter_and_keeps_result_shape():
    client = FakeProwlarrClient(
        {
            "Attack on Titan": [
                SearchResult(
                    title="Attack on Titan S01 1080p",
                    size_gb=12.5,
                    indexer="Nyaa",
                    seeders=20,
                    leechers=2,
                    download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                    info_url="https://example.com/aot",
                    quality_tag="WEB-1080p",
                )
            ]
        }
    )

    name, results, err, searched, hit_kw = search_service.search_prowlarr(
        client,
        search_service.build_keywords("Attack on Titan"),
    )

    assert name == "prowlarr"
    assert err is None
    assert searched == ["Attack on Titan"]
    assert hit_kw == "Attack on Titan"
    assert client.calls == ["Attack on Titan"]
    assert isinstance(results[0], SearchResult)
    assert results[0].indexer == "Nyaa"
    assert results[0].download_url.startswith("magnet:")
