"""MetadataProvider 工厂清单。

此模块是 Phase 5 的兼容桥：集中现有元数据客户端构造函数，但不改旧刮削调用链路。
"""

from typing import Mapping

from metadata_provider_adapter import (
    MetadataProviderAdapter,
    MetadataSourceFactory,
    build_metadata_providers,
)
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import MetadataSearchRequest, ProviderKind, ProviderMetadata


METADATA_SOURCE_ORDER = ("tmdb", "douban", "bangumi")


class TMDBMetadataSource:
    def __init__(self, client):
        self._client = client

    def search(self, request: MetadataSearchRequest) -> list[dict]:
        if request.media_type == "movie":
            return [_tmdb_search_item(item, "movie") for item in self._client.search_movie(request.query)]
        if request.media_type == "tv":
            return [_tmdb_search_item(item, "tv") for item in self._client.search_tv(request.query)]
        return (
            [_tmdb_search_item(item, "movie") for item in self._client.search_movie(request.query)]
            + [_tmdb_search_item(item, "tv") for item in self._client.search_tv(request.query)]
        )

    def get_detail(self, external_id: str, media_type: str = "") -> dict | None:
        tmdb_id = int(external_id)
        if media_type == "tv":
            return self._client.get_tv_detail(tmdb_id).dict()
        return self._client.get_movie_detail(tmdb_id).dict()


class DoubanMetadataSource:
    def __init__(self, client):
        self._client = client

    def search(self, request: MetadataSearchRequest) -> list[dict]:
        return self._client.search(request.query, count=request.limit)

    def get_detail(self, external_id: str, media_type: str = "") -> dict | None:
        return self._client.get_detail(external_id, media_type or "movie")


class BangumiMetadataSource:
    def __init__(self, client):
        self._client = client

    def search(self, request: MetadataSearchRequest) -> list[dict]:
        type_filter = 2 if request.media_type == "tv" else 0
        return self._client.search(request.query, type_filter=type_filter)

    def get_detail(self, external_id: str, media_type: str = "") -> dict | None:
        detail = self._client.get_detail(int(external_id))
        if not detail:
            return None
        episodes = self._client.get_episodes(int(external_id))
        return {**detail, "episodes": episodes, "media_type": media_type or "tv"}


def get_metadata_source_factories() -> Mapping[str, MetadataSourceFactory]:
    import bangumi_client
    import douban_api_v2
    from shared import config_m
    from tmdb_client import TMDBClient

    def _build_tmdb() -> TMDBMetadataSource:
        return TMDBMetadataSource(
            TMDBClient(
                config_m.config.tmdb_api_key,
                proxy=getattr(config_m.config, "http_proxy", "") or "",
            )
        )

    factories: dict[str, MetadataSourceFactory] = {
        "tmdb": _build_tmdb,
        "douban": lambda: DoubanMetadataSource(douban_api_v2),
        "bangumi": lambda: BangumiMetadataSource(bangumi_client),
    }
    return {name: factories[name] for name in METADATA_SOURCE_ORDER}


def build_metadata_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    source_factories: Mapping[str, MetadataSourceFactory] | None = None,
) -> list[MetadataProviderAdapter]:
    factories = source_factories or get_metadata_source_factories()
    metadata = [item for item in metadata_items if item.kind == ProviderKind.METADATA]
    return build_metadata_providers(metadata, factories)


def get_metadata_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    source_factories: Mapping[str, MetadataSourceFactory] | None = None,
) -> Mapping[str, MetadataProviderAdapter]:
    metadata = metadata_items
    if metadata is None:
        import plugin_guard

        metadata = [
            item
            for item in build_builtin_provider_metadata()
            if item.kind != ProviderKind.METADATA or plugin_guard.is_metadata_allowed(item.id)
        ]
    providers = build_metadata_providers_from_metadata(metadata, source_factories=source_factories)
    return {provider.metadata().id: provider for provider in providers}


def _tmdb_search_item(item: dict, media_type: str) -> dict:
    if media_type == "tv":
        return {
            "id": item.get("id", 0),
            "tmdb_id": item.get("id", 0),
            "name": item.get("name", ""),
            "original_name": item.get("original_name", ""),
            "title": item.get("name", ""),
            "original_title": item.get("original_name", ""),
            "first_air_date": item.get("first_air_date", ""),
            "year": (item.get("first_air_date", "") or "")[:4],
            "poster_url": _tmdb_poster(item.get("poster_path")),
            "overview": item.get("overview", ""),
            "rating": item.get("vote_average", 0),
            "popularity": item.get("popularity", 0),
            "media_type": "tv",
        }
    return {
        "id": item.get("id", 0),
        "tmdb_id": item.get("id", 0),
        "title": item.get("title", ""),
        "original_title": item.get("original_title", ""),
        "release_date": item.get("release_date", ""),
        "year": (item.get("release_date", "") or "")[:4],
        "poster_url": _tmdb_poster(item.get("poster_path")),
        "overview": item.get("overview", ""),
        "rating": item.get("vote_average", 0),
        "popularity": item.get("popularity", 0),
        "media_type": "movie",
    }


def _tmdb_poster(path: str | None) -> str:
    return f"https://image.tmdb.org/t/p/w500{path}" if path else ""
