"""插件装卸后的运行时服务刷新验证。"""

import os
import shutil
import tempfile

from download_manager import DownloadManager, DownloadTask
import shared


class FakeDownloadManager:
    def __init__(self):
        self.replacements = []

    def replace_backends(self, backends):
        self.replacements.append(backends)

    def get_backends_snapshot(self):
        return {"qb": "old-qb", "alist": "old-alist"}


def test_refresh_existing_download_backends(monkeypatch):
    """OpenList/qB 插件装卸后原子替换后端，不要求重启容器。"""
    manager = FakeDownloadManager()
    backends = {"alist": object()}
    monkeypatch.setattr(shared, "_download_manager", manager)
    monkeypatch.setattr(shared, "_build_download_backends", lambda: (backends, set()))

    assert shared.refresh_download_backends() is True
    assert manager.replacements == [backends]


def test_refresh_build_failure_preserves_only_still_installed_backend(monkeypatch):
    """仍安装后端构建失败时保留旧实例，但已卸载通道必须移除。"""
    manager = FakeDownloadManager()
    monkeypatch.setattr(shared, "_download_manager", manager)
    monkeypatch.setattr(shared, "_build_download_backends", lambda: ({}, {"alist"}))

    assert shared.refresh_download_backends() is False
    assert manager.replacements == [{"alist": "old-alist"}]


def test_refresh_does_not_create_unused_manager(monkeypatch):
    """下载管理器尚未使用时，插件装卸不应为刷新而额外创建常驻对象。"""
    monkeypatch.setattr(shared, "_download_manager", None)
    shared.refresh_download_backends()
    assert shared._download_manager is None


def test_initial_library_list_is_released_after_index_build():
    """媒体索引构建后不重复常驻原始媒体库列表。"""
    assert not hasattr(shared, "_init_lib")


class FakeAdapter:
    def __init__(self, client, task_id):
        self.client = client
        self.task_id = task_id
        self.calls = 0

    def _get_client(self):
        return self.client

    def submit(self, request):
        from provider_models import DownloadSubmitResult

        self.calls += 1
        return DownloadSubmitResult(success=True, externalTaskId=self.task_id)


def test_alist_push_uses_submit_snapshot_after_backend_replace():
    """提交已捕获旧后端时，刷新不能把网络阶段切换到新后端。"""
    directory = tempfile.mkdtemp(prefix="backend_snapshot_", dir=os.path.dirname(__file__))
    try:
        manager = DownloadManager(base_path=directory)
        old_backend = FakeAdapter(object(), "old-task")
        new_backend = FakeAdapter(object(), "new-task")
        manager.replace_backends({"alist": old_backend})
        manager._backend_context.alist_submit = old_backend
        manager.replace_backends({"alist": new_backend})

        success, task_id = manager._push_to_alist(DownloadTask(id="task", download_dir=directory))

        assert success is True
        assert task_id == "old-task"
        assert old_backend.calls == 1
        assert new_backend.calls == 0
    finally:
        shutil.rmtree(directory, ignore_errors=True)