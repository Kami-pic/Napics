from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from provider_models import AliasSet, ArtworkInfo, MetadataDetail
from routes import scrape as scrape_routes
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
