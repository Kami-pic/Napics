"""routes.relocate 路由行为保护测试。"""

import asyncio
from types import SimpleNamespace

from download_manager import DownloadTask
from file_relocator import CoexistPair, RelocateResult
from routes import relocate
from test_support.route_response_snapshot import RouteResponseSnapshot


class FakeDownloadManager:
    def __init__(self, task):
        self.task = task
        self.archive_calls = []

    def get_task(self, task_id):
        if self.task and task_id == self.task.id:
            return self.task
        return None

    def archive_task(self, task_id, organized=False):
        self.archive_calls.append({"task_id": task_id, "organized": organized})


class FakeQBClient:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def get_torrent_files(self, downloader_hash):
        self.calls.append(downloader_hash)
        return list(self.files)


class FakeRelocator:
    def __init__(self, relocate_result=None, execute_result=None):
        self.relocate_result = relocate_result
        self.execute_result = execute_result
        self.relocate_calls = []
        self.confirm_calls = []
        self.archive_calls = []
        self.recycle_calls = []

    async def relocate(self, task, new_files_whitelist=None):
        self.relocate_calls.append(
            {"task_id": task.id, "whitelist": list(new_files_whitelist) if new_files_whitelist else None}
        )
        return self.relocate_result

    async def confirm_replace(self, task, plan):
        self.confirm_calls.append({"task_id": task.id, "plan": dict(plan)})
        return self.execute_result

    async def archive_both(self, task, conflicts):
        self.archive_calls.append({"task_id": task.id, "conflicts": list(conflicts)})
        return self.execute_result

    def _recycle_old_files(self, pair, task_id):
        self.recycle_calls.append({"task_id": task_id, "old_file": pair.old_file})
        return True


def _make_task(**overrides):
    data = {
        "id": "task-1",
        "media_name": "Show",
        "save_path": r"C:\library\Show",
        "downloader_hash": "hash-1",
    }
    data.update(overrides)
    return DownloadTask(**data)


def test_organize_dry_run_returns_tree_snapshot_and_whitelist(monkeypatch):
    task = _make_task()
    dm = FakeDownloadManager(task)
    qb = FakeQBClient(
        [
            {"name": "[Group] Show S01 2160p/Show.S01E02.2160p.mkv", "size_bytes": 1234},
            {"name": "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass", "size_bytes": 56},
        ]
    )
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={
                "plan": [
                    {
                        "source_path": r"C:\library\Show\[Group] Show S01 2160p\Show.S01E02.2160p.mkv",
                        "original_filename": "Show.S01E02.2160p.mkv",
                        "target_filename": "Show.S01E02.2160p.mkv",
                        "target_season_dir": "Season 01",
                        "mapped": {"season": 1, "episode": 2},
                        "actions": ["write_episode_nfo"],
                    }
                ]
            },
            coexist_pairs=[
                CoexistPair(
                    new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
                    old_file=r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv",
                    old_size_gb=1.5,
                    category="video",
                    is_folder=False,
                )
            ],
        )
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": qb})
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: False)
    monkeypatch.setattr(relocate, "config_m", SimpleNamespace(config=SimpleNamespace(nas_paths=[])))

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id=task.id)))
    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert relocator.relocate_calls == [
        {
            "task_id": "task-1",
            "whitelist": [
                "[Group] Show S01 2160p/Show.S01E02.2160p.mkv",
                "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass",
            ],
        }
    ]
    assert qb.calls == ["hash-1"]
    assert snapshot.status_code == 200
    assert snapshot.body_type == "dict"
    assert body["status"] == "awaiting_confirm"
    assert snapshot.field_types["plan"] == "dict"
    assert snapshot.field_types["coexist_pairs"] == "list"
    assert snapshot.field_types["old_tree"] == "list"
    assert snapshot.field_types["new_tree"] == "list"
    assert snapshot.field_types["plan_tree"] == "list"
    assert snapshot.list_lengths["coexist_pairs"] == 1
    assert snapshot.list_lengths["old_tree"] == 1
    assert snapshot.list_lengths["new_tree"] == 1
    assert snapshot.list_lengths["plan_tree"] == 3


