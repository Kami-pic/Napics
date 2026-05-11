from main import app
from providers import list_providers


def test_provider_api_returns_empty_phase2_catalog():
    response = list_providers()

    assert response.model_dump(by_alias=True) == {
        "search": [],
        "panSearch": [],
        "metadata": [],
        "rss": [],
        "download": [],
        "storage": [],
        "notification": [],
    }


def test_provider_api_route_is_registered():
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/providers" in paths


def test_root_route_keeps_existing_response():
    from main import read_root

    assert read_root() == {"message": "NAS Video Upgrader API is running"}
