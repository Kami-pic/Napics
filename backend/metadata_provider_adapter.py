"""元数据源到 MetadataProvider 的通用适配层。

适配层只包装现有 TMDB / 豆瓣 / Bangumi 客户端的搜索与详情能力，不改变刮削决策。
"""

from typing import Any, Callable, Iterable, Mapping, Optional

from provider_context import ProviderContext
from provider_models import (
    AliasSet,
    ArtworkInfo,
    EpisodeInfo,
    MetadataCandidate,
    MetadataDetail,
    MetadataSearchRequest,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
)


MetadataSourceFactory = Callable[[], Any]


class MetadataProviderAdapter:
    kind = ProviderKind.METADATA

    def __init__(self, metadata: ProviderMetadata, source_factory: MetadataSourceFactory):
        if metadata.kind != ProviderKind.METADATA:
            raise ValueError("元数据适配器只接受 metadata 类型 provider metadata")
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

    def search_metadata(self, request: MetadataSearchRequest) -> list[MetadataCandidate]:
        source = self._get_source()
        items = source.search(request)
        limited = items[:request.limit] if request.limit else items
        return [self._to_candidate(item) for item in limited]

    def get_detail(self, external_id: str, media_type: str = "") -> Optional[MetadataDetail]:
        source = self._get_source()
        item = source.get_detail(external_id, media_type)
        if not item:
            return None
        return self._to_detail(item, external_id, media_type)

    def _get_source(self) -> Any:
        if self._source is None:
            self._source = self._source_factory()
        return self._source

    def _to_candidate(self, item: Mapping[str, Any]) -> MetadataCandidate:
        external_id = _first_text(item, "external_id", "tmdb_id", "douban_id", "bgm_id", "id")
        return MetadataCandidate(
            providerId=self.id,
            externalId=external_id,
            title=str(item.get("title") or item.get("name") or ""),
            originalTitle=str(item.get("original_title") or item.get("original_name") or ""),
            year=_int_or_none(item.get("year")),
            mediaType=_normalize_media_type(str(item.get("media_type") or item.get("type") or "")),
            overview=str(item.get("overview") or item.get("summary") or ""),
            posterUrl=str(item.get("poster_url") or item.get("cover_url") or ""),
            rating=_float_or_none(item.get("rating")),
            extra=dict(item),
        )

    def _to_detail(self, item: Mapping[str, Any], external_id: str, media_type: str) -> MetadataDetail:
        title = str(item.get("title") or item.get("name") or "")
        original_title = str(item.get("original_title") or item.get("original_name") or "")
        english_title = str(item.get("english_title") or "")
        detail_media_type = _normalize_media_type(str(item.get("media_type") or item.get("type") or media_type))
        return MetadataDetail(
            providerId=self.id,
            externalId=_first_text(item, "external_id", "tmdb_id", "douban_id", "bgm_id", "id") or str(external_id),
            title=title,
            originalTitle=original_title,
            mediaType=detail_media_type,
            year=_int_or_none(item.get("year")),
            overview=str(item.get("overview") or item.get("summary") or ""),
            runtime=_int_or_none(item.get("runtime")),
            rating=_float_or_none(item.get("rating")),
            aliases=AliasSet(cn=title, en=english_title, original=original_title, aliases=_aliases_from_item(item)),
            episodes=_episodes_from_item(item),
            artwork=_artwork_from_item(item),
        )


def build_metadata_providers(
    metadata_items: Iterable[ProviderMetadata],
    source_factories: Mapping[str, MetadataSourceFactory],
) -> list[MetadataProviderAdapter]:
    providers: list[MetadataProviderAdapter] = []
    for metadata in metadata_items:
        if metadata.kind != ProviderKind.METADATA:
            continue
        factory = source_factories.get(metadata.id)
        if factory is None:
            continue
        providers.append(MetadataProviderAdapter(metadata, factory))
    return providers


def build_metadata_provider_metadata(
    provider_id: str,
    name: str,
    *,
    enabled: bool = True,
    default_enabled: bool = True,
    requires: list[str] | None = None,
    supports_proxy: bool = False,
) -> ProviderMetadata:
    return ProviderMetadata(
        id=provider_id,
        name=name,
        kind=ProviderKind.METADATA,
        type="metadata",
        enabled=enabled,
        defaultEnabled=default_enabled,
        capabilities=["search", "detail", "artwork", "aliases", "episodes"],
        riskLevel=ProviderRiskLevel.LOW,
        requires=requires or [],
        supportsProxy=supports_proxy,
    )


def _first_text(item: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _normalize_media_type(value: str) -> str:
    if value in ("movie", "tv", "season", "episode"):
        return value
    if value in ("动画", "三次元"):
        return "tv"
    return value


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _aliases_from_item(item: Mapping[str, Any]) -> list[str]:
    aliases = item.get("aliases") or item.get("aka") or []
    if isinstance(aliases, str):
        return [part.strip() for part in aliases.split("/") if part.strip()]
    return [str(alias).strip() for alias in aliases if str(alias).strip()]


def _episodes_from_item(item: Mapping[str, Any]) -> list[EpisodeInfo]:
    episodes = item.get("episodes") or []
    result: list[EpisodeInfo] = []
    for episode in episodes:
        if not isinstance(episode, Mapping):
            continue
        ep_num = _int_or_none(episode.get("episode") or episode.get("ep"))
        if ep_num is None:
            continue
        result.append(
            EpisodeInfo(
                season=_int_or_none(episode.get("season")) or 1,
                episode=ep_num,
                title=str(episode.get("title") or episode.get("name_cn") or episode.get("name") or ""),
                airDate=str(episode.get("air_date") or episode.get("airdate") or ""),
            )
        )
    return result


def _artwork_from_item(item: Mapping[str, Any]) -> list[ArtworkInfo]:
    result: list[ArtworkInfo] = []
    poster_url = item.get("poster_url") or item.get("cover_url")
    backdrop_url = item.get("backdrop_url")
    if poster_url:
        result.append(ArtworkInfo(kind="poster", url=str(poster_url)))
    if backdrop_url:
        result.append(ArtworkInfo(kind="backdrop", url=str(backdrop_url)))
    return result
