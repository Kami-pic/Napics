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


class FakeAlistClient:
    def __init__(self):
        self.api_url = "http://alist"
        self.headers = {"Authorization": "token"}


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
    return DownloadTask(**data)


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


def test_sync_qb_progress_marks_unknown_when_info_request_fails():
    qb = FakeQBClient([FakeResponse(500, {})])
    dm = DownloadManager(qb_client=qb, alist_client=None, base_path=".")
    task = _make_task(status="downloading", channel="qb")

    dm._sync_qb_progress(task)

    assert task.status == "unknown"


def test_sync_alist_progress_marks_completed_when_done_and_local_files_exist(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_post(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(dm, "_check_local_files_exist", lambda directory: True)

    dm._sync_alist_progress(task)

    assert task.status == "completed"
    assert task.progress == 1.0
    assert task.phase == ""


def test_sync_alist_progress_keeps_local_sync_when_done_but_local_files_missing(monkeypatch):
    responses = [
        FakeResponse(200, {"data": []}),
        FakeResponse(200, {"data": [{"name": "magnet:?xt=urn:btih:123"}]}),
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_post(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
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

    def fake_post(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)

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

    def fake_post(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "cloud_download"
    assert task.progress == 0.45


def test_sync_alist_progress_switches_to_local_sync_for_completed_undone_task(monkeypatch):
    responses = [
        FakeResponse(
            200,
            {"data": [{"name": "magnet:?xt=urn:btih:123", "state": 2, "progress": 100}]},
        )
    ]
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    def fake_post(url, headers=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)

    dm._sync_alist_progress(task)

    assert task.status == "downloading"
    assert task.phase == "local_sync"
    assert task.progress == 1.0


def test_sync_alist_progress_marks_unknown_when_undone_request_fails(monkeypatch):
    alist = FakeAlistClient()
    dm = DownloadManager(qb_client=None, alist_client=alist, base_path=".")
    task = _make_task(status="downloading", channel="alist")

    monkeypatch.setattr(requests, "post", lambda url, headers=None, timeout=None: FakeResponse(500, {}))

    dm._sync_alist_progress(task)

    assert task.status == "unknown"


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
