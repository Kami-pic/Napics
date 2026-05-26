"""RSSProvider 工厂清单。

优先从 plugin registry 获取 RSS 源类（插件自加载模式），
fallback 到直接 import（兼容旧模式，过渡期保留）。
"""

import logging
from typing import Mapping

from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata
from rss_provider_adapter import RSSProviderAdapter, RSSSourceFactory, build_rss_providers

logger = logging.getLogger(__name__)


RSS_SOURCE_ORDER = (
    "prowlarr",
    "mikan",
    "nyaa",
    "eztv",
    "dmhy",
    "acgrip",
    "bangumi_moe",
    "yts",
)


def get_rss_source_factories() -> Mapping[str, RSSSourceFactory]:
    """获取 RSS 源工厂映射。

    优先从 plugin registry 获取（rss-anime / rss-tv-movie 插件注册的 source_class），
    未注册的源 fallback 到直接 import。
    最终根据已安装的 RSS 插件过滤可用源。
    """
    from shared import config_m
    proxy = getattr(config_m.config, "http_proxy", "") or ""

    # 1. 从 plugin registry 获取 RSS 源类
    source_classes: dict[str, type] = {}
    try:
        from plugin_context import get_plugin_providers
        for pid, info in get_plugin_providers().items():
            if info.get("type") == "rss_source" and "source_class" in info:
                source_classes[info["source_id"]] = info["source_class"]
    except Exception:
        pass

    # 2. 未从 registry 获取到时，RSS 源不可用（源文件已移入插件目录）
    if not source_classes:
        logger.debug("[RSS Factory] plugin registry 中无 RSS 源，可能未安装 rss-anime/rss-tv-movie 插件")

    # 3. 构造工厂函数
    def _build_prowlarr():
        cls = source_classes.get("prowlarr")
        if not cls:
            return None
        source = cls()
        if config_m.config.prowlarr_url and config_m.config.prowlarr_api_key:
            from searcher import ProwlarrClient
            source.set_client(ProwlarrClient(config_m.config.prowlarr_url, config_m.config.prowlarr_api_key))
        return source

    factories: dict[str, RSSSourceFactory] = {}
    for source_id in RSS_SOURCE_ORDER:
        if source_id not in source_classes:
            continue
        if source_id == "prowlarr":
            factories["prowlarr"] = _build_prowlarr
        elif source_id in ("acgrip", "bangumi_moe"):
            # 国内直连，不需要代理
            cls = source_classes[source_id]
            factories[source_id] = cls
        else:
            # 需要代理的源
            cls = source_classes[source_id]
            factories[source_id] = lambda c=cls: c(proxy=proxy)

    # 4. 根据已安装的 RSS 插件过滤可用源
    from plugin_guard import get_allowed_rss_sources
    allowed = get_allowed_rss_sources()

    return {name: factories[name] for name in RSS_SOURCE_ORDER if name in factories and name in allowed}


def build_rss_providers_from_metadata(
    metadata_items: list[ProviderMetadata],
    source_factories: Mapping[str, RSSSourceFactory] | None = None,
) -> list[RSSProviderAdapter]:
    factories = source_factories or get_rss_source_factories()
    rss_metadata = [metadata for metadata in metadata_items if metadata.kind == ProviderKind.RSS]
    return build_rss_providers(rss_metadata, factories)


def get_rss_provider_map(
    metadata_items: list[ProviderMetadata] | None = None,
    source_factories: Mapping[str, RSSSourceFactory] | None = None,
) -> Mapping[str, RSSProviderAdapter]:
    metadata = metadata_items or build_builtin_provider_metadata()
    providers = build_rss_providers_from_metadata(metadata, source_factories=source_factories)
    return {provider.metadata().id: provider for provider in providers}
