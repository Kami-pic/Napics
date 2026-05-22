import requests

from searcher import ProwlarrClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_prowlarr_search_prefers_infohash_built_magnet(monkeypatch):
    payload = [
        {
            "title": "JoJo's Bizarre Adventure S01E01 1080p",
            "size": 5 * 1024**3,
            "indexer": "Prowlarr",
            "seeders": 12,
            "leechers": 2,
            "infoHash": "ABCDEF1234567890ABCDEF1234567890ABCDEF12",
            "magnetUrl": "magnet:?xt=urn:btih:old",
            "downloadUrl": "http://127.0.0.1:9696/download?id=1",
        }
    ]

    monkeypatch.setattr("searcher.requests.get", lambda *args, **kwargs: FakeResponse(payload))

    client = ProwlarrClient("http://prowlarr", "token")
    results = client.search("jojo")

    assert len(results) == 1
    assert results[0].download_url == (
        "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        "&dn=JoJo%27s%20Bizarre%20Adventure%20S01E01%201080p"
    )


def test_prowlarr_search_falls_back_to_real_magnet_url(monkeypatch):
    payload = [
        {
            "title": "Attack on Titan S01E01",
            "size": 2 * 1024**3,
            "indexer": "Prowlarr",
            "seeders": 8,
            "leechers": 1,
            "infoHash": "",
            "magnetUrl": "magnet:?xt=urn:btih:feedface",
            "downloadUrl": "http://127.0.0.1:9696/download?id=2",
        }
    ]

    monkeypatch.setattr("searcher.requests.get", lambda *args, **kwargs: FakeResponse(payload))

    client = ProwlarrClient("http://prowlarr", "token")
    results = client.search("aot")

    assert len(results) == 1
    assert results[0].download_url == "magnet:?xt=urn:btih:feedface"
