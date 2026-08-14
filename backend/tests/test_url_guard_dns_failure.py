"""SSRF 防护不能把 DNS 故障误判成「URL 不安全」

真机现象（容器没有 DNS）：
    Temporary failure in name resolution
插件源安装被拒并返回 error=unsafe_url，用户看到的是「URL 不被允许」，
真实原因（容器无 DNS）被完全掩盖。

契约：DNS 解析失败时放行，让请求层去报真实的网络错误；
      但明确指向内网/环回的地址仍必须拦下。
"""
import socket

import pytest

from core import url_guard


@pytest.fixture(autouse=True)
def _clear_cache():
    url_guard.clear_cache()
    yield
    url_guard.clear_cache()


def test_dns_failure_is_allowed(monkeypatch):
    """DNS 解析失败必须放行，不能报成 unsafe"""
    def no_dns(*a, **k):
        raise socket.gaierror(-3, "Temporary failure in name resolution")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", no_dns)

    ok, reason = url_guard.check_external_url("https://raw.githubusercontent.com/x/y/main/manifest.json")
    assert ok is True, f"DNS 失败时不应判定为不安全（reason={reason}）"


def test_dns_failure_does_not_raise(monkeypatch):
    def no_dns(*a, **k):
        raise socket.gaierror(-3, "Temporary failure in name resolution")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", no_dns)
    url_guard.assert_external_url("https://api.themoviedb.org/3/")


def test_plugin_source_not_rejected_when_dns_down(monkeypatch):
    """插件源拉取在无 DNS 环境下不能返回 unsafe_url"""
    def no_dns(*a, **k):
        raise socket.gaierror(-3, "Temporary failure in name resolution")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", no_dns)

    from plugin_manager import PluginManager
    pm = PluginManager()
    result = pm.fetch_remote_index("https://github.com/someone/some-plugins")

    # 允许失败（确实没网），但不能是被安全校验拦下的
    assert result.get("error") != "unsafe_url", \
        "DNS 故障被误判为 unsafe_url，会掩盖真实的网络问题"


# ── 内网地址仍然必须拦住（防护不能因此失效）──

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8080/api/v2/torrents/info",
    "http://192.168.1.1/",
    "http://10.0.0.5/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]:8080/",
])
def test_internal_ip_literals_still_blocked(url, monkeypatch):
    """IP 字面量不经过 DNS，必须继续拦下"""
    def no_dns(*a, **k):
        raise socket.gaierror(-3, "Temporary failure in name resolution")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", no_dns)

    ok, _ = url_guard.check_external_url(url)
    assert ok is False, f"内网地址必须被拦下: {url}"


def test_domain_resolving_to_internal_still_blocked(monkeypatch):
    """域名解析到内网地址时仍要拦下"""
    def fake(*a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", fake)

    ok, reason = url_guard.check_external_url("http://evil.example.com/")
    assert ok is False
    assert "非公网" in reason or "127.0.0.1" in reason


def test_non_http_scheme_still_blocked(monkeypatch):
    def no_dns(*a, **k):
        raise socket.gaierror(-3, "boom")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", no_dns)
    ok, _ = url_guard.check_external_url("file:///etc/passwd")
    assert ok is False
