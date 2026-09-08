"""工具层行为保护：注入 fake napics/qb client，验证 §3 DTO 与 §5 错误契约。"""
import pytest

import server
import models as m
from napics_client import NapicsError
from qb_client import QbError


class FakeNapics:
    def __init__(self, **behav):
        self.behav = behav
        self.calls = []

    def reachable(self):
        return self.behav.get("reachable", True)

    def search(self, query, **kw):
        self.calls.append(("search", query, kw))
        if "search_raise" in self.behav:
            raise self.behav["search_raise"]
        return self.behav.get("search_return", {"query": query, "total": 0, "results": []})

    def submit(self, download_url, media_name, idempotency_key, save_path=None, channel="qb"):
        self.calls.append(("submit", idempotency_key))
        if "submit_raise" in self.behav:
            raise self.behav["submit_raise"]
        return self.behav["submit_return"]

    def process(self, path=None, task_id=None):
        if "process_raise" in self.behav:
            raise self.behav["process_raise"]
        return self.behav["process_return"]


class FakeQb:
    def __init__(self, **behav):
        self.behav = behav
        self.deleted = []

    def reachable(self):
        return self.behav.get("reachable", True)

    def torrent_info(self, h):
        if "info_raise" in self.behav:
            raise self.behav["info_raise"]
        return self.behav.get("info_return")

    def delete(self, h, delete_files=False):
        if "delete_raise" in self.behav:
            raise self.behav["delete_raise"]
        self.deleted.append((h, delete_files))
        return True


@pytest.fixture(autouse=True)
def _restore():
    yield
    server.set_clients(None, None)


# ── health ──

def test_health_both_up():
    server.set_clients(FakeNapics(reachable=True), FakeQb(reachable=True))
    out = server.napics_health()
    assert out["ok"] is True
    assert out["napics"]["available"] and out["qbittorrent"]["available"]


def test_health_qb_down():
    server.set_clients(FakeNapics(reachable=True), FakeQb(reachable=False))
    out = server.napics_health()
    assert out["ok"] is False
    assert out["napics"]["available"] is True
    assert out["qbittorrent"]["available"] is False


# ── search ──

def test_search_empty_returns_no_results_error():
    server.set_clients(FakeNapics(search_return={"query": "x", "total": 0, "results": []}), None)
    out = server.napics_search("x")
    assert out["error"]["code"] == m.ERR_NO_RESULTS


def test_search_maps_resources():
    server.set_clients(FakeNapics(search_return={
        "query": "Titanic", "total": 1,
        "results": [{"title": "Titanic 2160p", "download_url": "magnet:?x",
                     "size_gb": 40.2, "resolution": "2160p", "score": 88}],
    }), None)
    out = server.napics_search("Titanic")
    assert out["total"] == 1
    assert out["results"][0]["resolution"] == "2160p"
    assert out["results"][0]["download_url"] == "magnet:?x"


def test_search_no_source_is_search_failed():
    server.set_clients(FakeNapics(search_return={
        "query": "x", "total": 0, "results": [], "error": "no_source", "message": "未装插件"}), None)
    out = server.napics_search("x")
    assert out["error"]["code"] == m.ERR_SEARCH_FAILED


def test_search_napics_down_retryable():
    server.set_clients(FakeNapics(search_raise=NapicsError("boom")), None)
    out = server.napics_search("x")
    assert out["error"]["code"] == m.ERR_NAPICS_UNAVAILABLE
    assert out["error"]["retryable"] is True


def test_search_auth_error():
    server.set_clients(FakeNapics(search_raise=NapicsError("bad token", auth=True)), None)
    out = server.napics_search("x")
    assert out["error"]["code"] == m.ERR_AUTH_FAILED
    assert out["error"]["retryable"] is False


# ── download ──

def test_download_requires_key():
    server.set_clients(FakeNapics(), None)
    out = server.napics_download("magnet:?x", "片", "")
    assert out["error"]["code"] == m.ERR_DOWNLOAD_FAILED


def test_download_success_extracts_hash_from_task():
    server.set_clients(FakeNapics(submit_return={
        "success": True, "task": {"id": "a1b2", "downloader_hash": "HASH1", "status": "downloading"}}), None)
    out = server.napics_download("magnet:?x", "片", "k1")
    assert out["task_id"] == "a1b2"
    assert out["qb_hash"] == "HASH1"
    assert out["status"] == "downloading"


def test_download_failure_from_napics():
    server.set_clients(FakeNapics(submit_return={
        "success": False, "error": "黑名单", "task": {}}), None)
    out = server.napics_download("magnet:?x", "片", "k1")
    assert out["error"]["code"] == m.ERR_DOWNLOAD_FAILED


def test_download_empty_hash_is_none_not_crash():
    server.set_clients(FakeNapics(submit_return={
        "success": True, "task": {"id": "a1b2", "downloader_hash": "", "status": "downloading"}}), None)
    out = server.napics_download("magnet:?x", "片", "k1")
    assert out["qb_hash"] is None


# ── status ──

def test_status_maps_qb():
    server.set_clients(None, FakeQb(info_return={
        "state": "downloading", "progress": 0.25, "dlspeed": 2048, "eta": 120}))
    out = server.napics_download_status("h")
    assert out["status"] == "downloading"
    assert out["percentage"] == 25.0
    assert out["download_speed_bytes"] == 2048
    assert out["eta_seconds"] == 120


def test_status_infinite_eta_is_none():
    server.set_clients(None, FakeQb(info_return={
        "state": "stalledDL", "progress": 0.0, "dlspeed": 0, "eta": 8640000}))
    out = server.napics_download_status("h")
    assert out["eta_seconds"] is None


def test_status_not_found():
    server.set_clients(None, FakeQb(info_return=None))
    out = server.napics_download_status("ghost")
    assert out["error"]["code"] == m.ERR_DOWNLOAD_NOT_FOUND


def test_status_qb_down_retryable():
    server.set_clients(None, FakeQb(info_raise=QbError("conn refused")))
    out = server.napics_download_status("h")
    assert out["error"]["code"] == m.ERR_QB_UNAVAILABLE
    assert out["error"]["retryable"] is True


# ── cancel ──

def test_cancel_ok():
    qb = FakeQb()
    server.set_clients(None, qb)
    out = server.napics_cancel_download("h", delete_files=True)
    assert out["ok"] is True
    assert qb.deleted == [("h", True)]


def test_cancel_empty_hash():
    server.set_clients(None, FakeQb())
    out = server.napics_cancel_download("")
    assert out["error"]["code"] == m.ERR_DOWNLOAD_NOT_FOUND


# ── process ──

def test_process_partial_when_no_tmdb():
    server.set_clients(FakeNapics(process_return={
        "status": "partial", "library_path": "/lib", "files": [], "message": "未配 TMDB"}), None)
    out = server.napics_process(task_id="a1b2")
    assert out["status"] == "partial"
    assert out["message"] == "未配 TMDB"


def test_process_failed():
    server.set_clients(FakeNapics(process_return={"status": "failed", "error": "炸了"}), None)
    out = server.napics_process(task_id="a1b2")
    assert out["error"]["code"] == m.ERR_PROCESS_FAILED


def test_process_needs_target():
    server.set_clients(FakeNapics(), None)
    out = server.napics_process()
    assert out["error"]["code"] == m.ERR_PROCESS_FAILED
