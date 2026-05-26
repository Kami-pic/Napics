"""ACG.RIP BT 搜索源插件。

安装后提供：动画 BT 搜索（连接不稳定，默认禁用）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 ACG.RIP 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_acgrip")
    scraper_cls = getattr(mod, "ACGRipScraper")

    ctx.register_scraper_search_provider(
        provider_id="acgrip",
        name="ACG.RIP",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=False,
        description="动画 BT 搜索（连接不稳定，默认禁用）",
    )
    ctx.logger.info("ACG.RIP 搜索源已加载")


def unregister():
    pass
