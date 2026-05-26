"""网盘搜索插件 — 9 个网盘源聚合搜索。

通过 register(ctx) 注册所有网盘搜索源的 scraper 类到 plugin registry。
pan_search_service 从 registry 获取 scraper，不再直接 import。
"""

import os
import sys

# 将 sources/ 目录加入 sys.path
_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


# 源 ID → (模块名, 类名)
_PAN_SOURCES = {
    "pansearch": ("pan_scraper_pansearch", "PanSearchScraper"),
    "rrdynb": ("pan_scraper_rrdynb", "RrdynbScraper"),
    "ddys": ("pan_scraper_ddys", "DdysScraper"),
    "pansou": ("pan_scraper_pansou", "PanSouClient"),
    "sites": ("pan_scraper_sites", "MultiSiteScraper"),
    "slowread": ("pan_scraper_slowread", "SlowreadScraper"),
    "wnsearch": ("pan_scraper_wnsearch", "WnSearchScraper"),
    "gogopanso": ("pan_scraper_gogopanso", "GogoPansoScraper"),
    "github": ("pan_scraper_github", "GitHubPanScraper"),
}


def register(ctx):
    """插件注册入口 — 注册 9 个网盘搜索源的 scraper 类。"""
    import importlib

    for source_id, (module_name, class_name) in _PAN_SOURCES.items():
        mod = importlib.import_module(module_name)
        scraper_cls = getattr(mod, class_name)

        ctx.register_pan_search_provider(
            provider_id=source_id,
            name=source_id,
            search_fn=None,  # 不用 search_fn，用 scraper_class
            enabled=True,
            description=f"网盘搜索源: {source_id}",
        )
        # 额外存储 scraper_class 供 pan_search_service 使用
        from plugin_context import _plugin_providers
        _plugin_providers[source_id]["scraper_class"] = scraper_cls

    ctx.logger.info(f"网盘搜索源包已注册 {len(_PAN_SOURCES)} 个源")


def unregister():
    """卸载时注销"""
    pass
