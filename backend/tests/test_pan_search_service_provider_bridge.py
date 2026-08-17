from pan_search_service import PanSearchService
from provider_context import ProviderContext
from provider_contracts import PanSearchProvider
from provider_models import (
    PanSearchCandidate,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
    SearchRequest,
)


class FakePanProvider:
    id = "fake_pan"
    display_name = "Fake Pan"
    kind = ProviderKind.PAN_SEARCH

    def __init__(self):
        self.calls = []

    def initialize(self, context: ProviderContext) -> None:
        pass

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id=self.id,
            name=self.display_name,
            kind=ProviderKind.PAN_SEARCH,
            type="pan",
            enabled=True,
        )

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(status=ProviderHealthStatus.OK)

    def search_pan(self, request: SearchRequest) -> list[PanSearchCandidate]:
        self.calls.append(request)
        return [
            PanSearchCandidate(
                title="流浪地球2 2160p",
                cleanTitle="流浪地球2 2160p",
                shareUrl="https://pan.quark.cn/s/abc",
                panType="quark",
                password="1234",
                sourceProviderId=self.id,
                fileSize="12.5 GB",
                resolution="2160p",
            )
        ]


class FailingPanProvider(FakePanProvider):
    id = "failed_pan"
    display_name = "Failed Pan"

    def search_pan(self, request: SearchRequest) -> list[PanSearchCandidate]:
        raise RuntimeError("boom")


def test_pan_search_service_accepts_pan_search_providers():
    provider = FakePanProvider()
    service = PanSearchService(
        search_sources={"fake_pan": True, "missing_pan": False},
        pan_providers=[provider],
    )

    response = service.search_sync("流浪地球2", media_type="movie")

    assert isinstance(provider, PanSearchProvider)
    assert provider.calls[0].query == "流浪地球2"
    assert provider.calls[0].media_type == "movie"
    assert response.total == 1
    assert response.results[0].source == "fake_pan"
    assert response.results[0].pan_type.value == "quark"
    assert response.results[0].share_url == "https://pan.quark.cn/s/abc"
    assert response.results[0].password == "1234"
    assert response.results[0].size_gb == 12.5
    assert response.groups["quark"][0].title == "流浪地球2 2160p"


def test_pan_search_service_provider_statuses_keep_success_failed_disabled():
    service = PanSearchService(
        search_sources={"fake_pan": True, "failed_pan": True, "missing_pan": False},
        pan_providers=[FakePanProvider(), FailingPanProvider()],
    )

    response = service.search_sync("流浪地球2")
    statuses = {item.name: item for item in response.source_statuses}

    assert statuses["fake_pan"].status == "success"
    assert statuses["fake_pan"].count == 1
    assert statuses["failed_pan"].status == "failed"
    assert statuses["failed_pan"].error == "boom"
    assert statuses["missing_pan"].status == "disabled"


def test_shared_pan_service_passes_http_proxy_to_scrapers(monkeypatch):
    import shared

    captured = {}

    class FakePanSearchService:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(shared, "PanSearchService", FakePanSearchService)
    monkeypatch.setattr(shared, "_pan_search_service", None)
    monkeypatch.setattr(
        shared,
        "config_m",
        type("ConfigManager", (), {"config": type("Config", (), {"http_proxy": "http://proxy:7890"})()})(),
    )
    monkeypatch.setattr("plugin_guard.get_allowed_pan_sources", lambda: {"pansearch"})

    shared._get_pan_search_service()

    assert captured["scraper_proxy"] == "http://proxy:7890"
