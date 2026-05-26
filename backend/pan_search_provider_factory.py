"""网盘 PanSearchProvider 工厂清单。

优先从 plugin registry 获取 scraper 类（插件自加载模式），
fallback 到直接 import（兼容旧模式，过渡期保留）。
"""

import logging
from typing import Mapping

from pan_search_provider_adapter import (
    PanScraperFactory,
    PanSearchProviderAdapter,
    build_pan_search_providers,
)
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata

logger = logging.getLogger(__name__)


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
    """获取网盘搜索源工厂映射。

    优先从 plugin registry 获取（search-pan 插件注册的 scraper_class），
    未注册时 fallback 到直接 import。
    """
    proxy = scraper_proxy or None
    factories: dict[str, PanScraperFactory] = {}

    # 1. 从 plugin registry 获取
    scraper_classes: dict[str, type] = {}
    try:
        from plugin_context import get_plugin_providers
        for pid, info in get_plugin_providers().items():
            if info.get("type") == "pan_search" and "scraper_class" in info:
                scraper_classes[pid] = info["scraper_class"]
    except Exception:
        pass

    # 2. fallback：直接 import（兼容旧模式）
    if not scraper_classes:
        try:
            from pan_scraper_ddys import DdysScraper
            from pan_scraper_github import GitHubPanScraper
            from pan_scraper_gogopanso import GogoPansoScraper
            from pan_scraper_pansearch import PanSearchScraper
            from pan_scraper_pansou import PanSouClient
            from pan_scraper_rrdynb import RrdynbScraper
            from pan_scraper_sites import MultiSiteScraper
            from pan_scraper_slowread import SlowreadScraper
            from pan_scraper_wnsearch import WnSearchScraper
            scraper_classes = {
                "pansearch": PanSearchScraper,
                "rrdynb": RrdynbScraper,
                "ddys": DdysScraper,
                "pansou": PanSouClient,
                "sites": MultiSiteScraper,
                "slowread": SlowreadScraper,
                "wnsearch": WnSearchScraper,
                "gogopanso": GogoPansoScraper,
                "github": GitHubPanScraper,
            }
        except ImportError:
            pass  # 源文件已移入插件目录，纯 plugin 模式

    # 3. 构造工厂函数
    for name, cls in scraper_classes.items():
        if name == "pansou":
            if pansou_api_url:
                factories["pansou"] = lambda c=cls, u=pansou_api_url: c(api_url=u, proxy=proxy)
        else:
            factories[name] = lambda c=cls: c(proxy=proxy)

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
