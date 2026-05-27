"""Provider 运行期依赖注入容器。"""

import logging
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


@runtime_checkable
class ProviderConfigView(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError


@runtime_checkable
class ProviderHttpClient(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        raise NotImplementedError


@runtime_checkable
class ProviderCache(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        raise NotImplementedError


@runtime_checkable
class ProviderEventBus(Protocol):
    def publish(self, topic: str, payload: BaseModel) -> None:
        raise NotImplementedError


class ProviderRuntimeInfo(BaseModel):
    profile: str = "open-core"
    allow_private_providers: bool = Field(default=False, alias="allowPrivateProviders")


class MappingConfigView:
    def __init__(self, values: Mapping[str, Any] | None = None):
        self._values = dict(values or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


class MemoryProviderCache:
    def __init__(self):
        self._values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        self._values[key] = value


class ProviderContext(BaseModel):
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
