"""napics_client 对 Agent API 的调用契约保护。MockTransport 录制 napics 响应。"""
import httpx
import pytest

from napics_client import NapicsClient, NapicsError


def _client_with(handler, token=""):
    c = NapicsClient("http://napics.local", agent_token=token, timeout=5)
    c._client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5)
    return c


def test_search_passes_params_and_returns_json():
    def handler(req):
        assert req.url.path == "/api/agent/search"
        q = dict(req.url.params)
        assert q["query"] == "Titanic 1997"
        assert q["limit"] == "10"
        return httpx.Response(200, json={"query": "Titanic 1997", "total": 0, "results": []})
    c = _client_with(handler)
    out = c.search("Titanic 1997", limit=10)
    assert out["query"] == "Titanic 1997"


def test_submit_sends_idempotency_header_and_token():
    seen = {}

    def handler(req):
        assert req.url.path == "/download-manager/submit"
        seen["idem"] = req.headers.get("Idempotency-Key")
        seen["token"] = req.headers.get("X-Agent-Token")
        return httpx.Response(200, json={"success": True, "task": {"id": "a1b2", "status": "downloading"}})
    c = _client_with(handler, token="secret")
    out = c.submit("magnet:?xt=urn:btih:abc", "泰坦尼克号", "key-1")
    assert out["success"] is True
    assert seen["idem"] == "key-1"
    assert seen["token"] == "secret"


def test_process_posts_params():
    def handler(req):
        assert req.url.path == "/api/agent/process"
        assert dict(req.url.params)["task_id"] == "a1b2"
        return httpx.Response(200, json={"status": "processed", "library_path": "/lib/x", "files": ["/lib/x/a.mkv"]})
    c = _client_with(handler)
    out = c.process(task_id="a1b2")
    assert out["status"] == "processed"


def test_401_raises_auth():
    def handler(req):
        return httpx.Response(401)
    c = _client_with(handler)
    with pytest.raises(NapicsError) as ei:
        c.search("x")
    assert ei.value.auth is True


def test_404_raises_not_found():
    def handler(req):
        return httpx.Response(404)
    c = _client_with(handler)
    with pytest.raises(NapicsError) as ei:
        c.process(task_id="ghost")
    assert ei.value.not_found is True
