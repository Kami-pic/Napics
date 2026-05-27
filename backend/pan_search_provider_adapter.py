"""网盘搜索源到 PanSearchProvider 的通用适配层。

适配层只包装已有 scraper 的 `search()` 输出，不进入具体站点 parser。
"""

from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    PanSearchCandidate,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    SearchRequest,
)


PanScraperFactory = Callable[[], Any]


class PanSearchProviderAdapter:
    kind = ProviderKind.PAN_SEARCH

    def __init__(self, metadata: ProviderMetadata, scraper_factory: PanScraperFactory):
        if metadata.kind != ProviderKind.PAN_SEARCH:
            raise ValueError("网盘搜索适配器只接受 pan_search 类型 provider metadata")
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

    def search_pan(self, request: SearchRequest) -> list[PanSearchCandidate]:
        scraper = self._get_scraper()
        results = scraper.search(request.query)
        limited = results[:request.limit] if request.limit > 0 else results
        return [self._to_candidate(result) for result in limited]

    def _get_scraper(self) -> Any:
        if self._scraper is None:
            self._scraper = self._scraper_factory()
        return self._scraper

    def _to_candidate(self, result: Any) -> PanSearchCandidate:
        return PanSearchCandidate(
            title=result.title,
            cleanTitle=result.clean_title or result.title,
            shareUrl=result.share_url,
            panType=result.pan_type.value if hasattr(result.pan_type, "value") else str(result.pan_type),
            password=result.password or "",
            sourceProviderId=self.id,
            fileSize=_format_file_size(getattr(result, "size_gb", 0.0)),
            resolution=result.resolution or "",
        )


def build_pan_search_providers(
    metadata_items: Iterable[ProviderMetadata],
    scraper_factories: Mapping[str, PanScraperFactory],
) -> list[PanSearchProviderAdapter]:
    providers: list[PanSearchProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.PAN_SEARCH:
            continue
        factory = scraper_factories.get(metadata.id)
        if factory is None:
            continue
        providers.append(PanSearchProviderAdapter(metadata, factory))
    return providers


def build_pan_search_metadata(
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
        kind=ProviderKind.PAN_SEARCH,
        type="pan",
        enabled=enabled,
        defaultEnabled=default_enabled,
        capabilities=["search", "share_link"],
        riskLevel=ProviderRiskLevel.PRIVATE,
        supportsProxy=supports_proxy,
    )


def _format_file_size(size_gb: Any) -> str:
    try:
        value = float(size_gb or 0)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    return f"{value:g} GB"
