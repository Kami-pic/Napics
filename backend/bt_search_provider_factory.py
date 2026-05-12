"""BT 直搜 SearchProvider 工厂清单。

此模块是 Phase 3 的兼容桥：集中现有 shared.py scraper getter，但不改旧搜索调用链。
"""

from typing import Mapping

from bt_search_provider_adapter import (
    DirectBTSearchProviderAdapter,
    ScraperFactory,
    build_direct_bt_search_providers,
)
from provider_models import ProviderKind, ProviderMetadata


def get_direct_bt_scraper_factories() -> Mapping[str, ScraperFactory]:
    from shared import (
        _get_1337x_scraper,
        _get_acgrip_scraper,
        _get_bangumi_moe_scraper,
        _get_bitsearch_scraper,
        _get_cilixiong_scraper,
        _get_dmhy_scraper,
        _get_eztv_scraper,
        _get_limetorrents_scraper,
        _get_mikan_scraper,
        _get_nyaa_scraper,
        _get_xl720_scraper,
        _get_yts_scraper,
    )

    return {
        "bitsearch": _get_bitsearch_scraper,
        "cilixiong": _get_cilixiong_scraper,
        "xl720": _get_xl720_scraper,
        "nyaa": _get_nyaa_scraper,
        "mikan": _get_mikan_scraper,
        "yts": _get_yts_scraper,
        "limetorrents": _get_limetorrents_scraper,
        "acgrip": _get_acgrip_scraper,
        "bangumi_moe": _get_bangumi_moe_scraper,
        "eztv": _get_eztv_scraper,
        "dmhy": _get_dmhy_scraper,
        "1337x": _get_1337x_scraper,
    }


def build_direct_bt_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    scraper_factories: Mapping[str, ScraperFactory] | None = None,
) -> list[DirectBTSearchProviderAdapter]:
    factories = scraper_factories or get_direct_bt_scraper_factories()
    direct_bt_metadata = [
        metadata
        for metadata in metadata_items
        if metadata.kind == ProviderKind.SEARCH and metadata.type == "bt" and metadata.id != "prowlarr"
    ]
    return build_direct_bt_search_providers(direct_bt_metadata, factories)
