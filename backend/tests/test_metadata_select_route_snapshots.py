from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from provider_models import AliasSet, ArtworkInfo, MetadataDetail
from routes import scrape as scrape_routes
from routes import scrape_execute as scrape_execute_routes
from test_support.route_response_snapshot import RouteResponseSnapshot
from tmdb_client import ScrapeResult


class FakeTMDBProvider:
    def __init__(self, detail):
        self.detail = detail
        self.calls = []

    def get_detail(self, external_id, media_type=""):
        self.calls.append((external_id, media_type))
        return self.detail


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
    )


def test_scrape_select_uses_metadata_provider_for_movie_and_keeps_response(monkeypatch):
    provider = FakeTMDBProvider(_detail("movie"))
    writes = []
    monkeypatch.setattr(scrape_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})
    monkeypatch.setattr(scrape_routes, "config_m", SimpleNamespace(config=SimpleNamespace(tmdb_api_key="key")))
    monkeypatch.setattr(scrape_routes, "_write_scrape_result", lambda path, result: writes.append((path, result)))

    body = scrape_routes.scrape_select(path="D:/Media/Movie", tmdb_id=12345, media_type="movie")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert provider.calls == [("12345", "movie")]
    assert writes[0][0] == "D:/Media/Movie"
    assert isinstance(writes[0][1], ScrapeResult)
    assert body["status"] == "ok"
    assert body["data"]["tmdb_id"] == 12345
    assert body["data"]["media_type"] == "movie"
    assert body["data"]["english_title"] == "Attack on Titan"
    assert snapshot.field_types["status"] == "str"
    assert snapshot.field_types["data.tmdb_id"] == "int"
    assert snapshot.field_types["data.media_type"] == "str"
    assert snapshot.field_types["data.title"] == "str"
    assert snapshot.field_types["data.poster_url"] == "str"


def test_scrape_select_uses_metadata_provider_for_tv(monkeypatch):
    provider = FakeTMDBProvider(_detail("tv"))
    writes = []
    monkeypatch.setattr(scrape_routes, "get_metadata_provider_map", lambda: {"tmdb": provider})
    monkeypatch.setattr(scrape_routes, "config_m", SimpleNamespace(config=SimpleNamespace(tmdb_api_key="key")))
    monkeypatch.setattr(scrape_routes, "_write_scrape_result", lambda path, result: writes.append((path, result)))

    body = scrape_routes.scrape_select(path="D:/Media/TV", tmdb_id=12345, media_type="tv")

    assert provider.calls == [("12345", "tv")]
    assert writes[0][1].media_type == "tv"
    assert body["data"]["media_type"] == "tv"


def test_scrape_select_keeps_invalid_media_type_error(monkeypatch):
    monkeypatch.setattr(scrape_routes, "config_m", SimpleNamespace(config=SimpleNamespace(tmdb_api_key="key")))

    with pytest.raises(HTTPException) as exc:
        scrape_routes.scrape_select(path="D:/Media/TV", tmdb_id=12345, media_type="episode")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid media_type"


class FakeDoubanProvider:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search_metadata(self, request):
        self.search_calls.append(request)
        from provider_models import MetadataCandidate

        return [
            MetadataCandidate(
                providerId="douban",
                externalId="3020000",
                title="进击的巨人",
                originalTitle="進撃の巨人",
                year=2013,
                mediaType="tv",
            )
        ]

    def get_detail(self, external_id, media_type=""):
        self.detail_calls.append((external_id, media_type))
        if media_type != "tv":
            return None
        return MetadataDetail(
            providerId="douban",
            externalId=external_id,
            title="进击的巨人",
            originalTitle="進撃の巨人",
            mediaType="tv",
            year=2013,
            overview="巨人题材动画",
            runtime=24,
            rating=9.1,
            artwork=[ArtworkInfo(kind="poster", url="https://example.com/poster.jpg")],
            extra={
                "genres": ["动画"],
                "directors": ["荒木哲郎"],
                "actors": ["梶裕贵"],
            },
        )


def test_execute_scrape_douban_uses_metadata_provider_and_keeps_shape(monkeypatch):
    provider = FakeDoubanProvider()
    writes = []
    downloads = []
    clean_updates = []

    monkeypatch.setattr(scrape_execute_routes, "get_metadata_provider_map", lambda: {"douban": provider})
    monkeypatch.setattr(scrape_execute_routes.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(scrape_execute_routes.os.path, "isfile", lambda path: False)
    monkeypatch.setattr(scrape_execute_routes.os.path, "exists", lambda path: False)
    monkeypatch.setattr(scrape_execute_routes.os.path, "basename", lambda path: "进击的巨人")
    monkeypatch.setattr(scrape_execute_routes.scraper, "write_tvshow_nfo", lambda path, result: writes.append(("tv", path, result)))
    monkeypatch.setattr(scrape_execute_routes.scraper, "write_movie_nfo", lambda path, result: writes.append(("movie", path, result)))
    monkeypatch.setattr(scrape_execute_routes.scraper, "download_poster", lambda path, url, *args, **kwargs: downloads.append((path, url)))
    monkeypatch.setattr(scrape_execute_routes, "_update_clean_names_after_scrape", lambda path, result: clean_updates.append((path, result)))

    body = scrape_execute_routes._execute_scrape_douban("D:/Media/Anime")
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert provider.search_calls[0].query == "进击的巨人"
    assert provider.detail_calls == [("3020000", "tv")]
    assert writes[0][0] == "tv"
    assert downloads == [("D:/Media/Anime", "https://example.com/poster.jpg")]
    assert clean_updates[0][0] == "D:/Media/Anime"
    assert body["self"]["status"] == "ok"
    assert body["self"]["data"]["tmdb_id"] == 3020000
    assert body["self"]["data"]["media_type"] == "tv"
    assert body["self"]["confidence"]["level"] == "medium"
    assert snapshot.field_types["self.status"] == "str"
    assert snapshot.field_types["self.data.tmdb_id"] == "int"
    assert snapshot.field_types["self.data.media_type"] == "str"
    assert snapshot.field_types["self.confidence.level"] == "str"
