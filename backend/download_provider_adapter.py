"""下载客户端到 DownloadProvider 的通用适配层。

适配层只包装现有 qB / OpenList 提交能力，不改变下载状态机或进度同步逻辑。
"""

from typing import Any, Callable, Iterable, Mapping, Optional

import requests

from provider_context import ProviderContext
from provider_models import (
    DownloadProgress,
    DownloadRequest,
    DownloadSubmitResult,
    DownloadTaskInfo,
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
        client = self._get_client()
        if self.id == "qbittorrent":
            return self._progress_qb(client, external_task_id)
        if self.id == "openlist":
            return self._progress_openlist(client, external_task_id)
        return DownloadProgress(
            externalTaskId=external_task_id,
            progress=0.0,
            status="unknown",
        )

    def list_tasks(self) -> list[DownloadTaskInfo]:
        client = self._get_client()
        if self.id == "qbittorrent":
            return self._list_qb_tasks(client)
        return []

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

    def _progress_qb(self, client: Any, external_task_id: str) -> DownloadProgress:
        try:
            if not client._login():
                return DownloadProgress(externalTaskId=external_task_id, status="unknown")
            response = client.session.get(
                f"{client.url}/api/v2/torrents/info",
                params={"hashes": external_task_id},
                timeout=5,
            )
            if response.status_code != 200:
                return DownloadProgress(externalTaskId=external_task_id, status="unknown")
            torrents = response.json()
            if not torrents:
                return DownloadProgress(externalTaskId=external_task_id, status="lost")
            item = torrents[0]
            return DownloadProgress(
                externalTaskId=external_task_id,
                progress=round(float(item.get("progress", 0) or 0), 4),
                speed=_format_qb_speed(item.get("dlspeed", 0)),
                eta=_format_qb_eta(item.get("eta", 0)),
                status=str(item.get("state", "")),
            )
        except Exception:
            return DownloadProgress(externalTaskId=external_task_id, status="unknown")

    def _progress_openlist(self, client: Any, external_task_id: str) -> DownloadProgress:
        task_id = (external_task_id or "").strip()
        if not task_id or task_id.startswith("alist_"):
            return DownloadProgress(externalTaskId=external_task_id, status="unknown")
        try:
            response = requests.post(
                f"{client.api_url}/api/task/offline_download/info",
                headers=client.headers,
                params={"tid": task_id},
                timeout=5,
            )
            if response.status_code != 200:
                return DownloadProgress(externalTaskId=external_task_id, status="unknown")
            item = _first_openlist_task_item(response.json())
            if item is None:
                return DownloadProgress(externalTaskId=external_task_id, status="unknown")
            return DownloadProgress(
                externalTaskId=external_task_id,
                progress=_normalize_openlist_progress(item.get("progress", 0)),
                status=str(item.get("state", "")),
                extra={"error": str(item.get("error", "")).strip()},
            )
        except Exception:
            return DownloadProgress(externalTaskId=external_task_id, status="unknown")

    def _list_qb_tasks(self, client: Any) -> list[DownloadTaskInfo]:
        try:
            if not client._login():
                return []
            response = client.session.get(f"{client.url}/api/v2/torrents/info", timeout=5)
            if response.status_code != 200:
                return []
            items = response.json()
            if not isinstance(items, list):
                return []
            return [_qb_task_info(item) for item in items if isinstance(item, Mapping)]
        except Exception:
            return []


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


def _format_qb_speed(value: Any) -> str:
    try:
        speed = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if speed >= 1024 * 1024:
        return f"{speed / (1024 * 1024):.1f} MB/s"
    if speed > 0:
        return f"{speed / 1024:.0f} KB/s"
    return ""


def _format_qb_eta(value: Any) -> str:
    try:
        eta_secs = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if not eta_secs or eta_secs >= 8640000:
        return ""
    hours, rem = divmod(eta_secs, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _first_openlist_task_item(payload: Any) -> Mapping[str, Any] | None:
    data = payload.get("data", []) if isinstance(payload, Mapping) else []
    if isinstance(data, Mapping):
        return data
    if isinstance(data, list) and data:
        item = data[0]
        return item if isinstance(item, Mapping) else None
    return None


def _normalize_openlist_progress(progress: Any) -> float:
    try:
        value = float(progress)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    if value > 1:
        value = value / 100
    return round(min(value, 1.0), 4)


def _qb_task_info(item: Mapping[str, Any]) -> DownloadTaskInfo:
    return DownloadTaskInfo(
        externalTaskId=str(item.get("hash", "")),
        name=str(item.get("name", "")),
        savePath=str(item.get("save_path", "")),
        progress=round(float(item.get("progress", 0) or 0), 4),
        speed=_format_qb_speed(item.get("dlspeed", 0)),
        eta=_format_qb_eta(item.get("eta", 0)),
        status=str(item.get("state", "")),
        extra=dict(item),
    )
