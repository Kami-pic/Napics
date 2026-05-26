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

    支持两种模式：
    - 旧模式：search-bt-direct 捆绑包（兼容）
    - 新模式：每个源一个独立插件
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
    """网盘搜索是否可用（任意网盘源插件已安装）"""
    installed = get_installed_plugins()
    # 旧捆绑包兼容
    if "search-pan" in installed:
        return True
    # 新独立插件：任意一个网盘源安装即可
    for plugin_id in PAN_SOURCE_PLUGIN_MAP.values():
        if plugin_id in installed:
            return True
    return False


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