def test_organize_dry_run_falls_back_to_action_plan_when_qb_file_list_missing(monkeypatch):
    task = _make_task(downloader_hash="")
    dm = FakeDownloadManager(task)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={
                "plan": [
                    {
                        "source_path": r"C:\library\Show\[Group] Show S01 2160p\Show.S01E02.2160p.mkv",
                        "original_filename": "Show.S01E02.2160p.mkv",
                        "target_filename": "Show.S01E02.2160p.mkv",
                        "target_season_dir": "Season 01",
                        "mapped": {"season": 1, "episode": 2},
                        "actions": ["write_episode_nfo"],
                    }
                ]
            },
            coexist_pairs=[
                CoexistPair(
                    new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
                    old_file=r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv",
                    old_size_gb=1.5,
                    category="video",
                    is_folder=False,
                )
            ],
        )
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: False)
    monkeypatch.setattr(relocate, "config_m", SimpleNamespace(config=SimpleNamespace(nas_paths=[])))

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id=task.id)))

    assert relocator.relocate_calls == [{"task_id": "task-1", "whitelist": None}]
    assert body["status"] == "awaiting_confirm"
    assert body["new_files_all"] == [{"name": "[Group] Show S01 2160p\\Show.S01E02.2160p.mkv", "size": 0}]
    assert body["new_tree"] == [
        {
            "name": "[Group] Show S01 2160p",
            "type": "dir",
            "size_bytes": 0,
            "children": [{"name": "Show.S01E02.2160p.mkv", "type": "video", "size_bytes": 0}],
        }
    ]


def test_organize_execute_injects_whitelist_before_confirm(monkeypatch):
    task = _make_task()
    dm = FakeDownloadManager(task)
    qb = FakeQBClient(
        [
            {"name": "[Group] Show S01 2160p/Show.S01E02.2160p.mkv", "size_bytes": 1234},
            {"name": "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass", "size_bytes": 56},
        ]
    )
    relocator = FakeRelocator(
        execute_result=RelocateResult(success=True, status="archived", action_plan={"plan": []})
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": qb})

    req = relocate.ExecuteRelocateRequest(task_id=task.id, plan={"plan": [{"target_filename": "Show.S01E02.2160p.mkv"}]})
    body = asyncio.run(relocate.organize_execute(req))

    assert qb.calls == ["hash-1"]
    assert relocator.confirm_calls == [
        {
            "task_id": "task-1",
            "plan": {
                "plan": [{"target_filename": "Show.S01E02.2160p.mkv"}],
                "whitelist": [
                    "[Group] Show S01 2160p/Show.S01E02.2160p.mkv",
                    "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass",
                ],
            },
        }
    ]
    assert dm.archive_calls == [{"task_id": "task-1", "organized": True}]
    assert body == {"status": "archived", "message": "整理替换任务执行完毕"}


def test_organize_execute_skips_archive_when_confirm_fails(monkeypatch):
    task = _make_task(downloader_hash="")
    dm = FakeDownloadManager(task)
    relocator = FakeRelocator(
        execute_result=RelocateResult(success=False, status="failed", error="旧资源入回收站失败")
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    req = relocate.ExecuteRelocateRequest(task_id=task.id, plan={"plan": []})
    body = asyncio.run(relocate.organize_execute(req))

    assert relocator.confirm_calls == [{"task_id": "task-1", "plan": {"plan": []}}]
    assert dm.archive_calls == []
    assert body == {"status": "failed", "message": "旧资源入回收站失败"}


def test_organize_execute_raises_404_when_task_missing(monkeypatch):
    dm = FakeDownloadManager(task=None)
    relocator = FakeRelocator()

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    req = relocate.ExecuteRelocateRequest(task_id="missing", plan={"plan": []})

    try:
        asyncio.run(relocate.organize_execute(req))
    except Exception as exc:
        assert exc.status_code == 404
        assert exc.detail == "任务不存在"
    else:
        raise AssertionError("缺失任务时应抛出 HTTPException")


def test_organize_archive_both_relocates_again_before_archiving(monkeypatch):
    task = _make_task()
    dm = FakeDownloadManager(task)
    qb = FakeQBClient(
        [
            {"name": "[Group] Show S01 2160p/Show.S01E02.2160p.mkv", "size_bytes": 1234},
            {"name": "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass", "size_bytes": 56},
        ]
    )
    conflicts = [
        CoexistPair(
            new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
            old_file=r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv",
            old_size_gb=1.5,
            category="video",
            is_folder=False,
        )
    ]
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={"plan": []},
            coexist_pairs=conflicts,
        ),
        execute_result=RelocateResult(success=True, status="archived", action_plan={"plan": []}),
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": qb})

    req = relocate.ExecuteRelocateRequest(task_id=task.id, plan={"plan": []})
    body = asyncio.run(relocate.organize_archive_both(req))

    assert qb.calls == ["hash-1"]
    assert relocator.relocate_calls == [
        {
            "task_id": "task-1",
            "whitelist": [
                "[Group] Show S01 2160p/Show.S01E02.2160p.mkv",
                "[Group] Show S01 2160p/Subs/Show.S01E02.zh.ass",
            ],
        }
    ]
    assert len(relocator.archive_calls) == 1
    assert relocator.archive_calls[0]["task_id"] == "task-1"
    assert relocator.archive_calls[0]["conflicts"] == conflicts
    assert dm.archive_calls == [{"task_id": "task-1", "organized": True}]
    assert body == {"status": "archived", "message": "共存归档任务执行完毕"}


def test_organize_archive_both_skips_archive_when_archive_both_fails(monkeypatch):
    task = _make_task(downloader_hash="")
    dm = FakeDownloadManager(task)
    conflicts = [
        CoexistPair(
            new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
            old_file=r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv",
            old_size_gb=1.5,
            category="video",
            is_folder=False,
        )
    ]
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={"plan": []},
            coexist_pairs=conflicts,
        ),
        execute_result=RelocateResult(success=False, status="failed", error="archive both failed"),
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    req = relocate.ExecuteRelocateRequest(task_id=task.id, plan={"plan": []})
    body = asyncio.run(relocate.organize_archive_both(req))

    assert dm.archive_calls == []
    assert body == {"status": "failed", "message": "archive both failed"}


