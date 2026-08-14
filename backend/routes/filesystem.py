"""
路由模块：filesystem — 供前端网页版文件夹选择器浏览目录

为什么需要它：原来的"浏览文件夹"是在服务端弹出系统对话框（Windows 用
PowerShell 的 FolderBrowserDialog，其他平台用 tkinter）。这个设计只在
"后端跑在用户自己的桌面上"时成立 —— Docker 容器里没有桌面环境，NAS 上
更不可能弹窗，而浏览器也无法读取服务端文件系统。

所以改为后端提供目录列举接口，前端自己渲染选择器。这样 Windows / 飞牛 /
群晖 / Docker 全都用同一套实现。

注意：该接口会暴露服务端的目录结构，属于选择媒体库时的必要能力，
因此不能套用媒体库白名单（用户正是要浏览白名单之外的目录来添加媒体库）。
只返回目录、不返回文件，以减少暴露面。
"""
import logging
import os
import string
import sys
from typing import Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# 这些目录对选媒体库没有意义，且容易让用户误入，列举时直接隐藏
_HIDDEN_DIR_NAMES = {
    "$RECYCLE.BIN", "System Volume Information",
    "@eaDir", "#recycle", "#snapshot",
    "proc", "sys", "dev", "run",
}


class DirEntry(BaseModel):
    name: str
    path: str


class ListDirResponse(BaseModel):
    path: str                      # 当前目录（空表示处于根列表）
    parent: str = ""               # 上一级目录，空表示已到顶
    separator: str = "/"           # 该平台的路径分隔符，前端拼路径用
    is_root_list: bool = False     # 当前返回的是根/盘符列表
    dirs: List[DirEntry] = []
    error: str = ""


def _list_roots() -> List[DirEntry]:
    """返回可浏览的起点：Windows 是各盘符，类 Unix 是 /"""
    if sys.platform == "win32":
        roots = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                roots.append(DirEntry(name=drive, path=drive))
        return roots
    return [DirEntry(name="/", path="/")]


@router.get("/fs/list", response_model=ListDirResponse)
def list_directories(path: str = ""):
    """列出指定目录下的子目录。path 为空时返回根（Windows 盘符 / Unix 的 /）。"""
    sep = os.sep

    if not path:
        return ListDirResponse(
            path="", parent="", separator=sep,
            is_root_list=True, dirs=_list_roots(),
        )

    # 归一化，顺带处理用户手输的斜杠方向
    target = os.path.abspath(path)

    if not os.path.isdir(target):
        return ListDirResponse(
            path=path, separator=sep,
            error="目录不存在或不可访问",
        )

    parent = os.path.dirname(target.rstrip("\\/"))
    # 已经到顶时不再给上一级（Windows 盘根的 dirname 等于自身）
    if parent == target or not parent:
        parent = ""

    dirs: List[DirEntry] = []
    try:
        with os.scandir(target) as it:
            for entry in it:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if entry.name.startswith(".") or entry.name in _HIDDEN_DIR_NAMES:
                    continue
                dirs.append(DirEntry(name=entry.name, path=os.path.join(target, entry.name)))
    except PermissionError:
        return ListDirResponse(
            path=target, parent=parent, separator=sep,
            error="没有权限读取该目录",
        )
    except OSError as e:
        return ListDirResponse(
            path=target, parent=parent, separator=sep,
            error=f"读取目录失败: {e}",
        )

    dirs.sort(key=lambda d: d.name.lower())
    return ListDirResponse(path=target, parent=parent, separator=sep, dirs=dirs)


class PathCheckResponse(BaseModel):
    path: str
    exists: bool
    is_dir: bool
    readable: bool
    hint: str = ""


@router.get("/fs/check", response_model=PathCheckResponse)
def check_path(path: str):
    """校验路径在后端进程里是否可用。

    Docker 部署最常见的问题：填了宿主机路径但容器内没挂载，
    扫描永远没结果又不报错。前端可在保存前调用它给出提示。
    """
    if not path:
        return PathCheckResponse(path=path, exists=False, is_dir=False, readable=False,
                                 hint="路径为空")

    target = os.path.abspath(path)
    exists = os.path.exists(target)
    is_dir = os.path.isdir(target)
    readable = False
    if is_dir:
        try:
            os.listdir(target)
            readable = True
        except OSError:
            readable = False

    hint = ""
    if not exists:
        hint = "该路径在服务端不存在。若使用 Docker 部署，请确认这个目录已挂载进容器，且容器内路径与此处填写的完全一致。"
    elif not is_dir:
        hint = "该路径是文件，不是目录"
    elif not readable:
        hint = "目录存在但没有读取权限"

    return PathCheckResponse(path=target, exists=exists, is_dir=is_dir,
                             readable=readable, hint=hint)
