import search_service


def test_search_service_scraper_list_uses_provider_factory_order(monkeypatch):
    factories = {
        "bitsearch": lambda: object(),
        "cilixiong": lambda: object(),
        "xl720": lambda: object(),
        "nyaa": lambda: object(),
        "mikan": lambda: object(),
        "yts": lambda: object(),
        "limetorrents": lambda: object(),
        "acgrip": lambda: object(),
        "bangumi_moe": lambda: object(),
        "eztv": lambda: object(),
        "dmhy": lambda: object(),
        "1337x": lambda: object(),
    }

    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_scraper_factories",
        lambda: factories,
    )

    names = [name for name, _ in search_service._get_scraper_list()]

    assert names == [name for name in search_service.BT_SOURCE_DEFAULTS if name != "prowlarr"]


def test_enabled_sources_keeps_legacy_override_behavior(monkeypatch):
    factories = {
        name: (lambda: object())
        for name in search_service.BT_SOURCE_DEFAULTS
        if name != "prowlarr"
    }
    monkeypatch.setattr(
        "bt_search_provider_factory.get_direct_bt_scraper_factories",
        lambda: factories,
    )

    prowlarr_enabled, enabled_scrapers = search_service._get_enabled_sources(
        {
            "prowlarr": False,
            "bitsearch": {"enabled": False, "proxy": True},
            "limetorrents": True,
        }
    )

    enabled_names = [name for name, _ in enabled_scrapers]
    assert prowlarr_enabled is False
    assert "bitsearch" not in enabled_names
    assert "limetorrents" in enabled_names
