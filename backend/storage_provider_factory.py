"""StorageProvider 工厂清单。"""

from typing import Mapping

from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata
from storage_provider_adapter import StorageClientFactory, StorageProviderAdapter, build_storage_providers


STORAGE_PROVIDER_ORDER = ("openlist_storage",)


def get_storage_client_factories() -> Mapping[str, StorageClientFactory]:
    from downloader import AlistManager
    from shared import config_m

    conf = config_m.config
    factories: dict[str, StorageClientFactory] = {
        "openlist_storage": lambda: AlistManager(conf.alist_url, conf.alist_token),
    }
    return {name: factories[name] for name in STORAGE_PROVIDER_ORDER}


def build_storage_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    client_factories: Mapping[str, StorageClientFactory] | None = None,
) -> list[StorageProviderAdapter]:
    factories = client_factories or get_storage_client_factories()
    storage_metadata = [metadata for metadata in metadata_items if metadata.kind == ProviderKind.STORAGE]
    return build_storage_providers(storage_metadata, factories)


def get_storage_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    client_factories: Mapping[str, StorageClientFactory] | None = None,
) -> Mapping[str, StorageProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    providers = build_storage_providers_from_metadata(metadata, client_factories=client_factories)
    return {provider.metadata().id: provider for provider in providers}
