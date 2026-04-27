import requests

from downloader import AlistManager


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_transfer_link_returns_task_id_from_tasks_list(monkeypatch):
    manager = AlistManager("http://alist", "token")

    def fake_post(url, json=None, headers=None, timeout=None):
        return FakeResponse(
            {
                "code": 200,
                "data": {
                    "tasks": [
                        {"id": "task-123", "name": "demo-file"}
                    ]
                },
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)

    success, task_id = manager.transfer_link("http://example.com/file.torrent", "/Quark")

    assert success is True
    assert task_id == "task-123"


def test_transfer_link_returns_empty_task_id_when_missing(monkeypatch):
    manager = AlistManager("http://alist", "token")

    def fake_post(url, json=None, headers=None, timeout=None):
        return FakeResponse({"code": 200, "data": {}})

    monkeypatch.setattr(requests, "post", fake_post)

    success, task_id = manager.transfer_link("http://example.com/file.torrent", "/Quark")

    assert success is True
    assert task_id == ""
