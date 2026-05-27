"""BT 直搜 SearchProvider 工厂清单。

优先从 plugin registry 获取 scraper 类（插件自加载模式），
fallback 到 shared.py getter（兼容旧模式，过渡期保留）。
"""

import logging
from typing import Mapping

from bt_search_provider_adapter import (
    DirectBTSearchProviderAdapter,
    ScraperFactory,
    build_direct_bt_search_providers,
)
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata

logger = logging.getLogger(__name__)


DIRECT_BT_SOURCE_ORDER = (
    "bitsearch",
    "cilixiong",
    "xl720",
    "nyaa",
    "mikan",
    "yts",
    "limetorrents",
    "acgrip",
    "bangumi_moe",
    "eztv",
    "dmhy",
    "1337x",
)

LEGACY_SKIP_FILTER_DIRECT_BT_SOURCES = (
    "bitsearch",
    "cilixiong",
    "xl720",
    "nyaa",
    "mikan",
    "yts",
    "limetorrents",
    "acgrip",
    "bangumi_moe",
)


def _build_factory_from_registry(provider_id: str, scraper_class) -> ScraperFactory:
    """从 plugin registry 的 scraper_class 构造工厂函数（懒加载单例）。"""
    _instance = {}

    def _factory():
        if "inst" not in _instance:
            from search_service import get_source_proxy
            proxy = get_source_proxy(provider_id)
            _instance["inst"] = scraper_class(proxy=proxy)
        return _instance["inst"]

    return _factory


def get_direct_bt_scraper_factories() -> Mapping[str, ScraperFactory]:
    """获取 BT 直搜源工厂映射。

    优先从 plugin registry 获取（search-bt-direct 插件注册的 scraper_class），
    未注册的源 fallback 到 shared.py getter（兼容旧模式）。
    """
    factories: dict[str, ScraperFactory] = {}

    # 1. 从 plugin registry 获取
    try:
        from plugin_context import get_plugin_providers
        plugin_providers = get_plugin_providers()
        for source_id in DIRECT_BT_SOURCE_ORDER:
            if source_id in plugin_providers:
                info = plugin_providers[source_id]
                if info.get("type") == "scraper_search" and "scraper_class" in info:
                    factories[source_id] = _build_factory_from_registry(
                        source_id, info["scraper_class"]
                    )
    except Exception as e:
        logger.warning(f"[BT Factory] 从 plugin registry 获取失败: {e}")

    # 2. 未从 registry 获取到的源时，搜索不可用（源文件已移入插件目录）
    if len(factories) < len(DIRECT_BT_SOURCE_ORDER):
        missing = [s for s in DIRECT_BT_SOURCE_ORDER if s not in factories]
        if missing:
            logger.debug(f"[BT Factory] 以下源未从 plugin registry 获取: {missing}")

    return {name: factories[name] for name in DIRECT_BT_SOURCE_ORDER if name in factories}


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


def get_direct_bt_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    scraper_factories: Mapping[str, ScraperFactory] | None = None,
) -> Mapping[str, DirectBTSearchProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    providers = build_direct_bt_providers_from_metadata(metadata, scraper_factories=scraper_factories)
    return {provider.metadata().id: provider for provider in providers}
