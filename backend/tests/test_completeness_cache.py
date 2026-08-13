"""完整度缓存层：进程内常驻 + 批量落盘的行为等价性验证"""
import importlib
import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def comp(monkeypatch):
    """在独立临时数据目录下重新加载 completeness 模块"""
    d = tempfile.mkdtemp(prefix="napics_comp_")
    monkeypatch.setenv("NAPICS_DATA_DIR", d)
    import completeness as module
    importlib.reload(module)
    try:
        yield module, d
    finally:
        shutil.rmtree(d, ignore_errors=True)
        monkeypatch.undo()
        importlib.reload(module)


def test_save_then_read_roundtrip(comp):
    module, _ = comp
    module.save_completeness_to_cache("/media/tv/剧A", {"status": "ok", "completeness_pct": 80})

    got = module.get_cached_completeness("/media/tv/剧A")
    assert got["status"] == "ok"
    assert got["completeness_pct"] == 80
    assert "_cached_at" in got


def test_persisted_to_disk(comp):
    module, d = comp
    module.save_completeness_to_cache("/media/tv/剧B", {"status": "ok", "completeness_pct": 50})

    with open(os.path.join(d, "completeness_cache.json"), encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["/media/tv/剧B"]["completeness_pct"] == 50


def test_returned_entry_is_a_copy(comp):
    """调用方修改返回值不能污染常驻缓存"""
    module, _ = comp
    module.save_completeness_to_cache("/media/tv/剧C", {"status": "ok", "completeness_pct": 90})

    got = module.get_cached_completeness("/media/tv/剧C")
    got["completeness_pct"] = 0

    again = module.get_cached_completeness("/media/tv/剧C")
    assert again["completeness_pct"] == 90


def test_remove_from_cache(comp):
    module, _ = comp
    module.save_completeness_to_cache("/media/tv/剧D", {"status": "ok"})
    assert module.get_cached_completeness("/media/tv/剧D") is not None

    module.remove_from_cache("/media/tv/剧D")
    assert module.get_cached_completeness("/media/tv/剧D") is None


def test_missing_key_returns_none(comp):
    module, _ = comp
    assert module.get_cached_completeness("/media/tv/不存在") is None


def test_external_file_change_is_picked_up(comp):
    """文件被外部改写时，常驻缓存要能感知并重载"""
    module, d = comp
    module.save_completeness_to_cache("/media/tv/剧E", {"status": "ok", "completeness_pct": 10})

    cache_file = os.path.join(d, "completeness_cache.json")
    # 模拟外部进程改写（改内容且改变文件大小）
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"/media/tv/剧E": {"status": "ok", "completeness_pct": 100, "extra": "x" * 50}}, f)

    got = module.get_cached_completeness("/media/tv/剧E")
    assert got["completeness_pct"] == 100


def test_deferred_writes_reduce_disk_io(comp):
    """persist=False 只更新内存，flush 后才落盘"""
    module, d = comp
    cache_file = os.path.join(d, "completeness_cache.json")

    for i in range(10):
        module._set_cache_entry(f"/media/tv/剧{i}", {"status": "ok", "completeness_pct": i}, persist=False)

    assert not os.path.exists(cache_file), "persist=False 不应产生落盘"
    # 内存里已经可读
    assert module.get_cached_completeness("/media/tv/剧5")["completeness_pct"] == 5

    module._flush_cache()
    with open(cache_file, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert len(on_disk) == 10
    assert on_disk["/media/tv/剧9"]["completeness_pct"] == 9


def test_corrupted_cache_file_degrades_gracefully(comp):
    """缓存文件损坏时应回退到空缓存而不是抛异常"""
    module, d = comp
    cache_file = os.path.join(d, "completeness_cache.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("{ 这不是合法 JSON")

    assert module.get_cached_completeness("/media/tv/任意") is None
    # 仍然可以正常写入
    module.save_completeness_to_cache("/media/tv/剧F", {"status": "ok"})
    assert module.get_cached_completeness("/media/tv/剧F") is not None
