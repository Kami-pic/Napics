"""蜜柑计划 BT 搜索源插件。

安装后提供：中文动画 BT 搜索（需代理）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 蜜柑计划 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_mikan")
    scraper_cls = getattr(mod, "MikanScraper")

    ctx.register_scraper_search_provider(
        provider_id="mikan",
        name="蜜柑计划",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=True,
        description="中文动画 BT 搜索（需代理）",
    )
    ctx.logger.info("蜜柑计划 搜索源已加载")


def unregister():
    pass
