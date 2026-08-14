"""插件守卫 — 根据 installed_plugins 控制功能可用性。

提供轻量查询函数，供路由层和业务层判断某个功能是否可用。
"""

import logging
from typing import List, Set

logger = logging.getLogger(__name__)


def get_installed_plugins() -> List[str]:
    """获取当前已安装的插件列表"""
    try:
        from shared import config_m
        return config_m.config.installed_plugins or []
    except Exception:
        return []


def is_plugin_installed(plugin_id: str) -> bool:
    """检查指定插件是否已安装"""
    return plugin_id in get_installed_plugins()


# ── 插件 ID → 功能映射 ──

# BT 搜索源：每个源一个独立插件，也兼容旧的 search-bt-direct 捆绑包
BT_SOURCE_PLUGIN_MAP = {
    "bitsearch": "search-bitsearch",
    "cilixiong": "search-cilixiong",
    "xl720": "search-xl720",
    "nyaa": "search-nyaa",
    "mikan": "search-mikan",
    "yts": "search-yts",
    "limetorrents": "search-limetorrents",
    "acgrip": "search-acgrip",
    "bangumi_moe": "search-bangumi-moe",
    "eztv": "search-eztv",
    "dmhy": "search-dmhy",
    "1337x": "search-1337x",
}

# 网盘搜索源：每个源一个独立插件，也兼容旧的 search-pan 捆绑包
PAN_SOURCE_PLUGIN_MAP = {
    "pansearch": "search-pansearch",
    "rrdynb": "search-rrdynb",
    "ddys": "search-ddys",
    "pansou": "search-pansou",
    "sites": "search-sites",
    "slowread": "search-slowread",
    "wnsearch": "search-wnsearch",
    "gogopanso": "search-gogopanso",
    "github": "search-github-pan",
}


def get_allowed_bt_sources() -> Set[str]:
    """根据已安装插件返回允许使用的 BT 搜索源名称集合。

    支持三种模式：
    - 旧模式：search-bt-direct 捆绑包（兼容）
    - 新模式：每个源一个独立插件
    - 第三方分组模式：search-bt-mirror / search-bt-movie-tv / search-bt-anime-jp 等
    Prowlarr 需要安装 search-prowlarr 插件。
    """
    installed = get_installed_plugins()
    allowed = set()

    # Prowlarr
    if "search-prowlarr" in installed:
        allowed.add("prowlarr")

    # 旧捆绑包兼容
    if "search-bt-direct" in installed:
        allowed.update(BT_SOURCE_PLUGIN_MAP.keys())

    # 新独立插件
    for source_id, plugin_id in BT_SOURCE_PLUGIN_MAP.items():
        if plugin_id in installed:
            allowed.add(source_id)

    # 第三方分组插件（社区仓库按风险特征分组）
    if "search-bt-mirror" in installed:
        allowed.update(["bitsearch", "1337x", "limetorrents"])
    if "search-bt-movie-tv" in installed:
        allowed.update(["yts", "eztv"])
    if "search-bt-anime-jp" in installed:
        allowed.update(["nyaa", "bangumi_moe"])
    if "search-bt-anime-cn" in installed:
        allowed.update(["mikan", "acgrip", "dmhy"])
    if "search-bt-cn" in installed:
        allowed.update(["cilixiong", "xl720"])

    # 第三方插件注册的搜索源
    try:
        from plugin_context import get_plugin_providers
        for pid, info in get_plugin_providers().items():
            if info["type"] in ("search", "scraper_search"):
                if info.get("plugin_id") in installed:
                    allowed.add(pid)
    except Exception:
        pass

    return allowed


def is_bt_source_allowed(source_name: str) -> bool:
    """检查指定 BT 源是否被允许（对应插件已安装）"""
    return source_name in get_allowed_bt_sources()


def is_pan_search_allowed() -> bool:
    """网盘搜索是否有已安装且策略允许的 Provider。"""
    installed = get_installed_plugins()

    # 内置私有 Pan 清单只在显式开启时允许执行。
    from provider_runtime import allow_private_providers
    if allow_private_providers():
        if "search-pan" in installed:
            return True
        if any(plugin_id in installed for plugin_id in PAN_SOURCE_PLUGIN_MAP.values()):
            return True
        pan_group_plugins = {"search-pan-main", "search-pan-github", "search-pan-resource"}
        if pan_group_plugins.intersection(installed):
            return True

    # 第三方自定义网盘 Provider 使用自身 metadata，不受内置私有清单开关影响。
    try:
        from plugin_context import get_plugin_providers
        return any(
            info.get("type") == "pan_search" and info.get("plugin_id") in installed
            for info in get_plugin_providers().values()
        )
    except Exception:
        return False


