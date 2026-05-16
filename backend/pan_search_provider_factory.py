"""网盘 PanSearchProvider 工厂清单。

此模块是 Phase 8 的兼容桥：集中现有 pan scraper 构造函数，但不改旧搜索调用链。
"""

from typing import Mapping

from pan_search_provider_adapter import (
    PanScraperFactory,
    PanSearchProviderAdapter,
    build_pan_search_providers,
)
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata


PAN_SEARCH_SOURCE_ORDER = (
    "pansearch",
    "rrdynb",
    "ddys",
    "pansou",
    "sites",
    "slowread",
    "wnsearch",
    "gogopanso",
    "github",
)


def get_pan_search_scraper_factories(
    *,
    pansou_api_url: str = "",
    scraper_proxy: str = "",
) -> Mapping[str, PanScraperFactory]:
    from pan_scraper_ddys import DdysScraper
    from pan_scraper_github import GitHubPanScraper
    from pan_scraper_gogopanso import GogoPansoScraper
    from pan_scraper_pansearch import PanSearchScraper
    from pan_scraper_pansou import PanSouClient
    from pan_scraper_rrdynb import RrdynbScraper
    from pan_scraper_sites import MultiSiteScraper
    from pan_scraper_slowread import SlowreadScraper
    from pan_scraper_wnsearch import WnSearchScraper

    proxy = scraper_proxy or None
    factories: dict[str, PanScraperFactory] = {
        "pansearch": lambda: PanSearchScraper(proxy=proxy),
        "rrdynb": lambda: RrdynbScraper(proxy=proxy),
        "ddys": lambda: DdysScraper(proxy=proxy),
        "sites": lambda: MultiSiteScraper(proxy=proxy),
        "slowread": lambda: SlowreadScraper(proxy=proxy),
        "wnsearch": lambda: WnSearchScraper(proxy=proxy),
        "gogopanso": lambda: GogoPansoScraper(proxy=proxy),
        "github": lambda: GitHubPanScraper(proxy=proxy),
    }
    if pansou_api_url:
        factories["pansou"] = lambda: PanSouClient(api_url=pansou_api_url, proxy=proxy)
    return {name: factories[name] for name in PAN_SEARCH_SOURCE_ORDER if name in factories}


def build_pan_search_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    scraper_factories: Mapping[str, PanScraperFactory] | None = None,
) -> list[PanSearchProviderAdapter]:
    factories = scraper_factories or get_pan_search_scraper_factories()
    pan_metadata = [
        metadata
        for metadata in metadata_items
        if metadata.kind == ProviderKind.PAN_SEARCH
    ]
    return build_pan_search_providers(pan_metadata, factories)


def get_pan_search_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    scraper_factories: Mapping[str, PanScraperFactory] | None = None,
) -> Mapping[str, PanSearchProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    providers = build_pan_search_providers_from_metadata(metadata, scraper_factories=scraper_factories)
    return {provider.metadata().id: provider for provider in providers}
