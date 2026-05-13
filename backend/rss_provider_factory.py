"""RSSProvider 工厂清单。

此模块是 Phase 4 的兼容桥：集中现有 RSSSource 构造函数，但不改旧订阅调度链路。
"""

from typing import Mapping

from provider_builtin_metadata import build_builtin_provider_metadata
from provider_models import ProviderKind, ProviderMetadata
from rss_provider_adapter import RSSProviderAdapter, RSSSourceFactory, build_rss_providers


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
    from rss_source_acgrip import ACGRipRSSSource
    from rss_source_bangumi_moe import BangumiMoeRSSSource
    from rss_source_dmhy import DMHYRSSSource
    from rss_source_eztv import EZTVRSSSource
    from rss_source_mikan import MikanRSSSource
    from rss_source_nyaa import NyaaRSSSource
    from rss_source_prowlarr import ProwlarrRSSSource
    from rss_source_yts import YTSRSSSource
    from shared import config_m

    proxy = getattr(config_m.config, "http_proxy", "") or ""

    def _build_prowlarr() -> ProwlarrRSSSource:
        source = ProwlarrRSSSource()
        if config_m.config.prowlarr_url and config_m.config.prowlarr_api_key:
            from searcher import ProwlarrClient

            source.set_client(ProwlarrClient(config_m.config.prowlarr_url, config_m.config.prowlarr_api_key))
        return source

    factories: dict[str, RSSSourceFactory] = {
        "prowlarr": _build_prowlarr,
        "mikan": lambda: MikanRSSSource(proxy=proxy),
        "nyaa": lambda: NyaaRSSSource(proxy=proxy),
        "eztv": lambda: EZTVRSSSource(proxy=proxy),
        "dmhy": lambda: DMHYRSSSource(proxy=proxy),
        "acgrip": ACGRipRSSSource,
        "bangumi_moe": BangumiMoeRSSSource,
        "yts": lambda: YTSRSSSource(proxy=proxy),
    }
    return {name: factories[name] for name in RSS_SOURCE_ORDER}


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
