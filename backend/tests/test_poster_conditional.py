"""海报接口条件请求（304）验证：命中 ETag 时不重复传输图片内容"""
import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

from routes.poster import _if_none_match_hit


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


# ── ETag 匹配逻辑 ──

def test_if_none_match_exact():
    req = _FakeRequest({"if-none-match": '"123-456"'})
    assert _if_none_match_hit(req, '"123-456"') is True


def test_if_none_match_weak_prefix():
    req = _FakeRequest({"if-none-match": 'W/"123-456"'})
    assert _if_none_match_hit(req, '"123-456"') is True


def test_if_none_match_multiple_values():
    req = _FakeRequest({"if-none-match": '"aaa", "123-456", "bbb"'})
    assert _if_none_match_hit(req, '"123-456"') is True


def test_if_none_match_wildcard():
    req = _FakeRequest({"if-none-match": "*"})
    assert _if_none_match_hit(req, '"anything"') is True


def test_if_none_match_miss():
    req = _FakeRequest({"if-none-match": '"old-etag"'})
    assert _if_none_match_hit(req, '"new-etag"') is False


def test_if_none_match_absent_header():
    assert _if_none_match_hit(_FakeRequest({}), '"123"') is False


def test_if_none_match_no_request():
    assert _if_none_match_hit(None, '"123"') is False


# ── 端到端：真实海报文件 ──

@pytest.fixture
def poster_dir(monkeypatch):
    """临时海报目录，并把它注册进媒体库白名单（路由层有路径校验）"""
    d = tempfile.mkdtemp(prefix="napics_poster_")
    # 造一个够大的假图片，确保能观察到 body 差异
    with open(os.path.join(d, "poster.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"x" * 5000)

    import shared
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [d])
    shared.invalidate_allowed_roots_cache()
    try:
        yield d
    finally:
        shared.invalidate_allowed_roots_cache()
        shutil.rmtree(d, ignore_errors=True)


def test_poster_200_then_304(poster_dir):
    """首次 200 返回完整图片，带 ETag 复请求返回 304 且 body 为空"""
    from main import app
    client = TestClient(app)

    first = client.get("/scrape/poster", params={"path": poster_dir})
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert len(first.content) == 5004
    etag = first.headers["etag"]
    assert etag

    second = client.get(
        "/scrape/poster",
        params={"path": poster_dir},
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == etag


def test_poster_stale_etag_returns_full_content(poster_dir):
    """ETag 不匹配时必须返回完整内容（例如海报被重新刮削过）"""
    from main import app
    client = TestClient(app)

    resp = client.get(
        "/scrape/poster",
        params={"path": poster_dir},
        headers={"If-None-Match": '"stale-0"'},
    )
    assert resp.status_code == 200
    assert len(resp.content) == 5004


def test_poster_etag_changes_after_file_rewrite(poster_dir):
    """文件内容变化后 ETag 必须变，避免浏览器一直用旧图"""
    from main import app
    client = TestClient(app)

    first = client.get("/scrape/poster", params={"path": poster_dir})
    old_etag = first.headers["etag"]

    # 改写文件（长度变化 → size 变化 → ETag 变化）
    with open(os.path.join(poster_dir, "poster.jpg"), "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"y" * 8000)

    second = client.get(
        "/scrape/poster",
        params={"path": poster_dir},
        headers={"If-None-Match": old_etag},
    )
    assert second.status_code == 200
    assert second.headers["etag"] != old_etag
    assert len(second.content) == 8004


def test_missing_poster_still_404(monkeypatch):
    """没有海报的目录行为不变，仍是 404"""
    from main import app
    import shared
    client = TestClient(app)

    d = tempfile.mkdtemp(prefix="napics_empty_")
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [d])
    shared.invalidate_allowed_roots_cache()
    try:
        resp = client.get("/scrape/poster", params={"path": d})
        assert resp.status_code == 404
    finally:
        shared.invalidate_allowed_roots_cache()
        shutil.rmtree(d, ignore_errors=True)
