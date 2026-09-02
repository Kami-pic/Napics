"""需要「后端真的在跑」的 e2e 测试的跳过标记。

为什么需要它：有一批 e2e 测试直接往 http://127.0.0.1:8000 发请求。后端没起时它们
不是 skip 而是 **error**，而且 test_api_rename 之类在**模块级**就发请求 —— 收集期
就会炸，导致 `pytest tests/` 全量收集根本不可用（AGENTS.md 里那句「必须按文件名
指定测试」就是这么来的）。

用法：
    from test_support.live_backend import requires_live_backend

    @requires_live_backend
    def test_xxx():
        ...

模块级就发请求的文件，在 import 之前加：
    pytestmark = requires_live_backend
并把请求挪进函数里。
"""

import os
import socket
import urllib.parse

import pytest

# e2e 测试约定的后端地址。想指到别处就设 NAPICS_E2E_BASE。
BASE_URL = os.environ.get("NAPICS_E2E_BASE", "http://127.0.0.1:8000")

_probe_cache: dict = {}


def is_backend_live(base_url: str = BASE_URL, timeout: float = 0.4) -> bool:
    """后端端口是否可连。只探一次，结果缓存在进程内。

    刻意只做 TCP connect 而不发 HTTP 请求：探测本身不该有副作用，
    也不该因为某个路由 500 就判定"后端没起"。
    """
    if base_url in _probe_cache:
        return _probe_cache[base_url]

    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            live = True
    except OSError:
        live = False
    _probe_cache[base_url] = live
    return live


requires_live_backend = pytest.mark.skipif(
    not is_backend_live(),
    reason=f"需要后端在 {BASE_URL} 运行（e2e 测试）",
)
