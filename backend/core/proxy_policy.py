"""代理分流策略：国内站点直连，境外站点走代理。

解决的问题：http_proxy 是一个全局配置，原先所有请求都走它，没有分流。
于是出现「要么这个能用、要么那个能用」：
- 配了代理：TMDB 通了，但豆瓣图片 / Bangumi 被强行绕出国，反而失败
- 不配代理：豆瓣通了，但 TMDB 完全不可用

正确做法是按目标域名决定：国内能直连的站点不要走代理，
需要翻越的站点才走。用户仍然只配一个 http_proxy，分流由这里负责。

直连列表可通过 config.direct_domains 追加（不覆盖内置项）。
"""
import logging
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 国内可直连、且走代理反而更差（更慢/被拒/触发风控）的域名后缀
_BUILTIN_DIRECT_SUFFIXES: tuple = (
    # 豆瓣（含图片 CDN）
    "douban.com", "doubanio.com",
    # Bangumi
    "bgm.tv", "bangumi.tv",
    # 常见国内 CDN / 图床
    "hdslb.com", "bilivideo.com", "biliimg.com",
    "sinaimg.cn", "qpic.cn", "qlogo.cn",
    "alicdn.com", "aliyuncs.com",
    "126.net", "127.net", "163.com",
    "qq.com", "tencentcs.com",
    "baidu.com", "bdstatic.com", "baidupcs.com",
    "quark.cn", "quarkcdn.com",
    "115.com", "115cdn.com",
    "aliyundrive.com", "alipan.com",
    "cn",  # 兜底：.cn 域名一律直连
)


def _extra_direct_suffixes() -> List[str]:
    """读取用户在配置里追加的直连域名"""
    try:
        from shared import config_m
        extra = getattr(config_m.config, "direct_domains", None) or []
        return [str(d).strip().lower().lstrip(".") for d in extra if str(d).strip()]
    except Exception:
        return []


def is_direct_host(host: str, extra: Optional[Iterable[str]] = None) -> bool:
    """判断该主机是否应当直连（不走代理）"""
    if not host:
        return False
    h = host.strip().lower().rstrip(".")

    # 本机与内网一律直连
    if h in ("localhost", "127.0.0.1", "::1", "host.docker.internal"):
        return True

    suffixes = list(_BUILTIN_DIRECT_SUFFIXES)
    suffixes.extend(extra if extra is not None else _extra_direct_suffixes())

    for suf in suffixes:
        if h == suf or h.endswith("." + suf):
            return True
    return False


def should_use_proxy(url: str, extra_direct: Optional[Iterable[str]] = None) -> bool:
    """给定 URL，判断是否应该走代理"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return not is_direct_host(host, extra_direct)


def proxies_for(url: str, proxy: str = "",
                extra_direct: Optional[Iterable[str]] = None) -> Optional[Dict[str, str]]:
    """按目标域名返回 requests 用的 proxies 参数。

    未配置代理时返回 None；目标属于直连列表时也返回 None。
    """
    p = (proxy or "").strip()
    if not p:
        return None
    if not should_use_proxy(url, extra_direct):
        return None
    return {"http": p, "https": p}


def proxies_from_config(url: str) -> Optional[Dict[str, str]]:
    """便捷入口：自动读取配置里的 http_proxy 再做分流判断"""
    try:
        from shared import config_m
        proxy = getattr(config_m.config, "http_proxy", "") or ""
    except Exception:
        proxy = ""
    return proxies_for(url, proxy)


def proxies_for_plugin(plugin_id: str, url: str) -> Optional[Dict[str, str]]:
    """按插件级代理覆盖返回 proxies 参数。

    优先级：plugin_proxy_overrides[plugin_id] > 域名分流 > 无代理。
    - "direct" → 返回 None（强制直连）
    - "proxy"  → 返回 {"http": proxy, "https": proxy}（强制走代理）
    - "auto" 或未配置 → 走正常域名分流（proxies_from_config）
    """
    try:
        from shared import config_m
        overrides = getattr(config_m.config, "plugin_proxy_overrides", None) or {}
        mode = overrides.get(plugin_id, "auto")
        proxy = getattr(config_m.config, "http_proxy", "") or ""

        if mode == "direct":
            return None
        if mode == "proxy":
            return {"http": proxy, "https": proxy} if proxy else None
        # auto: 走域名分流
        return proxies_for(url, proxy)
    except Exception:
        return proxies_from_config(url)
