from types import SimpleNamespace

from config_manager import AppConfig
from routes import config as config_routes


def test_update_config_resets_pan_service_when_proxy_changes(monkeypatch):
    previous = AppConfig(http_proxy="")
    updated = previous.model_copy(update={"http_proxy": "http://proxy:7890"})
    manager = SimpleNamespace(config=previous)

    def save(conf):
        manager.config = conf

    manager.save = save
    reset_calls = []
    monkeypatch.setattr(config_routes, "config_m", manager)
    monkeypatch.setattr(config_routes, "reset_pan_search_service", lambda: reset_calls.append(True))
    monkeypatch.setattr(config_routes, "invalidate_allowed_roots_cache", lambda: None)

    config_routes.update_config(updated)

    assert reset_calls == [True]


def test_update_config_keeps_pan_service_when_proxy_unchanged(monkeypatch):
    previous = AppConfig(http_proxy="http://proxy:7890")
    updated = previous.model_copy(update={"exclude_dirs": "@eaDir"})
    manager = SimpleNamespace(config=previous)

    def save(conf):
        manager.config = conf

    manager.save = save
    reset_calls = []
    monkeypatch.setattr(config_routes, "config_m", manager)
    monkeypatch.setattr(config_routes, "reset_pan_search_service", lambda: reset_calls.append(True))
    monkeypatch.setattr(config_routes, "invalidate_allowed_roots_cache", lambda: None)

    config_routes.update_config(updated)

    assert reset_calls == []
