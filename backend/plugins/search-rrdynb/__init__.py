"""人人电影 网盘搜索源插件。

安装后提供：网盘资源搜索（有 CF 限频）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 人人电影 网盘搜索源"""
    import importlib
    mod = importlib.import_module("pan_scraper_rrdynb")
    scraper_cls = getattr(mod, "RrdynbScraper")

    ctx.register_pan_search_provider(
        provider_id="rrdynb",
        name="人人电影",
        search_fn=None,
        enabled=True,
        description="网盘资源搜索（有 CF 限频）",
    )
    # 存储 scraper_class 供 pan_search_service 使用
    from plugin_context import _plugin_providers
    _plugin_providers["rrdynb"]["scraper_class"] = scraper_cls
    ctx.logger.info("人人电影 网盘搜索源已加载")


def unregister():
    pass
