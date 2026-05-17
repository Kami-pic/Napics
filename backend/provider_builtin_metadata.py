"""内置 Provider metadata 兼容输出。

本模块只把现有源清单投影为 ProviderMetadata，不初始化或迁移具体实现。
"""

from typing import Any, Mapping

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

METADATA_SOURCE_DEFAULTS = {
    "tmdb": {"label": "TMDB", "enabled": True, "requires": ["api_key"], "supports_proxy": True},
    "douban": {"label": "豆瓣", "enabled": True, "requires": [], "supports_proxy": False},
    "bangumi": {"label": "Bangumi", "enabled": True, "requires": [], "supports_proxy": True},
}

DOWNLOAD_PROVIDER_DEFAULTS = {
    "qbittorrent": {"label": "qBittorrent", "enabled": True, "requires": ["api_url", "username", "password"]},
    "openlist": {"label": "OpenList", "enabled": True, "requires": ["api_url", "token"]},
}

STORAGE_PROVIDER_DEFAULTS = {
    "openlist_storage": {"label": "OpenList Storage", "enabled": True, "requires": ["api_url", "token"]},
}


def build_builtin_provider_metadata(
    bt_overrides: Mapping[str, Any] | None = None,
    pan_overrides: Mapping[str, Any] | None = None,
    include_private_pan: bool = False,
) -> list[ProviderMetadata]:
    providers: list[ProviderMetadata] = []
    providers.extend(_build_search_metadata(bt_overrides or {}))
    if include_private_pan:
        providers.extend(_build_pan_search_metadata(pan_overrides or {}))
    providers.extend(_build_metadata_metadata())
    providers.extend(_build_rss_metadata())
    providers.extend(_build_download_metadata())
    providers.extend(_build_storage_metadata())
    return providers


def _build_search_metadata(bt_overrides: Mapping[str, Any]) -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in BT_SOURCE_DEFAULTS.items():
        enabled, proxy = _resolve_bt_override(provider_id, info, bt_overrides)
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.SEARCH,
                type=info.get("type", "bt"),
                enabled=enabled,
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["search", "magnet", "torrent", "size", "seeders"],
                riskLevel=ProviderRiskLevel.USER_CONFIGURED if provider_id == "prowlarr" else ProviderRiskLevel.HIGH,
                requires=["api_url", "api_key"] if provider_id == "prowlarr" else [],
                supportsProxy=proxy,
            )
        )
    return result


def _build_pan_search_metadata(pan_overrides: Mapping[str, Any]) -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in PAN_SOURCE_DEFAULTS.items():
        override = pan_overrides.get(provider_id)
        enabled = override if isinstance(override, bool) else bool(info.get("enabled", False))
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.PAN_SEARCH,
                type=info.get("type", "pan"),
                enabled=enabled,
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["search", "share_link"],
                riskLevel=ProviderRiskLevel.PRIVATE,
                supportsProxy=False,
            )
        )
    return result


def _resolve_bt_override(
    provider_id: str,
    info: Mapping[str, Any],
    bt_overrides: Mapping[str, Any],
) -> tuple[bool, bool]:
    override = bt_overrides.get(provider_id)
    default_enabled = bool(info.get("enabled", False))
    default_proxy = bool(info.get("needs_proxy", False))
    if isinstance(override, dict):
        return bool(override.get("enabled", default_enabled)), bool(override.get("proxy", default_proxy))
    if isinstance(override, bool):
        return override, default_proxy
    return default_enabled, default_proxy


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


def _build_metadata_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in METADATA_SOURCE_DEFAULTS.items():
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.METADATA,
                type="metadata",
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["search", "detail", "artwork", "aliases", "episodes"],
                riskLevel=ProviderRiskLevel.LOW,
                requires=list(info.get("requires", [])),
                supportsProxy=bool(info.get("supports_proxy", False)),
            )
        )
    return result


def _build_download_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in DOWNLOAD_PROVIDER_DEFAULTS.items():
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.DOWNLOAD,
                type="download",
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["submit", "progress"],
                riskLevel=ProviderRiskLevel.USER_CONFIGURED,
                requires=list(info.get("requires", [])),
            )
        )
    return result


def _build_storage_metadata() -> list[ProviderMetadata]:
    result: list[ProviderMetadata] = []
    for provider_id, info in STORAGE_PROVIDER_DEFAULTS.items():
        result.append(
            ProviderMetadata(
                id=provider_id,
                name=info["label"],
                kind=ProviderKind.STORAGE,
                type="storage",
                enabled=bool(info.get("enabled", False)),
                defaultEnabled=bool(info.get("enabled", False)),
                capabilities=["list_mounts", "list_dir", "exists"],
                riskLevel=ProviderRiskLevel.USER_CONFIGURED,
                requires=list(info.get("requires", [])),
            )
        )
    return result
