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
