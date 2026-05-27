"""动漫花园 BT 搜索源插件。

安装后提供：中文动画 BT 搜索（需代理，CF 保护）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 动漫花园 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_dmhy")
    scraper_cls = getattr(mod, "DMHYScraper")

    ctx.register_scraper_search_provider(
        provider_id="dmhy",
        name="动漫花园",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=True,
        description="中文动画 BT 搜索（需代理，CF 保护）",
    )
    ctx.logger.info("动漫花园 搜索源已加载")


def unregister():
    pass
