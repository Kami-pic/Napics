"""磁力熊 BT 搜索源插件。

安装后提供：中文磁力聚合搜索（国内直连）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 磁力熊 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_cilixiong")
    scraper_cls = getattr(mod, "CilixiongScraper")

    ctx.register_scraper_search_provider(
        provider_id="cilixiong",
        name="磁力熊",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=False,
        description="中文磁力聚合搜索（国内直连）",
    )
    ctx.logger.info("磁力熊 搜索源已加载")


def unregister():
    pass
