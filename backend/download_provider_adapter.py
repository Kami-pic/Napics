"""下载客户端到 DownloadProvider 的通用适配层。

适配层只包装现有 qB / OpenList 提交能力，不改变下载状态机或进度同步逻辑。
"""

from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    DownloadProgress,
    DownloadRequest,
    DownloadSubmitResult,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
)


DownloadClientFactory = Callable[[], Any]


class DownloadProviderAdapter:
    kind = ProviderKind.DOWNLOAD

    def __init__(self, metadata: ProviderMetadata, client_factory: DownloadClientFactory):
        if metadata.kind != ProviderKind.DOWNLOAD:
            raise ValueError("下载适配器只接受 download 类型 provider metadata")
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

    def submit(self, request: DownloadRequest) -> DownloadSubmitResult:
        client = self._get_client()
        if self.id == "qbittorrent":
            return self._submit_qb(client, request)
        if self.id == "openlist":
            return self._submit_openlist(client, request)
        return DownloadSubmitResult(success=False, errorCode="unsupported_provider", message="不支持的下载 provider")

    def progress(self, external_task_id: str) -> DownloadProgress:
        return DownloadProgress(
            externalTaskId=external_task_id,
            progress=0.0,
            status="unknown",
        )

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _submit_qb(self, client: Any, request: DownloadRequest) -> DownloadSubmitResult:
        try:
            success = client.add_torrent(request.url, request.save_path)
        except Exception as exc:
            return DownloadSubmitResult(success=False, errorCode="qbittorrent_error", message=str(exc))
        return DownloadSubmitResult(
            success=bool(success),
            errorCode="" if success else "qbittorrent_error",
            message="" if success else "qBittorrent 推送失败",
        )

    def _submit_openlist(self, client: Any, request: DownloadRequest) -> DownloadSubmitResult:
        try:
            result = client.transfer_link(request.url, request.save_path)
        except Exception as exc:
            return DownloadSubmitResult(success=False, errorCode="openlist_error", message=str(exc))
        success, task_id = _normalize_transfer_result(result)
        return DownloadSubmitResult(
            success=success,
            externalTaskId=task_id,
            errorCode="" if success else "openlist_error",
            message="" if success else "OpenList 推送失败",
        )


def build_download_providers(
    metadata_items: Iterable[ProviderMetadata],
    client_factories: Mapping[str, DownloadClientFactory],
) -> list[DownloadProviderAdapter]:
    providers: list[DownloadProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.DOWNLOAD:
            continue
        factory = client_factories.get(metadata.id)
        if factory is None:
            continue
        providers.append(DownloadProviderAdapter(metadata, factory))
    return providers


def _normalize_transfer_result(result: Any) -> tuple[bool, str]:
    if isinstance(result, tuple):
        success = bool(result[0]) if result else False
        task_id = str(result[1]).strip() if len(result) > 1 and result[1] else ""
        return success, task_id
    if isinstance(result, bool):
        return result, ""
    return False, ""
