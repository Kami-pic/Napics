"""qb_client 直连 qB 的行为保护。用 httpx.MockTransport 录制 qB 响应，不连真实 qB。"""
import httpx
import pytest

from qb_client import QbClient, QbError


def _client_with(handler):
    c = QbClient("http://qb.local", "admin", "pw", timeout=5)
    c._client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5)
    return c


def test_login_ok_then_reachable():
    def handler(req):
        assert req.url.path == "/api/v2/auth/login"
        return httpx.Response(200, text="Ok.")
    c = _client_with(handler)
    assert c.reachable() is True


def test_login_failure_raises_auth():
    def handler(req):
        return httpx.Response(403, text="Fails.")
    c = _client_with(handler)
    with pytest.raises(QbError) as ei:
        c._login()
    assert ei.value.auth is True


def test_torrent_info_returns_first_item():
    def handler(req):
        if req.url.path.endswith("/auth/login"):
            return httpx.Response(200, text="Ok.")
        assert req.url.path == "/api/v2/torrents/info"
        return httpx.Response(200, json=[{"hash": "abc", "state": "downloading",
                                          "progress": 0.5, "dlspeed": 1000, "eta": 60}])
    c = _client_with(handler)
    info = c.torrent_info("ABC")
    assert info["state"] == "downloading"


def test_torrent_info_none_when_empty():
    def handler(req):
        if req.url.path.endswith("/auth/login"):
            return httpx.Response(204)
        return httpx.Response(200, json=[])
    c = _client_with(handler)
    assert c.torrent_info("nope") is None


def test_delete_hash_not_found_still_ok():
    """qB delete 端点对不存在的 hash 也回 200，视作成功。"""
    seen = {}

    def handler(req):
        if req.url.path.endswith("/auth/login"):
            return httpx.Response(200, text="Ok.")
        assert req.url.path == "/api/v2/torrents/delete"
        seen["body"] = req.content.decode()
        return httpx.Response(200)
    c = _client_with(handler)
    assert c.delete("ghost", delete_files=True) is True
    assert "deleteFiles=true" in seen["body"]


def test_get_retries_once_on_403():
    """403 视作 session 过期，清登录态重登一次。"""
    calls = {"login": 0, "info": 0}

    def handler(req):
        if req.url.path.endswith("/auth/login"):
            calls["login"] += 1
            return httpx.Response(200, text="Ok.")
        calls["info"] += 1
        if calls["info"] == 1:
            return httpx.Response(403)
        return httpx.Response(200, json=[{"hash": "x", "state": "stalledDL",
                                          "progress": 0.0, "dlspeed": 0}])
    c = _client_with(handler)
    info = c.torrent_info("x")
    assert info["state"] == "stalledDL"
    assert calls["login"] == 2  # 首登 + 403 后重登
    assert calls["info"] == 2
