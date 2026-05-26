"""盘搜 网盘搜索源插件。

安装后提供：多插件网盘聚合搜索
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 盘搜 网盘搜索源"""
    import importlib
    mod = importlib.import_module("pan_scraper_pansou")
    scraper_cls = getattr(mod, "PanSouClient")

    ctx.register_pan_search_provider(
        provider_id="pansou",
        name="盘搜",
        search_fn=None,
        enabled=True,
        description="多插件网盘聚合搜索",
    )
    # 存储 scraper_class 供 pan_search_service 使用
    from plugin_context import _plugin_providers
    _plugin_providers["pansou"]["scraper_class"] = scraper_cls
    ctx.logger.info("盘搜 网盘搜索源已加载")


def unregister():
    pass
