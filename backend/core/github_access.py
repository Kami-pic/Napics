"""GitHub 访问助手：官方地址不通时自动回退到镜像。

背景：国内直连 raw.githubusercontent.com / github.com 经常超时，
导致插件源拉取与插件安装完全不可用（真机报 Read timed out）。

策略：官方地址优先，失败（超时/连接错误）时依次尝试镜像。
镜像列表可通过 config.github_mirrors 覆盖；设为空列表即关闭回退。

安全说明：镜像由第三方运营，理论上可能篡改内容。因此：
- 官方地址始终排在第一位，只有连不上才回退
- 插件包若提供了 sha256，安装流程仍会校验（见 plugin_manager）
- 用户可通过配置关闭镜像回退
"""
import logging
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# 默认镜像。前缀型镜像用 {url} 占位表示「把完整原始 URL 拼在后面」
_DEFAULT_RAW_MIRRORS = [
    "https://raw.githubusercontent.com",   # 官方，始终第一
    "https://raw.gitmirror.com",
    "https://ghproxy.net/https://raw.githubusercontent.com",
]

_DEFAULT_REPO_MIRRORS = [
    "https://github.com",                  # 官方，始终第一
    "https://ghproxy.net/https://github.com",
    "https://gh-proxy.com/https://github.com",
]


def _mirror_candidates(url: str, mirrors: List[str], official_host: str) -> List[str]:
    """把原始 URL 改写成各镜像上的等价地址"""
    candidates = []
    for base in mirrors:
        if base.rstrip("/").endswith(official_host.rstrip("/")):
            # 同构替换：https://raw.githubusercontent.com/a/b -> <base>/a/b
            candidates.append(url.replace(official_host, base.rstrip("/"), 1))
        else:
            candidates.append(url.replace(official_host, base.rstrip("/"), 1))
    # 去重并保持顺序
    seen = set()
    result = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def build_candidates(url: str, mirrors: Optional[List[str]] = None) -> List[str]:
    """给定 GitHub URL，返回按优先级排列的候选地址（含官方与镜像）。

    mirrors 为 None 表示用内置默认列表；
    显式传空列表表示关闭镜像回退，只用官方地址（注意不能用 `or` 判断，
    空列表是 falsy，会被误当成未配置）。
    """
    if "raw.githubusercontent.com" in url:
        m = _DEFAULT_RAW_MIRRORS if mirrors is None else mirrors
        if not m:
            return [url]
        return _mirror_candidates(url, m, "https://raw.githubusercontent.com")
    if "github.com" in url:
        m = _DEFAULT_REPO_MIRRORS if mirrors is None else mirrors
        if not m:
            return [url]
        return _mirror_candidates(url, m, "https://github.com")
    return [url]


def get(url: str, *, timeout: int = 10, proxies=None, headers=None,
        mirrors: Optional[List[str]] = None) -> Tuple[Optional[requests.Response], str]:
    """请求 GitHub 资源，官方不通时自动回退镜像。

    返回 (response, 实际使用的 url)；全部失败时返回 (None, 最后的错误描述)。
    """
    candidates = build_candidates(url, mirrors)
    last_err = ""

    for idx, candidate in enumerate(candidates):
        try:
            resp = requests.get(candidate, timeout=timeout, proxies=proxies,
                                headers=headers or {"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            if idx > 0:
                logger.info(f"[GitHubAccess] 官方地址不通，已通过镜像获取: {candidate}")
            return resp, candidate
        except requests.exceptions.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            if idx < len(candidates) - 1:
                logger.info(f"[GitHubAccess] {candidate} 失败({type(e).__name__})，尝试下一个镜像")
            continue

    logger.warning(f"[GitHubAccess] 全部候选地址均失败: {url} — {last_err}")
    return None, last_err