def test_organize_archive_both_raises_404_when_task_missing(monkeypatch):
    dm = FakeDownloadManager(task=None)
    relocator = FakeRelocator()

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    req = relocate.ExecuteRelocateRequest(task_id="missing", plan={"plan": []})

    try:
        asyncio.run(relocate.organize_archive_both(req))
    except Exception as exc:
        assert exc.status_code == 404
        assert exc.detail == "任务不存在"
    else:
        raise AssertionError("缺失任务时应抛出 HTTPException")


def test_organize_purge_old_requires_qb_file_list(monkeypatch):
    task = _make_task(downloader_hash="")
    dm = FakeDownloadManager(task)
    relocator = FakeRelocator()

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    body = asyncio.run(relocate.organize_purge_old(task.id))

    assert relocator.relocate_calls == []
    assert relocator.recycle_calls == []
    assert body == {"status": "failed", "message": "无法识别新任务文件，为防误删，停止清理"}


def test_organize_purge_old_returns_ok_when_no_conflicts_found(monkeypatch):
    task = _make_task()
    dm = FakeDownloadManager(task)
    qb = FakeQBClient([{"name": "[Group] Show S01 2160p/Show.S01E02.2160p.mkv", "size_bytes": 1234}])
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=True,
            status="archived",
            action_plan={"plan": []},
            coexist_pairs=[],
        )
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": qb})

    body = asyncio.run(relocate.organize_purge_old(task.id))

    assert relocator.recycle_calls == []
    assert body == {"status": "ok", "message": "未发现需要清理的旧数据"}


def test_organize_purge_old_raises_404_when_task_missing(monkeypatch):
    dm = FakeDownloadManager(task=None)
    relocator = FakeRelocator()

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})

    try:
        asyncio.run(relocate.organize_purge_old("missing"))
    except Exception as exc:
        assert exc.status_code == 404
        assert exc.detail == "任务不存在"
    else:
        raise AssertionError("缺失任务时应抛出 HTTPException")


