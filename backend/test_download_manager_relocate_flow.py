"""download_manager 下载完成到自动归位的行为保护测试。"""

import sys
import threading
import shutil
import uuid
from types import SimpleNamespace
from pathlib import Path

import requests

from download_manager import DownloadManager, DownloadTask
from file_relocator import RelocateResult


class FakeSubscriptionManager:
    def __init__(self, sub):
        self.sub = sub
        self.download_complete_calls = []
        self.update_calls = []

    def on_download_complete(self, **kwargs):
        self.download_complete_calls.append(kwargs)

    def get(self, sub_id):
        if self.sub and sub_id == self.sub.id:
            return self.sub
        return None

    def update(self, sub_id, payload):
        self.update_calls.append({"sub_id": sub_id, "payload": dict(payload)})


class FakeRelocator:
    def __init__(self, relocate_result, confirm_result=None):
        self.relocate_result = relocate_result
        self.confirm_result = confirm_result
        self.relocate_calls = []
        self.confirm_calls = []

    async def relocate(self, task):
        self.relocate_calls.append(task.id)
        return self.relocate_result

    async def confirm_replace(self, task, plan):
        self.confirm_calls.append({"task_id": task.id, "plan": dict(plan)})
        return self.confirm_result


class BlockingConcurrentRelocator:
    def __init__(self, expected_calls):
        self.expected_calls = expected_calls
        self.relocate_calls = []
        self.thread_names = []
        self.confirm_calls = []
        self.all_started = threading.Event()
        self.release = threading.Event()
        self.all_finished = threading.Event()
        self._lock = threading.Lock()
        self._finished = 0

    async def relocate(self, task):
        with self._lock:
            self.relocate_calls.append(task.id)
            self.thread_names.append(threading.current_thread().name)
            if len(self.relocate_calls) == self.expected_calls:
                self.all_started.set()
        self.release.wait(timeout=2)
        with self._lock:
            self._finished += 1
            if self._finished == self.expected_calls:
                self.all_finished.set()
        return RelocateResult(success=True, status="archived", action_plan={"plan": []})

    async def confirm_replace(self, task, plan):
        self.confirm_calls.append({"task_id": task.id, "plan": dict(plan)})
        return RelocateResult(success=True, status="archived", action_plan={"plan": []})


class ImmediateThread:
    def __init__(self, target=None, args=None, kwargs=None, **_):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class RecordingThread:
    created = []

    def __init__(self, target=None, args=None, kwargs=None, **extra):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.extra = dict(extra)
        self.started = False
        RecordingThread.created.append(self)

    def start(self):
        self.started = True


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeQBSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


class FakeQBClient:
    def __init__(self, responses, login_result=True):
        self.url = "http://qb"
        self.session = FakeQBSession(responses)
        self.login_result = login_result

    def _login(self):
        return self.login_result


class FakeSubmitQBClient:
    def __init__(self, add_result=True, add_exception=None):
        self.add_result = add_result
        self.add_exception = add_exception
        self.calls = []

    def add_torrent(self, download_url, save_path):
        self.calls.append({"download_url": download_url, "save_path": save_path})
        if self.add_exception:
            raise self.add_exception
        return self.add_result


class FakeAlistClient:
    def __init__(self):
        self.api_url = "http://alist"
        self.headers = {"Authorization": "token"}


class FakeSubmitAlistClient:
    def __init__(self, transfer_result=True, transfer_exception=None):
        self.transfer_result = transfer_result
        self.transfer_exception = transfer_exception
        self.calls = []

    def transfer_link(self, download_url, download_dir):
        self.calls.append({"download_url": download_url, "download_dir": download_dir})
        if self.transfer_exception:
            raise self.transfer_exception
        return self.transfer_result


def _with_temp_dir(name, test_fn):
    tmp_dir = Path.cwd() / f"{name}_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir()
    try:
        test_fn(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _make_task(**overrides):
    data = {
        "id": "task-1",
        "media_name": "Show",
        "download_url": "magnet:?xt=urn:btih:123",
        "save_path": r"C:\library\Show",
        "channel": "qb",
        "downloader_hash": "hash-1",
        "category_hint": "tv",
        "subscription_id": "sub-1",
        "subscription_episode": 2,
    }
    data.update(overrides)
    if data.get("channel") == "alist" and "downloader_hash" not in overrides:
        data["downloader_hash"] = f"alist_{data['id']}"
    return DownloadTask(**data)


def test_submit_marks_qb_task_downloading_and_persists(monkeypatch):
    def run(tmp_dir):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=str(tmp_dir))
        task = _make_task(channel="qb", downloader_hash="")
        save_calls = []
        now_values = iter(["2026-04-26T10:00:00", "2026-04-26T10:00:01"])

        monkeypatch.setattr("download_manager.uuid.uuid4", lambda: "abcd1234-0000")
        monkeypatch.setattr("download_manager.datetime", SimpleNamespace(now=lambda: SimpleNamespace(isoformat=lambda: next(now_values))))
        monkeypatch.setattr(dm, "_push_to_qb", lambda current: (True, "hash-new"))
        monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

        result = dm.submit(task)

        assert result is task
        assert task.id == "abcd1234"
        assert task.status == "downloading"
        assert task.downloader_hash == "hash-new"
        assert task.phase == ""
        assert task.created_at == "2026-04-26T10:00:00"
        assert task.updated_at == "2026-04-26T10:00:01"
        assert Path(task.download_dir).is_dir()
        assert dm.tasks == [task]
        assert save_calls == ["saved"]

    _with_temp_dir("download_manager_submit_qb", run)


def test_submit_marks_alist_task_downloading_with_cloud_phase(monkeypatch):
    def run(tmp_dir):
        dm = DownloadManager(qb_client=None, alist_client=object(), base_path=str(tmp_dir))
        task = _make_task(channel="alist", downloader_hash="")
        save_calls = []

        monkeypatch.setattr("download_manager.uuid.uuid4", lambda: "efgh5678-0000")
        monkeypatch.setattr(dm, "_push_to_alist", lambda current: (True, "alist_efgh5678"))
        monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

        dm.submit(task)

        assert task.id == "efgh5678"
        assert task.status == "downloading"
        assert task.downloader_hash == "alist_efgh5678"
        assert task.phase == "cloud_download"
        assert Path(task.download_dir).is_dir()
        assert save_calls == ["saved"]

    _with_temp_dir("download_manager_submit_alist", run)


