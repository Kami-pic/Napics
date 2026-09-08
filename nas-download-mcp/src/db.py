"""SQLite 持久化（todo §10）。

五表：tasks / task_events / resources / probe_batches / service_locks。
用 SQLite 而非纯 JSON：任务状态、事件、qB hash、服务锁都要持久化，且要支持崩溃恢复。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    media_type TEXT,
    title TEXT,
    year INTEGER,
    original_title TEXT,
    original_language TEXT,
    status TEXT,
    current_stage TEXT,
    napics_task_id TEXT,
    qb_hashes_json TEXT,        -- probe 一批多 hash，选定后收敛为 1
    selected_qb_hash TEXT,
    save_path TEXT,
    error_code TEXT,
    error_message TEXT,
    cleanup_status TEXT,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    kind TEXT,
    detail_json TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    batch_number INTEGER,
    title TEXT,
    download_url TEXT,
    size_bytes INTEGER,
    seeders INTEGER,
    quality_json TEXT,
    status TEXT,
    qb_hash TEXT,
    speed INTEGER,
    selected INTEGER DEFAULT 0,
    created_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS probe_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    batch_number INTEGER,
    started_at REAL,
    deadline REAL,
    status TEXT,
    selected_resource_id INTEGER
);

CREATE TABLE IF NOT EXISTS service_locks (
    name TEXT PRIMARY KEY,      -- 'workflow_lock'
    task_id TEXT,
    acquired_at REAL
);
"""


class Db:
    def __init__(self, path: str):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ── tasks ──
    def create_task(self, task_id: str, fields: dict) -> None:
        now = time.time()
        cols = {
            "id": task_id,
            "qb_hashes_json": "[]",
            "cleanup_status": "",
            "created_at": now,
            "updated_at": now,
            **fields,
        }
        keys = ",".join(cols.keys())
        marks = ",".join("?" for _ in cols)
        with self._lock:
            self._conn.execute(f"INSERT INTO tasks ({keys}) VALUES ({marks})", tuple(cols.values()))
            self._conn.commit()

    def update_task(self, task_id: str, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        sets = ",".join(f"{k}=?" for k in fields)
        with self._lock:
            self._conn.execute(
                f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), task_id)
            )
            self._conn.commit()

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self, status: str = "") -> list[dict]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def set_qb_hashes(self, task_id: str, hashes: list[str]) -> None:
        self.update_task(task_id, qb_hashes_json=json.dumps(hashes))

    def get_qb_hashes(self, task_id: str) -> list[str]:
        t = self.get_task(task_id)
        if not t:
            return []
        try:
            return json.loads(t.get("qb_hashes_json") or "[]")
        except Exception:
            return []

    # ── events ──
    def add_event(self, task_id: str, kind: str, detail: Any = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO task_events (task_id, kind, detail_json, created_at) VALUES (?,?,?,?)",
                (task_id, kind, json.dumps(detail) if detail is not None else None, time.time()),
            )
            self._conn.commit()

    def list_events(self, task_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM task_events WHERE task_id=? ORDER BY id", (task_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 并发锁（todo §5，同时只允许一个 workflow）──
    def try_acquire_lock(self, task_id: str, name: str = "workflow_lock") -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT task_id FROM service_locks WHERE name=?", (name,)
            ).fetchone()
            if row is not None:
                return False
            self._conn.execute(
                "INSERT INTO service_locks (name, task_id, acquired_at) VALUES (?,?,?)",
                (name, task_id, time.time()),
            )
            self._conn.commit()
            return True

    def release_lock(self, name: str = "workflow_lock") -> None:
        with self._lock:
            self._conn.execute("DELETE FROM service_locks WHERE name=?", (name,))
            self._conn.commit()

    def current_lock_task(self, name: str = "workflow_lock") -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT task_id FROM service_locks WHERE name=?", (name,)
            ).fetchone()
        return row["task_id"] if row else None

    # ── 崩溃恢复用：查非终态任务 ──
    def unfinished_tasks(self, terminal: list[str]) -> list[dict]:
        placeholders = ",".join("?" for _ in terminal)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM tasks WHERE status NOT IN ({placeholders})", tuple(terminal)
            ).fetchall()
        return [dict(r) for r in rows]
