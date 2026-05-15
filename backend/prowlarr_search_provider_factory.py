"""Prowlarr SearchProvider 工厂。

此模块是 Phase 6 的兼容桥：集中 Prowlarr provider 构造逻辑，但不改旧搜索调用链。
"""

from typing import Mapping

from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata
from prowlarr_search_provider_adapter import ProwlarrClientFactory, ProwlarrSearchProviderAdapter


PROWLARR_PROVIDER_ID = "prowlarr"


def get_prowlarr_client_factory() -> ProwlarrClientFactory:
    from searcher import ProwlarrClient
    from shared import config_m

    return lambda: ProwlarrClient(config_m.config.prowlarr_url, config_m.config.prowlarr_api_key)


def build_prowlarr_provider_from_metadata(
    metadata_items: list[ProviderMetadata],
    client_factory: ProwlarrClientFactory | None = None,
) -> ProwlarrSearchProviderAdapter | None:
    factory = client_factory or get_prowlarr_client_factory()
    for metadata in metadata_items:
        if metadata.kind == ProviderKind.SEARCH and metadata.id == PROWLARR_PROVIDER_ID:
            return ProwlarrSearchProviderAdapter(metadata, factory)
    return None


def get_prowlarr_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    client_factory: ProwlarrClientFactory | None = None,
) -> Mapping[str, ProwlarrSearchProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    provider = build_prowlarr_provider_from_metadata(metadata, client_factory=client_factory)
    return {provider.metadata().id: provider} if provider else {}
