"""BT 直搜源到 SearchProvider 的通用适配层。

适配层只消费已有 scraper 的 `search_as_search_results()`，不进入具体站点 parser。
"""

from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    SearchCandidate,
    SearchRequest,
)


ScraperFactory = Callable[[], Any]


class DirectBTSearchProviderAdapter:
    kind = ProviderKind.SEARCH

    def __init__(self, metadata: ProviderMetadata, scraper_factory: ScraperFactory):
        if metadata.kind != ProviderKind.SEARCH:
            raise ValueError("BT 搜索适配器只接受 search 类型 provider metadata")
        self.id = metadata.id
        self.display_name = metadata.name
        self._metadata = metadata
        self._scraper_factory = scraper_factory
        self._context: Optional[ProviderContext] = None
        self._scraper: Any = None

    def initialize(self, context: ProviderContext) -> None:
        self._context = context

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.OK if self._metadata.enabled else ProviderHealthStatus.DISABLED)

    def search(self, request: SearchRequest) -> list[SearchCandidate]:
        scraper = self._get_scraper()
        results = scraper.search_as_search_results(request.query, max_results=request.limit)
        return [self._to_candidate(result) for result in results]

    def _get_scraper(self) -> Any:
        if self._scraper is None:
            self._scraper = self._scraper_factory()
        return self._scraper

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


def build_direct_bt_search_providers(
    metadata_items: Iterable[ProviderMetadata],
    scraper_factories: Mapping[str, ScraperFactory],
) -> list[DirectBTSearchProviderAdapter]:
    providers: list[DirectBTSearchProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.SEARCH or metadata.type != "bt":
            continue
        factory = scraper_factories.get(metadata.id)
        if factory is None:
            continue
        providers.append(DirectBTSearchProviderAdapter(metadata, factory))
    return providers


def build_direct_bt_search_metadata(
    provider_id: str,
    name: str,
    *,
    enabled: bool = True,
    default_enabled: bool = True,
    supports_proxy: bool = False,
) -> ProviderMetadata:
    return ProviderMetadata(
        id=provider_id,
        name=name,
        kind=ProviderKind.SEARCH,
        type="bt",
        enabled=enabled,
        defaultEnabled=default_enabled,
        capabilities=["search", "magnet", "torrent", "size", "seeders"],
        riskLevel=ProviderRiskLevel.HIGH,
        supportsProxy=supports_proxy,
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
