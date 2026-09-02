"""目录树节点的 path 必须是**真实**绝对路径。

原来是 `os.path.join(scan_paths[0], 相对路径)` 拼的 —— 只有当这个文件恰好来自
第一个扫描路径时才对。文件来自 scan_paths[1..] 或某个虚拟库时，拼出来的是文件
系统上不存在的路径。而前端的「查看 / 定位到目录」是拿真实路径（下载任务的
save_path、发现条目的 local_folder）去树里比对的，假路径必然匹配不上 ——
用户看到的就是「点了没反应」。
"""
import os
from types import SimpleNamespace

import pytest

from routes import library_tree
from routes.library_tree import _build_real_node_paths


def _video(file_path: str, folder_name: str) -> dict:
    return {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "folder_name": folder_name,
        "height": 1080,
    }


# ── _build_real_node_paths ──

def test_derives_every_level_from_file_path():
    videos = [_video(r"E:\影视2\电影\某片 (2024)\某片.mkv", r"电影\某片 (2024)")]
    got = _build_real_node_paths(videos)
    assert got["电影"] == r"E:\影视2\电影"
    assert got["电影/某片 (2024)"] == r"E:\影视2\电影\某片 (2024)"


def test_ignores_entries_whose_folder_name_is_out_of_sync():
    """folder_name 和 file_path 对不上时不采信 —— 宁可退回旧拼法，
    也不要往树上写一个更离谱的路径。"""
    videos = [_video(r"E:\影视2\电影\真实目录\某片.mkv", r"电影\对不上的名字")]
    assert _build_real_node_paths(videos) == {}


def test_skips_entries_without_file_path():
    """老条目可能没有 file_path。"""
    assert _build_real_node_paths([{"folder_name": "电影"}]) == {}


def test_first_value_wins_and_stays_consistent():
    videos = [
        _video(r"E:\影视2\电影\某片\a.mkv", r"电影\某片"),
        _video(r"E:\影视2\电影\某片\b.mkv", r"电影\某片"),
    ]
    got = _build_real_node_paths(videos)
    assert got["电影/某片"] == r"E:\影视2\电影\某片"


def test_handles_unc_paths():
    videos = [_video(r"\\niuniuos\video\电影\某片\a.mkv", r"电影\某片")]
    got = _build_real_node_paths(videos)
    assert got["电影"] == r"\\niuniuos\video\电影"
    assert got["电影/某片"] == r"\\niuniuos\video\电影\某片"


# ── 端到端：整棵树 ──

@pytest.fixture
def tree_with_two_scan_roots(monkeypatch):
    """两个扫描路径，第二个下面也有片子 —— 这是老 bug 的触发条件。"""
    videos = [
        _video(r"D:\影视\电影\第一个根的片\a.mkv", r"电影\第一个根的片"),
        _video(r"E:\影视2\电影\第二个根的片\b.mkv", r"电影\第二个根的片"),
    ]
    fake = SimpleNamespace(
        load_library=lambda: videos,
        config=SimpleNamespace(
            scan_paths=[r"D:\影视", r"E:\影视2"],
            media_libraries=[],
            category_tags={},
        ),
        mutate_library=lambda fn: False,
    )
    monkeypatch.setattr(library_tree, "config_m", fake)
    return library_tree.get_library_tree()


def _find(node, name):
    if node.get("name") == name:
        return node
    for child in node.get("children") or []:
        found = _find(child, name)
        if found:
            return found
    return None


def test_node_under_second_scan_root_gets_its_real_path(tree_with_two_scan_roots):
    """这条是老 bug 的直接复现：第二个扫描路径下的节点，
    原来 path 会被拼成 D:\\影视\\电影\\第二个根的片 —— 一个不存在的路径。"""
    node = _find(tree_with_two_scan_roots, "第二个根的片")
    assert node is not None
    assert node["path"] == r"E:\影视2\电影\第二个根的片"
    assert not node["path"].startswith(r"D:\影视")


def test_node_under_first_scan_root_unchanged(tree_with_two_scan_roots):
    node = _find(tree_with_two_scan_roots, "第一个根的片")
    assert node is not None
    assert node["path"] == r"D:\影视\电影\第一个根的片"


def test_shared_top_level_node_keeps_a_real_path(tree_with_two_scan_roots):
    """两个根下都有「电影」这一级，节点会被合并成一个。

    合并后 path 只能是其中之一 —— 这是 folder_name 建树的固有性质（同名相对目录
    会合并）。要求是它必须指向一个**真实存在过的**目录，而不是拼出来的。
    """
    node = _find(tree_with_two_scan_roots, "电影")
    assert node is not None
    assert node["path"] in (r"D:\影视\电影", r"E:\影视2\电影")


def test_virtual_library_node_uses_real_path(monkeypatch):
    """虚拟库：folder_name 第一段是库名，节点 path 要落在库的真实路径上。"""
    videos = [_video(r"F:\anime\某番\S01\01.mkv", r"动画番\某番\S01")]
    fake = SimpleNamespace(
        load_library=lambda: videos,
        config=SimpleNamespace(
            scan_paths=[],
            media_libraries=[SimpleNamespace(
                name="动画番", paths=[r"F:\anime"], category_tag="anime_tv", exclude_dirs=[],
            )],
            category_tags={},
        ),
        mutate_library=lambda fn: False,
    )
    monkeypatch.setattr(library_tree, "config_m", fake)
    tree = library_tree.get_library_tree()

    season = _find(tree, "S01")
    assert season is not None
    assert season["path"] == r"F:\anime\某番\S01"
