from provider_context import ProviderContext
from provider_contracts import SearchProvider
from provider_models import (
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    ProviderRiskLevel,
)
from provider_registry import ProviderRegistry, ProviderRegistryError
from providers import get_provider_catalog


class DummySearchProvider:
    id = "dummy"
    display_name = "Dummy"
    kind = ProviderKind.SEARCH

    def __init__(self):
        self.initialized = False

    def initialize(self, context: ProviderContext) -> None:
        self.initialized = True

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id=self.id,
            name=self.display_name,
            kind=self.kind,
            type="bt",
            enabled=True,
            defaultEnabled=True,
            capabilities=["search", "magnet"],
            riskLevel=ProviderRiskLevel.LOW,
        )

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.OK)

    def search(self, request):
        return []


def test_dummy_provider_satisfies_search_protocol():
    assert isinstance(DummySearchProvider(), SearchProvider)


def test_registry_registers_provider_and_groups_catalog():
    registry = ProviderRegistry()
    provider = DummySearchProvider()

    registry.register(provider)
    catalog = registry.catalog()

    assert provider.initialized is True
    assert registry.get("dummy") is provider
    assert registry.enabled(ProviderKind.SEARCH)[0].id == "dummy"
    assert catalog.search[0].id == "dummy"
    assert catalog.rss == []


def test_registry_rejects_duplicate_provider_id():
    registry = ProviderRegistry()
    registry.register(DummySearchProvider())

    try:
        registry.register(DummySearchProvider())
    except ProviderRegistryError as exc:
        assert "dummy" in str(exc)
    else:
        raise AssertionError("重复 provider id 应被拒绝")


def test_registry_can_expose_metadata_without_provider_instance():
    registry = ProviderRegistry()
    registry.register_metadata(
        ProviderMetadata(
            id="rss-example",
            name="RSS Example",
            kind=ProviderKind.RSS,
            capabilities=["rss"],
        )
    )

    assert registry.get("rss-example") is None
    assert registry.list("rss")[0].name == "RSS Example"


def test_default_provider_catalog_starts_empty_for_non_migrated_phase():
    catalog = get_provider_catalog()

    assert catalog.search == []
    assert catalog.metadata == []
    assert catalog.rss == []
