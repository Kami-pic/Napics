"""Provider 列表 API 初版。

本文件只提供可挂载的只读入口；是否接入主应用由后续阶段单独处理。
"""

from fastapi import APIRouter

from provider_models import ProviderCatalog
from provider_builtin_metadata import build_builtin_provider_metadata
from provider_registry import ProviderRegistry, default_provider_registry


router = APIRouter(prefix="/api/providers", tags=["providers"])


def get_provider_catalog() -> ProviderCatalog:
    registry = ProviderRegistry()
    registry.load_metadata(build_builtin_provider_metadata(*_get_config_overrides()))
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
    return get_provider_catalog()
