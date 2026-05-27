"""BT 直搜源包插件 — 内置 12 个直搜源。

通过 register(ctx) 注册所有 BT 搜索源的 scraper 类到 plugin registry。
bt_search_provider_factory 从 registry 获取 scraper 工厂，不再依赖 shared.py getter。
"""

import os
import sys

# 将 sources/ 目录加入 sys.path，确保 scraper 文件可被 import
_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


# 源 ID → (模块名, 类名, 是否需要代理)
_BT_SOURCES = {
    "bitsearch": ("bt_scraper_bitsearch", "BitsearchScraper", True),
    "cilixiong": ("bt_scraper_cilixiong", "CilixiongScraper", False),
    "xl720": ("bt_scraper_xl720", "XL720Scraper", False),
    "nyaa": ("bt_scraper_nyaa", "NyaaScraper", True),
    "mikan": ("bt_scraper_mikan", "MikanScraper", True),
    "yts": ("bt_scraper_yts", "YTSScraper", True),
    "limetorrents": ("bt_scraper_limetorrents", "LimeTorrentsScraper", True),
    "acgrip": ("bt_scraper_acgrip", "ACGRipScraper", False),
    "bangumi_moe": ("bt_scraper_bangumi_moe", "BangumiMoeScraper", False),
    "eztv": ("bt_scraper_eztv", "EZTVScraper", True),
    "dmhy": ("bt_scraper_dmhy", "DMHYScraper", True),
    "1337x": ("bt_scraper_1337x", "X1337xScraper", True),
}


def register(ctx):
    """插件注册入口 — 注册 12 个 BT 直搜源的 scraper 类。

    注册方式：register_scraper_search_provider(provider_id, name, scraper_class)
    scraper_class 是延迟加载的类引用，首次调用时才 import 模块。
    """
    import importlib

    for source_id, (module_name, class_name, supports_proxy) in _BT_SOURCES.items():
        # 延迟加载：首次实例化时才 import 对应模块
        mod = importlib.import_module(module_name)
        scraper_cls = getattr(mod, class_name)

        ctx.register_scraper_search_provider(
            provider_id=source_id,
            name=source_id,
            scraper_class=scraper_cls,
            enabled=True,
            supports_proxy=supports_proxy,
            description=f"BT 直搜源: {source_id}",
        )

    ctx.logger.info(f"BT 直搜源包已注册 {len(_BT_SOURCES)} 个源")


def unregister():
    """插件卸载时调用"""
    pass
