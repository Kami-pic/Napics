"""db.py 测试：五表建表、tasks 读写、并发锁、孤儿查询。数据库用 pytest tmp。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db import Db  # noqa: E402


@pytest.fixture
def db(tmp_path):
    d = Db(str(tmp_path / "t.db"))
    yield d
    d.close()


def test_create_and_get(db):
    db.create_task("task-1", {"title": "泰坦尼克号", "status": "starting", "current_stage": "CREATED"})
    t = db.get_task("task-1")
    assert t["title"] == "泰坦尼克号"
    assert t["qb_hashes_json"] == "[]"


def test_update(db):
    db.create_task("task-1", {"title": "x", "status": "starting", "current_stage": "CREATED"})
    db.update_task("task-1", status="downloading", current_stage="DOWNLOADING")
    assert db.get_task("task-1")["status"] == "downloading"


def test_qb_hashes_roundtrip(db):
    db.create_task("task-1", {"title": "x", "status": "probing", "current_stage": "PROBING_RESOURCES"})
    db.set_qb_hashes("task-1", ["h1", "h2", "h3"])
    assert db.get_qb_hashes("task-1") == ["h1", "h2", "h3"]


def test_lock_mutual_exclusion(db):
    assert db.try_acquire_lock("task-1") is True
    # 第二个任务拿不到锁（同时只允许一个 workflow）
    assert db.try_acquire_lock("task-2") is False
    assert db.current_lock_task() == "task-1"
    db.release_lock()
    assert db.try_acquire_lock("task-2") is True


def test_events(db):
    db.create_task("task-1", {"title": "x", "status": "starting", "current_stage": "CREATED"})
    db.add_event("task-1", "SEARCH_STARTED", {"q": "Titanic"})
    db.add_event("task-1", "SEARCH_COMPLETED", {"total": 5})
    evs = db.list_events("task-1")
    assert [e["kind"] for e in evs] == ["SEARCH_STARTED", "SEARCH_COMPLETED"]


def test_unfinished_tasks(db):
    db.create_task("done-1", {"title": "a", "status": "completed", "current_stage": "COMPLETED"})
    db.create_task("live-1", {"title": "b", "status": "downloading", "current_stage": "DOWNLOADING"})
    terminal = ["completed", "failed", "cancelled", "timeout", "exhausted"]
    unfinished = db.unfinished_tasks(terminal)
    ids = {t["id"] for t in unfinished}
    assert "live-1" in ids and "done-1" not in ids
