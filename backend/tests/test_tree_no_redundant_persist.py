"""/library/tree 幂等性验证：重复请求不应反复触发全库落盘

目录树里的清洗名"自愈"逻辑原本无条件覆盖并置脏标记，导致每次刷新首页
都会 save_library 一次（连带重建媒体库索引 + 触发完整度刷新）。
本测试锁定：第一次请求可以落盘补全，之后值没变就不再落盘，
且两次请求返回的树结构完全一致。
"""
import copy
import json
import os

import pytest
from fastapi.testclient import TestClient

SANDBOX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sandbox_real"
)

pytestmark = pytest.mark.skipif(
    not os.path.isdir(SANDBOX), reason="需要 sandbox_real 测试媒体库"
)


def _fake_library():
    """构造指向 sandbox_real 真实目录的媒体库条目"""
    return [
        {
            "file_path": os.path.join(SANDBOX, "动画电影", "你的名字。 Your Name. (2016) 1080p", "movie.mkv"),
            "file_name": "Your.Name.2016.1080p.BluRay.x264.mkv",
            "folder_name": os.path.join("动画电影", "你的名字。 Your Name. (2016) 1080p"),
            "height": 1080,
            "size_gb": 4.2,
        },
        {
            "file_path": os.path.join(SANDBOX, "动画电影", "红辣椒 Paprika (2006)", "movie.mkv"),
            "file_name": "Paprika.2006.1080p.x265.mkv",
            "folder_name": os.path.join("动画电影", "红辣椒 Paprika (2006)"),
            "height": 1080,
            "size_gb": 3.1,
        },
    ]


@pytest.fixture
def client_with_lib(monkeypatch):
    """接管 config_m 的库读写，统计 save_library 次数"""
    import shared
    from main import app

    state = {"lib": _fake_library(), "saves": 0}

    def fake_load_library():
        # 每次返回独立副本，保持与真实实现相同的语义
        return copy.deepcopy(state["lib"])

    def fake_save_library(data):
        state["saves"] += 1
        state["lib"] = copy.deepcopy(data)

    monkeypatch.setattr(shared.config_m, "load_library", fake_load_library)
    monkeypatch.setattr(shared.config_m, "save_library", fake_save_library)
    monkeypatch.setattr(shared.config_m.config, "scan_paths", [SANDBOX])
    monkeypatch.setattr(shared.config_m.config, "media_libraries", [])

    yield TestClient(app), state


def test_repeated_tree_requests_converge(client_with_lib):
    """连续三次请求：落盘次数必须收敛（不随请求次数线性增长）"""
    client, state = client_with_lib

    r1 = client.get("/library/tree")
    assert r1.status_code == 200
    saves_after_first = state["saves"]

    r2 = client.get("/library/tree")
    assert r2.status_code == 200
    r3 = client.get("/library/tree")
    assert r3.status_code == 200

    # 第二、三次不应再落盘：说明清洗名已收敛，不再重复写
    assert state["saves"] == saves_after_first, (
        f"重复请求仍在落盘：首次 {saves_after_first} 次，三次后 {state['saves']} 次"
    )


def test_tree_output_is_stable(client_with_lib):
    """两次请求返回的树结构必须完全一致（保证优化没有改变输出）"""
    client, _ = client_with_lib

    first = client.get("/library/tree").json()
    second = client.get("/library/tree").json()

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == \
        json.dumps(second, sort_keys=True, ensure_ascii=False)


def test_tree_contains_expected_nodes(client_with_lib):
    """基本正确性：树里能找到构造的分类节点与视频"""
    client, _ = client_with_lib
    tree = client.get("/library/tree").json()

    names = [c["name"] for c in tree.get("children", [])]
    assert "动画电影" in names

    anime = next(c for c in tree["children"] if c["name"] == "动画电影")
    child_names = [c["name"] for c in anime.get("children", [])]
    assert any("你的名字" in n for n in child_names)
    assert anime["video_count"] == 2
