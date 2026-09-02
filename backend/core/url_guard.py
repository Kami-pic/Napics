"""外部 URL 安全校验：阻止 SSRF（服务端请求伪造）。

后端有几个接口会按用户给的 URL 去发请求（图片代理、按 URL 设置海报、拉取插件源）。
如果不校验，攻击者可以让后端去请求内网地址，借后端当跳板探测局域网 —— 比如
`/proxy/image?url=http://127.0.0.1:8080/api/v2/torrents/info` 就能读到 qBittorrent
的接口响应，因为响应体会原样回显给调用方。

防护策略：
- 协议只允许 http / https
- 解析主机名得到 IP，拒绝环回、私有网段、链路本地、保留地址等非公网目标
- 域名会做一次 DNS 解析并检查全部返回地址（防止域名指向内网）

已知局限：解析与实际请求之间存在时间窗，理论上可被 DNS rebinding 绕过。
彻底防御需要在连接层固定 IP，成本高；当前实现足以拦掉常规探测。
"""
import ipaddress
import logging
import socket
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")

# 代码里写死的官方分发域名，跳过 IP 归属判定。
#
# 起因：fake-ip 模式的代理（Clash / Surge）会把这些域名解析到 198.18.0.0/15
# 这类保留段地址（实测 raw.githubusercontent.com -> 198.18.0.73），按 IP 判定
# 会被当成「非公网」拦下 —— 用户装插件时看到的是「插件源地址不被允许」，
# 而真实情况是这份流量本该交给代理转发出去。
#
# 放行它们不会开出内网探测的入口：这批域名不由用户输入决定，攻击者无法让
# 后端借此访问局域网内的任意地址。用户输入的其他域名照旧走完整校验。
_TRUSTED_SOURCE_HOSTS = frozenset({
    "github.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "ghcr.io",
})

# 域名解析结果缓存：host -> (是否公网, 判定时间)
# 图片代理会被首页大量并发调用，避免每次都做 DNS 查询
_resolve_cache: dict = {}
_CACHE_TTL_SECONDS = 300


class UnsafeUrlError(Exception):
    """URL 指向非公网地址或协议不被允许。"""


def _is_public_ip(ip_str: str) -> bool:
    """判断 IP 是否为可对外访问的公网地址。"""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # 覆盖 127.0.0.0/8、10/8、172.16/12、192.168/16、169.254/16、::1、fc00::/7 等
    if (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
        return False
    return True


def _resolve_host_is_public(host: str) -> Tuple[bool, str]:
    """解析主机名并判断所有解析结果是否都是公网地址。

    返回 (是否安全, 失败原因)。
    """
    now = time.time()
    cached = _resolve_cache.get(host)
    if cached and now - cached[1] < _CACHE_TTL_SECONDS:
        return cached[0], "缓存判定为内网地址" if not cached[0] else ""

    # IP 字面量直接判断，不做 DNS
    try:
        ipaddress.ip_address(host)
        ok = _is_public_ip(host)
        _resolve_cache[host] = (ok, now)
        return ok, "" if ok else f"目标是非公网地址: {host}"
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        # DNS 解析失败不代表目标是内网地址，因此这里必须放行。
        # 容器里很常见 DNS 未配置（Temporary failure in name resolution），
        # 若在此拦下，网络故障会被伪装成「URL 不被允许」，把真实原因藏起来。
        # 放行后请求会自然失败，用户看到的是真实的网络错误。
        logger.warning(f"[UrlGuard] 域名 {host} 解析失败，放行交由请求层报错: {e}")
        return True, ""

    addresses = {info[4][0] for info in infos}
    if not addresses:
        return False, "域名未解析到任何地址"

    for addr in addresses:
        if not _is_public_ip(addr):
            _resolve_cache[host] = (False, now)
            return False, f"域名 {host} 指向非公网地址 {addr}"

    _resolve_cache[host] = (True, now)
    return True, ""


def check_external_url(url: str) -> Tuple[bool, str]:
    """校验 URL 可否安全地由后端发起请求。返回 (是否允许, 拒绝原因)。"""
    if not url or not isinstance(url, str):
        return False, "URL 为空"

    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        return False, f"URL 解析失败: {e}"

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"不支持的协议: {parsed.scheme or '(空)'}"

    host = parsed.hostname
    if not host:
        return False, "URL 缺少主机名"

    # 官方分发域名不做 IP 判定，理由见 _TRUSTED_SOURCE_HOSTS
    if host.strip().lower().rstrip(".") in _TRUSTED_SOURCE_HOSTS:
        return True, ""

    return _resolve_host_is_public(host)


def assert_external_url(url: str) -> None:
    """校验失败时抛 UnsafeUrlError。"""
    ok, reason = check_external_url(url)
    if not ok:
        raise UnsafeUrlError(reason)


def is_https_url(url: str) -> bool:
    """判断是否是 https（用于决定能否附带凭据）。"""
    try:
        return urlparse(url.strip()).scheme.lower() == "https"
    except Exception:
        return False


def clear_cache() -> None:
    """清空解析缓存（测试用）。"""
    _resolve_cache.clear()
