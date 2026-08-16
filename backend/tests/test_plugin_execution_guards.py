"""插件卸载后，业务执行入口不得继续调用对应外部服务。"""
from types import SimpleNamespace

import plugin_guard
from metadata_provider_factory import get_metadata_provider_map
from storage_provider_factory import get_storage_provider_map
from routes import library_crud as library_routes
from routes import media_detail as media_detail_routes
from routes import media_info as media_info_routes
from routes import scrape_execute as scrape_execute_routes
from routes import search as search_routes
import shared


def _disabled(*_args, **_kwargs):
    return False


def _unexpected_call(*_args, **_kwargs):
    raise AssertionError("插件已卸载，不应调用外部服务")


def test_default_metadata_provider_map_filters_uninstalled_plugins(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_metadata_allowed", lambda provider: provider == "tmdb")

    providers = get_metadata_provider_map(
        source_factories={
            "tmdb": lambda: object(),
            "douban": lambda: object(),
            "bangumi": lambda: object(),
        }
    )

    assert list(providers) == ["tmdb"]


def test_default_storage_provider_map_filters_uninstalled_plugin(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_storage_allowed", _disabled)

    providers = get_storage_provider_map(
        client_factories={"openlist_storage": lambda: object()}
    )

    assert providers == {}


def test_tmdb_candidates_do_not_construct_client_when_plugin_uninstalled(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_metadata_allowed", _disabled)
    monkeypatch.setattr(
        media_info_routes,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(tmdb_api_key="configured", http_proxy="")),
    )
    monkeypatch.setattr(media_info_routes.tmdb_client, "TMDBClient", _unexpected_call)

    response = media_info_routes.scrape_candidates("测试影片")

    assert response == {
        "query": "测试影片",
        "candidates": [],
        "error": "plugin_not_installed",
    }


def test_execute_scrape_does_not_construct_tmdb_when_plugin_uninstalled(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_metadata_allowed", _disabled)
    monkeypatch.setattr(
        scrape_execute_routes,
        "config_m",
        SimpleNamespace(
            config=SimpleNamespace(
                default_scrape_source="tmdb",
                tmdb_api_key="configured",
                http_proxy="",
            ),
            load_no_scrape=lambda: [],
        ),
    )
    monkeypatch.setattr(scrape_execute_routes.tmdb_client, "TMDBClient", _unexpected_call)

    response = scrape_execute_routes.execute_scrape("D:/Media/Test")

    assert response == {"self": {"status": "plugin_not_installed", "data": None}}


def test_media_detail_helpers_skip_all_uninstalled_sources(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_metadata_allowed", _disabled)
    monkeypatch.setattr(media_detail_routes.douban_api_v2, "search", _unexpected_call)
    monkeypatch.setattr(media_detail_routes.bangumi_client, "search", _unexpected_call)
    monkeypatch.setattr(media_detail_routes, "get_metadata_provider_map", _unexpected_call)

    assert media_detail_routes._try_douban_detail("测试", "2024", "movie") is None
    assert media_detail_routes._try_bangumi_detail("测试") is None
    assert media_detail_routes._try_tmdb_detail("测试", "2024", "movie") == {"found": False}
    assert media_detail_routes._try_tmdb_detail_by_id(1, "movie") == {"found": False}


def test_alist_mounts_does_not_build_provider_when_plugin_uninstalled(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_storage_allowed", _disabled)
    monkeypatch.setattr(search_routes, "get_storage_provider_map", _unexpected_call)

    response = search_routes.get_alist_mounts()

    assert response == {"mounts": [], "error": "plugin_not_installed"}


def test_local_matcher_returns_neutral_state_when_plugin_uninstalled(monkeypatch):
    from local_media_matcher import LocalMediaMatcher

    matcher = LocalMediaMatcher()
    matcher._indexed = True
    matcher._tmdb_index = {123: {"quality": "high", "folder": "D:/Media/Test"}}
    monkeypatch.setattr(plugin_guard, "is_feature_allowed", _disabled)
    monkeypatch.setattr(matcher, "_enqueue_async", _unexpected_call)

    items = [{"tmdb_id": 123, "title": "测试"}, {"douban_id": "456", "title": "未匹配"}]
    result = matcher.match_batch(items)

    assert result == [
        {"tmdb_id": 123, "title": "测试", "local_status": "none", "local_folder": ""},
        {"douban_id": "456", "title": "未匹配", "local_status": "none", "local_folder": ""},
    ]


def test_completeness_batch_does_not_start_when_plugin_uninstalled(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_feature_allowed", _disabled)
    monkeypatch.setattr(library_routes, "_tmdb_client", _unexpected_call)
    monkeypatch.setattr(library_routes.threading, "Thread", _unexpected_call)

    response = library_routes.refresh_all_completeness()

    assert response == {
        "status": "plugin_not_installed",
        "message": "请先安装「季集完整性检测」插件",
    }


def test_shared_tmdb_factory_skips_uninstalled_plugin(monkeypatch):
    monkeypatch.setattr(plugin_guard, "is_metadata_allowed", _disabled)
    monkeypatch.setattr(shared.tmdb_client, "TMDBClient", _unexpected_call)
    monkeypatch.setattr(
        shared,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(tmdb_api_key="configured", http_proxy="")),
    )

    assert shared._tmdb_client() is None
