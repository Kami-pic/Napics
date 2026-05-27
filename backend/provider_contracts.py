"""Provider 协议定义。

协议只描述 Core 可依赖的能力，不导入任何具体 provider 实现。
"""

from typing import List, Optional, Protocol, runtime_checkable

from provider_context import ProviderContext
from provider_models import (
    DownloadProgress,
    DownloadFileInfo,
    DownloadRequest,
    DownloadSubmitResult,
    DownloadTaskInfo,
    MetadataCandidate,
    MetadataDetail,
    MetadataSearchRequest,
    PanSearchCandidate,
    ProviderHealth,
    ProviderKind,
    ProviderMetadata,
    RSSCandidate,
    RSSFetchRequest,
    SearchCandidate,
    SearchRequest,
    StorageEntry,
    StorageMountInfo,
)


@runtime_checkable
class Provider(Protocol):
    id: str
    display_name: str
    kind: ProviderKind

    def initialize(self, context: ProviderContext) -> None:
        raise NotImplementedError

    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    def health_check(self) -> ProviderHealth:
        raise NotImplementedError


@runtime_checkable
class SearchProvider(Provider, Protocol):
    def search(self, request: SearchRequest) -> List[SearchCandidate]:
        raise NotImplementedError


@runtime_checkable
class PanSearchProvider(Provider, Protocol):
    def search_pan(self, request: SearchRequest) -> List[PanSearchCandidate]:
        raise NotImplementedError


@runtime_checkable
class RSSProvider(Provider, Protocol):
    def fetch(self, request: RSSFetchRequest) -> List[RSSCandidate]:
        raise NotImplementedError

    def can_download(self, item: RSSCandidate) -> bool:
        raise NotImplementedError


@runtime_checkable
class MetadataProvider(Provider, Protocol):
    def search_metadata(self, request: MetadataSearchRequest) -> List[MetadataCandidate]:
        raise NotImplementedError

    def get_detail(self, external_id: str, media_type: str = "") -> Optional[MetadataDetail]:
        raise NotImplementedError


@runtime_checkable
class DownloadProvider(Provider, Protocol):
    def submit(self, request: DownloadRequest) -> DownloadSubmitResult:
        raise NotImplementedError

    def progress(self, external_task_id: str) -> DownloadProgress:
        raise NotImplementedError

    def list_tasks(self, status: str = "") -> List[DownloadTaskInfo]:
        raise NotImplementedError

    def list_files(self, external_task_id: str) -> List[DownloadFileInfo]:
        raise NotImplementedError


@runtime_checkable
class StorageProvider(Provider, Protocol):
    def list_dir(self, path: str) -> List[StorageEntry]:
        raise NotImplementedError

    def list_mounts(self) -> List[StorageMountInfo]:
        raise NotImplementedError

    def exists(self, path: str) -> bool:
        raise NotImplementedError
