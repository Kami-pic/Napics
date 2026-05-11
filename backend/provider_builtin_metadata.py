"""内置 Provider metadata 兼容输出。

本模块只把现有源清单投影为 ProviderMetadata，不初始化或迁移具体实现。
"""

from provider_models import ProviderKind, ProviderMetadata, ProviderRiskLevel
from search_service import BT_SOURCE_DEFAULTS, PAN_SOURCE_DEFAULTS


RSS_SOURCE_DEFAULTS = {
    "prowlarr": {"label": "Prowlarr", "enabled": True},
    "mikan": {"label": "蜜柑计划", "enabled": True},
    "nyaa": {"label": "Nyaa", "enabled": True},
    "eztv": {"label": "EZTV", "enabled": True},
    "dmhy": {"label": "动漫花园", "enabled": True},
    "acgrip": {"label": "ACG.RIP", "enabled": True},
    "bangumi_moe": {"label": "Bangumi Moe", "enabled": True},
    "yts": {"label": "YTS", "enabled": True},
}


def build_builtin_provider_metadata() -> list[ProviderMetadata]:
    providers: list[ProviderMetadata] = []
    providers.extend(_build_search_metadata())
    providers.extend(_build_pan_search_metadata())
    providers.extend(_build_rss_metadata())
    return providers


def _build_search_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in BT_SOURCE_DEFAULTS.items():
        needs_proxy = bool(info.get("needs_proxy", False))
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.SEARCH,
                type=info.get("type", "bt"),
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["search", "magnet", "torrent", "size", "seeders"],
                riskLevel=ProviderRiskLevel.USER_CONFIGURED if provider_id == "prowlarr" else ProviderRiskLevel.HIGH,
                requires=["api_url", "api_key"] if provider_id == "prowlarr" else [],
                supportsProxy=needs_proxy,
            )
        )
    return result


def _build_pan_search_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in PAN_SOURCE_DEFAULTS.items():
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.PAN_SEARCH,
                type=info.get("type", "pan"),
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["search", "share_link"],
                riskLevel=ProviderRiskLevel.PRIVATE,
                supportsProxy=False,
            )
        )
    return result


def _build_rss_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in RSS_SOURCE_DEFAULTS.items():
        result.append(
            ProviderMetadata(
                id=f"rss_{provider_id}",
                name=info["label"],
                kind=ProviderKind.RSS,
                type="rss",
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["rss", "download_url"],
                riskLevel=ProviderRiskLevel.HIGH,
            )
        )
    return result
