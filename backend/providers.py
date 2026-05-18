"""Provider 列表 API 初版。

本文件只提供可挂载的只读入口；是否接入主应用由后续阶段单独处理。
"""

from fastapi import APIRouter

from provider_models import ProviderCatalog
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
    registry.load_metadata(default_provider_registry.list())
    return registry.catalog()


def _get_config_overrides() -> tuple[dict, dict]:
    try:
        from shared import config_m
    except Exception:
        return {}, {}
    conf = config_m.config
    return conf.bt_search_sources or {}, conf.pan_search_sources or {}


@router.get("", response_model=ProviderCatalog)
def list_providers() -> ProviderCatalog:
    """返回 provider 列表，根据已安装插件过滤。"""
    from plugin_guard import get_installed_plugins
    catalog = get_provider_catalog()
    installed = get_installed_plugins()

    # 如果没有安装任何插件，返回空 catalog
    if not installed:
        return ProviderCatalog()

    # 根据插件安装状态过滤
    from plugin_guard import get_allowed_bt_sources, is_pan_search_allowed
    allowed_bt = get_allowed_bt_sources()

    filtered_search = [p for p in catalog.search if p.id in allowed_bt]
    filtered_pan = catalog.pan_search if is_pan_search_allowed() else []
    filtered_metadata = [p for p in catalog.metadata if f"metadata-{p.id}" in installed]
    filtered_rss = catalog.rss if any(pid.startswith("rss-") for pid in installed) else []
    filtered_download = [p for p in catalog.download if f"download-{p.id}" in installed]
    filtered_storage = [p for p in catalog.storage if any(pid.startswith("storage-") for pid in installed)] if any(pid.startswith("storage-") for pid in installed) else []

    return ProviderCatalog(
        search=filtered_search,
        panSearch=filtered_pan,
        metadata=filtered_metadata,
        rss=filtered_rss,
        download=filtered_download,
        storage=filtered_storage,
    )
