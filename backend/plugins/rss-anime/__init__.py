"""动画 RSS 源包插件 — 蜜柑/Nyaa/ACG.RIP/Bangumi Moe/动漫花园。

通过 register(ctx) 注册动画类 RSS 源的类到 plugin registry。
rss_provider_factory 从 registry 获取源工厂。
"""

import os
import sys

# 将 sources/ 目录加入 sys.path
_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)


# 源 ID → (模块名, 类名)
_ANIME_RSS_SOURCES = {
    "mikan": ("rss_source_mikan", "MikanRSSSource"),
    "nyaa": ("rss_source_nyaa", "NyaaRSSSource"),
    "acgrip": ("rss_source_acgrip", "ACGRipRSSSource"),
    "bangumi_moe": ("rss_source_bangumi_moe", "BangumiMoeRSSSource"),
    "dmhy": ("rss_source_dmhy", "DMHYRSSSource"),
}


def register(ctx):
    """插件注册入口 — 注册 5 个动画 RSS 源。"""
    import importlib
    from plugin_context import _plugin_providers

    for source_id, (module_name, class_name) in _ANIME_RSS_SOURCES.items():
        mod = importlib.import_module(module_name)
        source_cls = getattr(mod, class_name)

        # 存储到 plugin_providers 供 rss_provider_factory 使用
        _plugin_providers[f"rss_{source_id}"] = {
            "type": "rss_source",
            "source_id": source_id,
            "source_class": source_cls,
            "plugin_id": "rss-anime",
        }

    ctx.logger.info(f"动画 RSS 源包已注册 {len(_ANIME_RSS_SOURCES)} 个源")


def unregister():
    """卸载时注销"""
    pass
