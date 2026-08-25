"""`/playback/stream` 的 HTTP Range 语义测试。

修复前的实际行为（每条都是真实缺陷，不是假想）：
`bytes=-500` 返回文件**开头**、越界返回 206、倒置产生**负 Content-Length**、
空文件产出 `bytes 0--1/0`、多段 Range 抛 ValueError 后回退成整文件 206。

插件目录不在 sys.path，模块按文件路径加载；白名单用 monkeypatch 绕开，
不动 config.json 的 scan_paths。
"""
import importlib.util
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _load():
    init_dir = os.path.join(_BACKEND, "plugins", "feature-player")
    if init_dir not in sys.path:
        sys.path.insert(0, init_dir)
    spec = importlib.util.spec_from_file_location(
        "pb_range_under_test", os.path.join(init_dir, "playback_routes.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pb = _load()

BODY = bytes(range(256)) * 8      # 2048 字节，内容可按偏移逐字节验证
SIZE = len(BODY)


@pytest.fixture
def client(monkeypatch):
    # 白名单绕过：不改 NAPICS_DATA_DIR 下的 scan_paths
    monkeypatch.setattr(pb, "guard_path", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(pb.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def video(tmp_path):
    p = tmp_path / "sample.mp4"
    p.write_bytes(BODY)
    return str(p)


@pytest.fixture
def empty_video(tmp_path):
    p = tmp_path / "empty.mp4"
    p.write_bytes(b"")
    return str(p)


def _get(client, path, range_header=None):
    headers = {"Range": range_header} if range_header else {}
    return client.get("/playback/stream", params={"path": path}, headers=headers)


# ── 七个用例 ──

def test_no_range_returns_full_200(client, video):
    r = _get(client, video)
    assert r.status_code == 200
    assert r.headers["content-length"] == str(SIZE)
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["content-type"].startswith("video/mp4")
    assert r.content == BODY


def test_explicit_range_returns_206_with_content_range(client, video):
    r = _get(client, video, "bytes=0-99")
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-99/{SIZE}"
    assert r.headers["content-length"] == "100"
    assert r.content == BODY[0:100]


def test_suffix_range_returns_tail_not_head(client, video):
    """修复前：`bytes=-500` 被当成 0-500，返回的是文件开头"""
    r = _get(client, video, "bytes=-500")
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes {SIZE - 500}-{SIZE - 1}/{SIZE}"
    assert r.headers["content-length"] == "500"
    assert r.content == BODY[-500:]


def test_open_ended_range_reaches_eof(client, video):
    r = _get(client, video, "bytes=100-")
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 100-{SIZE - 1}/{SIZE}"
    assert r.headers["content-length"] == str(SIZE - 100)
    assert r.content == BODY[100:]


def test_out_of_bounds_start_returns_416(client, video):
    """修复前：start 被 clamp 到 size-1 后返回 206，客户端拿到错位数据"""
    r = _get(client, video, f"bytes={SIZE + 10}-{SIZE + 20}")
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{SIZE}"


def test_inverted_range_returns_416(client, video):
    """修复前：产生负 Content-Length"""
    r = _get(client, video, "bytes=500-100")
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{SIZE}"


def test_empty_file_range_returns_416(client, empty_video):
    """修复前：产出非法的 `Content-Range: bytes 0--1/0`"""
    r = _get(client, empty_video, "bytes=0-99")
    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */0"


# ── 附加：多段与非法语法不得伪装成 206 全量 ──

def test_multi_range_serves_first_part_only(client, video):
    """修复前：抛 ValueError 后回退成「206 + 整个文件」"""
    r = _get(client, video, "bytes=0-1,5-6")
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-1/{SIZE}"
    assert r.content == BODY[0:2]


@pytest.mark.parametrize("bad", ["bytes=abc-def", "items=0-99", "bytes=", "0-99"])
def test_malformed_range_is_ignored_and_returns_200(client, video, bad):
    """RFC 9110：语法非法的 Range 头必须被忽略，按完整响应处理"""
    r = _get(client, video, bad)
    assert r.status_code == 200
    assert r.headers["content-length"] == str(SIZE)
    assert "content-range" not in r.headers
    assert r.content == BODY


def test_head_keeps_full_length_and_accept_ranges(client, video):
    r = client.head("/playback/stream", params={"path": video})
    assert r.status_code == 200
    assert r.headers["content-length"] == str(SIZE)
    assert r.headers["accept-ranges"] == "bytes"


def test_zero_length_suffix_range_returns_416(client, video):
    """`bytes=-0` 请求「末尾 0 字节」，语法合法但不可满足"""
    r = _get(client, video, "bytes=-0")
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{SIZE}"
