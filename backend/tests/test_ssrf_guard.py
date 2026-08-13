"""SSRF 防护验证：后端不能被诱导去请求内网地址

/proxy/image 会把响应体原样回显，如果不校验就能用它读取局域网服务的接口响应
（比如 qBittorrent 的 127.0.0.1:8080）。这里锁定内网目标被拒、公网目标放行。
"""
import pytest

from core.url_guard import (
    UnsafeUrlError,
    assert_external_url,
    check_external_url,
    clear_cache,
    is_https_url,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


# ── 必须拒绝的目标 ──

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080/api/v2/torrents/info",   # qBittorrent
    "http://127.0.0.1:9696/api/v1/indexer",         # Prowlarr
    "http://localhost:5245/api/fs/list",            # OpenList
    "http://0.0.0.0:8001/",
    "http://[::1]:8080/",
    "http://192.168.1.1/",
    "http://10.0.0.5/admin",
    "http://172.16.31.7/",
    "http://169.254.169.254/latest/meta-data/",     # 云厂商 metadata
])
def test_rejects_internal_targets(url):
    ok, reason = check_external_url(url)
    assert ok is False, f"内网地址未被拦截: {url}"
    assert reason


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://127.0.0.1:8080/_test",
    "ftp://example.com/x.jpg",
    "data:image/png;base64,iVBORw0KGgo=",
])
def test_rejects_non_http_schemes(url):
    ok, _ = check_external_url(url)
    assert ok is False, f"非 http(s) 协议未被拦截: {url}"


@pytest.mark.parametrize("url", ["", "   ", "not-a-url", "http://", "https://"])
def test_rejects_malformed(url):
    ok, _ = check_external_url(url)
    assert ok is False


def test_assert_raises_on_internal():
    with pytest.raises(UnsafeUrlError):
        assert_external_url("http://127.0.0.1:8080/")


# ── 必须放行的目标（公网 IP 字面量，不依赖 DNS） ──

@pytest.mark.parametrize("url", [
    "https://8.8.8.8/img.jpg",
    "http://1.1.1.1/poster.png",
    "https://93.184.216.34/x.jpg",
])
def test_allows_public_ip_literals(url):
    ok, reason = check_external_url(url)
    assert ok is True, f"公网地址被误拦: {url} ({reason})"


# ── https 判定（决定能否附带 License Key） ──

def test_is_https_url():
    assert is_https_url("https://example.com/index.json") is True
    assert is_https_url("http://example.com/index.json") is False
    assert is_https_url("HTTPS://Example.com/x") is True


# ── 路由层集成 ──

def test_proxy_image_rejects_internal_address():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    resp = client.get("/proxy/image", params={"url": "http://127.0.0.1:8080/api/v2/app/preferences"})
    assert resp.status_code == 400
    # 不能把内网响应内容回显出来
    assert b"preferences" not in resp.content


def test_poster_url_rejects_internal_address(monkeypatch):
    """路径合法但 URL 指向内网时，必须因 SSRF 校验被拒（400 而非 403）"""
    import os
    import shutil
    import tempfile

    from fastapi.testclient import TestClient
    from main import app
    import shared

    d = tempfile.mkdtemp(prefix="napics_ssrf_")
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [d])
    shared.invalidate_allowed_roots_cache()
    try:
        client = TestClient(app)
        resp = client.post("/scrape/poster-url", params={
            "path": d,
            "url": "http://192.168.1.1/x.jpg",
        })
        assert resp.status_code == 400
    finally:
        shared.invalidate_allowed_roots_cache()
        shutil.rmtree(d, ignore_errors=True)


def test_plugin_source_rejects_internal_address():
    """插件源拉取也要拦，否则同样能探测内网"""
    from plugin_manager import PluginManager
    pm = PluginManager()

    result = pm.fetch_remote_index("http://127.0.0.1:9696/index.json")
    assert result["success"] is False
    assert result.get("error") == "unsafe_url"
