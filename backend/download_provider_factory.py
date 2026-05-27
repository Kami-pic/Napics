"""DownloadProvider 工厂清单。

此模块是 Phase 7 的兼容桥：集中 qB / OpenList provider 构造逻辑，但不改旧下载调用链。
"""

from typing import Mapping

from download_provider_adapter import DownloadClientFactory, DownloadProviderAdapter, build_download_providers
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata


DOWNLOAD_PROVIDER_ORDER = ("qbittorrent", "openlist")


def get_download_client_factories() -> Mapping[str, DownloadClientFactory]:
    from downloader import AlistManager, QBittorrentClient
    from shared import config_m

    conf = config_m.config
    factories: dict[str, DownloadClientFactory] = {
        "qbittorrent": lambda: QBittorrentClient(conf.qb_url, conf.qb_username, conf.qb_password),
        "openlist": lambda: AlistManager(conf.alist_url, conf.alist_token),
    }
    return {name: factories[name] for name in DOWNLOAD_PROVIDER_ORDER}


def build_download_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    client_factories: Mapping[str, DownloadClientFactory] | None = None,
) -> list[DownloadProviderAdapter]:
    factories = client_factories or get_download_client_factories()
    download_metadata = [metadata for metadata in metadata_items if metadata.kind == ProviderKind.DOWNLOAD]
    return build_download_providers(download_metadata, factories)


def get_download_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    client_factories: Mapping[str, DownloadClientFactory] | None = None,
) -> Mapping[str, DownloadProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    providers = build_download_providers_from_metadata(metadata, client_factories=client_factories)
    return {provider.metadata().id: provider for provider in providers}
