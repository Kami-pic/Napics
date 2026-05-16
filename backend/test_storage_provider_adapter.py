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
