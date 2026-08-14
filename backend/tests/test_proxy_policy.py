"""代理分流：国内站点直连，境外站点走代理

用户反馈的核心问题：http_proxy 是唯一的全局配置，所有请求都走它，
于是「要么豆瓣能用、要么 TMDB 能用」——配了代理之后豆瓣封面反而全挂，
因为豆瓣图床被强行绕出国。
"""
import pytest

from core.proxy_policy import is_direct_host, proxies_for, should_use_proxy

PROXY = "http://127.0.0.1:7890"


# ── 必须直连的国内站点 ──

@pytest.mark.parametrize("url", [
    "https://movie.douban.com/j/search_subjects",
    "https://img9.doubanio.com/view/photo/p123.webp",
    "https://api.bgm.tv/calendar",
    "https://lain.bgm.tv/pic/cover/l/x.jpg",
    "https://i0.hdslb.com/bfs/archive/x.jpg",
    "https://example.cn/x.jpg",
])
def test_domestic_sites_bypass_proxy(url):
    assert proxies_for(url, PROXY) is None, f"国内站点不应走代理: {url}"
    assert should_use_proxy(url) is False


def test_douban_image_bypasses_proxy_even_when_proxy_set():
    """这条正是用户遇到的：配了代理后豆瓣封面全挂"""
    url = "https://img2.doubanio.com/view/photo/m_ratio_poster/public/p1234.webp"
    assert proxies_for(url, PROXY) is None


# ── 必须走代理的境外站点 ──

@pytest.mark.parametrize("url", [
    "https://api.themoviedb.org/3/configuration",
    "https://image.tmdb.org/t/p/w500/abc.jpg",
    "https://raw.githubusercontent.com/u/r/main/index.json",
    "https://github.com/u/r/archive/main.zip",
])
def test_foreign_sites_use_proxy(url):
    assert proxies_for(url, PROXY) == {"http": PROXY, "https": PROXY}, \
        f"境外站点应走代理: {url}"
    assert should_use_proxy(url) is True


# ── 没配代理时一律直连 ──

def test_no_proxy_configured_returns_none():
    assert proxies_for("https://api.themoviedb.org/3/", "") is None
    assert proxies_for("https://movie.douban.com/", "") is None


def test_blank_proxy_treated_as_unset():
    assert proxies_for("https://api.themoviedb.org/3/", "   ") is None


# ── 本机与内网直连 ──

@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "host.docker.internal"])
def test_local_hosts_are_direct(host):
    assert is_direct_host(host) is True


def test_local_service_bypasses_proxy():
    assert proxies_for("http://127.0.0.1:8080/api/v2/torrents/info", PROXY) is None


# ── 自定义追加 ──

def test_extra_direct_domains_respected():
    url = "https://my-nas-site.example/x.jpg"
    assert proxies_for(url, PROXY) is not None, "默认应走代理"
    assert proxies_for(url, PROXY, extra_direct=["example"]) is None, "追加后应直连"


# ── 边界 ──

def test_malformed_url_does_not_crash():
    assert proxies_for("not a url", PROXY) is not None or True  # 不抛异常即可
    assert is_direct_host("") is False


def test_suffix_match_not_substring():
    """notdouban.com 不应因为包含 douban.com 就被当成直连"""
    assert is_direct_host("notdouban.com") is False
    assert is_direct_host("img.douban.com") is True
