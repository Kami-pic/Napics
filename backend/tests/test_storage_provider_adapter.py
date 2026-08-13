from provider_models import ProviderKind, ProviderMetadata
from storage_provider_adapter import StorageProviderAdapter
from storage_provider_factory import get_storage_provider_map


class FakeMount:
    def __init__(self, pan_type, driver, mount_path, status):
        self.pan_type = pan_type
        self.driver = driver
        self.mount_path = mount_path
        self.status = status

    def dict(self):
        return {
            "pan_type": self.pan_type,
            "driver": self.driver,
            "mount_path": self.mount_path,
            "status": self.status,
        }


class FakeOpenListClient:
    api_url = "http://alist"
    headers = {"Authorization": "token"}

    def get_mounts_list(self):
        return [
            FakeMount("quark", "Quark", "/Quark", "work"),
            {"pan_type": "pikpak", "driver": "PikPak", "mount_path": "/PikPak", "status": "error"},
        ]


def _metadata(provider_id="openlist_storage"):
    return ProviderMetadata(
        id=provider_id,
        name="OpenList Storage",
        kind=ProviderKind.STORAGE,
        type="storage",
        enabled=True,
        capabilities=["list_mounts"],
    )


def test_openlist_storage_provider_lists_mounts_as_dto():
    provider = StorageProviderAdapter(_metadata(), FakeOpenListClient)

    mounts = provider.list_mounts()

    assert [item.pan_type for item in mounts] == ["quark", "pikpak"]
    assert mounts[0].mount_path == "/Quark"
    assert mounts[1].status == "error"


def test_storage_provider_factory_builds_openlist_storage_provider():
    providers = get_storage_provider_map(
        metadata_items=[_metadata()],
        client_factories={"openlist_storage": FakeOpenListClient},
    )

    assert list(providers.keys()) == ["openlist_storage"]
    assert providers["openlist_storage"].metadata().kind == ProviderKind.STORAGE


def test_openlist_storage_provider_lists_directory_entries(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})

        class Response:
            status_code = 200

            def json(self):
                return {
                    "data": {
                        "content": [
                            {"name": "Movies", "is_dir": True, "size": 0},
                            {"name": "demo.mkv", "is_dir": False, "size": 1234},
                        ]
                    }
                }

        return Response()

    monkeypatch.setattr("storage_provider_adapter.requests.post", fake_post)
    provider = StorageProviderAdapter(_metadata(), FakeOpenListClient)

    entries = provider.list_dir("Quark")

    assert [(item.path, item.name, item.is_dir, item.size) for item in entries] == [
        ("/Quark/Movies", "Movies", True, 0),
        ("/Quark/demo.mkv", "demo.mkv", False, 1234),
    ]
    assert calls == [
        {
            "url": "http://alist/api/fs/list",
            "headers": {"Authorization": "token"},
            "json": {"path": "/Quark", "page": 1, "per_page": 0, "refresh": False},
            "timeout": 10,
        }
    ]


def test_openlist_storage_provider_exists_checks_parent_listing(monkeypatch):
    provider = StorageProviderAdapter(_metadata(), FakeOpenListClient)
    monkeypatch.setattr(
        provider,
        "list_dir",
        lambda path: [
            type("Entry", (), {"name": "demo.mkv"})(),
        ],
    )

    assert provider.exists("/Quark/demo.mkv") is True
    assert provider.exists("/Quark/missing.mkv") is False
    assert provider.exists("/") is True


def test_alist_mounts_route_keeps_legacy_response_shape(monkeypatch):
    from routes import search as search_routes

    provider = StorageProviderAdapter(_metadata(), FakeOpenListClient)
    monkeypatch.setattr(search_routes, "get_storage_provider_map", lambda: {"openlist_storage": provider})

    response = search_routes.get_alist_mounts()

    assert response == {
        "mounts": [
            {"pan_type": "quark", "driver": "Quark", "mount_path": "/Quark", "status": "work"},
            {"pan_type": "pikpak", "driver": "PikPak", "mount_path": "/PikPak", "status": "error"},
        ]
    }
