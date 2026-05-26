"""Bangumi Moe BT 搜索源插件。

安装后提供：动画 BT 搜索（萌番组，国内直连）
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 Bangumi Moe 搜索源"""
    import importlib
    mod = importlib.import_module("bt_scraper_bangumi_moe")
    scraper_cls = getattr(mod, "BangumiMoeScraper")

    ctx.register_scraper_search_provider(
        provider_id="bangumi_moe",
        name="Bangumi Moe",
        scraper_class=scraper_cls,
        enabled=True,
        supports_proxy=False,
        description="动画 BT 搜索（萌番组，国内直连）",
    )
    ctx.logger.info("Bangumi Moe 搜索源已加载")


def unregister():
    pass
