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


class FakeOpenListClient:
    def __init__(self, result=(True, "task-1")):
        self.result = result
        self.calls = []

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


def test_build_download_providers_filters_download_metadata_only():
    providers = build_download_providers(
        [
            _metadata("qbittorrent", "qBittorrent"),
            ProviderMetadata(id="tmdb", name="TMDB", kind=ProviderKind.METADATA),
        ],
        {"qbittorrent": FakeQBClient},
    )

    assert [provider.metadata().id for provider in providers] == ["qbittorrent"]
