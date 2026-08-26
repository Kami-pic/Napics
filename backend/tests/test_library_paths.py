"""library_paths —— folder_name 归属计算。

这个模块存在的原因是同一份计算被复制了四处、其中两处算错，而算错的后果直接
显示在用户眼前：目录树完全按 folder_name 重建，写死 `scan_paths[0]` 会让第二个
扫描路径下的文件得到 `..\\..\\share\\视频\\电影\\某片` 这种相对路径，建树时 `..`
成为一个节点名 —— 用户看到的就是「外层文件夹名变成一串看不懂的东西」。
"""
import os
from types import SimpleNamespace

import library_paths


def _config(scan_paths=(), libraries=()):
    """libraries: [(name, [paths...])]"""
    return SimpleNamespace(
        scan_paths=list(scan_paths),
        media_libraries=[SimpleNamespace(name=n, paths=list(p)) for n, p in libraries],
    )


# ── scan_bases ──

def test_scan_bases_lists_scan_paths_before_libraries():
    conf = _config([r"D:\影视"], [("动画番", [r"E:\anime"])])
    assert library_paths.scan_bases(conf) == [(r"D:\影视", ""), (r"E:\anime", "动画番")]


def test_scan_bases_dedups_case_and_separator_variants():
    """同一个目录用不同写法配了两遍时只留一个，否则最长匹配会在两个等长基准间摇摆。"""
    conf = _config([r"D:\影视", "D:/影视/", r"d:\影视"])
    assert library_paths.scan_bases(conf) == [(r"D:\影视", "")]


# ── resolve_base ──

def test_resolve_base_picks_longest_prefix():
    """库路径嵌在扫描根之下时必须归给更具体的那个，否则 folder_name 会多出一段、
    库名前缀也会丢。"""
    conf = _config([r"D:\影视"], [("动画番", [r"D:\影视\动画"])])
    base, name = library_paths.resolve_base(r"D:\影视\动画\某番\01.mkv", conf)
    assert (base, name) == (r"D:\影视\动画", "动画番")


def test_resolve_base_does_not_match_sibling_with_shared_prefix():
    """`D:\\影视2` 不是 `D:\\影视` 的子目录。裸 startswith 会误判。"""
    conf = _config([r"D:\影视"])
    assert library_paths.resolve_base(r"D:\影视2\a.mkv", conf) == ("", "")


def test_resolve_base_returns_empty_when_outside_all_roots():
    conf = _config([r"D:\影视"])
    assert library_paths.resolve_base(r"E:\下载\a.mkv", conf) == ("", "")


# ── compute_folder_name ──

def test_compute_folder_name_is_relative_to_owning_scan_root():
    conf = _config([r"D:\影视"])
    got = library_paths.compute_folder_name(r"D:\影视\电影\某片 (2024)\某片.mkv", conf)
    assert got == os.path.join("电影", "某片 (2024)")


def test_compute_folder_name_is_empty_at_scan_root():
    conf = _config([r"D:\影视"])
    assert library_paths.compute_folder_name(r"D:\影视\某片.mkv", conf) == ""


def test_compute_folder_name_prefixes_library_name():
    """虚拟库的第一段必须是库名 —— 目录树用第一段反查库路径。"""
    conf = _config([], [("动画番", [r"E:\anime"])])
    got = library_paths.compute_folder_name(r"E:\anime\某番\S01\01.mkv", conf)
    assert got == os.path.join("动画番", "某番", "S01")


def test_compute_folder_name_is_library_name_only_at_library_root():
    conf = _config([], [("动画番", [r"E:\anime"])])
    assert library_paths.compute_folder_name(r"E:\anime\01.mkv", conf) == "动画番"


def test_compute_folder_name_returns_none_outside_scan_roots():
    """算不出来就是 None，绝不回退到某个"差不多"的基准。

    写死 scan_paths[0] 的老写法在这里会返回 `..\\..\\下载\\某片`，
    调用方拿到后照写进库，坏值就长期留在目录树上。
    """
    conf = _config([r"D:\影视"])
    assert library_paths.compute_folder_name(r"E:\下载\某片\a.mkv", conf) is None


def test_compute_folder_name_uses_second_scan_path_not_the_first():
    """这条是老 bug 的直接复现：文件在第二个扫描路径下。"""
    conf = _config([r"D:\影视", r"E:\影视2"])
    got = library_paths.compute_folder_name(r"E:\影视2\电影\某片\某片.mkv", conf)
    assert got == os.path.join("电影", "某片")
    assert ".." not in got
