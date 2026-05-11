from main import app
from providers import list_providers


def test_provider_api_returns_static_phase2_catalog():
    response = list_providers()
    payload = response.model_dump(by_alias=True)

    assert payload["metadata"] == []
    assert payload["download"] == []
    assert payload["storage"] == []
    assert payload["notification"] == []
    assert any(item["id"] == "prowlarr" for item in payload["search"])
    assert any(item["id"] == "pansearch" for item in payload["panSearch"])
    assert any(item["id"] == "rss_mikan" for item in payload["rss"])
    prowlarr = next(item for item in payload["search"] if item["id"] == "prowlarr")
    assert prowlarr["kind"] == "search"
    assert prowlarr["riskLevel"] == "user_configured"
    assert prowlarr["requires"] == ["api_url", "api_key"]
    assert prowlarr["supportsProxy"] is False


def test_provider_api_route_is_registered():
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/providers" in paths


def test_root_route_keeps_existing_response():
    from main import read_root

    assert read_root() == {"message": "NAS Video Upgrader API is running"}
