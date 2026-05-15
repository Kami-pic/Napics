from types import SimpleNamespace

from provider_models import DownloadSubmitResult
from routes import download as download_routes


class FakeDownloadProvider:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def submit(self, request):
        self.calls.append((request.url, request.save_path))
        return DownloadSubmitResult(success=self.success, externalTaskId="task-1")


def test_download_route_submits_qb_via_download_provider(monkeypatch):
    provider = FakeDownloadProvider(success=True)
    monkeypatch.setattr(
        download_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(qb_url="http://qb", alist_url="", alist_token="")),
    )
    monkeypatch.setattr(download_routes, "get_download_provider_map", lambda: {"qbittorrent": provider})

    response = download_routes.trigger_download(
        download_routes.DownloadRequest(
            url="magnet:?xt=urn:btih:abc",
            save_path="D:/Downloads",
            download_type="qb",
        )
    )

    assert response == {"success": True, "message": "任务已下达"}
    assert provider.calls == [("magnet:?xt=urn:btih:abc", "D:/Downloads")]


def test_download_route_submits_openlist_via_download_provider(monkeypatch):
    provider = FakeDownloadProvider(success=True)
    monkeypatch.setattr(
        download_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(qb_url="", alist_url="http://alist", alist_token="token")),
    )
    monkeypatch.setattr(download_routes, "get_download_provider_map", lambda: {"openlist": provider})

    response = download_routes.trigger_download(
        download_routes.DownloadRequest(
            url="https://example.test/file",
            save_path="/downloads",
            download_type="alist",
        )
    )

    assert response == {"success": True, "message": "任务已下达"}
    assert provider.calls == [("https://example.test/file", "/downloads")]


def test_batch_download_keeps_legacy_response_shape_with_download_provider(monkeypatch):
    qb_provider = FakeDownloadProvider(success=True)
    openlist_provider = FakeDownloadProvider(success=False)
    monkeypatch.setattr(
        download_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(qb_url="http://qb", alist_url="http://alist", alist_token="token")),
    )
    monkeypatch.setattr(
        download_routes,
        "get_download_provider_map",
        lambda: {"qbittorrent": qb_provider, "openlist": openlist_provider},
    )

    response = download_routes.batch_download(
        download_routes.BatchDownloadRequest(
            tasks=[
                download_routes.BatchDownloadTask(download_url="magnet:?xt=urn:btih:abc", save_path="D:/Downloads", download_type="qb"),
                download_routes.BatchDownloadTask(download_url="https://example.test/file", save_path="/downloads", download_type="alist"),
            ]
        )
    )

    assert response == {
        "results": [
            {"index": 0, "success": True, "message": "任务已下达"},
            {"index": 1, "success": False, "message": "执行异常"},
        ]
    }
    assert qb_provider.calls == [("magnet:?xt=urn:btih:abc", "D:/Downloads")]
    assert openlist_provider.calls == [("https://example.test/file", "/downloads")]


def test_download_route_still_rejects_unconfigured_and_unknown_download_type(monkeypatch):
    monkeypatch.setattr(
        download_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(qb_url="", alist_url="", alist_token="")),
    )

    qb_response = download_routes.trigger_download(
        download_routes.DownloadRequest(url="magnet:?xt=urn:btih:abc", save_path="", download_type="qb")
    )
    unknown_response = download_routes.trigger_download(
        download_routes.DownloadRequest(url="x", save_path="", download_type="other")
    )

    assert qb_response == {"success": False, "message": "qBittorrent 未配置"}
    assert unknown_response == {"success": False, "message": "不支持的下载类型: other"}
