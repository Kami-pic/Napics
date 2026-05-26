"""XL720 BT 搜索源插件。

安装后提供：中文磁力聚合搜索（国内直连，响应较慢）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 XL720 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_xl720")
    scraper_cls = getattr(mod, "XL720Scraper")

    ctx.register_scraper_search_provider(
        provider_id="xl720",
        name="XL720",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=False,
        description="中文磁力聚合搜索（国内直连，响应较慢）",
    )
    ctx.logger.info("XL720 搜索源已加载")


def unregister():
    pass
