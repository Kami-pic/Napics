"""Provider 列表 API 初版。

本文件只提供可挂载的只读入口；是否接入主应用由后续阶段单独处理。
"""

from fastapi import APIRouter

from provider_models import ProviderCatalog, ProviderKind, ProviderMetadata
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_registry import ProviderRegistry, default_provider_registry
from provider_runtime import allow_private_providers


router = APIRouter(prefix="/api/providers", tags=["providers"])


def get_provider_catalog() -> ProviderCatalog:
    registry = ProviderRegistry()
    bt_overrides, pan_overrides = _get_config_overrides()
    registry.load_metadata(
        build_builtin_provider_metadata(
            bt_overrides,
            pan_overrides,
            include_private_pan=allow_private_providers(),
        )
    )
    for metadata in default_provider_registry.list():
        if registry.get_metadata(metadata.id) is None:
            registry.register_metadata(metadata)

    # 第三方自定义 Provider 的 metadata 不在内置清单中，必须并入 catalog。
    try:
        from plugin_context import get_plugin_providers
        for info in get_plugin_providers().values():
            metadata = info.get("metadata")
            if isinstance(metadata, ProviderMetadata) and registry.get_metadata(metadata.id) is None:
                registry.register_metadata(metadata)
    except Exception:
        pass

    return registry.catalog()


def _get_config_overrides() -> tuple[dict, dict]:
    try:
        from shared import config_m
    except Exception:
        return {}, {}
    conf = config_m.config
    return conf.bt_search_sources or {}, conf.pan_search_sources or {}


def _get_registered_provider_ids() -> dict[ProviderKind, set[str]]:
    """返回当前进程中真正可执行的 Provider ID。"""
    registered = {kind: set() for kind in ProviderKind}

    for metadata in default_provider_registry.list():
        if default_provider_registry.get(metadata.id) is not None:
            registered[metadata.kind].add(metadata.id)

    try:
        from plugin_context import get_plugin_providers
        for provider_id, info in get_plugin_providers().items():
            provider_type = info.get("type")
            if provider_type in {"search", "scraper_search"}:
                registered[ProviderKind.SEARCH].add(provider_id)
            elif provider_type == "pan_search":
                registered[ProviderKind.PAN_SEARCH].add(provider_id)
            elif provider_type == "rss_source":
                source_id = info.get("source_id", provider_id)
                registered[ProviderKind.RSS].add(f"rss_{source_id}")
    except Exception:
        pass

    # 以下 Provider 由主体适配器实现，但仍由对应插件控制安装/卸载。
    registered[ProviderKind.SEARCH].add("prowlarr")
    registered[ProviderKind.METADATA].update({"tmdb", "douban", "bangumi"})
    registered[ProviderKind.DOWNLOAD].update({"qbittorrent", "openlist"})
    registered[ProviderKind.STORAGE].add("openlist_storage")
    return registered


def _with_availability(
    providers: list[ProviderMetadata],
    registered_ids: set[str] | None = None,
) -> list[ProviderMetadata]:
    """为已安装 Provider 附加运行时状态。"""
    result = []
    for provider in providers:
        registered = registered_ids is None or provider.id in registered_ids
        result.append(provider.model_copy(update={
            "installed": True,
            "registered": registered,
            "available": registered,
            "load_error": "" if registered else "插件已安装，但运行时未注册该 Provider",
        }))
    return result


@router.get("", response_model=ProviderCatalog)
def list_providers() -> ProviderCatalog:
    """返回已安装 Provider，并标明当前进程是否已注册实现。"""
    from plugin_guard import get_installed_plugins
    catalog = get_provider_catalog()
    installed = get_installed_plugins()

    if not installed:
        return ProviderCatalog()

    from plugin_guard import (
        get_allowed_bt_sources,
        get_allowed_pan_sources,
        get_allowed_rss_sources,
        is_pan_search_allowed,
    )
    registered = _get_registered_provider_ids()
    allowed_bt = get_allowed_bt_sources()

    filtered_search = _with_availability(
        [p for p in catalog.search if p.id in allowed_bt],
        registered[ProviderKind.SEARCH],
    )
    if is_pan_search_allowed():
        allowed_pan = get_allowed_pan_sources()
        filtered_pan = _with_availability(
            [p for p in catalog.pan_search if p.id in allowed_pan],
            registered[ProviderKind.PAN_SEARCH],
        )
    else:
        filtered_pan = []
    filtered_metadata = _with_availability([
        p for p in catalog.metadata if f"metadata-{p.id}" in installed
    ], registered[ProviderKind.METADATA])
    allowed_rss = get_allowed_rss_sources()
    filtered_rss = _with_availability(
        [p for p in catalog.rss if p.id.removeprefix("rss_") in allowed_rss],
        registered[ProviderKind.RSS],
    )
    filtered_download = _with_availability([
        p for p in catalog.download if f"download-{p.id}" in installed
    ], registered[ProviderKind.DOWNLOAD])
    filtered_storage = _with_availability([
        p for p in catalog.storage if p.id == "openlist_storage" and "storage-openlist" in installed
    ], registered[ProviderKind.STORAGE])

    return ProviderCatalog(
        search=filtered_search,
        panSearch=filtered_pan,
        metadata=filtered_metadata,
        rss=filtered_rss,
        download=filtered_download,
        storage=filtered_storage,
    )
