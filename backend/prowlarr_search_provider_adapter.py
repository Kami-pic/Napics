"""Prowlarr 搜索客户端到 SearchProvider 的适配层。

适配层只包装现有 ProwlarrClient.search()，不改变请求、下载链接选择或错误处理。
"""

from typing import Any, Callable, Optional

from provider_context import ProviderContext
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    SearchCandidate,
    SearchRequest,
)


ProwlarrClientFactory = Callable[[], Any]


class ProwlarrSearchProviderAdapter:
    kind = ProviderKind.SEARCH

    def __init__(self, metadata: ProviderMetadata, client_factory: ProwlarrClientFactory):
        if metadata.kind != ProviderKind.SEARCH:
            raise ValueError("Prowlarr 搜索适配器只接受 search 类型 provider metadata")
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

    def search(self, request: SearchRequest) -> list[SearchCandidate]:
        client = self._get_client()
        results = client.search(request.query)
        limited = results[:request.limit] if request.limit else results
        return [self._to_candidate(result) for result in limited]

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _to_candidate(self, result: Any) -> SearchCandidate:
        return SearchCandidate(
            title=result.title,
            downloadUrl=result.download_url,
            infoUrl=result.info_url or "",
            sizeGb=result.size_gb,
            seeders=result.seeders,
            leechers=result.leechers,
            rawQuality=result.quality_tag,
            providerId=self.id,
            indexer=result.indexer,
            infoHash=_extract_info_hash(result.download_url),
        )


def _extract_info_hash(download_url: str) -> str:
    marker = "btih:"
    lower_url = download_url.lower()
    start = lower_url.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    value = download_url[start:start + 40]
    return value.upper() if len(value) == 40 else ""
