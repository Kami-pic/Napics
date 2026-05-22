from routes import subscribe as subscribe_routes


class FakeRSSSource:
    display_name = "Fake RSS"
    enabled = True

    def __init__(self, name):
        self.name = name

    def fetch(self, subscription):
        return []


def test_subscribe_source_manager_registers_rss_sources_from_factory(monkeypatch):
    subscribe_routes._source_manager = None
    factories = {
        "prowlarr": lambda: FakeRSSSource("prowlarr"),
        "mikan": lambda: FakeRSSSource("mikan"),
    }
    monkeypatch.setattr(subscribe_routes, "get_rss_source_factories", lambda: factories)

    manager = subscribe_routes._get_source_manager()
    sources = manager.get_all_sources()

    assert [source["name"] for source in sources] == ["prowlarr", "mikan"]
    assert [source["display_name"] for source in sources] == ["Fake RSS", "Fake RSS"]

    subscribe_routes._source_manager = None


def test_subscribe_source_manager_skips_failed_factory(monkeypatch):
    subscribe_routes._source_manager = None

    def _broken():
        raise RuntimeError("boom")

    factories = {
        "broken": _broken,
        "mikan": lambda: FakeRSSSource("mikan"),
    }
    monkeypatch.setattr(subscribe_routes, "get_rss_source_factories", lambda: factories)

    manager = subscribe_routes._get_source_manager()
    sources = manager.get_all_sources()

    assert [source["name"] for source in sources] == ["mikan"]

    subscribe_routes._source_manager = None
