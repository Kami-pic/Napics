from provider_models import AliasSet, ArtworkInfo, MetadataDetail
from routes import media_detail as media_info_routes
from test_support.route_response_snapshot import RouteResponseSnapshot


class FakeTMDBProvider:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_detail(self, external_id, media_type=""):
        self.calls.append((external_id, media_type))
        return self.responses.get(media_type)


def _detail(media_type="movie"):
    return MetadataDetail(
        providerId="tmdb",
        externalId="12345",
        title="进击的巨人",
        originalTitle="進撃の巨人",
        mediaType=media_type,
        year=2013,
        overview="巨人题材动画",
        runtime=24,
        rating=8.9,
        aliases=AliasSet(en="Attack on Titan"),
        artwork=[
            ArtworkInfo(kind="poster", url="https://image.tmdb.org/t/p/w500/poster.jpg"),
            ArtworkInfo(kind="backdrop", url="https://image.tmdb.org/t/p/w1280/backdrop.jpg"),
        ],
        extra={
            "genres": ["动画"],
            "director": "荒木哲郎",
            "cast": ["梶裕贵", "石川由依", "井上麻里奈", "谷山纪章", "小林优", "三上枝织", "下野纮"],
            "imdb_id": "tt2560140",
            "total_seasons": 4,
            "episode_count": 25,
            "status": "Ended",
            "countries": ["Japan"],
        },
    )


def test_try_tmdb_detail_by_id_uses_metadata_provider_and_keeps_shape(monkeypatch):
    provider = FakeTMDBProvider({"movie": _detail("movie")})
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})

    body = media_info_routes._try_tmdb_detail_by_id(12345, "movie")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert provider.calls == [("12345", "movie")]
    assert body["found"] is True
    assert body["tmdb_id"] == 12345
    assert body["source"] == "tmdb"
    assert body["cast"] == ["梶裕贵", "石川由依", "井上麻里奈", "谷山纪章", "小林优", "三上枝织"]
    assert snapshot.field_types["found"] == "bool"
    assert snapshot.field_types["tmdb_id"] == "int"
    assert snapshot.field_types["title"] == "str"
    assert snapshot.field_types["english_title"] == "str"
    assert snapshot.field_types["poster_url"] == "str"
    assert snapshot.field_types["genres"] == "list"
    assert snapshot.field_types["cast"] == "list"
    assert snapshot.field_types["source"] == "str"


def test_try_tmdb_detail_by_id_keeps_type_fallback(monkeypatch):
    provider = FakeTMDBProvider({"movie": None, "tv": _detail("tv")})
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})

    body = media_info_routes._try_tmdb_detail_by_id(12345, "movie")

    assert provider.calls == [("12345", "movie"), ("12345", "tv")]
    assert body["found"] is True
    assert body["tmdb_id"] == 12345


def test_try_tmdb_detail_by_id_returns_not_found_when_provider_misses(monkeypatch):
    provider = FakeTMDBProvider({"movie": None, "tv": None})
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})

    body = media_info_routes._try_tmdb_detail_by_id(12345, "movie")

    assert provider.calls == [("12345", "movie"), ("12345", "tv")]
    assert body == {"found": False}


def test_try_tmdb_detail_uses_metadata_provider_search_and_detail(monkeypatch):
    from metadata_provider_adapter import MetadataProviderAdapter, build_metadata_provider_metadata

    class FakeTMDBSource:
        def search(self, request):
            return [
                {
                    "id": 12345,
                    "tmdb_id": 12345,
                    "title": "进击的巨人",
                    "original_title": "進撃の巨人",
                    "release_date": "2013-04-07",
                    "year": "2013",
                    "popularity": 100,
                    "media_type": "movie",
                }
            ]

        def get_detail(self, external_id, media_type=""):
            return {
                "tmdb_id": int(external_id),
                "title": "进击的巨人",
                "original_title": "進撃の巨人",
                "english_title": "Attack on Titan",
                "year": "2013",
                "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
                "overview": "巨人题材动画",
                "rating": 8.9,
                "genres": ["动画"],
                "media_type": media_type,
            }

    source = FakeTMDBSource()
    provider = MetadataProviderAdapter(
        build_metadata_provider_metadata("tmdb", "TMDB"),
        lambda: source,
    )
    monkeypatch.setattr(media_info_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})

    body = media_info_routes._try_tmdb_detail("进击的巨人", "2013", "movie")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert body["found"] is True
    assert body["tmdb_id"] == 12345
    assert body["source"] == "tmdb"
    assert body["english_title"] == "Attack on Titan"
    assert snapshot.field_types["found"] == "bool"
    assert snapshot.field_types["tmdb_id"] == "int"
    assert snapshot.field_types["title"] == "str"
    assert snapshot.field_types["english_title"] == "str"
    assert snapshot.field_types["source"] == "str"
