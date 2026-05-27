"""RSS 源到 RSSProvider 的通用适配层。

适配层只包装已有 RSSSourceBase.fetch()，不改变订阅匹配、轮询和下载决策。
"""

from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    RSSCandidate,
    RSSFetchRequest,
)


RSSSourceFactory = Callable[[], Any]


class RSSProviderAdapter:
    kind = ProviderKind.RSS

    def __init__(self, metadata: ProviderMetadata, source_factory: RSSSourceFactory):
        if metadata.kind != ProviderKind.RSS:
            raise ValueError("RSS 适配器只接受 rss 类型 provider metadata")
        self.id = metadata.id
        self.display_name = metadata.name
        self._metadata = metadata
        self._source_factory = source_factory
        self._context: Optional[ProviderContext] = None
        self._source: Any = None

    def initialize(self, context: ProviderContext) -> None:
        self._context = context

    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.OK if self._metadata.enabled else ProviderHealthStatus.DISABLED)

    def fetch(self, request: RSSFetchRequest) -> list[RSSCandidate]:
        source = self._get_source()
        subscription = _request_to_subscription(request)
        items = source.fetch(subscription)
        limited = items[:request.limit] if request.limit else items
        return [self._to_candidate(item) for item in limited]

    def can_download(self, item: RSSCandidate) -> bool:
        source = self._get_source()
        legacy_item = SimpleNamespace(download_url=item.download_url)
        return bool(source.can_download(legacy_item))

    def _get_source(self) -> Any:
        if self._source is None:
            self._source = self._source_factory()
        return self._source

    def _to_candidate(self, item: Any) -> RSSCandidate:
        return RSSCandidate(
            title=item.title,
            downloadUrl=item.download_url,
            infoUrl=item.info_url,
            sizeGb=item.size_gb,
            infoHash=item.info_hash,
            qualityTag=item.quality_tag,
            resolution=item.resolution,
            episode=item.episode,
            season=item.season,
            providerId=self.id,
            seeders=item.seeders,
            indexer=item.indexer or item.source_name,
        )


def build_rss_providers(
    metadata_items: Iterable[ProviderMetadata],
    source_factories: Mapping[str, RSSSourceFactory],
) -> list[RSSProviderAdapter]:
    providers: list[RSSProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.RSS:
            continue
        source_name = _metadata_id_to_source_name(metadata.id)
        factory = source_factories.get(source_name)
        if factory is None:
            continue
        providers.append(RSSProviderAdapter(metadata, factory))
    return providers


def build_rss_provider_metadata(
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
        kind=ProviderKind.RSS,
        type="rss",
        enabled=enabled,
        defaultEnabled=default_enabled,
        capabilities=["rss", "download_url"],
        riskLevel=ProviderRiskLevel.HIGH,
        supportsProxy=supports_proxy,
    )


def _metadata_id_to_source_name(provider_id: str) -> str:
    return provider_id[4:] if provider_id.startswith("rss_") else provider_id


def _request_to_subscription(request: RSSFetchRequest) -> SimpleNamespace:
    keywords = request.keywords
    aliases = {
        "cn": [keywords.cn] if keywords.cn else [],
        "en": [keywords.en] if keywords.en else [],
        "original": [keywords.original] if keywords.original else [],
    }
    return SimpleNamespace(
        id=request.subscription_id,
        title=request.title,
        type=request.media_type,
        search_keyword=request.title,
        season=None,
        aliases=aliases,
        imdb_id="",
        tmdb_id=None,
        douban_id=None,
        year="",
    )
