"""Provider 注册表。"""

from typing import Iterable, List, Optional

from provider_context import ProviderContext
from provider_contracts import Provider
from provider_models import ProviderCatalog, ProviderKind, ProviderMetadata


class ProviderRegistryError(ValueError):
    pass


class ProviderRegistry:
    def __init__(self, context: ProviderContext | None = None):
        self._context = context or ProviderContext()
        self._providers: dict[str, Provider] = {}
        self._metadata: dict[str, ProviderMetadata] = {}

    def register(self, provider: Provider, *, initialize: bool = True) -> None:
        metadata = provider.metadata()
        if metadata.id in self._metadata:
            raise ProviderRegistryError(f"provider 已注册: {metadata.id}")
        if initialize:
            provider.initialize(self._context)
        self._providers[metadata.id] = provider
        self._metadata[metadata.id] = metadata

    def register_metadata(self, metadata: ProviderMetadata) -> None:
        if metadata.id in self._metadata:
            raise ProviderRegistryError(f"provider 已注册: {metadata.id}")
        self._metadata[metadata.id] = metadata

    def get(self, provider_id: str) -> Optional[Provider]:
        return self._providers.get(provider_id)

    def get_metadata(self, provider_id: str) -> Optional[ProviderMetadata]:
        return self._metadata.get(provider_id)

    def list(self, kind: ProviderKind | str | None = None) -> List[ProviderMetadata]:
        normalized_kind = ProviderKind(kind) if kind else None
        providers = sorted(self._metadata.values(), key=lambda item: (item.kind.value, item.name, item.id))
        if normalized_kind is None:
            return providers
        return [item for item in providers if item.kind == normalized_kind]

    def enabled(self, kind: ProviderKind | str | None = None) -> List[ProviderMetadata]:
        return [item for item in self.list(kind) if item.enabled]

    def catalog(self) -> ProviderCatalog:
        grouped: dict[ProviderKind, list[ProviderMetadata]] = {
            kind: self.list(kind)
            for kind in ProviderKind
        }
        return ProviderCatalog(
            search=grouped[ProviderKind.SEARCH],
            panSearch=grouped[ProviderKind.PAN_SEARCH],
            metadata=grouped[ProviderKind.METADATA],
            rss=grouped[ProviderKind.RSS],
            download=grouped[ProviderKind.DOWNLOAD],
            storage=grouped[ProviderKind.STORAGE],
            notification=grouped[ProviderKind.NOTIFICATION],
        )

    def load_metadata(self, providers: Iterable[ProviderMetadata]) -> None:
        for provider in providers:
            self.register_metadata(provider)


default_provider_registry = ProviderRegistry()
