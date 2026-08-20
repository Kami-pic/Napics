"""pytest 全局配置 — 加载主体插件和本地独立社区插件的 sources。"""

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOTS = [
    os.path.join(_BACKEND_DIR, "plugins"),
    os.path.join(os.path.dirname(_BACKEND_DIR), "community-plugins"),
]

# community-plugins 是独立仓库；本地存在时运行其源实现测试，不复制回主体。
for plugin_root in _PLUGIN_ROOTS:
    if not os.path.isdir(plugin_root):
        continue
    for entry in os.listdir(plugin_root):
        sources_dir = os.path.join(plugin_root, entry, "sources")
        if os.path.isdir(sources_dir) and sources_dir not in sys.path:
            sys.path.insert(0, sources_dir)


# ── 真实数据保护 ──
# 出过事故：test_phase4_e2e 用默认 ConfigManager() 直接 save_library，
# 把用户 2600+ 条的 media_library.json 覆盖成 3 条测试夹具，且不可恢复
# （它的"备份"拼在 tests/ 下，保护的是另一个不存在的文件）。
#
# ConfigManager 的 lib_path 只认 NAPICS_DATA_DIR，构造参数无法隔离，
# 所以在这里统一把测试会话钉到临时数据目录：任何测试即便忘了隔离，
# 也只会写到临时目录，碰不到真实媒体库和 config.json。
#
# 确实要针对真实数据跑时，显式设置 NAPICS_ALLOW_REAL_DATA=1（自负风险）。
if not os.environ.get("NAPICS_ALLOW_REAL_DATA") and not os.environ.get("NAPICS_DATA_DIR"):
    import shutil
    import tempfile

    _TEST_DATA_DIR = tempfile.mkdtemp(prefix="napics_test_data_")
    os.environ["NAPICS_DATA_DIR"] = _TEST_DATA_DIR

    # config.json 复制一份进来：不少测试要读真实配置（已装插件、API key、扫描路径），
    # 只给一个空目录会让它们全部拿到默认空配置而失败。
    # 复制品可以被随便写，写的也只是临时目录里的副本。
    _REAL_CONFIG = os.path.join(_BACKEND_DIR, "config.json")
    if os.path.isfile(_REAL_CONFIG):
        shutil.copy2(_REAL_CONFIG, os.path.join(_TEST_DATA_DIR, "config.json"))

    # media_library.json 不复制：它是这次事故的受害者，测试一律从空库开始。
    # 需要库数据的测试自己造夹具，不许依赖用户的真实媒体库。
    with open(os.path.join(_TEST_DATA_DIR, "media_library.json"), "w", encoding="utf-8") as _f:
        _f.write("[]")
