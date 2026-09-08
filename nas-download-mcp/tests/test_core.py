"""nas-download-mcp 单元测试（todo §17）。

不连真实 napics/qB：纯逻辑（state 映射、约束筛选、白名单）+ mock。
运行：cd nas-download-mcp && python -m pytest tests/ -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Constraints, QbState, Resource, ErrorCode, err  # noqa: E402
from adapters.qb_client import _map_state  # noqa: E402
from adapters.docker_adapter import DockerAdapter  # noqa: E402


# ── qB state → 统一枚举 ──
@pytest.mark.parametrize("raw,progress,expected", [
    ("downloading", 0.3, QbState.DOWNLOADING),
    ("metaDL", 0.0, QbState.DOWNLOADING),
    ("stalledDL", 0.1, QbState.STALLED),
    ("pausedDL", 0.5, QbState.PAUSED),
    ("uploading", 1.0, QbState.COMPLETED),
    ("stalledUP", 1.0, QbState.COMPLETED),
    ("error", 0.2, QbState.ERROR),
    ("missingFiles", 0.0, QbState.ERROR),
    ("weirdstate", 0.4, QbState.UNKNOWN),
])
def test_qb_state_map(raw, progress, expected):
    assert _map_state(raw, progress) == expected


def test_progress_100_forces_completed():
    # progress==1 无论 state 都算完成
    assert _map_state("downloading", 1.0) == QbState.COMPLETED


# ── 约束筛选（4k / <50g）──
def _match(res, c):
    from workflow import _res_matches
    return _res_matches(res, c)


def test_constraint_size():
    c = Constraints(max_size_gb=50)
    assert _match(Resource(title="a", size_gb=20), c) is True
    assert _match(Resource(title="b", size_gb=90), c) is False
    # size 未知不拦
    assert _match(Resource(title="c", size_gb=None), c) is True


def test_constraint_4k():
    c = Constraints(min_resolution="4k")
    assert _match(Resource(title="a", resolution="2160p"), c) is True
    assert _match(Resource(title="b", resolution="1080p"), c) is False


def test_constraint_none_allows_all():
    assert _match(Resource(title="a", resolution="480p", size_gb=999), None) is True


# ── magnet 判定 ──
def test_is_magnet():
    assert Resource(title="a", download_url="magnet:?xt=urn:btih:abc").is_magnet() is True
    assert Resource(title="b", download_url="http://x/y.torrent").is_magnet() is False


# ── docker 白名单 ──
def test_docker_whitelist_reject():
    d = DockerAdapter.__new__(DockerAdapter)  # 不触发 SDK 连接
    d._client = None
    with pytest.raises(PermissionError):
        d._check("evil-container")


def test_docker_whitelist_accept_logical_and_real():
    d = DockerAdapter.__new__(DockerAdapter)
    d._client = None
    assert d._check("napics") == "kami-pic"
    assert d._check("kami-pic") == "kami-pic"
    assert d._check("prowlarr") == "prowlarr"


# ── 错误契约 ──
def test_err_shape():
    e = err(ErrorCode.NO_RESULTS, "无结果", retryable=False)
    assert e["error"]["code"] == "NO_RESULTS"
    assert e["error"]["retryable"] is False
