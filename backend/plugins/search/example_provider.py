"""公开搜索 Provider 示例。

示例只演示 Provider 契约形状，不访问真实资源站。
"""

from provider_context import ProviderContext
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
    SearchCandidate,
    SearchRequest,
)


class ExampleSearchProvider:
    id = "example_search"
    display_name = "Example Search"
    kind = ProviderKind.SEARCH

    def __init__(self):
        self._context: ProviderContext | None = None

    def initialize(self, context: ProviderContext) -> None:
        self._context = context

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id=self.id,
            name=self.display_name,
            kind=ProviderKind.SEARCH,
            type="example",
            enabled=False,
            defaultEnabled=False,
            capabilities=["search"],
            riskLevel=ProviderRiskLevel.LOW,
            description="Provider SDK 示例，不访问真实资源站。",
        )

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.DISABLED)

    def search(self, request: SearchRequest) -> list[SearchCandidate]:
        return []
