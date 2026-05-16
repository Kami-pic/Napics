from download_provider_adapter import DownloadProviderAdapter, build_download_providers
from provider_context import ProviderContext
from provider_contracts import DownloadProvider
from provider_models import DownloadRequest, ProviderKind, ProviderMetadata


class FakeQBClient:
    def __init__(self, success=True):
        self.success = success
        self.calls = []

    def add_torrent(self, url, save_path):
        self.calls.append((url, save_path))
        return self.success


class FakeQBProgressSession:
    def __init__(self, response, list_response=None):
        self.response = response
        self.list_response = list_response or response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.response if params else self.list_response


class FakeQBProgressClient:
    url = "http://qb"

    def __init__(self, response, login_result=True, list_response=None):
        self.login_result = login_result
        self.session = FakeQBProgressSession(response, list_response=list_response)

    def _login(self):
        return self.login_result


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeOpenListClient:
    def __init__(self, result=(True, "task-1")):
        self.result = result
        self.calls = []
        self.api_url = "http://alist"
        self.headers = {"Authorization": "token"}

    def transfer_link(self, url, save_path):
        self.calls.append((url, save_path))
        return self.result


def _metadata(provider_id: str, name: str) -> ProviderMetadata:
    return ProviderMetadata(
        id=provider_id,
        name=name,
        kind=ProviderKind.DOWNLOAD,
        type="download",
        enabled=True,
        defaultEnabled=True,
        capabilities=["submit", "progress"],
    )


def test_qbittorrent_download_provider_submits_existing_client_call():
    client = FakeQBClient()
    provider = DownloadProviderAdapter(_metadata("qbittorrent", "qBittorrent"), lambda: client)
    provider.initialize(ProviderContext())

    result = provider.submit(
        DownloadRequest(
            url="magnet:?xt=urn:btih:abc",
            savePath="D:/Downloads",
        )
    )

    assert isinstance(provider, DownloadProvider)
    assert result.success is True
    assert result.external_task_id == ""
    assert client.calls == [("magnet:?xt=urn:btih:abc", "D:/Downloads")]


def test_openlist_download_provider_returns_task_id_from_transfer_link():
    client = FakeOpenListClient((True, "openlist-task-1"))
    provider = DownloadProviderAdapter(_metadata("openlist", "OpenList"), lambda: client)

    result = provider.submit(
        DownloadRequest(
            url="https://example.test/file",
            savePath="/downloads",
        )
    )

    assert result.success is True
    assert result.external_task_id == "openlist-task-1"
    assert client.calls == [("https://example.test/file", "/downloads")]


def test_download_provider_progress_is_structured_unknown_until_state_machine_migrates():
    provider = DownloadProviderAdapter(_metadata("qbittorrent", "qBittorrent"), FakeQBClient)

    progress = provider.progress("hash-1")

    assert progress.external_task_id == "hash-1"
    assert progress.status == "unknown"
    assert progress.progress == 0.0


def test_qbittorrent_download_provider_progress_reads_client_status():
    client = FakeQBProgressClient(
        FakeResponse(
            200,
            [
                {
                    "progress": 0.37567,
                    "dlspeed": 3 * 1024 * 1024,
                    "eta": 90,
                    "state": "downloading",
                }
            ],
        )
    )
    provider = DownloadProviderAdapter(_metadata("qbittorrent", "qBittorrent"), lambda: client)

    progress = provider.progress("hash-1")

    assert progress.external_task_id == "hash-1"
    assert progress.progress == 0.3757
    assert progress.speed == "3.0 MB/s"
    assert progress.eta == "00:01:30"
    assert progress.status == "downloading"
    assert client.session.calls[0]["params"] == {"hashes": "hash-1"}


def test_qbittorrent_download_provider_progress_returns_lost_when_hash_missing():
    client = FakeQBProgressClient(FakeResponse(200, []))
    provider = DownloadProviderAdapter(_metadata("qbittorrent", "qBittorrent"), lambda: client)

    progress = provider.progress("hash-1")

    assert progress.status == "lost"


def test_qbittorrent_download_provider_lists_tasks():
    client = FakeQBProgressClient(
        FakeResponse(200, []),
        list_response=FakeResponse(
            200,
            [
                {
                    "hash": "hash-1",
                    "name": "Show S01",
                    "save_path": "D:/Downloads",
                    "progress": 0.5,
                    "dlspeed": 2048,
                    "eta": 60,
                    "state": "downloading",
                }
            ],
        ),
    )
    provider = DownloadProviderAdapter(_metadata("qbittorrent", "qBittorrent"), lambda: client)

    tasks = provider.list_tasks()

    assert len(tasks) == 1
    assert tasks[0].external_task_id == "hash-1"
    assert tasks[0].name == "Show S01"
    assert tasks[0].save_path == "D:/Downloads"
    assert tasks[0].speed == "2 KB/s"


def test_openlist_download_provider_progress_reads_task_info(monkeypatch):
    client = FakeOpenListClient()
    post_calls = []

    def fake_post(url, headers=None, params=None, timeout=None):
        post_calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return FakeResponse(
            200,
            {"data": [{"id": "task-real-123", "state": "succeeded", "progress": 100, "error": ""}]},
        )

    monkeypatch.setattr("download_provider_adapter.requests.post", fake_post)
    provider = DownloadProviderAdapter(_metadata("openlist", "OpenList"), lambda: client)

    progress = provider.progress("task-real-123")

    assert progress.external_task_id == "task-real-123"
    assert progress.status == "succeeded"
    assert progress.progress == 1.0
    assert post_calls == [
        {
            "url": "http://alist/api/task/offline_download/info",
            "headers": {"Authorization": "token"},
            "params": {"tid": "task-real-123"},
            "timeout": 5,
        }
    ]


def test_openlist_download_provider_progress_skips_legacy_marker():
    provider = DownloadProviderAdapter(_metadata("openlist", "OpenList"), FakeOpenListClient)

    progress = provider.progress("alist_task-1")

    assert progress.status == "unknown"


def test_build_download_providers_filters_download_metadata_only():
    providers = build_download_providers(
        [
            _metadata("qbittorrent", "qBittorrent"),
            ProviderMetadata(id="tmdb", name="TMDB", kind=ProviderKind.METADATA),
        ],
        {"qbittorrent": FakeQBClient},
    )

    assert [provider.metadata().id for provider in providers] == ["qbittorrent"]
