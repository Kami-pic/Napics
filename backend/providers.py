"""Provider 列表 API 初版。

本文件只提供可挂载的只读入口；是否接入主应用由后续阶段单独处理。
"""

from fastapi import APIRouter

from provider_models import ProviderCatalog
from provider_registry import default_provider_registry


router = APIRouter(prefix="/api/providers", tags=["providers"])


def get_provider_catalog() -> ProviderCatalog:
    return default_provider_registry.catalog()


@router.get("", response_model=ProviderCatalog)
def list_providers() -> ProviderCatalog:
    return get_provider_catalog()
