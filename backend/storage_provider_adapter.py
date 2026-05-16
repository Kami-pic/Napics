"""OpenList 客户端到 StorageProvider 的只读适配层。"""

from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    StorageEntry,
    StorageMountInfo,
)


StorageClientFactory = Callable[[], Any]


class StorageProviderAdapter:
    kind = ProviderKind.STORAGE

    def __init__(self, metadata: ProviderMetadata, client_factory: StorageClientFactory):
        if metadata.kind != ProviderKind.STORAGE:
            raise ValueError("存储适配器只接受 storage 类型 provider metadata")
        self.id = metadata.id
        self.display_name = metadata.name
        self._metadata = metadata
        self._client_factory = client_factory
        self._context: Optional[ProviderContext] = None
        self._client: Any = None

    def initialize(self, context: ProviderContext) -> None:
        self._context = context

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.OK if self._metadata.enabled else ProviderHealthStatus.DISABLED)

    def list_dir(self, path: str) -> list[StorageEntry]:
        return []

    def list_mounts(self) -> list[StorageMountInfo]:
        client = self._get_client()
        if self.id != "openlist_storage":
            return []
        return [
            StorageMountInfo(
                panType=str(item.get("pan_type", "")),
                driver=str(item.get("driver", "")),
                mountPath=str(item.get("mount_path", "")),
                status=str(item.get("status", "")),
            )
            for item in _mount_items(client.get_mounts_list())
        ]

    def exists(self, path: str) -> bool:
        return False

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client


def build_storage_providers(
    metadata_items: Iterable[ProviderMetadata],
    client_factories: Mapping[str, StorageClientFactory],
) -> list[StorageProviderAdapter]:
    providers: list[StorageProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.STORAGE:
            continue
        factory = client_factories.get(metadata.id)
        if factory is None:
            continue
        providers.append(StorageProviderAdapter(metadata, factory))
    return providers


def _mount_items(items: Any) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    if not isinstance(items, list):
        return result
    for item in items:
        if isinstance(item, Mapping):
            result.append(item)
            continue
        if hasattr(item, "model_dump"):
            result.append(item.model_dump())
            continue
        if hasattr(item, "dict"):
            result.append(item.dict())
    return result
