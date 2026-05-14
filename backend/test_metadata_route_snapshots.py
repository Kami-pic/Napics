from metadata_provider_adapter import MetadataProviderAdapter, build_metadata_provider_metadata
from routes import media_info as media_info_routes
from test_support.route_response_snapshot import RouteResponseSnapshot


class FakeBangumiSource:
    def __init__(self):
        self.calls = []

    def search(self, request):
        self.calls.append(request)
        return [
            {
                "bgm_id": 100,
                "title": "进击的巨人",
                "original_title": "進撃の巨人",
                "year": "2013",
                "poster_url": "https://example.com/poster.jpg",
                "summary": "巨人题材动画",
                "type": "动画",
                "type_id": 2,
                "rating": 8.9,
                "rank": 100,
            }
        ]

    def get_detail(self, external_id, media_type=""):
        return None


class FakeDoubanSource:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, request):
        self.calls.append(request)
        return self.results

    def get_detail(self, external_id, media_type=""):
        return None


def test_scrape_bangumi_candidates_uses_metadata_provider_and_keeps_shape(monkeypatch):
    source = FakeBangumiSource()
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("bangumi", "Bangumi"),
        lambda: source,
    )
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"bangumi": provider})
    monkeypatch.setattr(media_info_routes.tmdb_client, "parse_filename", lambda name: {"clean_name": "进击的巨人"})

    body = media_info_routes.scrape_bangumi_candidates("Attack on Titan")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert source.calls[0].query == "进击的巨人"
    assert body["query"] == "进击的巨人"
    assert body["candidates"][0]["bgm_id"] == 100
    assert body["candidates"][0]["type_id"] == 2
    assert body["candidates"][0]["rank"] == 100
    assert snapshot.field_types["query"] == "str"
    assert snapshot.field_types["candidates"] == "list"
    assert snapshot.field_types["candidates[].bgm_id"] == "int"
    assert snapshot.field_types["candidates[].title"] == "str"
    assert snapshot.field_types["candidates[].original_title"] == "str"
    assert snapshot.field_types["candidates[].year"] == "str"
    assert snapshot.field_types["candidates[].poster_url"] == "str"
    assert snapshot.field_types["candidates[].summary"] == "str"
    assert snapshot.field_types["candidates[].type"] == "str"
    assert snapshot.field_types["candidates[].type_id"] == "int"
    assert snapshot.field_types["candidates[].rating"] == "float"
    assert snapshot.field_types["candidates[].rank"] == "int"


def test_scrape_douban_candidates_uses_metadata_provider_and_keeps_api_v2_shape(monkeypatch):
    source = FakeDoubanSource(
        [
            {
                "douban_id": "3020000",
                "title": "进击的巨人",
                "original_title": "進撃の巨人",
                "year": "2013",
                "poster_url": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p123.jpg",
                "rating": 9.1,
                "overview": "巨人题材动画",
                "media_type": "tv",
                "episode_count": 25,
                "countries": ["日本"],
            }
        ]
    )
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("douban", "豆瓣"),
        lambda: source,
    )
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"douban": provider})
    monkeypatch.setattr(media_info_routes.tmdb_client, "parse_filename", lambda name: {"clean_name": "进击的巨人"})

    body = media_info_routes.scrape_douban_candidates("Attack on Titan")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert source.calls[0].query == "进击的巨人"
    assert body["source"] == "api_v2"
    assert body["candidates"][0]["douban_id"] == "3020000"
    assert body["candidates"][0]["poster_url_original"].startswith("https://img1.doubanio.com")
    assert body["candidates"][0]["poster_url"].startswith("/proxy/image?url=")
    assert snapshot.field_types["query"] == "str"
    assert snapshot.field_types["source"] == "str"
    assert snapshot.field_types["candidates"] == "list"
    assert snapshot.field_types["candidates[].douban_id"] == "str"
    assert snapshot.field_types["candidates[].title"] == "str"
    assert snapshot.field_types["candidates[].original_title"] == "str"
    assert snapshot.field_types["candidates[].year"] == "str"
    assert snapshot.field_types["candidates[].poster_url"] == "str"
    assert snapshot.field_types["candidates[].poster_url_original"] == "str"
    assert snapshot.field_types["candidates[].rating"] == "float"
    assert snapshot.field_types["candidates[].media_type"] == "str"


def test_scrape_douban_candidates_keeps_web_fallback_when_provider_empty(monkeypatch):
    source = FakeDoubanSource([])
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("douban", "豆瓣"),
        lambda: source,
    )
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"douban": provider})
    monkeypatch.setattr(media_info_routes.tmdb_client, "parse_filename", lambda name: {"clean_name": "进击的巨人"})
    monkeypatch.setattr(
        media_info_routes.douban_client,
        "search",
        lambda query: [
            {
                "douban_id": "3020000",
                "title": "进击的巨人",
                "year": "2013",
                "poster_url": "https://img1.doubanio.com/view/photo/m_ratio_poster/public/p123.jpg",
            }
        ],
    )

    body = media_info_routes.scrape_douban_candidates("Attack on Titan")

    assert body["source"] == "web_fallback"
    assert body["candidates"][0]["poster_url_original"].startswith("https://img1.doubanio.com")
    assert body["candidates"][0]["poster_url"].startswith("/proxy/image?url=")
