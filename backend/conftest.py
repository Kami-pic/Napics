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