def test_submit_marks_task_failed_when_push_fails(monkeypatch):
    def run(tmp_dir):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=str(tmp_dir))
        task = _make_task(channel="qb", downloader_hash="")
        save_calls = []

        monkeypatch.setattr("download_manager.uuid.uuid4", lambda: "fail1234-0000")
        monkeypatch.setattr(dm, "_push_to_qb", lambda current: (False, "qb failed"))
        monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

        dm.submit(task)

        assert task.status == "failed"
        assert task.error == "qb failed"
        assert task.downloader_hash == ""
        assert Path(task.download_dir).is_dir()
        assert save_calls == ["saved"]

    _with_temp_dir("download_manager_submit_failed", run)


def test_submit_marks_task_failed_when_channel_is_not_configured(monkeypatch):
    def run(tmp_dir):
        dm = DownloadManager(qb_client=None, alist_client=None, base_path=str(tmp_dir))
        task = _make_task(channel="qb", downloader_hash="")
        save_calls = []

        monkeypatch.setattr("download_manager.uuid.uuid4", lambda: "miss1234-0000")
        monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

        dm.submit(task)

        assert task.status == "failed"
        assert task.error == "下载通道 qb 未配置"
        assert Path(task.download_dir).is_dir()
        assert save_calls == ["saved"]

    _with_temp_dir("download_manager_submit_missing_channel", run)


