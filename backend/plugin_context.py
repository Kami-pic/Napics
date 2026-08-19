"""插件运行时上下文 — 提供给第三方插件的 API。

第三方插件通过 PluginContext 访问系统能力，不直接 import 内部模块。
这是插件与 Core 之间的唯一接口边界。
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from provider_models import (
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    SearchCandidate,
    SearchRequest,
    PanSearchCandidate,
)
from scraper_base import ScraperBase


logger = logging.getLogger(__name__)

# 第三方插件注册的 provider 存储
_plugin_providers: Dict[str, Any] = {}

# 第三方插件注册的路由存储 — {plugin_id: [APIRouter, ...]}
_plugin_routers: Dict[str, List[Any]] = {}


class PluginContext:
    """插件运行时上下文 — 第三方插件的唯一入口。

    提供：
    - register_search_provider: 注册 BT 搜索源
    - register_pan_search_provider: 注册网盘搜索源
    - register_router: 注册 FastAPI 路由（功能型插件用）
    - get_config: 读取系统配置
    - get_proxy: 获取代理地址
    - get_logger: 获取日志器
    - ScraperBase: 爬虫基类（可继承）
    """

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.logger = logging.getLogger(f"plugin.{plugin_id}")
        self.ScraperBase = ScraperBase  # 暴露基类供第三方继承

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取系统配置项"""
        try:
            from shared import config_m
            return getattr(config_m.config, key, default)
        except Exception:
            return default

    def get_proxy(self) -> str:
        """获取系统代理地址"""
        return self.get_config("http_proxy", "") or ""

    def get_logger(self, name: str = "") -> logging.Logger:
        """获取日志器"""
        full_name = f"plugin.{self.plugin_id}"
        if name:
            full_name += f".{name}"
        return logging.getLogger(full_name)

    def register_router(self, router: Any, *, prefix: str = "", tags: Optional[List[str]] = None) -> None:
        """注册 FastAPI 路由到主应用。

        功能型插件（如播放器、转码等）可通过此方法注册自己的 HTTP 路由。
        路由在应用启动时统一挂载，卸载后需重启才能移除。

        参数：
        - router: FastAPI APIRouter 实例
        - prefix: 路由前缀（如 "/playback"），默认为空（沿用 router 自身 prefix）
        - tags: OpenAPI 标签列表

        示例：
            from fastapi import APIRouter
            router = APIRouter()

            @router.get("/stream")
            def stream_video(...):
                ...

            def register(ctx):
                ctx.register_router(router, tags=["playback"])
        """
        if self.plugin_id not in _plugin_routers:
            _plugin_routers[self.plugin_id] = []
        _plugin_routers[self.plugin_id].append({
            "router": router,
            "prefix": prefix,
            "tags": tags,
        })
        logger.info(f"[PluginContext] 注册路由: plugin={self.plugin_id}, prefix={prefix!r}")

    def register_rss_source_provider(
        self,
        source_id: str,
        name: str,
        source_class: type,
        *,
        enabled: bool = True,
        supports_proxy: bool = False,
        capabilities: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """注册一个基于 RSSSourceBase 的订阅源。"""
        provider_id = f"rss_{source_id}"
        metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            kind=ProviderKind.RSS,
            type="rss",
            enabled=enabled,
            defaultEnabled=enabled,
            capabilities=capabilities or ["rss", "download_url"],
            riskLevel=ProviderRiskLevel.HIGH,
            supportsProxy=supports_proxy,
            description=description,
        )
        _plugin_providers[provider_id] = {
            "type": "rss_source",
            "metadata": metadata,
            "source_id": source_id,
            "source_class": source_class,
            "plugin_id": self.plugin_id,
        }
        logger.info(f"[PluginContext] 注册 RSS 源: {source_id} ({name})")

    def register_search_provider(
        self,
        provider_id: str,
        name: str,
        search_fn: Callable[[str, int], List[SearchCandidate]],
        *,
        enabled: bool = True,
        supports_proxy: bool = False,
        capabilities: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """注册一个 BT 搜索源。

        参数：
        - provider_id: 源唯一 ID（小写英文+下划线，如 "my_source"）
        - name: 显示名称
        - search_fn: 搜索函数，签名 (keyword: str, max_results: int) -> List[SearchCandidate]
        - enabled: 是否默认启用
        - supports_proxy: 是否支持代理
        - capabilities: 能力列表（如 ["keyword_en", "keyword_cn"]）
        - description: 描述

        示例：
            def my_search(keyword: str, max_results: int) -> list:
                # 你的搜索逻辑
                return [SearchCandidate(title=..., downloadUrl=..., providerId="my_source", ...)]

            def register(ctx):
                ctx.register_search_provider("my_source", "我的源", my_search)
        """
        metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            kind=ProviderKind.SEARCH,
            type="bt",
            enabled=enabled,
            defaultEnabled=enabled,
            capabilities=capabilities or ["search", "magnet", "size"],
            riskLevel=ProviderRiskLevel.HIGH,
            supportsProxy=supports_proxy,
            description=description,
        )
        _plugin_providers[provider_id] = {
            "type": "search",
            "metadata": metadata,
            "search_fn": search_fn,
            "plugin_id": self.plugin_id,
        }
        logger.info(f"[PluginContext] 注册搜索源: {provider_id} ({name})")

    def register_pan_search_provider(
        self,
        provider_id: str,
        name: str,
        search_fn: Callable[[str, int], List[PanSearchCandidate]],
        *,
        enabled: bool = True,
        description: str = "",
    ) -> None:
        """注册一个网盘搜索源。

        参数：
        - provider_id: 源唯一 ID
        - name: 显示名称
        - search_fn: 搜索函数，签名 (keyword: str, max_results: int) -> List[PanSearchCandidate]

        示例：
            def my_pan_search(keyword: str, max_results: int) -> list:
                return [PanSearchCandidate(title=..., shareUrl=..., sourceProviderId="my_pan", ...)]

            def register(ctx):
                ctx.register_pan_search_provider("my_pan", "我的网盘源", my_pan_search)
        """
        metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            kind=ProviderKind.PAN_SEARCH,
            type="pan",
            enabled=enabled,
            defaultEnabled=enabled,
            capabilities=["search", "share_link"],
            riskLevel=ProviderRiskLevel.HIGH,
            description=description,
        )
        _plugin_providers[provider_id] = {
            "type": "pan_search",
            "metadata": metadata,
            "search_fn": search_fn,
            "plugin_id": self.plugin_id,
        }
        logger.info(f"[PluginContext] 注册网盘源: {provider_id} ({name})")

    def register_scraper_search_provider(
        self,
        provider_id: str,
        name: str,
        scraper_class: type,
        *,
        enabled: bool = True,
        supports_proxy: bool = False,
        capabilities: Optional[List[str]] = None,
        description: str = "",
    ) -> None:
        """注册一个基于 ScraperBase 的 BT 搜索源（推荐方式）。

        第三方只需继承 ScraperBase 并实现 search_as_search_results 方法。
        系统会自动处理代理、缓存、重试等。

        参数：
        - provider_id: 源唯一 ID
        - name: 显示名称
        - scraper_class: 继承 ScraperBase 的爬虫类
        - enabled: 是否默认启用
        - supports_proxy: 是否支持代理

        示例：
            class MyScraper(ctx.ScraperBase):
                def __init__(self, proxy=None):
                    super().__init__(proxy=proxy, cache_ttl=600)

                def search_as_search_results(self, keyword, max_results=20):
                    # 你的搜索逻辑，返回 List[SearchResult]
                    from searcher import SearchResult
                    return [SearchResult(title=..., download_url=..., ...)]

            def register(ctx):
                ctx.register_scraper_search_provider("my_source", "我的源", MyScraper)
        """
        metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            kind=ProviderKind.SEARCH,
            type="bt",
            enabled=enabled,
            defaultEnabled=enabled,
            capabilities=capabilities or ["search", "magnet", "size"],
            riskLevel=ProviderRiskLevel.HIGH,
            supportsProxy=supports_proxy,
            description=description,
        )
        _plugin_providers[provider_id] = {
            "type": "scraper_search",
            "metadata": metadata,
            "scraper_class": scraper_class,
            "plugin_id": self.plugin_id,
        }
        logger.info(f"[PluginContext] 注册爬虫搜索源: {provider_id} ({name})")


def get_plugin_context(plugin_id: str) -> PluginContext:
    """获取指定插件的运行时上下文"""
    return PluginContext(plugin_id)


def get_plugin_providers() -> Dict[str, Any]:
    """获取所有第三方插件注册的 provider"""
    return _plugin_providers.copy()


def unregister_plugin_providers(plugin_id: str) -> None:
    """注销指定插件注册的所有 provider"""
    to_remove = [pid for pid, info in _plugin_providers.items() if info.get("plugin_id") == plugin_id]
    for pid in to_remove:
        del _plugin_providers[pid]
    if to_remove:
        logger.info(f"[PluginContext] 注销插件 {plugin_id} 的 provider: {to_remove}")


def get_plugin_routers() -> Dict[str, List[Any]]:
    """获取所有插件注册的路由 — {plugin_id: [{router, prefix, tags}, ...]}"""
    return _plugin_routers.copy()


def unregister_plugin_routers(plugin_id: str) -> None:
    """注销指定插件注册的路由（从注册表移除，实际路由移除需重启）"""
    removed = _plugin_routers.pop(plugin_id, None)
    if removed:
        logger.info(f"[PluginContext] 注销插件 {plugin_id} 的路由（需重启生效）")
