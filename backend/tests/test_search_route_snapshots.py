import asyncio
import json
from types import SimpleNamespace

from fastapi.responses import StreamingResponse

from routes import search as search_routes
from routes import search_single as search_single_routes
from searcher import SearchResult
from test_support.route_response_snapshot import RouteResponseSnapshot
from bt_search_provider_adapter import DirectBTSearchProviderAdapter, build_direct_bt_search_metadata


class FakeSearchClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search(self, keyword):
        self.calls.append(keyword)
        return list(self.responses.get(keyword, []))


def test_search_single_source_snapshot_keeps_keyword_chain_shape(monkeypatch):
    client = FakeSearchClient(
        {
            "进击的巨人": [],
            "Attack on Titan": [
                SearchResult(
                    title="Attack on Titan S01E01",
                    size_gb=1.23,
                    indexer="Prowlarr",
                    seeders=15,
                    leechers=3,
                    download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                    info_url="https://example.com/aot",
                    quality_tag="WEB-1080p",
                )
            ],
        }
    )

    # FakeSearchClient 适配为 provider 接口
    from provider_models import SearchCandidate
    class FakeProwlarrProvider:
        def search(self, request):
            raw = client.search(request.query)
            return [SearchCandidate(
                providerId="prowlarr", externalId="", title=r.title,
                downloadUrl=r.download_url, infoUrl=r.info_url, sizeGb=r.size_gb,
                seeders=r.seeders, leechers=r.leechers, indexer=r.indexer, rawQuality=r.quality_tag,
            ) for r in raw]

    monkeypatch.setattr(search_single_routes, "get_prowlarr_provider_map", lambda client_factory=None: {"prowlarr": FakeProwlarrProvider()})
    monkeypatch.setattr(search_single_routes, "get_clients", lambda: {"search": client})
    monkeypatch.setattr("plugin_guard.is_bt_source_allowed", lambda source: True)
    monkeypatch.setattr(
        search_single_routes,
        "_enrich_result",
        lambda result, query, match_names=None: {
            "title": result.title,
            "download_url": result.download_url,
            "_source": result.indexer.lower(),
            "match_score": 92,
            "search_query": query,
            "match_names": list(match_names or []),
        },
    )

    body = search_single_routes.search_single_source(
        source="prowlarr",
        keyword="进击的巨人",
        fallback_keywords="Attack on Titan,進撃の巨人",
    )
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert client.calls == ["进击的巨人", "Attack on Titan"]
    assert body["hit_keyword"] == "Attack on Titan"
    assert body["search_keywords"] == ["进击的巨人", "Attack on Titan"]
    assert snapshot.field_types["source"] == "str"
    assert snapshot.field_types["results"] == "list"
    assert snapshot.field_types["results[].title"] == "str"
    assert snapshot.field_types["results[].download_url"] == "str"
    assert snapshot.field_types["results[].match_score"] == "int"
    assert snapshot.field_types["results[].match_names"] == "list"
    assert snapshot.field_types["search_keywords"] == "list"
    assert snapshot.list_lengths["results"] == 1
    assert snapshot.list_lengths["search_keywords"] == 2


def test_search_single_direct_source_uses_provider_adapter(monkeypatch):
    class FakeDirectScraper:
        def __init__(self):
            self.calls = []

        def search_as_search_results(self, keyword, max_results=40):
            self.calls.append((keyword, max_results))
            return [
                SearchResult(
                    title="Bitsearch Result S01E01",
                    size_gb=2.0,
                    indexer="bitsearch",
                    seeders=7,
                    leechers=1,
                    download_url="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12",
                    info_url="https://example.com/bitsearch",
                    quality_tag="WEB-1080p",
                )
            ]

    scraper = FakeDirectScraper()
    provider = DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata("bitsearch", "Bitsearch"),
        lambda: scraper,
    )
    monkeypatch.setattr(search_single_routes, "get_direct_bt_provider_map", lambda: {"bitsearch": provider})
    monkeypatch.setattr("plugin_guard.is_bt_source_allowed", lambda source: True)
    monkeypatch.setattr(
        search_single_routes,
        "_enrich_result",
        lambda result, query, match_names=None: {
            "title": result.title,
            "_source": result.indexer,
            "match_names": list(match_names or []),
        },
    )

    body = search_single_routes.search_single_source(source="bitsearch", keyword="Attack on Titan")

    assert scraper.calls == [("Attack on Titan", 40)]
    assert body["source"] == "bitsearch"
    assert body["count"] == 1
    assert body["results"][0]["_source"] == "bitsearch"


def test_search_single_keyword_skip_filter_uses_provider_adapter(monkeypatch):
    class FakeDirectScraper:
        def __init__(self):
            self.calls = []

        def search_as_search_results(self, keyword, max_results=40):
            self.calls.append((keyword, max_results))
            return [
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

    client = FakeSearchClient(
        {
            "Attack on Titan": [
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
        }
    )
    scraper = FakeDirectScraper()
    provider = DirectBTSearchProviderAdapter(
        build_direct_bt_search_metadata("bitsearch", "Bitsearch"),
        lambda: scraper,
    )
    monkeypatch.setattr(search_single_routes, "get_clients", lambda: {"search": client})
    monkeypatch.setattr(search_single_routes, "get_direct_bt_provider_map", lambda: {"bitsearch": provider})
    monkeypatch.setattr(
        search_single_routes,
        "LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES",
        ("bitsearch",),
    )
    monkeypatch.setattr(
        search_single_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(bt_search_sources={})),
    )
    monkeypatch.setattr(
        search_single_routes,
        "_enrich_result",
        lambda result, query, match_names=None: {
            "title": result.title,
            "_source": result.indexer,
        },
    )

    body = search_single_routes.search_single_keyword(keyword="Attack on Titan", skip_filter=True)

    assert scraper.calls == [("Attack on Titan", 20)]
    assert body["bt_count"] == 2
    assert [item["_source"] for item in body["bt_results"]] == ["Prowlarr", "bitsearch"]


def test_search_stream_snapshot_emits_source_done_event(monkeypatch):
    monkeypatch.setattr("plugin_guard.get_allowed_bt_sources", lambda: {"prowlarr"})
    monkeypatch.setattr(search_routes, "build_keywords", lambda **kwargs: {"query": kwargs["query"]})
    monkeypatch.setattr(search_routes, "get_clients", lambda: {"search": object()})
    monkeypatch.setattr(
        search_routes,
        "search_all_sources_iter",
        lambda **kwargs: iter(
            [
                'event: source_start\ndata: {"source":"prowlarr","keyword":"Attack on Titan"}\n\n',
                'event: source_done\ndata: {"source":"prowlarr","count":1,"search_keywords":["Attack on Titan","进击的巨人"],"hit_keyword":"Attack on Titan"}\n\n',
            ]
        ),
    )

    response = search_routes.search_resources_stream(
        query="Attack on Titan",
        cn_name="进击的巨人",
        en_name="Attack on Titan",
        original_name="進撃の巨人",
        season_number=1,
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"

    async def _collect():
        return [chunk async for chunk in response.body_iterator]

    chunks = asyncio.run(_collect())
    assert len(chunks) == 2
    assert 'event: source_start' in chunks[0]
    assert 'event: source_done' in chunks[1]

    payload = json.loads(chunks[1].split("data: ", 1)[1].strip())
    assert payload["source"] == "prowlarr"
    assert payload["count"] == 1
    assert payload["search_keywords"] == ["Attack on Titan", "进击的巨人"]
    assert payload["hit_keyword"] == "Attack on Titan"
