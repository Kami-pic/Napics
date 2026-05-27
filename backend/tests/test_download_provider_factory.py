from download_provider_factory import get_download_provider_map
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind


class FakeQBClient:
    def add_torrent(self, url, save_path):
        return True


class FakeOpenListClient:
    def transfer_link(self, url, save_path):
        return True, "task-1"


def test_download_provider_factory_builds_qb_and_openlist_from_static_metadata():
    providers = get_download_provider_map(
        build_builtin_provider_metadata(),
        client_factories={
            "qbittorrent": FakeQBClient,
            "openlist": FakeOpenListClient,
        },
    )

    assert list(providers.keys()) == ["qbittorrent", "openlist"]
    assert providers["qbittorrent"].metadata().kind == ProviderKind.DOWNLOAD
    assert providers["openlist"].metadata().kind == ProviderKind.DOWNLOAD


def test_download_provider_metadata_is_exposed_in_builtin_catalog():
    metadata = build_builtin_provider_metadata()

    downloads = [item for item in metadata if item.kind == ProviderKind.DOWNLOAD]
    qb = next(item for item in downloads if item.id == "qbittorrent")
    openlist = next(item for item in downloads if item.id == "openlist")

    assert len(downloads) == 2
    assert qb.risk_level == "user_configured"
    assert qb.requires == ["api_url", "username", "password"]
    assert openlist.requires == ["api_url", "token"]
