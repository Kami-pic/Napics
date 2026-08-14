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


# ── 运行环境探测 ──

class RuntimeEnvResponse(BaseModel):
    in_container: bool                 # 后端是否运行在容器内
    platform: str                      # win32 / linux / darwin
    can_use_local_player: bool         # 能否调起后端所在机器的播放器
    host_alias: str                    # 访问「宿主机上其他服务」时建议填的主机名
    host_alias_reachable: bool         # 该主机名当前是否可解析
    dns_ok: bool                       # 容器内域名解析是否正常
    hints: List[str] = []              # 给用户的配置建议


def _resolvable(host: str) -> bool:
    import socket
    try:
        socket.getaddrinfo(host, None)
        return True
    except Exception:
        return False


@router.get("/api/system/environment", response_model=RuntimeEnvResponse)
def runtime_environment():
    """返回后端运行环境，供前端给出针对性的配置建议。

    解决两个实际困扰：
    1. 容器内没有桌面环境，本地播放器功能不可用，前端应隐藏
    2. 容器内 127.0.0.1 指向容器自己，填 qBittorrent / Prowlarr / OpenList
       地址时该填什么取决于网络模式，需要明确告知
    """
    in_container = os.path.exists("/.dockerenv")
    dns_ok = _resolvable("api.themoviedb.org")

    # host 网络模式下容器与宿主机共用网络栈，127.0.0.1 就是宿主机；
    # bridge 模式下需要 host.docker.internal（compose 已配 host-gateway 映射）
    host_gateway_ok = _resolvable("host.docker.internal") if in_container else False
    host_alias = "127.0.0.1" if (not in_container or not host_gateway_ok) else "host.docker.internal"

    hints: List[str] = []
    if in_container:
        if not dns_ok:
            hints.append(
                "容器内域名解析失败，刮削 / 搜索 / 发现页 / 插件源都无法工作。"
                "建议把容器网络改为 host 模式，或为容器显式指定 DNS（如 223.5.5.5）。"
            )
        if host_gateway_ok:
            hints.append(
                "下载器与网盘服务若装在 NAS 上，地址请填 http://host.docker.internal:端口，"
                "填 127.0.0.1 会指向容器自身。"
            )
        else:
            hints.append(
                "当前容器可直接使用 127.0.0.1 访问宿主机服务（host 网络模式）。"
            )
        hints.append("后端在容器内运行，无法调起本地播放器，播放请使用 NAS 自带影音应用。")

    return RuntimeEnvResponse(
        in_container=in_container,
        platform=sys.platform,
        can_use_local_player=(not in_container),
        host_alias=host_alias,
        host_alias_reachable=host_gateway_ok or not in_container,
        dns_ok=dns_ok,
        hints=hints,
    )


# ── 总体诊断 ──

@router.get("/api/system/diagnose")
def system_diagnose():
    """一次性返回部署健康状况，避免逐项试错。

    覆盖：运行环境、数据目录是否持久化、媒体库路径可达性、媒体库规模、
    各外部服务连通性（含是否需要代理）、以及针对性的处置建议。
    """
    import concurrent.futures
    import socket

    import requests

    from shared import config_m

    conf = config_m.config
    in_container = os.path.exists("/.dockerenv")
    proxy = (getattr(conf, "http_proxy", "") or "").strip()
    proxies = {"http": proxy, "https": proxy} if proxy else None

    # ── 媒体库路径 ──
    paths_status = []
    for p in (conf.scan_paths or []):
        paths_status.append({
            "path": p,
            "exists": os.path.isdir(p),
        })
    for lib in (conf.media_libraries or []):
        for p in (lib.paths or []):
            paths_status.append({
                "path": p,
                "exists": os.path.isdir(p),
                "library": lib.name,
            })

    # ── 媒体库规模 ──
    try:
        library = config_m.load_library()
    except Exception:
        library = []
    folders = {os.path.dirname(v.get("file_path", "")) for v in library if v.get("file_path")}

    # ── 数据目录持久化 ──
    data_dir = config_m.data_dir
    data_persisted = None
    if in_container:
        # /app/data 若没挂载卷，容器重建后配置与媒体库都会丢
        try:
            with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
                mounts = f.read()
            data_persisted = any(
                line.split()[1] == data_dir.rstrip("/") for line in mounts.splitlines()
                if len(line.split()) > 1
            )
        except Exception:
            data_persisted = None

    # ── 外部服务连通性（并发 + 短超时）──
    targets = {
        "douban": "https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&page_limit=1&page_start=0",
        "tmdb": "https://api.themoviedb.org/3/configuration",
        "bangumi": "https://api.bgm.tv/calendar",
        "github_raw": "https://raw.githubusercontent.com/Kami-pic/Napics/release/README.md",
    }

    def probe(name: str, url: str):
        result = {"name": name, "dns_ok": False, "reachable": False, "detail": ""}
        try:
            host = url.split("//", 1)[1].split("/", 1)[0]
            socket.getaddrinfo(host, 443)
            result["dns_ok"] = True
        except Exception as e:
            result["detail"] = f"域名解析失败: {e}"
            return result
        try:
            r = requests.get(url, timeout=6, proxies=proxies,
                             headers={"User-Agent": "Mozilla/5.0"})
            result["reachable"] = r.status_code < 500
            result["detail"] = f"HTTP {r.status_code}"
        except requests.exceptions.Timeout:
            result["detail"] = "连接超时（国内访问该站点通常需要代理）"
        except Exception as e:
            result["detail"] = f"{type(e).__name__}: {e}"[:160]
        return result

    services = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(probe, n, u) for n, u in targets.items()]
        for f in futs:
            try:
                services.append(f.result(timeout=10))
            except Exception:
                pass

    svc = {s["name"]: s for s in services}

    # ── 建议 ──
    problems = []
    if in_container and data_persisted is False:
        problems.append(
            f"数据目录 {data_dir} 没有挂载卷：容器重建后配置与媒体库会全部丢失。"
            f"请把一个宿主机目录挂载到 {data_dir}。"
        )
    if not paths_status:
        problems.append("尚未配置任何媒体库路径，请在设置页添加。")
    for ps in paths_status:
        if not ps["exists"]:
            problems.append(
                f"媒体库路径在后端不可见：{ps['path']}。"
                "容器部署时请确认该目录已挂载进容器，且容器内路径与填写的一致。"
            )
    if not library:
        problems.append("媒体库为空，请在首页执行扫描。")
    if not (conf.tmdb_api_key or "").strip():
        problems.append("未配置 TMDB API Key，TMDB 相关的刮削与发现页无法使用。")
    if svc.get("tmdb") and not svc["tmdb"]["reachable"]:
        problems.append(
            "TMDB 不可达。国内网络通常需要在设置里填 HTTP 代理，"
            "或改用豆瓣作为刮削源（设置项 default_scrape_source）。"
        )
    if svc.get("github_raw") and not svc["github_raw"]["reachable"]:
        problems.append(
            "GitHub 不可达，插件源安装会失败。需要代理，或改用可访问的插件源地址。"
        )
    if svc.get("douban") and svc["douban"]["reachable"]:
        problems.append("豆瓣可直连，建议把默认刮削源设为豆瓣（无需代理）。")

    return {
        "environment": {
            "in_container": in_container,
            "platform": sys.platform,
            "data_dir": data_dir,
            "data_dir_persisted": data_persisted,
            "http_proxy_configured": bool(proxy),
        },
        "media_library": {
            "video_count": len(library),
            "folder_count": len(folders),
            "configured_paths": paths_status,
        },
        "external_services": services,
        "problems": problems,
    }
