"""通用网盘站 网盘搜索源插件。

安装后提供：凌风云/盘搜搜/小白盘/趣盘搜
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 通用网盘站 网盘搜索源"""
    import importlib
    mod = importlib.import_module("pan_scraper_sites")
    scraper_cls = getattr(mod, "MultiSiteScraper")

    ctx.register_pan_search_provider(
        provider_id="sites",
        name="通用网盘站",
        search_fn=None,
        enabled=True,
        description="凌风云/盘搜搜/小白盘/趣盘搜",
    )
    # 存储 scraper_class 供 pan_search_service 使用
    from plugin_context import _plugin_providers
    _plugin_providers["sites"]["scraper_class"] = scraper_cls
    ctx.logger.info("通用网盘站 网盘搜索源已加载")


def unregister():
    pass
