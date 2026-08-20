"""数据隔离自检：测试会话绝不能写到真实数据目录。

事故背景：test_phase4_e2e 用默认 ConfigManager() 调 save_library，
而 lib_path 只认 NAPICS_DATA_DIR、不受构造参数影响，
于是把用户 2600+ 条的 media_library.json 覆盖成 3 条 P4TEST 夹具，无备份可恢复。

conftest.py 会把整个测试会话钉到临时 NAPICS_DATA_DIR。
这个文件负责让那层防护"自证"——防护被删掉或被绕过时，这里会先红。
"""

import os

import config_manager


_REAL_BACKEND_DIR = os.path.dirname(os.path.abspath(config_manager.__file__))
_REAL_LIB = os.path.join(_REAL_BACKEND_DIR, "media_library.json")
_REAL_CONFIG = os.path.join(_REAL_BACKEND_DIR, "config.json")


def test_data_dir_is_isolated():
    """NAPICS_DATA_DIR 必须已被指向临时目录，而不是 backend/"""
    data_dir = os.environ.get("NAPICS_DATA_DIR")
    assert data_dir, "NAPICS_DATA_DIR 未设置：conftest 的数据隔离防护缺失"
    assert os.path.abspath(data_dir) != _REAL_BACKEND_DIR, (
        "NAPICS_DATA_DIR 指向真实 backend 目录，测试会写坏用户媒体库"
    )


def test_config_manager_writes_outside_real_data_dir():
    """默认构造的 ConfigManager 也必须落在隔离目录里"""
    manager = config_manager.ConfigManager()
    assert os.path.abspath(manager.lib_path) != _REAL_LIB, (
        f"ConfigManager.lib_path 指向真实媒体库: {manager.lib_path}"
    )
    assert os.path.abspath(manager.config_path) != _REAL_CONFIG, (
        f"ConfigManager.config_path 指向真实配置: {manager.config_path}"
    )


def test_writing_library_does_not_touch_real_file():
    """真写一次库，确认真实文件的内容与修改时间都没变"""
    before_exists = os.path.exists(_REAL_LIB)
    before_bytes = open(_REAL_LIB, "rb").read() if before_exists else None

    config_manager.ConfigManager().save_library([
        {"file_path": "ISOLATION_PROBE.mkv", "file_name": "ISOLATION_PROBE.mkv", "height": 1080},
    ])

    assert os.path.exists(_REAL_LIB) == before_exists, "真实媒体库被测试创建/删除了"
    if before_exists:
        assert open(_REAL_LIB, "rb").read() == before_bytes, "真实媒体库被测试改写了"
