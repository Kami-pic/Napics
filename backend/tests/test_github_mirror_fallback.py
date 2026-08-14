"""GitHub 镜像回退：国内直连超时时自动换镜像

真机现象：
    https://github.com/icatmiumiu/plugins-of-napics
    网络请求失败: HTTPSConnectionPool(host='raw.githubusercontent.com', port=443):
    Read timed out. (read timeout=15)

DNS 已经正常（host 网络模式生效），是国内直连 GitHub 超时。
"""
import requests

import pytest

from core import github_access


# ── 候选地址生成 ──

def test_raw_url_gets_mirror_candidates():
    url = "https://raw.githubusercontent.com/user/repo/main/index.json"
    cands = github_access.build_candidates(url)
    assert cands[0] == url, "官方地址必须排第一"
    assert len(cands) > 1, "应该有镜像候选"
    assert all("user/repo/main/index.json" in c for c in cands), "路径部分要保留"


def test_repo_url_gets_mirror_candidates():
    url = "https://github.com/user/repo/archive/refs/heads/main.zip"
    cands = github_access.build_candidates(url)
    assert cands[0] == url
    assert len(cands) > 1


def test_non_github_url_unchanged():
    url = "https://example.com/a.json"
    assert github_access.build_candidates(url) == [url]


def test_custom_mirrors_respected():
    url = "https://raw.githubusercontent.com/u/r/main/x.json"
    cands = github_access.build_candidates(url, mirrors=["https://my.mirror.test"])
    assert cands == ["https://my.mirror.test/u/r/main/x.json"]


def test_empty_mirror_list_disables_fallback():
    """配置为空列表即关闭回退"""
    url = "https://raw.githubusercontent.com/u/r/main/x.json"
    cands = github_access.build_candidates(url, mirrors=[])
    assert cands == [url] or cands == []


# ── 回退行为 ──

def test_falls_back_to_mirror_on_timeout(monkeypatch):
    """官方地址超时时应自动尝试下一个候选并成功"""
    attempts = []

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass

    def fake_get(url, **kwargs):
        attempts.append(url)
        if "raw.githubusercontent.com" in url and "ghproxy" not in url and "gitmirror" not in url:
            raise requests.exceptions.ReadTimeout("Read timed out")
        return FakeResp()

    monkeypatch.setattr(github_access.requests, "get", fake_get)

    resp, used = github_access.get("https://raw.githubusercontent.com/u/r/main/index.json")
    assert resp is not None, "镜像应该成功"
    assert len(attempts) >= 2, "应该先试官方再试镜像"
    assert "raw.githubusercontent.com" in attempts[0], "第一次必须是官方地址"


def test_returns_none_when_all_candidates_fail(monkeypatch):
    def always_timeout(url, **kwargs):
        raise requests.exceptions.ReadTimeout("Read timed out")

    monkeypatch.setattr(github_access.requests, "get", always_timeout)

    resp, err = github_access.get("https://raw.githubusercontent.com/u/r/main/index.json")
    assert resp is None
    assert "Timeout" in err or "timed out" in err.lower()


def test_official_used_when_reachable(monkeypatch):
    """官方地址通的时候不应该走镜像"""
    attempts = []

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass

    def fake_get(url, **kwargs):
        attempts.append(url)
        return FakeResp()

    monkeypatch.setattr(github_access.requests, "get", fake_get)

    resp, used = github_access.get("https://raw.githubusercontent.com/u/r/main/index.json")
    assert resp is not None
    assert len(attempts) == 1, "官方地址可用时不应继续尝试镜像"
    assert "raw.githubusercontent.com" in used


# ── 插件源接入 ──

def test_plugin_source_reports_network_error_not_unsafe(monkeypatch):
    """全部不可达时应报网络错误，而不是安全校验失败"""
    def always_timeout(url, **kwargs):
        raise requests.exceptions.ReadTimeout("Read timed out")

    monkeypatch.setattr(github_access.requests, "get", always_timeout)

    from plugin_manager import PluginManager
    pm = PluginManager()
    result = pm.fetch_remote_index("https://github.com/someone/some-plugins")

    assert result["success"] is False
    assert result.get("error") != "unsafe_url", "网络问题不应报成安全问题"
    assert "镜像" in result.get("message", ""), "应说明已尝试过镜像"
