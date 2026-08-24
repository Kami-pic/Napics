"""媒体库写入互斥。

临界区是 `load_library → 修改 → save_library` 整段，只锁 save 挡不住丢更新：
两个请求各自读到旧库、各自写回，后写的把先写的整条抹掉。

`save_library` 内部按 file_path 去重「保留最后一条」，这个行为会**掩盖**丢更新
（两次都写同一条时看不出问题），所以下面专门有一条不加锁的对照用例，
证明是锁在起作用，而不是去重逻辑碰巧让断言变绿。
"""

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_manager


@pytest.fixture
def mgr(tmp_path, monkeypatch):
    """指向临时数据目录的独立 ConfigManager"""
    monkeypatch.setenv("NAPICS_DATA_DIR", str(tmp_path))
    m = config_manager.ConfigManager()
    m.save_library([])
    return m


def _video(name: str) -> dict:
    return {"file_path": f"/media/{name}.mkv", "file_name": f"{name}.mkv", "height": 1080}


def test_concurrent_mutate_keeps_both_entries(mgr):
    """两个线程各追加一条，最终库里必须同时有两条"""
    ready = threading.Barrier(2)

    def append(name):
        # barrier 必须在 mutate_library 之外：放进回调里就会变成
        # 「先拿锁的那个在临界区里等第二个进临界区」，直接自锁死等。
        ready.wait(timeout=5)
        mgr.mutate_library(lambda library: library.append(_video(name)))

    threads = [threading.Thread(target=append, args=(n,)) for n in ("alpha", "beta")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    paths = {v["file_path"] for v in mgr.load_library()}
    assert paths == {"/media/alpha.mkv", "/media/beta.mkv"}


def test_unlocked_load_save_loses_update(mgr):
    """对照：不加锁的裸 load + save 会丢更新。

    这条用例存在的意义是证明上面那条不是假绿 —— 如果哪天锁被摘掉、
    或者 save_library 的去重把问题掩盖了，这里会先炸。
    """
    ready = threading.Barrier(2)
    mid = threading.Barrier(2)

    def append_without_lock(name):
        library = mgr.load_library()      # 两边都读到空库
        ready.wait(timeout=5)
        library.append(_video(name))
        mid.wait(timeout=5)
        mgr.save_library(library)         # 后写的覆盖先写的

    threads = [threading.Thread(target=append_without_lock, args=(n,)) for n in ("alpha", "beta")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    paths = {v["file_path"] for v in mgr.load_library()}
    assert len(paths) == 1, "不加锁竟然没丢更新，说明这个对照失去了意义"


def test_nested_lock_does_not_deadlock(mgr):
    """/sync 单请求内会两次落盘，锁必须可重入"""
    done = []

    def body():
        with mgr.library_lock:
            with mgr.library_lock:
                library = mgr.load_library()
                library.append(_video("nested"))
                mgr.save_library(library)
            # 内层退出后外层仍持锁，此时再落一次盘（对应 /sync 的二次落盘）
            library = mgr.load_library()
            library.append(_video("nested2"))
            mgr.save_library(library)
        done.append(True)

    t = threading.Thread(target=body)
    t.start()
    t.join(timeout=5)
    assert done == [True], "嵌套持锁死锁了"
    assert len(mgr.load_library()) == 2


def test_mutate_library_inside_lock_does_not_deadlock(mgr):
    """已经持锁的调用方再调 mutate_library 也不能死锁"""
    with mgr.library_lock:
        mgr.mutate_library(lambda lib: lib.append(_video("outer")))
    assert len(mgr.load_library()) == 1


def test_lock_is_shared_across_instances(tmp_path, monkeypatch):
    """同一个 media_library.json 的不同 ConfigManager 实例必须共享同一把锁。

    download_manager._trigger_local_refresh 用的是**新建的**默认 ConfigManager()，
    实例级锁在这种场景下等于没加。
    """
    monkeypatch.setenv("NAPICS_DATA_DIR", str(tmp_path))
    a = config_manager.ConfigManager()
    b = config_manager.ConfigManager()
    a.save_library([])

    assert a.library_lock is b.library_lock

    ready = threading.Barrier(2)

    def append(m, name):
        ready.wait(timeout=5)
        m.mutate_library(lambda library: library.append(_video(name)))

    threads = [
        threading.Thread(target=append, args=(a, "from_a")),
        threading.Thread(target=append, args=(b, "from_b")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    paths = {v["file_path"] for v in a.load_library()}
    assert paths == {"/media/from_a.mkv", "/media/from_b.mkv"}


def test_mutate_library_can_skip_save(mgr):
    """fn 返回 False 表示无需落盘，不该产生一次多余的整库写"""
    mgr.save_library([_video("keep")])
    writes = []
    mgr._on_library_save_callbacks.append(lambda data: writes.append(len(data)))

    mgr.mutate_library(lambda lib: False)

    assert writes == []
    assert len(mgr.load_library()) == 1


def test_mutate_library_accepts_replacement_list(mgr):
    """fn 返回 list 时用它覆盖整库（对应删除媒体库这类整体替换）"""
    mgr.save_library([_video("old")])
    mgr.mutate_library(lambda lib: [_video("new")])
    assert [v["file_path"] for v in mgr.load_library()] == ["/media/new.mkv"]
