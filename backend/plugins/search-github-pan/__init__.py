"""GitHub 网盘仓库 网盘搜索源插件。

安装后提供：GitHub 夸克/阿里资源仓库索引
"""

import os
import sys

_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


def register(ctx):
    """注册 GitHub 网盘仓库 网盘搜索源"""
    import importlib
    mod = importlib.import_module("pan_scraper_github")
    scraper_cls = getattr(mod, "GitHubPanScraper")

    ctx.register_pan_search_provider(
        provider_id="github",
        name="GitHub 网盘仓库",
        search_fn=None,
        enabled=True,
        description="GitHub 夸克/阿里资源仓库索引",
    )
    # 存储 scraper_class 供 pan_search_service 使用
    from plugin_context import _plugin_providers
    _plugin_providers["github"]["scraper_class"] = scraper_cls
    ctx.logger.info("GitHub 网盘仓库 网盘搜索源已加载")


def unregister():
    pass
