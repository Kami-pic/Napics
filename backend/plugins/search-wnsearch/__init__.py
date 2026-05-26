"""我能搜 网盘搜索源插件。

安装后提供：夸克/百度/迅雷/UC 网盘搜索
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 我能搜 网盘搜索源"""
    import importlib
    mod = importlib.import_module("pan_scraper_wnsearch")
    scraper_cls = getattr(mod, "WnSearchScraper")

    ctx.register_pan_search_provider(
        provider_id="wnsearch",
        name="我能搜",
        search_fn=None,
        enabled=True,
        description="夸克/百度/迅雷/UC 网盘搜索",
    )
    # 存储 scraper_class 供 pan_search_service 使用
    from plugin_context import _plugin_providers
    _plugin_providers["wnsearch"]["scraper_class"] = scraper_cls
    ctx.logger.info("我能搜 网盘搜索源已加载")


def unregister():
    pass
