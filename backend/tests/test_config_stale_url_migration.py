"""清掉「从没配置过」的出厂默认地址。

这三个地址以前的默认值是 http://127.0.0.1:<端口>。Napics 多数跑在 NAS 或容器里、
外部服务在别的机器上，所以这个默认值几乎必然是错的 —— 用户打开插件配置看到一个
填好的地址，点「测试连接」是真的在连本机、必然失败。改代码里的默认值只影响新装
用户，已经落盘的配置不会自己变，所以要一次性迁移。

判据刻意保守：地址正好等于旧默认值 **且** 对应凭据为空。真配过的人不会留着凭据
不填，所以有凭据的一律不动。
"""
import json

import pytest

from config_manager import ConfigManager


def _load(tmp_path, raw: dict):
    path = tmp_path / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    manager = ConfigManager(config_path=str(path))
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    return manager.config, saved


def test_clears_untouched_default_urls(tmp_path):
    config, saved = _load(tmp_path, {
        "prowlarr_url": "http://127.0.0.1:9696", "prowlarr_api_key": "",
        "qb_url": "http://127.0.0.1:8080", "qb_password": "",
        "alist_url": "http://127.0.0.1:5244", "alist_token": "",
    })
    assert config.prowlarr_url == ""
    assert config.qb_url == ""
    assert config.alist_url == ""
    # 必须落盘，否则每次启动都要重算
    assert saved["prowlarr_url"] == ""
    assert "clear_stale_default_urls" in saved["config_migrations"]


def test_keeps_default_url_when_credential_is_filled(tmp_path):
    """填了凭据说明用户真的在用这个地址（服务确实在本机）。"""
    config, _ = _load(tmp_path, {
        "prowlarr_url": "http://127.0.0.1:9696", "prowlarr_api_key": "abc123",
        "qb_url": "http://127.0.0.1:8080", "qb_password": "letmein",
        "alist_url": "http://127.0.0.1:5244", "alist_token": "tok",
    })
    assert config.prowlarr_url == "http://127.0.0.1:9696"
    assert config.qb_url == "http://127.0.0.1:8080"
    assert config.alist_url == "http://127.0.0.1:5244"


def test_keeps_user_configured_address(tmp_path):
    """用户自己填的局域网地址绝不能动，哪怕凭据还空着。"""
    config, _ = _load(tmp_path, {
        "prowlarr_url": "http://192.168.100.111:9696", "prowlarr_api_key": "",
        "qb_url": "http://192.168.100.111:8080", "qb_password": "",
    })
    assert config.prowlarr_url == "http://192.168.100.111:9696"
    assert config.qb_url == "http://192.168.100.111:8080"


def test_tolerates_trailing_slash(tmp_path):
    config, _ = _load(tmp_path, {"qb_url": "http://127.0.0.1:8080/", "qb_password": ""})
    assert config.qb_url == ""


def test_migration_runs_only_once(tmp_path):
    """跑过一次就记下来。用户之后主动填回 127.0.0.1 不能被再清一遍。"""
    path = tmp_path / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"qb_url": "http://127.0.0.1:8080", "qb_password": ""}, f)

    first = ConfigManager(config_path=str(path))
    assert first.config.qb_url == ""

    # 模拟用户之后自己填了 127.0.0.1（服务真在本机，凭据留空）
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    saved["qb_url"] = "http://127.0.0.1:8080"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(saved, f)

    second = ConfigManager(config_path=str(path))
    assert second.config.qb_url == "http://127.0.0.1:8080", "迁移不该跑第二次"


def test_partial_config_does_not_crash(tmp_path):
    """配置里没有这些字段时不能炸。"""
    config, saved = _load(tmp_path, {"scan_paths": []})
    assert config.qb_url == ""
    assert "clear_stale_default_urls" in saved["config_migrations"]


# ── 连接失败时点出「地址指向本机回环」──

class _Conf:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:9696",
    "http://localhost:9696",
    "HTTP://LocalHost:9696",
    "http://[::1]:9696",
])
def test_loopback_note_is_added_for_local_addresses(url):
    from routes.plugins import _loopback_note

    note = _loopback_note(_Conf(prowlarr_url=url), "search-prowlarr")
    assert "回环" in note
    assert "局域网" in note


def test_loopback_note_is_silent_for_lan_addresses():
    """用户填了真实局域网地址还连不上时，别用无关的提示干扰他。"""
    from routes.plugins import _loopback_note

    assert _loopback_note(_Conf(prowlarr_url="http://192.168.100.111:9696"), "search-prowlarr") == ""
    assert _loopback_note(_Conf(prowlarr_url="http://nas.local:9696"), "search-prowlarr") == ""


def test_loopback_note_handles_unknown_plugin_and_empty_url():
    from routes.plugins import _loopback_note

    assert _loopback_note(_Conf(), "metadata-tmdb") == ""
    assert _loopback_note(_Conf(qb_url=""), "download-qbittorrent") == ""
