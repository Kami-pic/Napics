from types import SimpleNamespace

import search_helpers
from bt_search_provider_adapter import DirectBTSearchProviderAdapter, build_direct_bt_search_metadata
from searcher import SearchResult


class FakeDirectScraper:
    def __init__(self, results):
        self.calls = []
        self.results = results

    def search_as_search_results(self, keyword, max_results=40):
        self.calls.append((keyword, max_results))
        return list(self.results)


def _provider(name, scraper):
    return DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata(name, name),
        lambda: scraper,
    )


def test_merge_bt_extra_sources_uses_provider_adapter(monkeypatch):
    existing = [
        SearchResult(
            title="Prowlarr Result S01E01",
            size_gb=1.0,
            indexer="Prowlarr",
            seeders=5,
            leechers=1,
            download_url="magnet:?xt=urn:btih:AAAAAA1234567890ABCDEF1234567890ABCDEF12",
            info_url="https://example.com/prowlarr",
            quality_tag="WEB-1080p",
        )
    ]
    scraper = FakeDirectScraper(
        [
            SearchResult(
                title="Bitsearch Extra S01E02",
                size_gb=2.5,
                indexer="bitsearch",
                seeders=9,
                leechers=1,
                download_url="magnet:?xt=urn:btih:BBBBBB1234567890ABCDEF1234567890ABCDEF12",
                info_url="https://example.com/bitsearch-extra",
                quality_tag="WEB-1080p",
            )
        ]
    )

    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_provider_map",
        lambda: {"bitsearch": _provider("bitsearch", scraper)},
    )
    monkeypatch.setattr(
        "shared.config_m",
        SimpleNamespace(config=SimpleNamespace(bt_search_sources={})),
    )

    merged = search_helpers.merge_bt_extra_sources("Attack on Titan", existing)

    assert scraper.calls == [("Attack on Titan", 40)]
    assert [item.indexer for item in merged] == ["Prowlarr", "bitsearch"]


def test_merge_bt_extra_sources_respects_disabled_provider(monkeypatch):
    scraper = FakeDirectScraper(
        [
            SearchResult(
                title="Disabled Result",
                size_gb=1.0,
                indexer="bitsearch",
                seeders=1,
                leechers=0,
                download_url="magnet:?xt=urn:btih:CCCCCC1234567890ABCDEF1234567890ABCDEF12",
                info_url="",
                quality_tag="",
            )
        ]
    )

    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_provider_map",
        lambda: {"bitsearch": _provider("bitsearch", scraper)},
    )
    monkeypatch.setattr(
        "shared.config_m",
        SimpleNamespace(config=SimpleNamespace(bt_search_sources={"bitsearch": {"enabled": False}})),
    )

    merged = search_helpers.merge_bt_extra_sources("Attack on Titan", [])

    assert scraper.calls == []
    assert merged == []
