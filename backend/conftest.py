"""pytest 全局配置 — 将插件 sources 目录加入 sys.path，确保测试能 import 已移入插件的模块。"""
import os
import sys

_PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")

# 扫描所有插件的 sources/ 目录并加入 sys.path
if os.path.isdir(_PLUGINS_DIR):
    for entry in os.listdir(_PLUGINS_DIR):
        sources_dir = os.path.join(_PLUGINS_DIR, entry, "sources")
        if os.path.isdir(sources_dir) and sources_dir not in sys.path:
            sys.path.insert(0, sources_dir)
