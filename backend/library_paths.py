"""媒体库路径归属计算 —— 「这个文件属于哪个扫描根、folder_name 该是什么」的唯一口径。

为什么单独抽出来：`folder_name` 是目录树的唯一数据源（`routes/library_tree.py`
完全按它重建树，文件系统不参与），算错一次就会在树上长期留下一个位置错误、
名字也可能错误的节点。而这个计算原本被复制在四处，其中两处是错的：

- `routes/library.py` /scan：对，因为它本来就按「当前正在扫哪个根」来算；
- `routes/library_sync.py` /sync：对，最长前缀匹配 + 库名前缀；
- `routes/rename.py`：**错**，写死 `scan_paths[0]` 且不加库名前缀；
- `download_manager._trigger_local_refresh`：**错**，基准是 save_path 本身。

写死 `scan_paths[0]` 的后果不是"少了个前缀"这么轻：文件在第二个扫描路径下时
`os.path.relpath` 会算出 `..\..\share\视频\电影\某片`，建树时 `..` 成为一个节点名，
用户看到的就是外层文件夹名变成一串看不懂的东西。

所以这里的约定是：**算不出来就返回 None，由调用方决定跳过还是报错，绝不回退到
某个"差不多"的基准。**
"""
import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def is_under_path(file_path: str, base: str) -> bool:
    """file_path 是否位于 base 目录之下（或就是它本身）。

    不能直接用 `startswith(base)`：那样 `D:\\影视2\\a.mkv` 会被当成
    `D:\\影视` 的子路径。扫描 / 同步判断"这条属于哪个库"时踩过这个坑 ——
    两个名字有共同前缀的平级目录会互相误判，扫一个库会连带处理另一个库的条目。

    住在这里而不是 shared.py：本模块必须零项目内依赖。它被 download_manager
    在后台线程里 import，而 shared 的导入会连带构造 ConfigManager 单例。
    （`shared.is_under_path` 仍然可用，那边转发到这里。）
    """
    if not file_path or not base:
        return False
    trimmed = base.rstrip("\\/")
    if file_path == trimmed:
        return True
    return file_path.startswith(trimmed + os.sep) or file_path.startswith(trimmed + "/")


def scan_bases(config=None) -> List[Tuple[str, str]]:
    """列出所有扫描根，返回 [(base, library_name)]。

    library_name 为空串表示裸扫描路径（`scan_paths`），非空表示虚拟媒体库 ——
    后者的 folder_name 需要以库名作为第一段，因为目录树用第一段去反查库路径。
    """
    if config is None:
        from shared import config_m
        config = config_m.config

    bases: List[Tuple[str, str]] = []
    seen = set()

    def _add(path: str, name: str):
        if not path:
            return
        key = path.replace("/", "\\").rstrip("\\").lower()
        if key in seen:
            return
        seen.add(key)
        bases.append((path, name))

    for path in (config.scan_paths or []):
        _add(path, "")
    for lib in (config.media_libraries or []):
        for path in (lib.paths or []):
            _add(path, lib.name)
    return bases


def resolve_base(file_path: str, config=None) -> Tuple[str, str]:
    """找出 file_path 所属的扫描根，返回 (base, library_name)。

    **最长前缀优先**：一个库路径可能嵌在另一个之下（例如扫描根是 `\\\\nas\\video`
    而虚拟库指向 `\\\\nas\\video\\动画`），此时必须归给更具体的那个，否则
    folder_name 会多出一段、库名前缀也会丢。

    都匹配不上时返回 ("", "")。
    """
    if not file_path:
        return ("", "")

    best_base = ""
    best_name = ""
    for base, name in scan_bases(config):
        if is_under_path(file_path, base) and len(base) > len(best_base):
            best_base = base
            best_name = name
    return (best_base, best_name)


def compute_folder_name(file_path: str, config=None) -> Optional[str]:
    """算出 file_path 应有的 folder_name（相对所属扫描根的目录，虚拟库带库名前缀）。

    file_path 不在任何扫描根之下时返回 **None** —— 这种情况调用方必须显式处理
    （通常是跳过入库），不能拿任意一个基准硬算。
    """
    base, library_name = resolve_base(file_path, config)
    if not base:
        return None

    rel_dir = os.path.relpath(os.path.dirname(file_path), base)
    rel_dir = "" if rel_dir == "." else rel_dir
    if library_name:
        return os.path.join(library_name, rel_dir) if rel_dir else library_name
    return rel_dir