def test_notify_subscription_complete_triggers_auto_relocate_for_best_version(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=True,
        purpose="follow",
        type="tv",
    )
    mgr = FakeSubscriptionManager(sub)
    notifications = []
    auto_relocate_calls = []

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(
        add_notification=lambda *_args: notifications.append(_args[2:])
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    monkeypatch.setattr(
        dm,
        "_auto_relocate",
        lambda task, sub_obj=None: auto_relocate_calls.append(
            {"task_id": task.id, "sub_id": getattr(sub_obj, "id", "")}
        ),
    )

    dm._notify_subscription_complete(_make_task())

    assert mgr.download_complete_calls == [
        {
            "subscription_id": "sub-1",
            "episode": 2,
            "info_hash": "hash-1",
            "title": "Show",
            "quality_tag": "",
            "source": "tv",
            "channel": "qb",
            "task_id": "task-1",
        }
    ]
    assert auto_relocate_calls == [{"task_id": "task-1", "sub_id": "sub-1"}]
    assert notifications == [("download_complete", "下载完成: Show")]


def test_auto_relocate_confirms_replace_when_conflicts_found(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={"plan": [{"target_filename": "Show.S01E02.2160p.mkv"}]},
        ),
        confirm_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda *_args, **_kwargs: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert relocator.relocate_calls == ["task-1"]
    assert relocator.confirm_calls == [
        {"task_id": "task-1", "plan": {"plan": [{"target_filename": "Show.S01E02.2160p.mkv"}]}}
    ]
    assert mgr.update_calls == []


def test_auto_relocate_skips_confirm_when_no_conflicts(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda *_args, **_kwargs: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert relocator.relocate_calls == ["task-1"]
    assert relocator.confirm_calls == []
    assert mgr.update_calls == []


def test_auto_relocate_starts_named_daemon_thread(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    RecordingThread.created = []
    monkeypatch.setattr(threading, "Thread", RecordingThread)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert len(RecordingThread.created) == 1
    created = RecordingThread.created[0]
    assert created.started is True
    assert created.extra["daemon"] is True
    assert created.extra["name"] == "relocate-task-1"
    assert callable(created.target)


def test_auto_relocate_relocates_after_recovering_missing_local_path(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path=r"C:\missing\Show",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )
    match_calls = []

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(
            match=lambda payload: match_calls.append(dict(payload)) or ("matched", r"C:\library\Show")
        ),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr("download_manager.os.path.exists", lambda path: False)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert match_calls == [{"title": "Show", "year": 2024, "tmdb_id": 1}]
    assert mgr.update_calls == [
        {"sub_id": "sub-1", "payload": {"local_file_path": r"C:\library\Show"}}
    ]
    assert relocator.relocate_calls == ["task-1"]
    assert relocator.confirm_calls == []


def test_auto_relocate_keeps_relocating_when_matcher_returns_no_folder(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path=r"C:\missing\Show",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda payload: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr("download_manager.os.path.exists", lambda path: False)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert mgr.update_calls == []
    assert relocator.relocate_calls == ["task-1"]


def test_auto_relocate_keeps_relocating_when_matcher_raises(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path=r"C:\missing\Show",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(
            match=lambda payload: (_ for _ in ()).throw(RuntimeError("match failed"))
        ),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr("download_manager.os.path.exists", lambda path: False)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert mgr.update_calls == []
    assert relocator.relocate_calls == ["task-1"]


def test_auto_relocate_runs_two_tasks_on_real_threads_without_serializing(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = BlockingConcurrentRelocator(expected_calls=2)

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda *_args, **_kwargs: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task1 = _make_task(id="task-1")
    task2 = _make_task(id="task-2", downloader_hash="hash-2")

    dm._auto_relocate(task1, sub)
    dm._auto_relocate(task2, sub)

    assert relocator.all_started.wait(1.5) is True
    assert set(relocator.relocate_calls) == {"task-1", "task-2"}
    assert set(relocator.thread_names) == {"relocate-task-1", "relocate-task-2"}

    relocator.release.set()

    assert relocator.all_finished.wait(1.5) is True
    assert relocator.confirm_calls == []
    assert mgr.update_calls == []


def test_auto_relocate_skips_confirm_when_relocator_returns_failure_status(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    mgr = FakeSubscriptionManager(sub)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="failed",
            error="boom",
            action_plan={"plan": []},
        ),
    )

    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda *_args, **_kwargs: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert relocator.relocate_calls == ["task-1"]
    assert relocator.confirm_calls == []
    assert mgr.update_calls == []


def test_auto_relocate_swallows_relocator_exceptions(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        title="Show",
        year=2024,
        tmdb_id=1,
        local_file_path="",
    )
    mgr = FakeSubscriptionManager(sub)

    class ExplodingRelocator:
        def __init__(self):
            self.relocate_calls = []

        async def relocate(self, task):
            self.relocate_calls.append(task.id)
            raise RuntimeError("relocate boom")

    relocator = ExplodingRelocator()
    fake_shared = SimpleNamespace(
        _get_file_relocator=lambda: relocator,
        _get_sub_manager=lambda: mgr,
        media_matcher=SimpleNamespace(match=lambda *_args, **_kwargs: ("missing", "")),
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm._auto_relocate(_make_task(), sub)

    assert relocator.relocate_calls == ["task-1"]
    assert mgr.update_calls == []


def test_sync_progress_triggers_relocate_and_subscription_callback_for_completed_qb(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_qb_progress", lambda current: setattr(current, "status", "completed"))
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "completed"
    assert events == [
        ("relocate", "task-1"),
        ("notify", "task-1"),
        ("save_now", None),
    ]


def test_sync_progress_retries_unknown_qb_task_and_finishes_recovery_flow(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="unknown", channel="qb")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_qb_progress", lambda current: setattr(current, "status", "completed"))
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "completed"
    assert events == [
        ("relocate", "task-1"),
        ("notify", "task-1"),
        ("save_now", None),
    ]


def test_sync_progress_triggers_relocate_without_subscription_callback_for_completed_alist(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="alist", subscription_id=None, subscription_episode=None)
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_alist_progress", lambda current: setattr(current, "status", "completed"))
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "completed"
    assert events == [
        ("relocate", "task-1"),
        ("save_now", None),
    ]


def test_sync_progress_uses_debounced_save_when_status_unchanged(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_qb_progress", lambda current: None)
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert events == [("save_debounced", None)]


def test_sync_progress_uses_debounced_save_when_no_active_tasks(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(status="completed", channel="qb")]

    events = []
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert events == [("save_debounced", None)]


def test_sync_progress_updates_timestamp_and_debounces_for_unknown_channel(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="manual", updated_at="2026-04-24T10:00:00")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.updated_at != "2026-04-24T10:00:00"
    assert task.status == "downloading"
    assert events == [("save_debounced", None)]


def test_sync_progress_saves_now_when_qb_task_becomes_lost(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_qb_progress", lambda current: setattr(current, "status", "lost"))
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "lost"
    assert events == [("save_now", None)]


def test_sync_progress_saves_now_when_alist_task_becomes_unknown(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="alist")
    dm.tasks = [task]

    events = []
    monkeypatch.setattr(dm, "_sync_alist_progress", lambda current: setattr(current, "status", "unknown"))
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "unknown"
    assert events == [("save_now", None)]


def test_sync_progress_retries_unknown_alist_task_until_it_recovers_to_downloading(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="unknown", channel="alist")
    dm.tasks = [task]

    events = []

    def recover(current):
        current.status = "downloading"
        current.phase = "local_sync"
        current.progress = 1.0

    monkeypatch.setattr(dm, "_sync_alist_progress", recover)
    monkeypatch.setattr(dm, "_relocate_to_save_path", lambda current: events.append(("relocate", current.id)))
    monkeypatch.setattr(dm, "_notify_subscription_complete", lambda current: events.append(("notify", current.id)))
    monkeypatch.setattr(dm, "_save_now", lambda: events.append(("save_now", None)))
    monkeypatch.setattr(dm, "_save_debounced", lambda: events.append(("save_debounced", None)))

    dm.sync_progress()

    assert task.status == "downloading"
    assert task.phase == "local_sync"
    assert task.progress == 1.0
    assert events == [("save_now", None)]


def test_relocate_to_save_path_moves_files_and_cleans_empty_sandbox(monkeypatch):
    def run(tmp_dir):
        save_path = tmp_dir / "library" / "Show"
        download_dir = tmp_dir / "downloads" / "task-1"
        moved_file = download_dir / "Show.S01E01.2160p.mkv"
        subtitle_file = download_dir / "Show.S01E01.2160p.srt"
        download_dir.mkdir(parents=True, exist_ok=True)
        moved_file.write_bytes(b"video")
        subtitle_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        task = _make_task(
            status="downloading",
            save_path=str(save_path),
            download_dir=str(download_dir),
        )
        refresh_calls = []
        monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))

        dm._relocate_to_save_path(task)

        assert task.status == "completed"
        assert (save_path / "Show.S01E01.2160p.mkv").read_bytes() == b"video"
        assert (save_path / "Show.S01E01.2160p.srt").exists()
        assert not download_dir.exists()
        assert refresh_calls == [str(save_path)]

    _with_temp_dir("download_manager_relocate_move", run)


def test_relocate_to_save_path_skips_existing_destination_and_keeps_sandbox(monkeypatch):
    def run(tmp_dir):
        save_path = tmp_dir / "library" / "Show"
        download_dir = tmp_dir / "downloads" / "task-1"
        existing_file = save_path / "Show.S01E01.2160p.mkv"
        duplicate_file = download_dir / "Show.S01E01.2160p.mkv"
        save_path.mkdir(parents=True, exist_ok=True)
        download_dir.mkdir(parents=True, exist_ok=True)
        existing_file.write_bytes(b"old")
        duplicate_file.write_bytes(b"new")

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        task = _make_task(
            status="downloading",
            save_path=str(save_path),
            download_dir=str(download_dir),
        )
        refresh_calls = []
        monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))

        dm._relocate_to_save_path(task)

        assert task.status == "downloading"
        assert existing_file.read_bytes() == b"old"
        assert duplicate_file.read_bytes() == b"new"
        assert download_dir.exists()
        assert refresh_calls == []

    _with_temp_dir("download_manager_relocate_skip_duplicate", run)


def test_relocate_to_save_path_records_error_when_move_raises(monkeypatch):
    def run(tmp_dir):
        save_path = tmp_dir / "library" / "Show"
        download_dir = tmp_dir / "downloads" / "task-1"
        broken_file = download_dir / "Show.S01E01.2160p.mkv"
        download_dir.mkdir(parents=True, exist_ok=True)
        broken_file.write_bytes(b"video")

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        task = _make_task(
            status="downloading",
            save_path=str(save_path),
            download_dir=str(download_dir),
        )
        refresh_calls = []
        monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))
        monkeypatch.setattr("download_manager.shutil.move", lambda src, dst: (_ for _ in ()).throw(PermissionError("denied")))

        dm._relocate_to_save_path(task)

        assert task.status == "downloading"
        assert task.error == "转移失败: denied"
        assert broken_file.exists()
        assert refresh_calls == []

    _with_temp_dir("download_manager_relocate_error", run)


def test_relocate_to_save_path_returns_early_without_save_path(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(save_path="", download_dir=r"C:\downloads\task-1", status="downloading")
    refresh_calls = []

    monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))

    dm._relocate_to_save_path(task)

    assert task.status == "downloading"
    assert refresh_calls == []


def test_relocate_to_save_path_returns_early_when_download_dir_missing(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(save_path=r"C:\library\Show", download_dir="", status="downloading")
    refresh_calls = []

    monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))

    dm._relocate_to_save_path(task)

    assert task.status == "downloading"
    assert refresh_calls == []


def test_relocate_to_save_path_returns_early_when_download_dir_is_not_directory(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(save_path=r"C:\library\Show", download_dir=r"C:\downloads\task-1", status="downloading")
    refresh_calls = []

    monkeypatch.setattr(dm, "_trigger_local_refresh", lambda path: refresh_calls.append(path))
    monkeypatch.setattr("download_manager.os.path.isdir", lambda path: False)

    dm._relocate_to_save_path(task)

    assert task.status == "downloading"
    assert refresh_calls == []


def test_trigger_local_refresh_adds_only_new_files_on_real_thread(monkeypatch):
    def run(tmp_dir):
        save_event = threading.Event()
        saved_libraries = []
        existing_path = str(tmp_dir / "library" / "Show" / "Show.S01E01.1080p.mkv")
        new_path = str(tmp_dir / "library" / "Show" / "Show.S01E02.2160p.mkv")

        class FakeConfigManagerForRefresh:
            def load_library(self):
                return [{"file_path": existing_path, "title": "Show"}]

            def save_library(self, library):
                saved_libraries.append(list(library))
                save_event.set()

        fake_config_manager = SimpleNamespace(ConfigManager=FakeConfigManagerForRefresh)
        fake_scanner = SimpleNamespace(
            scan_folder=lambda path: [
                {"file_path": existing_path, "title": "Show"},
                {"file_path": new_path, "title": "Show"},
            ]
        )

        monkeypatch.setitem(sys.modules, "config_manager", fake_config_manager)
        monkeypatch.setitem(sys.modules, "scanner", fake_scanner)

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        dm._trigger_local_refresh(str(tmp_dir / "library" / "Show"))

        assert save_event.wait(1.5) is True
        assert len(saved_libraries) == 1
        assert saved_libraries[0] == [
            {"file_path": existing_path, "title": "Show"},
            {"file_path": new_path, "title": "Show"},
        ]

    _with_temp_dir("download_manager_local_refresh_thread", run)


def test_trigger_local_refresh_skips_when_library_is_empty(monkeypatch):
    def run(tmp_dir):
        save_event = threading.Event()

        class FakeConfigManagerForRefresh:
            def load_library(self):
                return []

            def save_library(self, library):
                save_event.set()

        fake_config_manager = SimpleNamespace(ConfigManager=FakeConfigManagerForRefresh)
        fake_scanner = SimpleNamespace(scan_folder=lambda path: [{"file_path": "x"}])

        monkeypatch.setitem(sys.modules, "config_manager", fake_config_manager)
        monkeypatch.setitem(sys.modules, "scanner", fake_scanner)

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        dm._trigger_local_refresh(str(tmp_dir / "library" / "Show"))

        assert save_event.wait(0.3) is False

    _with_temp_dir("download_manager_local_refresh_empty_library", run)


def test_trigger_local_refresh_skips_when_scan_returns_empty(monkeypatch):
    def run(tmp_dir):
        save_event = threading.Event()

        class FakeConfigManagerForRefresh:
            def load_library(self):
                return [{"file_path": "existing"}]

            def save_library(self, library):
                save_event.set()

        fake_config_manager = SimpleNamespace(ConfigManager=FakeConfigManagerForRefresh)
        fake_scanner = SimpleNamespace(scan_folder=lambda path: [])

        monkeypatch.setitem(sys.modules, "config_manager", fake_config_manager)
        monkeypatch.setitem(sys.modules, "scanner", fake_scanner)

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        dm._trigger_local_refresh(str(tmp_dir / "library" / "Show"))

        assert save_event.wait(0.3) is False

    _with_temp_dir("download_manager_local_refresh_empty_scan", run)


def test_trigger_local_refresh_skips_when_no_new_files(monkeypatch):
    def run(tmp_dir):
        save_event = threading.Event()
        existing_path = str(tmp_dir / "library" / "Show" / "Show.S01E01.1080p.mkv")

        class FakeConfigManagerForRefresh:
            def load_library(self):
                return [{"file_path": existing_path, "title": "Show"}]

            def save_library(self, library):
                save_event.set()

        fake_config_manager = SimpleNamespace(ConfigManager=FakeConfigManagerForRefresh)
        fake_scanner = SimpleNamespace(
            scan_folder=lambda path: [{"file_path": existing_path, "title": "Show"}]
        )

        monkeypatch.setitem(sys.modules, "config_manager", fake_config_manager)
        monkeypatch.setitem(sys.modules, "scanner", fake_scanner)

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
        dm._trigger_local_refresh(str(tmp_dir / "library" / "Show"))

        assert save_event.wait(0.3) is False

    _with_temp_dir("download_manager_local_refresh_no_new_files", run)


def test_write_json_and_load_round_trip_tasks_from_disk():
    def run(tmp_dir):
        dm = DownloadManager(qb_client=None, alist_client=None, base_path=str(tmp_dir))
        task = _make_task(
            id="task-persist",
            status="archived",
            progress=1.0,
            phase="local_sync",
            error="",
            created_at="2026-04-24T10:00:00",
            updated_at="2026-04-24T10:05:00",
        )
        dm.tasks = [task]

        dm._write_json()

        reloaded = DownloadManager(qb_client=None, alist_client=None, base_path=str(tmp_dir))
        loaded = reloaded.get_task("task-persist")

        assert loaded is not None
        assert loaded.status == "archived"
        assert loaded.progress == 1.0
        assert loaded.phase == "local_sync"
        assert loaded.save_path == task.save_path
        assert loaded.download_dir == task.download_dir

    _with_temp_dir("download_manager_persist_round_trip", run)


def test_notify_subscription_complete_marks_upgrade_movie_completed(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=False,
        purpose="upgrade",
        type="movie",
    )
    mgr = FakeSubscriptionManager(sub)
    notifications = []

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(
        add_notification=lambda *_args: notifications.append(_args[2:])
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    dm._notify_subscription_complete(_make_task(subscription_episode=None, category_hint="movie"))

    assert mgr.download_complete_calls == [
        {
            "subscription_id": "sub-1",
            "episode": None,
            "info_hash": "hash-1",
            "title": "Show",
            "quality_tag": "",
            "source": "movie",
            "channel": "qb",
            "task_id": "task-1",
        }
    ]
    assert mgr.update_calls == [
        {
            "sub_id": "sub-1",
            "payload": {"state": "completed", "note": "洗版完成，已下载更高质量版本"},
        }
    ]
    assert notifications == [("upgrade_complete", "洗版完成，已下载更高质量版本")]


def test_notify_subscription_complete_uses_download_url_when_hash_missing(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=False,
        purpose="follow",
        type="tv",
    )
    mgr = FakeSubscriptionManager(sub)
    notifications = []

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(
        add_notification=lambda *_args: notifications.append(_args[2:])
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    dm._notify_subscription_complete(
        _make_task(downloader_hash="", download_url="magnet:?xt=urn:btih:fallback")
    )

    assert mgr.download_complete_calls == [
        {
            "subscription_id": "sub-1",
            "episode": 2,
            "info_hash": "magnet:?xt=urn:btih:fallback",
            "title": "Show",
            "quality_tag": "",
            "source": "tv",
            "channel": "qb",
            "task_id": "task-1",
        }
    ]
    assert notifications == [("download_complete", "下载完成: Show")]


def test_notify_subscription_complete_uses_unknown_source_when_category_hint_missing(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=False,
        purpose="follow",
        type="movie",
    )
    mgr = FakeSubscriptionManager(sub)

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(add_notification=lambda *_args: None)

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    dm._notify_subscription_complete(_make_task(category_hint=""))

    assert mgr.download_complete_calls[0]["source"] == "unknown"


def test_notify_subscription_complete_skips_auto_relocate_without_save_path(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=True,
        purpose="follow",
        type="tv",
    )
    mgr = FakeSubscriptionManager(sub)
    auto_relocate_calls = []

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(add_notification=lambda *_args: None)

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    monkeypatch.setattr(
        dm,
        "_auto_relocate",
        lambda task, sub_obj=None: auto_relocate_calls.append(
            {"task_id": task.id, "sub_id": getattr(sub_obj, "id", "")}
        ),
    )

    dm._notify_subscription_complete(_make_task(save_path=""))

    assert auto_relocate_calls == []


def test_notify_subscription_complete_swallows_notification_errors(monkeypatch):
    sub = SimpleNamespace(
        id="sub-1",
        best_version=False,
        purpose="follow",
        type="tv",
    )
    mgr = FakeSubscriptionManager(sub)

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(
        add_notification=lambda *_args: (_ for _ in ()).throw(RuntimeError("notify boom"))
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    dm._notify_subscription_complete(_make_task())

    assert len(mgr.download_complete_calls) == 1


def test_notify_subscription_complete_without_subscription_still_sends_download_complete(monkeypatch):
    mgr = FakeSubscriptionManager(sub=None)
    notifications = []
    auto_relocate_calls = []

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: mgr)
    fake_notification_service = SimpleNamespace(
        add_notification=lambda *_args: notifications.append(_args[2:])
    )

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    monkeypatch.setattr(
        dm,
        "_auto_relocate",
        lambda task, sub_obj=None: auto_relocate_calls.append(
            {"task_id": task.id, "sub_id": getattr(sub_obj, "id", "")}
        ),
    )

    dm._notify_subscription_complete(_make_task(subscription_id="sub-missing"))

    assert len(mgr.download_complete_calls) == 1
    assert mgr.update_calls == []
    assert notifications == [("download_complete", "下载完成: Show")]
    assert auto_relocate_calls == []


def test_notify_subscription_complete_swallows_manager_errors(monkeypatch):
    class BrokenSubscriptionManager:
        def on_download_complete(self, **kwargs):
            raise RuntimeError("manager boom")

    fake_shared = SimpleNamespace(_get_sub_manager=lambda: BrokenSubscriptionManager())
    fake_notification_service = SimpleNamespace(add_notification=lambda *_args: None)

    monkeypatch.setitem(sys.modules, "shared", fake_shared)
    monkeypatch.setitem(sys.modules, "notification_service", fake_notification_service)

    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    dm._notify_subscription_complete(_make_task())


def test_get_qb_hashes_returns_empty_when_login_fails():
    qb = FakeQBClient([], login_result=False)
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")

    assert dm._get_qb_hashes() == set()


def test_get_qb_hashes_returns_empty_when_info_status_is_not_200(monkeypatch):
    qb = FakeQBClient([])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")

    monkeypatch.setattr(qb.session, "get", lambda url, timeout=None: FakeResponse(500, {}))

    assert dm._get_qb_hashes() == set()


def test_get_qb_hashes_returns_empty_when_payload_is_invalid(monkeypatch):
    qb = FakeQBClient([])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")

    class BrokenResponse:
        status_code = 200

        def json(self):
            raise ValueError("bad qb hashes payload")

    monkeypatch.setattr(qb.session, "get", lambda url, timeout=None: BrokenResponse())

    assert dm._get_qb_hashes() == set()


def test_push_to_qb_returns_new_hash_when_detected(monkeypatch):
    qb = FakeSubmitQBClient(add_result=True)
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(save_path=r"C:\library\Show")
    hash_sets = [set(), {"hash-new"}]

    monkeypatch.setattr(dm, "_get_qb_hashes", lambda: hash_sets.pop(0))
    monkeypatch.setattr("download_manager.time.sleep", lambda _seconds: None)

    success, hash_or_error = dm._push_to_qb(task)

    assert success is True
    assert hash_or_error == "hash-new"
    assert qb.calls == [{"download_url": "magnet:?xt=urn:btih:123", "save_path": r"C:\library\Show"}]


def test_push_to_qb_returns_empty_hash_when_added_but_not_detected(monkeypatch):
    qb = FakeSubmitQBClient(add_result=True)
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(save_path=r"C:\library\Show")

    monkeypatch.setattr(dm, "_get_qb_hashes", lambda: set())
    monkeypatch.setattr("download_manager.time.sleep", lambda _seconds: None)

    success, hash_or_error = dm._push_to_qb(task)

    assert success is True
    assert hash_or_error == ""


def test_push_to_qb_returns_error_when_add_torrent_fails():
    qb = FakeSubmitQBClient(add_result=False)
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task()

    success, hash_or_error = dm._push_to_qb(task)

    assert success is False
    assert "qBittorrent 推送失败" in hash_or_error


def test_push_to_qb_returns_exception_message_when_add_torrent_raises():
    qb = FakeSubmitQBClient(add_exception=RuntimeError("qb add boom"))
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task()

    success, hash_or_error = dm._push_to_qb(task)

    assert success is False
    assert hash_or_error == "qb add boom"


def test_push_to_alist_returns_real_task_id_when_transfer_provides_one():
    alist = FakeSubmitAlistClient(transfer_result=(True, "task-real-123"))
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(id="task-123", download_dir=r"C:\downloads\task-123")

    success, task_id_or_error = dm._push_to_alist(task)

    assert success is True
    assert task_id_or_error == "task-real-123"
    assert alist.calls == [
        {"download_url": "magnet:?xt=urn:btih:123", "download_dir": r"C:\downloads\task-123"}
    ]


def test_push_to_alist_falls_back_to_legacy_marker_when_task_id_missing():
    alist = FakeSubmitAlistClient(transfer_result=(True, ""))
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(id="task-123", download_dir=r"C:\downloads\task-123")

    success, task_id_or_error = dm._push_to_alist(task)

    assert success is True
    assert task_id_or_error == "alist_task-123"


def test_push_to_alist_returns_error_when_transfer_fails():
    alist = FakeSubmitAlistClient(transfer_result=False)
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task()

    success, task_id_or_error = dm._push_to_alist(task)

    assert success is False
    assert task_id_or_error == "Alist 所有工具均失败"


def test_push_to_alist_returns_exception_message_when_transfer_raises():
    alist = FakeSubmitAlistClient(transfer_exception=RuntimeError("alist boom"))
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task()

    success, task_id_or_error = dm._push_to_alist(task)

    assert success is False
    assert task_id_or_error == "alist boom"


def test_sync_qb_progress_marks_completed_for_pausedup_state():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.56,
                        "dlspeed": 2048,
                        "eta": 120,
                        "state": "pausedUP",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.speed == ""
    assert task.eta == ""
    assert qb.session.calls[0]["params"] == {"hashes": "hash-1"}


def test_sync_qb_progress_returns_early_without_client_or_hash():
    dm_no_client = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task_no_client = _make_task(status="downloading", channel="qb", downloader_hash="hash-1")

    dm_no_client._sync_qb_progress(task_no_client)

    assert task_no_client.status == "downloading"
    assert task_no_client.progress == 0.0

    qb = FakeQBClient([])
    dm_no_hash = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task_no_hash = _make_task(status="downloading", channel="qb", downloader_hash="")

    dm_no_hash._sync_qb_progress(task_no_hash)

    assert task_no_hash.status == "downloading"
    assert qb.session.calls == []


def test_sync_qb_progress_marks_lost_when_hash_missing():
    qb = FakeQBClient([FakeResponse(200, [])])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "lost"
    assert task.error == "种子在 qBittorrent 中不存在"


def test_sync_qb_progress_marks_completed_for_stalledup_state():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.82,
                        "dlspeed": 0,
                        "eta": 0,
                        "state": "stalledUP",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.speed == ""
    assert task.eta == ""


def test_sync_qb_progress_marks_completed_when_progress_reaches_one():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 1.0,
                        "dlspeed": 8192,
                        "eta": 30,
                        "state": "downloading",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.speed == ""
    assert task.eta == ""


def test_sync_qb_progress_formats_speed_in_mb_and_clears_huge_eta():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.42,
                        "dlspeed": 3 * 1024 * 1024,
                        "eta": 8640000,
                        "state": "downloading",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "downloading"
    assert task.speed == "3.0 MB/s"
    assert task.eta == ""


def test_sync_qb_progress_marks_unknown_on_login_failure():
    qb = FakeQBClient([], login_result=False)
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "unknown"


def test_sync_qb_progress_keeps_downloading_for_missingfiles_state():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.37,
                        "dlspeed": 4096,
                        "eta": 90,
                        "state": "missingFiles",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "downloading"
    assert task.progress == 0.37
    assert task.speed == "4 KB/s"
    assert task.eta == "00:01:30"


def test_sync_qb_progress_recovers_unknown_task_to_downloading_for_missingfiles_state():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.37,
                        "dlspeed": 4096,
                        "eta": 90,
                        "state": "missingFiles",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="unknown", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "downloading"
    assert task.progress == 0.37
    assert task.speed == "4 KB/s"
    assert task.eta == "00:01:30"


def test_sync_qb_progress_recovers_unknown_task_to_downloading_for_forceddl_state():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.4356,
                        "dlspeed": 0,
                        "eta": 0,
                        "state": "forcedDL",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="unknown", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "downloading"
    assert task.progress == 0.4356
    assert task.speed == ""
    assert task.eta == ""


def test_sync_qb_progress_marks_unknown_when_info_request_fails():
    qb = FakeQBClient([FakeResponse(500, {})])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "unknown"


def test_sync_qb_progress_marks_unknown_when_info_request_times_out(monkeypatch):
    qb = FakeQBClient([])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    def fake_get(url, params=None, timeout=None):
        raise requests.Timeout("qb timeout")

    monkeypatch.setattr(qb.session, "get", fake_get)

    dm._sync_qb_progress(task)

    assert task.status == "unknown"


def test_sync_qb_progress_marks_unknown_when_payload_is_invalid(monkeypatch):
    qb = FakeQBClient([])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    class BrokenResponse:
        status_code = 200

        def json(self):
            raise ValueError("bad qb payload")

    monkeypatch.setattr(qb.session, "get", lambda url, params=None, timeout=None: BrokenResponse())

    dm._sync_qb_progress(task)

    assert task.status == "unknown"


def test_sync_qb_progress_skips_query_when_task_already_organized():
    qb = FakeQBClient(
        [
            FakeResponse(
                200,
                [
                    {
                        "progress": 0.91,
                        "dlspeed": 1024,
                        "eta": 30,
                        "state": "downloading",
                    }
                ],
            )
        ]
    )
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb", organized=True)

    dm._sync_qb_progress(task)

    assert task.status == "downloading"
    assert task.progress == 0.0
    assert qb.session.calls == []


def test_sync_alist_progress_marks_completed_when_done_and_local_files_exist(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: True)

    dm._sync_alist_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.phase == ""


def test_sync_alist_progress_uses_real_task_id_info_before_scanning_lists(monkeypatch):
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(
        status="downloading",
        channel="alist",
        downloader_hash="task-real-123",
    )
    post_calls = []

    def fake_post(url, headers=None, params=None, timeout=None):
        post_calls.append({"url": url, "params": params})
        return FakeResponse(
            200,
            {"data": [{"id": "task-real-123", "state": "succeeded", "progress": 100}]},
        )

    def fake_get(url, headers=None, timeout=None):
        raise AssertionError("should not scan list when task info succeeds")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: True)

    dm._sync_alist_progress(task)

    assert post_calls == [
        {
            "url": "http://alist/api/task/offline_download/info",
            "params": {"tid": "task-real-123"},
        }
    ]
    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.phase == ""


def test_sync_alist_progress_falls_back_to_list_scan_when_real_task_info_missing(monkeypatch):
    responses = [
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123", "state": 1, "progress": 45}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(
        status="downloading",
        channel="alist",
        downloader_hash="task-real-123",
    )

    def fake_post(url, headers=None, params=None, timeout=None):
        return FakeResponse(200, {"data": []})

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "cloud_download"
    assert task.progress == 0.45


def test_sync_alist_progress_skips_task_info_for_legacy_alist_marker(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(
        status="downloading",
        channel="alist",
        downloader_hash="alist_task-123",
    )

    def fake_post(url, headers=None, params=None, timeout=None):
        raise AssertionError("legacy marker should not hit task info")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: True)

    dm._sync_alist_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0


def test_sync_alist_progress_returns_early_without_client():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.progress == 0.0


def test_sync_alist_progress_keeps_local_sync_when_done_but_local_files_missing(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: False)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "local_sync"
    assert task.progress == 0.8


def test_sync_alist_progress_marks_lost_when_task_missing(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": []}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "lost"
    assert task.error == "Alist 中未找到对应任务"


def test_sync_alist_progress_keeps_cloud_download_for_undone_task(monkeypatch):
    responses = [
        FakeResponse(
            200,
            {"data": [{"name": "magnet:?xt=urn:btih:123", "state": 1, "progress": 45}]},
        )
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "cloud_download"
    assert task.progress == 0.45


def test_sync_alist_progress_uses_zero_progress_when_undone_progress_missing(monkeypatch):
    responses = [
        FakeResponse(
            200,
            {"data": [{"name": "magnet:?xt=urn:btih:123", "state": 1, "progress": 0}]},
        )
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "cloud_download"
    assert task.progress == 0.0


def test_sync_alist_progress_switches_to_local_sync_for_completed_undone_task(monkeypatch):
    responses = [
        FakeResponse(
            200,
            {"data": [{"name": "magnet:?xt=urn:btih:123", "state": "succeeded", "progress": 100}]},
        )
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "local_sync"
    assert task.progress == 1.0


def test_sync_alist_progress_keeps_cloud_download_for_missing_state(monkeypatch):
    responses = [
        FakeResponse(
            200,
            {"data": [{"name": "magnet:?xt=urn:btih:123", "progress": 12}]},
        )
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "cloud_download"
    assert task.progress == 0.12


def test_sync_alist_progress_marks_unknown_when_undone_request_fails(monkeypatch):
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: FakeResponse(500, {}))

    dm._sync_alist_progress(task)

    assert task.status == "unknown"


def test_sync_alist_progress_marks_unknown_when_undone_request_times_out(monkeypatch):
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        raise requests.Timeout("alist timeout")

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "unknown"


def test_sync_alist_progress_marks_lost_when_done_request_fails_after_undone_empty(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(500, {}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "lost"
    assert task.error == "Alist 中未找到对应任务"


def test_sync_alist_progress_marks_unknown_when_done_request_raises_after_undone_empty(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        RuntimeError("done boom"),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "unknown"


def test_sync_alist_progress_marks_unknown_when_done_payload_is_invalid(monkeypatch):
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    class BrokenResponse:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            raise ValueError("bad alist payload")

    responses = [
        FakeResponse(200, {"data": []}),
        BrokenResponse(200),
    ]

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "unknown"


def test_sync_alist_progress_marks_lost_when_done_list_has_only_non_matching_tasks(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "other-task"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    dm._sync_alist_progress(task)

    assert task.status == "lost"
    assert task.error == "Alist 中未找到对应任务"


def test_sync_alist_progress_matches_done_task_by_download_url_file_name(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "[ANK-Raws] 妖精的旋律 エルフェンリート Elfen Lied BDBOX"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(
        status="downloading",
        channel="alist",
        id="499b0bd2",
        downloader_hash="alist_499b0bd2",
        download_url="http://127.0.0.1:9696/7/download?file=%5BANK-Raws%5D+%E5%A6%96%E7%B2%BE%E7%9A%84%E6%97%8B%E5%BE%8B+%E3%82%A8%E3%83%AB%E3%83%95%E3%82%A7%E3%83%B3%E3%83%AA%E3%83%BC%E3%83%88+Elfen+Lied+BDBOX",
    )

    def fake_get(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: True)

    dm._sync_alist_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0


def test_on_startup_marks_pending_task_failed_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    pending_task = _make_task(status="pending", downloader_hash="")
    downloading_task = _make_task(id="task-2", status="downloading", downloader_hash="hash-2")
    dm.tasks = [pending_task, downloading_task]

    reconciled = []
    save_calls = []
    monkeypatch.setattr(dm, "_reconcile_task", lambda task: reconciled.append(task.id))
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.on_startup()

    assert pending_task.status == "failed"
    assert pending_task.error == "服务重启时任务未完成推送"
    assert reconciled == ["task-2"]
    assert save_calls == ["saved"]


def test_on_startup_reconciles_alist_downloading_task_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(id="task-alist", status="downloading", channel="alist", downloader_hash="alist_1")
    dm.tasks = [task]

    reconciled = []
    save_calls = []
    monkeypatch.setattr(dm, "_reconcile_task", lambda current: reconciled.append((current.id, current.channel)))
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.on_startup()

    assert reconciled == [("task-alist", "alist")]
    assert save_calls == ["saved"]


def test_reconcile_task_marks_qb_task_lost_when_hash_missing(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb", downloader_hash="hash-1")

    monkeypatch.setattr(dm, "_get_qb_hashes", lambda: {"other-hash"})

    dm._reconcile_task(task)

    assert task.status == "lost"
    assert task.error == "qBittorrent 中未找到该种子"


def test_reconcile_task_marks_task_lost_when_hash_missing():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb", downloader_hash="")

    dm._reconcile_task(task)

    assert task.status == "lost"
    assert task.error == "无下载器 Hash，无法对账"


def test_reconcile_task_keeps_qb_task_downloading_when_hash_exists(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb", downloader_hash="hash-1")

    monkeypatch.setattr(dm, "_get_qb_hashes", lambda: {"hash-1"})

    dm._reconcile_task(task)

    assert task.status == "downloading"
    assert task.error == ""


def test_reconcile_task_keeps_alist_task_downloading():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="alist", downloader_hash="alist_1")

    dm._reconcile_task(task)

    assert task.status == "downloading"
    assert task.error == ""


def test_recommend_channel_prefers_qb_for_good_seeders_and_small_size():
    dm = DownloadManager(qb_client=object(), alist_client=object(), base_path=".")

    assert dm.recommend_channel(seeders=5, size_gb=50) == "qb"


def test_recommend_channel_prefers_alist_for_low_seeders():
    dm = DownloadManager(qb_client=object(), alist_client=object(), base_path=".")

    assert dm.recommend_channel(seeders=4, size_gb=10) == "alist"


def test_recommend_channel_prefers_alist_for_large_size():
    dm = DownloadManager(qb_client=object(), alist_client=object(), base_path=".")

    assert dm.recommend_channel(seeders=10, size_gb=51) == "alist"


def test_recommend_channel_returns_only_configured_channel():
    dm_qb_only = DownloadManager(qb_client=object(), alist_client=None, base_path=".")
    dm_alist_only = DownloadManager(qb_client=None, alist_client=object(), base_path=".")

    assert dm_qb_only.recommend_channel(seeders=0, size_gb=999) == "qb"
    assert dm_alist_only.recommend_channel(seeders=999, size_gb=1) == "alist"


def test_recommend_channel_defaults_to_qb_when_no_channel_configured():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")

    assert dm.recommend_channel(seeders=0, size_gb=999) == "qb"


def test_get_tasks_returns_items_sorted_by_created_at_desc():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    older = _make_task(id="task-old", status="completed", created_at="2026-04-24T10:00:00")
    newer = _make_task(id="task-new", status="downloading", created_at="2026-04-24T11:00:00")
    dm.tasks = [older, newer]

    tasks = dm.get_tasks()

    assert [task.id for task in tasks] == ["task-new", "task-old"]


def test_get_tasks_filters_by_status_before_sorting():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    pending = _make_task(id="task-pending", status="pending", created_at="2026-04-24T09:00:00")
    failed = _make_task(id="task-failed", status="failed", created_at="2026-04-24T12:00:00")
    archived = _make_task(id="task-archived", status="failed", created_at="2026-04-24T10:00:00")
    dm.tasks = [pending, archived, failed]

    tasks = dm.get_tasks(status="failed")

    assert [task.id for task in tasks] == ["task-failed", "task-archived"]


def test_get_tasks_sorts_empty_created_at_last():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    missing_time = _make_task(id="task-empty", status="completed", created_at="")
    dated = _make_task(id="task-dated", status="completed", created_at="2026-04-24T11:00:00")
    dm.tasks = [missing_time, dated]

    tasks = dm.get_tasks()

    assert [task.id for task in tasks] == ["task-dated", "task-empty"]


def test_update_status_updates_task_error_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(id="task-1", status="downloading", error="")
    dm.tasks = [task]
    save_calls = []
    now_values = iter(["2026-04-26T11:00:00"])

    monkeypatch.setattr("download_manager.datetime", SimpleNamespace(now=lambda: SimpleNamespace(isoformat=lambda: next(now_values))))
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.update_status("task-1", "failed", "boom")

    assert task.status == "failed"
    assert task.error == "boom"
    assert task.updated_at == "2026-04-26T11:00:00"
    assert save_calls == ["saved"]


def test_update_status_still_saves_when_task_missing(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-1", status="downloading", error="")]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.update_status("task-missing", "failed", "boom")

    assert dm.tasks[0].status == "downloading"
    assert save_calls == ["saved"]


def test_archive_task_marks_organized_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(id="task-1", status="completed", organized=False)
    dm.tasks = [task]
    save_calls = []
    now_values = iter(["2026-04-26T12:00:00"])

    monkeypatch.setattr("download_manager.datetime", SimpleNamespace(now=lambda: SimpleNamespace(isoformat=lambda: next(now_values))))
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.archive_task("task-1", organized=True)

    assert task.status == "archived"
    assert task.organized is True
    assert task.updated_at == "2026-04-26T12:00:00"
    assert save_calls == ["saved"]


def test_archive_task_still_saves_when_task_missing(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-1", status="completed", organized=False)]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm.archive_task("task-missing", organized=True)

    assert dm.tasks[0].status == "completed"
    assert dm.tasks[0].organized is False
    assert save_calls == ["saved"]


def test_delete_task_removes_existing_task_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    keep = _make_task(id="task-keep")
    remove = _make_task(id="task-remove")
    dm.tasks = [keep, remove]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    removed = dm.delete_task("task-remove")

    assert removed is True
    assert [task.id for task in dm.tasks] == ["task-keep"]
    assert save_calls == ["saved"]


def test_delete_task_skips_save_when_task_missing(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-keep")]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    removed = dm.delete_task("task-missing")

    assert removed is False
    assert [task.id for task in dm.tasks] == ["task-keep"]
    assert save_calls == []


def test_delete_tasks_removes_multiple_tasks_and_saves(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    keep = _make_task(id="task-keep")
    remove1 = _make_task(id="task-remove-1")
    remove2 = _make_task(id="task-remove-2")
    dm.tasks = [keep, remove1, remove2]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    removed = dm.delete_tasks(["task-remove-1", "task-remove-2"])

    assert removed == 2
    assert [task.id for task in dm.tasks] == ["task-keep"]
    assert save_calls == ["saved"]


def test_delete_tasks_skips_save_when_nothing_removed(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-keep")]
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    removed = dm.delete_tasks(["task-missing"])

    assert removed == 0
    assert [task.id for task in dm.tasks] == ["task-keep"]
    assert save_calls == []


def test_get_task_returns_matching_task():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    task = _make_task(id="task-1")
    dm.tasks = [task]

    assert dm.get_task("task-1") is task


def test_get_task_returns_none_when_missing():
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-1")]

    assert dm.get_task("task-missing") is None


def test_save_debounced_triggers_save_after_interval(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    save_calls = []

    dm._last_save_time = 10
    monkeypatch.setattr("download_manager.time.time", lambda: 41)
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm._save_debounced()

    assert dm._dirty is True
    assert save_calls == ["saved"]


def test_save_debounced_keeps_dirty_without_save_before_interval(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    save_calls = []

    dm._last_save_time = 10
    monkeypatch.setattr("download_manager.time.time", lambda: 20)
    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm._save_debounced()

    assert dm._dirty is True
    assert save_calls == []


def test_flush_saves_only_when_dirty(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    save_calls = []

    monkeypatch.setattr(dm, "_save_now", lambda: save_calls.append("saved"))

    dm._dirty = False
    dm.flush()
    dm._dirty = True
    dm.flush()

    assert save_calls == ["saved"]


def test_check_local_files_exist_detects_video_file():
    def run(tmp_dir):
        target = tmp_dir / "library"
        target.mkdir()
        (target / "Show.S01E01.mkv").write_bytes(b"video")
        (target / "note.txt").write_text("ignore", encoding="utf-8")

        assert DownloadManager._check_local_files_exist(str(target)) is True

    _with_temp_dir("download_manager_check_local_video", run)


def test_check_local_files_exist_returns_false_for_non_video_files():
    def run(tmp_dir):
        target = tmp_dir / "library"
        target.mkdir()
        (target / "note.txt").write_text("ignore", encoding="utf-8")
        (target / "poster.jpg").write_bytes(b"image")

        assert DownloadManager._check_local_files_exist(str(target)) is False

    _with_temp_dir("download_manager_check_local_non_video", run)


def test_load_recovers_with_empty_tasks_when_json_is_invalid():
    def run(tmp_dir):
        task_file = tmp_dir / "download_tasks.json"
        task_file.write_text("{not-json", encoding="utf-8")

        dm = DownloadManager(qb_client=None, alist_client=None, base_path=str(tmp_dir))

        assert dm.tasks == []

    _with_temp_dir("download_manager_load_invalid_json", run)


def test_load_uses_empty_tasks_when_file_missing():
    def run(tmp_dir):
        dm = DownloadManager(qb_client=None, alist_client=None, base_path=str(tmp_dir))

        assert dm.tasks == []

    _with_temp_dir("download_manager_load_missing_file", run)


def test_write_json_swallows_file_errors(monkeypatch):
    dm = DownloadManager(qb_client=None, alist_client=None, base_path=".")
    dm.tasks = [_make_task(id="task-1")]

    monkeypatch.setattr(
        "builtins.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    dm._write_json()