def test_organize_purge_old_recycles_each_detected_conflict(monkeypatch):
    task = _make_task()
    dm = FakeDownloadManager(task)
    qb = FakeQBClient([{"name": "[Group] Show S01 2160p/Show.S01E02.2160p.mkv", "size_bytes": 1234}])
    conflicts = [
        CoexistPair(
            new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
            old_file=r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv",
            old_size_gb=1.5,
            category="video",
            is_folder=False,
        ),
        CoexistPair(
            new_file=r"C:\library\Show\Season 01\Show.S01E02.2160p.mkv",
            old_file=r"C:\library\Show\Season 01\Season 01",
            old_size_gb=3.0,
            category="folder",
            is_folder=True,
        ),
    ]
    relocator = FakeRelocator(
        relocate_result=RelocateResult(
            success=False,
            status="awaiting_confirm",
            action_plan={"plan": []},
            coexist_pairs=conflicts,
        )
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": qb})

    body = asyncio.run(relocate.organize_purge_old(task.id))

    assert qb.calls == ["hash-1"]
    assert relocator.relocate_calls == [
        {
            "task_id": "task-1",
            "whitelist": ["[Group] Show S01 2160p/Show.S01E02.2160p.mkv"],
        }
    ]
    assert relocator.recycle_calls == [
        {"task_id": "task-1", "old_file": r"C:\library\Show\Season 01\Show.S01E01.1080p.mkv"},
        {"task_id": "task-1", "old_file": r"C:\library\Show\Season 01\Season 01"},
    ]
    assert body == {"status": "ok", "message": "已清理 2 组旧存量数据"}


def test_organize_dry_run_fails_when_task_missing(monkeypatch):
    dm = FakeDownloadManager(task=None)

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: False)
    monkeypatch.setattr(relocate, "config_m", SimpleNamespace(config=SimpleNamespace(nas_paths=[])))

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id="missing")))

    assert body == {"status": "failed", "message": "任务不存在: missing", "coexist_pairs": []}


def test_organize_dry_run_fails_for_top_category(monkeypatch):
    task = _make_task(save_path=r"C:\library\TV")
    dm = FakeDownloadManager(task)

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: True)
    monkeypatch.setattr(relocate, "config_m", SimpleNamespace(config=SimpleNamespace(nas_paths=[])))

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id=task.id)))

    assert body["status"] == "failed"
    assert "一级分类目录" in body["message"]
    assert body["coexist_pairs"] == []


def test_organize_dry_run_fails_for_nas_root(monkeypatch):
    task = _make_task(save_path=r"C:\library\root")
    dm = FakeDownloadManager(task)

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: False)
    monkeypatch.setattr(
        relocate,
        "config_m",
        SimpleNamespace(config=SimpleNamespace(nas_paths=[r"C:\library\root"])),
    )

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id=task.id)))

    assert body == {
        "status": "failed",
        "message": "该任务的保存路径是 NAS 根目录，无法进行整理替换探测。",
        "coexist_pairs": [],
    }


def test_organize_dry_run_returns_failed_when_relocator_fails(monkeypatch):
    task = _make_task(downloader_hash="")
    dm = FakeDownloadManager(task)
    relocator = FakeRelocator(
        relocate_result=RelocateResult(success=False, status="failed", error="dry run failed")
    )

    monkeypatch.setattr(relocate, "_get_download_manager", lambda: dm)
    monkeypatch.setattr(relocate, "_get_file_relocator", lambda: relocator)
    monkeypatch.setattr(relocate, "get_clients", lambda: {"qb": None})
    monkeypatch.setattr(relocate, "_is_top_category", lambda path: False)
    monkeypatch.setattr(relocate, "config_m", SimpleNamespace(config=SimpleNamespace(nas_paths=[])))

    body = asyncio.run(relocate.organize_dry_run(relocate.RelocateRequest(task_id=task.id)))

    assert body == {"status": "failed", "message": "探测失败: dry run failed", "coexist_pairs": []}
