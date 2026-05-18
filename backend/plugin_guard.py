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

# BT 搜索源：search-prowlarr 控制 Prowlarr，search-bt-direct 控制所有直搜源
BT_DIRECT_SOURCES = {
    "bitsearch", "cilixiong", "xl720", "nyaa", "mikan",
    "yts", "limetorrents", "acgrip", "bangumi_moe", "eztv", "dmhy", "1337x",
}

# 网盘搜索源：search-pan 控制所有网盘源
PAN_SOURCES = {"pansearch", "gogopanso", "github", "rrdynb", "ddys", "pansou"}


def get_allowed_bt_sources() -> Set[str]:
    """根据已安装插件返回允许使用的 BT 搜索源名称集合。

    Prowlarr 需要安装 search-prowlarr 插件。
    直搜源需要安装 search-bt-direct 插件。
    """
    installed = get_installed_plugins()
    allowed = set()
    if "search-prowlarr" in installed:
        allowed.add("prowlarr")
    if "search-bt-direct" in installed:
        allowed.update(BT_DIRECT_SOURCES)

    # 第三方插件注册的搜索源：只要对应插件已安装就允许
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
    """网盘搜索是否可用"""
    return is_plugin_installed("search-pan")


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