def get_allowed_pan_sources() -> Set[str]:
    """根据安装状态、运行时注册和 private 策略返回网盘源。"""
    installed = get_installed_plugins()
    allowed = set()

    from provider_runtime import allow_private_providers
    if allow_private_providers():
        if "search-pan" in installed:
            allowed.update(PAN_SOURCE_PLUGIN_MAP.keys())

        for source_id, plugin_id in PAN_SOURCE_PLUGIN_MAP.items():
            if plugin_id in installed:
                allowed.add(source_id)

        if "search-pan-main" in installed:
            allowed.update(["pansearch", "pansou"])
        if "search-pan-github" in installed:
            allowed.update(["gogopanso", "github"])
        if "search-pan-resource" in installed:
            allowed.update(["rrdynb", "ddys", "sites", "slowread", "wnsearch"])

    try:
        from plugin_context import get_plugin_providers
        for provider_id, info in get_plugin_providers().items():
            if info.get("type") == "pan_search" and info.get("plugin_id") in installed:
                allowed.add(provider_id)
    except Exception:
        pass

    return allowed


def is_metadata_allowed(provider: str) -> bool:
    """元数据源是否可用（tmdb/douban/bangumi）"""
    mapping = {
        "tmdb": "metadata-tmdb",
        "douban": "metadata-douban",
        "bangumi": "metadata-bangumi",
    }
    plugin_id = mapping.get(provider)
    if not plugin_id:
        return False
    return is_plugin_installed(plugin_id)


def is_download_allowed(provider: str) -> bool:
    """下载器是否可用"""
    mapping = {
        "qbittorrent": "download-qbittorrent",
        "qb": "download-qbittorrent",
        "openlist": "download-openlist",
        "alist": "download-openlist",
    }
    plugin_id = mapping.get(provider)
    if not plugin_id:
        return False
    return is_plugin_installed(plugin_id)


def has_any_download_backend() -> bool:
    """是否安装了任何下载后端插件"""
    installed = get_installed_plugins()
    return "download-qbittorrent" in installed or "download-openlist" in installed


def is_feature_allowed(feature: str) -> bool:
    """增强功能是否可用"""
    mapping = {
        "completeness": "feature-completeness",
        "discover": "feature-discover",
        "subscribe": "feature-subscribe",
        "local_match": "feature-local-match",
    }
    plugin_id = mapping.get(feature)
    if not plugin_id:
        return False
    return is_plugin_installed(plugin_id)


# ── RSS 源守卫 ──

# RSS 源 ID → 所属插件 ID
RSS_ANIME_SOURCES = {"mikan", "nyaa", "acgrip", "bangumi_moe", "dmhy"}
RSS_TV_MOVIE_SOURCES = {"eztv", "yts", "prowlarr"}


def get_allowed_rss_sources() -> Set[str]:
    """根据已安装插件返回允许使用的 RSS 源名称集合。"""
    installed = get_installed_plugins()
    allowed = set()
    if "rss-anime" in installed:
        allowed.update(RSS_ANIME_SOURCES)
    if "rss-tv-movie" in installed:
        allowed.update(RSS_TV_MOVIE_SOURCES)

    try:
        from plugin_context import get_plugin_providers
        for provider_id, info in get_plugin_providers().items():
            if info.get("type") == "rss_source" and info.get("plugin_id") in installed:
                allowed.add(info.get("source_id", provider_id))
    except Exception:
        pass

    return allowed


def is_rss_source_allowed(source_name: str) -> bool:
    """检查指定 RSS 源是否被允许"""
    return source_name in get_allowed_rss_sources()


def is_storage_allowed(provider: str = "openlist") -> bool:
    """存储浏览是否可用"""
    mapping = {
        "openlist": "storage-openlist",
        "alist": "storage-openlist",
    }
    plugin_id = mapping.get(provider)
    if not plugin_id:
        return False
    return is_plugin_installed(plugin_id)
