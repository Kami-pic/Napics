"""plan_tree 预览测试：验证字幕和附属文件在预览中正确展示目标位置。"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from routes.relocate import _build_plan_tree


def _find_node(tree, name, depth=3):
    """在树中递归查找指定名称的节点。"""
    for node in tree:
        if node.get("name") == name:
            return node
        if depth > 0 and "children" in node:
            found = _find_node(node["children"], name, depth - 1)
            if found:
                return found
    return None


def _collect_all_names(tree, depth=5):
    """收集树中所有节点的名称。"""
    names = []
    for node in tree:
        names.append(node.get("name", ""))
        if depth > 0 and "children" in node:
            names.extend(_collect_all_names(node["children"], depth - 1))
    return names


def test_subtitle_in_subdir_shown_in_season():
    """字幕在 Subs 子目录中时，预览应展示在 Season 01 下。"""
    save_path = "D:\\test\\冰菓 Hyouka"
    season_dir = os.path.join(save_path, "Season 01")
    torrent_name = "[SubGroup] Hyouka BDRip 1080p"

    action_plan = {
        "plan": [
            {
                "original_path": os.path.join(save_path, torrent_name, "[SubGroup] Hyouka - 01.mkv"),
                "original_filename": "[SubGroup] Hyouka - 01.mkv",
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "target_filename": "冰菓 Hyouka S01E01.mkv",
                "target_season_dir": "Season 01",
                "mapped": {"season": 1, "episode": 1},
                "actions": ["move_to_season", "write_episode_nfo"],
            },
            {
                "original_path": os.path.join(save_path, torrent_name, "[SubGroup] Hyouka - 02.mkv"),
                "original_filename": "[SubGroup] Hyouka - 02.mkv",
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E02.mkv"),
                "target_filename": "冰菓 Hyouka S01E02.mkv",
                "target_season_dir": "Season 01",
                "mapped": {"season": 1, "episode": 2},
                "actions": ["move_to_season", "write_episode_nfo"],
            },
        ],
    }

    new_files_all = [
        {"name": f"{torrent_name}\\[SubGroup] Hyouka - 01.mkv", "size": 1000},
        {"name": f"{torrent_name}\\[SubGroup] Hyouka - 02.mkv", "size": 1000},
        {"name": f"{torrent_name}\\Subs\\[SubGroup] Hyouka - 01.chs.ass", "size": 50},
        {"name": f"{torrent_name}\\Subs\\[SubGroup] Hyouka - 02.chs.ass", "size": 50},
    ]

    tree = _build_plan_tree(action_plan, save_path=save_path, new_files_all=new_files_all)

    # Season 01 节点应该存在
    season_node = _find_node(tree, "Season 01")
    assert season_node is not None, f"Season 01 节点不存在，树: {tree}"

    # 字幕应在 Season 01 的 children 中
    season_children_names = [c.get("name") for c in season_node.get("children", [])]
    print(f"Season 01 children: {season_children_names}")

    assert "冰菓 Hyouka S01E01.chs.ass" in season_children_names, \
        f"字幕应在 Season 01 下，实际 children: {season_children_names}"
    assert "冰菓 Hyouka S01E02.chs.ass" in season_children_names

    # 不应该有 Subs 目录节点
    all_names = _collect_all_names(tree)
    assert "Subs" not in all_names, f"不应有 Subs 目录节点，所有名称: {all_names}"


def test_sp_shown_at_root_level():
    """SPs 子目录应在预览中展示在根级（和 Season 同级）。"""
    save_path = "D:\\test\\冰菓 Hyouka"
    season_dir = os.path.join(save_path, "Season 01")
    torrent_name = "[SubGroup] Hyouka BDRip 1080p"

    action_plan = {
        "plan": [
            {
                "original_path": os.path.join(save_path, torrent_name, "[SubGroup] Hyouka - 01.mkv"),
                "original_filename": "[SubGroup] Hyouka - 01.mkv",
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "target_filename": "冰菓 Hyouka S01E01.mkv",
                "target_season_dir": "Season 01",
                "mapped": {"season": 1, "episode": 1},
                "actions": ["move_to_season", "write_episode_nfo"],
            },
        ],
    }

    new_files_all = [
        {"name": f"{torrent_name}\\[SubGroup] Hyouka - 01.mkv", "size": 1000},
        {"name": f"{torrent_name}\\SPs\\SP01.mkv", "size": 500},
        {"name": f"{torrent_name}\\SPs\\SP02.mkv", "size": 500},
    ]

    tree = _build_plan_tree(action_plan, save_path=save_path, new_files_all=new_files_all)

    # SPs 应在根级（和 Season 01 同级）
    top_names = [n.get("name") for n in tree]
    print(f"顶层节点: {top_names}")
    assert "SPs" in top_names, f"SPs 应在顶层，实际: {top_names}"

    # SPs 不应在 Season 01 下
    season_node = _find_node(tree, "Season 01")
    if season_node:
        season_children_names = [c.get("name") for c in season_node.get("children", [])]
        assert "SPs" not in season_children_names, \
            f"SPs 不应在 Season 01 下，实际: {season_children_names}"


def test_fonts_dir_shown_at_root_level():
    """Fonts 字体目录应在预览中展示在根级。"""
    save_path = "D:\\test\\冰菓 Hyouka"
    season_dir = os.path.join(save_path, "Season 01")
    torrent_name = "[SubGroup] Hyouka BDRip 1080p"

    action_plan = {
        "plan": [
            {
                "original_path": os.path.join(save_path, torrent_name, "[SubGroup] Hyouka - 01.mkv"),
                "original_filename": "[SubGroup] Hyouka - 01.mkv",
                "target_path": os.path.join(season_dir, "冰菓 Hyouka S01E01.mkv"),
                "target_filename": "冰菓 Hyouka S01E01.mkv",
                "target_season_dir": "Season 01",
                "mapped": {"season": 1, "episode": 1},
                "actions": ["move_to_season", "write_episode_nfo"],
            },
        ],
    }

    new_files_all = [
        {"name": f"{torrent_name}\\[SubGroup] Hyouka - 01.mkv", "size": 1000},
        {"name": f"{torrent_name}\\Fonts\\font1.ttf", "size": 10},
        {"name": f"{torrent_name}\\Fonts\\font2.otf", "size": 10},
    ]

    tree = _build_plan_tree(action_plan, save_path=save_path, new_files_all=new_files_all)

    top_names = [n.get("name") for n in tree]
    print(f"顶层节点: {top_names}")
    assert "Fonts" in top_names, f"Fonts 应在顶层，实际: {top_names}"
