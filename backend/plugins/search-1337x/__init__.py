"""1337x BT 搜索源插件。

安装后提供：综合 BT 搜索（镜像站，需代理）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 1337x 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_1337x")
    scraper_cls = getattr(mod, "X1337xScraper")

    ctx.register_scraper_search_provider(
        provider_id="1337x",
        name="1337x",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=True,
        description="综合 BT 搜索（镜像站，需代理）",
    )
    ctx.logger.info("1337x 搜索源已加载")


def unregister():
    pass
