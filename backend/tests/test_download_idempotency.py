"""download_manager 幂等提交 + magnet→btih 可靠 hash 的行为保护（MCP todo §2.2）。

数据隔离：conftest.py 已把 NAPICS_DATA_DIR 钉到临时目录；这里再用独立 base_path，
两层都不碰真实库。
"""
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from download_manager import DownloadManager, DownloadTask


def _with_temp_dir(prefix, fn):
    tmp = tempfile.mkdtemp(prefix=prefix + "_")
    try:
        fn(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _task(**over):
    data = {
        "media_name": "Show",
        "download_url": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567",
        "save_path": r"C:\library\Show",
        "channel": "qb",
    }
    data.update(over)
    return DownloadTask(**data)


# ── 幂等 ──

def test_same_idempotency_key_reuses_existing_task(monkeypatch):
    """同 key 且已存在未失败任务 → 直接复用，不第二次 push。"""
    def run(tmp):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=tmp)
        push_calls = []

        def fake_push(task):
            push_calls.append(task.id)
            return True, "HASHFIRST"

        monkeypatch.setattr(dm, "_push_to_qb", fake_push)
        monkeypatch.setattr(dm, "_save_now", lambda: None)

        first = dm.submit(_task(idempotency_key="dune-2021-magnet"))
        second = dm.submit(_task(idempotency_key="dune-2021-magnet"))

        # 复用同一条，push 只发生一次，任务列表里只有一条
        assert second.id == first.id
        assert len(push_calls) == 1
        assert len([t for t in dm.tasks if t.idempotency_key == "dune-2021-magnet"]) == 1

    _with_temp_dir("dm_idem_reuse", run)


def test_failed_task_is_not_reused(monkeypatch):
    """失败的任务不复用 —— 允许用同 key 重试。"""
    def run(tmp):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=tmp)
        results = iter([(False, "boom"), (True, "HASHOK")])
        monkeypatch.setattr(dm, "_push_to_qb", lambda t: next(results))
        monkeypatch.setattr(dm, "_save_now", lambda: None)

        first = dm.submit(_task(idempotency_key="retry-key"))
        second = dm.submit(_task(idempotency_key="retry-key"))

        assert first.status == "failed"
        assert second.id != first.id
        assert second.status == "downloading"

    _with_temp_dir("dm_idem_retry", run)


def test_empty_idempotency_key_never_dedups(monkeypatch):
    """空 key 保持旧行为：每次都是新任务。"""
    def run(tmp):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=tmp)
        monkeypatch.setattr(dm, "_push_to_qb", lambda t: (True, "H"))
        monkeypatch.setattr(dm, "_save_now", lambda: None)

        a = dm.submit(_task(idempotency_key=""))
        b = dm.submit(_task(idempotency_key=""))

        assert a.id != b.id
        assert len(dm.tasks) == 2

    _with_temp_dir("dm_idem_empty", run)


# ── magnet → btih 可靠 hash ──

def test_push_to_qb_takes_hash_from_magnet_btih(monkeypatch):
    """magnet 链接直接从 btih 取 infohash（大写），不走差集轮询。"""
    def run(tmp):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=tmp)

        # provider.submit 成功；差集快照返回空 —— 若代码回落差集会拿到空 hash
        fake_provider = SimpleNamespace(
            submit=lambda req: SimpleNamespace(success=True, message="ok"),
        )
        monkeypatch.setattr(dm, "_backends", {"qb": fake_provider})
        monkeypatch.setattr(dm, "_get_qb_hashes_snapshot", lambda provider: set())

        task = _task(
            download_url="magnet:?xt=urn:btih:abcdef0123456789abcdef0123456789abcdef01&dn=x",
        )
        # 直接走内部快照路径
        dm._backend_context.qb_submit = (fake_provider, object())
        try:
            ok, h = dm._push_to_qb(task)
        finally:
            del dm._backend_context.qb_submit

        assert ok is True
        assert h == "ABCDEF0123456789ABCDEF0123456789ABCDEF01"

    _with_temp_dir("dm_btih", run)


def test_push_to_qb_falls_back_to_diff_for_non_magnet(monkeypatch):
    """非 magnet（种子文件 URL）没有 btih → 回落加种前后差集。"""
    def run(tmp):
        dm = DownloadManager(qb_client=object(), alist_client=None, base_path=tmp)
        fake_provider = SimpleNamespace(
            submit=lambda req: SimpleNamespace(success=True, message="ok"),
        )
        snapshots = iter([set(), {"NEWHASH"}])  # before, after
        monkeypatch.setattr(dm, "_get_qb_hashes_snapshot", lambda provider: next(snapshots))
        monkeypatch.setattr("download_manager.time.sleep", lambda *_: None)

        task = _task(download_url="https://example.com/x.torrent")
        dm._backend_context.qb_submit = (fake_provider, object())
        try:
            ok, h = dm._push_to_qb(task)
        finally:
            del dm._backend_context.qb_submit

        assert ok is True
        assert h == "NEWHASH"

    _with_temp_dir("dm_diff_fallback", run)
