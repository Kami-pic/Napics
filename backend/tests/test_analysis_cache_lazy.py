"""分析缓存惰性加载行为等价验证。"""

import json
import os
import shutil
import tempfile
import threading

from analysis_cache import AnalysisCache


def _temp_dir():
    return tempfile.mkdtemp(prefix="analysis_cache_", dir=os.path.dirname(__file__))


def test_cache_is_loaded_on_first_read():
    directory = _temp_dir()
    try:
        path = os.path.join(directory, "analysis_cache.json")
        payload = {"results": [{"path": "/media/a"}], "summary": {"total_folders": 1}, "updated_at": 100}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        cache = AnalysisCache(path)
        assert cache._loaded is False
        assert cache.get() == payload
        assert cache._loaded is True
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_update_folder_preserves_existing_cache_before_first_read():
    directory = _temp_dir()
    try:
        path = os.path.join(directory, "analysis_cache.json")
        payload = {"results": [{"path": "/media/a", "structure_ops": []}], "summary": {}, "updated_at": 100}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        cache = AnalysisCache(path)
        cache.update_folder("/media/b", {"path": "/media/b", "structure_ops": []})
        results = cache.get()["results"]
        assert [item["path"] for item in results] == ["/media/a", "/media/b"]
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_invalidate_does_not_reload_old_file():
    directory = _temp_dir()
    try:
        path = os.path.join(directory, "analysis_cache.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"results": [{"path": "/old"}], "updated_at": 100}, f)

        cache = AnalysisCache(path)
        cache.invalidate()
        assert cache.get() is None
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_invalidate_waits_for_first_load_and_wins():
    """首次读取与失效并发时，失效后的旧缓存不能复活。"""
    directory = _temp_dir()
    try:
        path = os.path.join(directory, "analysis_cache.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"results": [{"path": "/old"}], "updated_at": 100}, f)

        cache = AnalysisCache(path)
        original_load = cache._load
        load_started = threading.Event()
        allow_load = threading.Event()

        def blocked_load():
            load_started.set()
            assert allow_load.wait(timeout=2)
            original_load()

        cache._load = blocked_load
        read_thread = threading.Thread(target=cache.get)
        invalidate_thread = threading.Thread(target=cache.invalidate)
        read_thread.start()
        assert load_started.wait(timeout=2)
        invalidate_thread.start()
        allow_load.set()
        read_thread.join(timeout=2)
        invalidate_thread.join(timeout=2)

        assert not read_thread.is_alive()
        assert not invalidate_thread.is_alive()
        assert cache.get() is None
    finally:
        shutil.rmtree(directory, ignore_errors=True)