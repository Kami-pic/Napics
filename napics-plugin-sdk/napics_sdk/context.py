"""Provider 运行期依赖注入容器 — Napics 插件 SDK。

ProviderContext 是插件初始化时接收的运行时环境，提供配置、日志、缓存等能力。
"""

import logging
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


@runtime_checkable
class ProviderConfigView(Protocol):
    """配置视图协议 — 只读访问系统配置"""
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError


@runtime_checkable
class ProviderHttpClient(Protocol):
    """HTTP 客户端协议"""
    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        raise NotImplementedError


@runtime_checkable
class ProviderCache(Protocol):
    """缓存协议"""
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        raise NotImplementedError


@runtime_checkable
class ProviderEventBus(Protocol):
    """事件总线协议"""
    def publish(self, topic: str, payload: BaseModel) -> None:
        raise NotImplementedError


class ProviderRuntimeInfo(BaseModel):
    """运行时信息"""
    profile: str = "open-core"
    allow_private_providers: bool = Field(default=False, alias="allowPrivateProviders")


class MappingConfigView:
    """基于字典的配置视图实现（测试用）"""
    def __init__(self, values: Mapping[str, Any] | None = None):
        self._values = dict(values or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


class MemoryProviderCache:
    """内存缓存实现（测试用）"""
    def __init__(self):
        self._values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        self._values[key] = value


class ProviderContext(BaseModel):
    """Provider 运行时上下文 — 依赖注入容器。

    插件通过此对象访问系统能力（配置、日志、缓存、HTTP 客户端等）。
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: ProviderConfigView = Field(default_factory=MappingConfigView)
    logger: logging.Logger = Field(
        default_factory=lambda: logging.getLogger("providers"),
    )
    http_client: Optional[ProviderHttpClient] = None
    cache: Optional[ProviderCache] = Field(default_factory=MemoryProviderCache)
    runtime_info: ProviderRuntimeInfo = Field(default_factory=ProviderRuntimeInfo)
    feature_flags: Mapping[str, bool] = Field(default_factory=dict)
    event_bus: Optional[ProviderEventBus] = None
