"""nas-download-mcp 入口（todo §3/§13）。

Streamable HTTP MCP 常驻服务，对 Hermes 暴露 6 个工具。
download_movie 立刻返回 task_id，workflow 在后台 asyncio 任务里跑（不阻塞 HTTP）。
启动时跑一次孤儿清理（崩溃恢复，§8/§45）。
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid

# src 目录加进 path，模块用扁平导入（config/models/...）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from config import load_config  # noqa: E402
from db import Db  # noqa: E402
from models import (  # noqa: E402
    Constraints,
    DownloadMovieInput,
    ErrorCode,
    TaskStatus,
    err,
)
from adapters.docker_adapter import DockerAdapter  # noqa: E402
from adapters.qb_client import QbClient  # noqa: E402
from service_manager import ServiceManager  # noqa: E402
from workflow import Workflow  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nas_download_mcp")

cfg = load_config()
db = Db(cfg.database_path)
mcp = FastMCP("nas-download-mcp", host=cfg.mcp_host, port=cfg.mcp_port)

# 记录后台 workflow 任务，避免被 GC
_running_tasks: dict[str, asyncio.Task] = {}

_TERMINAL = [
    TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value,
    TaskStatus.TIMEOUT.value, TaskStatus.EXHAUSTED.value,
]


def _new_task_id() -> str:
    return f"task-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"


# ── §3.1 download_movie ──
@mcp.tool()
async def download_movie(
    title: str,
    media_type: str = "movie",
    year: int | None = None,
    original_title: str | None = None,
    original_language: str | None = None,
    queries: list[str] | None = None,
    min_resolution: str | None = None,
    max_size_gb: float | None = None,
    save_path: str | None = None,
    season: int | None = None,
    interactive: bool = True,
) -> dict:
    """创建一个电影/剧集下载任务。立刻返回 task_id，实际下载在后台跑。

    语言理解归上层 agent：agent 应先判定作品身份、拼好 queries（如 "Titanic 1997"），
    并按需给 min_resolution（"2160p"/"4k"）、max_size_gb（如 50）做筛选约束。
    用 get_download_task(task_id) 轮询进度。
    """
    # 并发锁：第一版同时只允许一个 workflow（§17）
    task_id = _new_task_id()
    if not db.try_acquire_lock(task_id):
        holder = db.current_lock_task()
        return err(ErrorCode.INTERNAL_ERROR, f"已有下载任务在跑（{holder}），第一版同时只允许一个", retryable=True)

    inp = DownloadMovieInput(
        title=title, media_type=media_type, year=year,
        original_title=original_title, original_language=original_language,
        queries=queries or [],
        constraints=Constraints(min_resolution=min_resolution, max_size_gb=max_size_gb),
        save_path=save_path, season=season, interactive=interactive,
    )
    db.create_task(task_id, {
        "media_type": media_type, "title": title, "year": year,
        "original_title": original_title or "", "original_language": original_language or "",
        "status": TaskStatus.STARTING.value, "current_stage": "CREATED",
        "napics_task_id": "", "selected_qb_hash": "", "save_path": save_path or "",
        "error_code": "", "error_message": "",
    })
    db.add_event(task_id, "TASK_CREATED", {"title": title})

    wf = Workflow(cfg, db)
    t = asyncio.create_task(wf.run(task_id, inp))
    _running_tasks[task_id] = t
    t.add_done_callback(lambda _t: _running_tasks.pop(task_id, None))
    return {"task_id": task_id, "status": "starting"}


# ── §3.2 get_download_task ──
@mcp.tool()
def get_download_task(task_id: str) -> dict:
    """查单个任务状态/进度。"""
    t = db.get_task(task_id)
    if not t:
        return err(ErrorCode.DOWNLOAD_NOT_FOUND, f"任务不存在: {task_id}")
    progress = 0.0
    hashv = t.get("selected_qb_hash") or ""
    if hashv and t.get("status") in (TaskStatus.DOWNLOADING.value,):
        qb = QbClient(cfg.qb_url, cfg.qb_username, cfg.qb_password)
        try:
            st = qb.info(hashv)
            progress = st.percentage
        finally:
            qb.close()
    return {
        "task_id": task_id,
        "status": t.get("status"),
        "stage": t.get("current_stage"),
        "progress": progress,
        "error_code": t.get("error_code") or "",
        "message": t.get("error_message") or "",
    }


# ── §3.3 list_download_tasks ──
@mcp.tool()
def list_download_tasks(status: str = "") -> dict:
    """列任务，可按统一状态过滤。"""
    tasks = db.list_tasks(status)
    return {"tasks": [
        {"task_id": t["id"], "title": t.get("title"), "status": t.get("status"),
         "stage": t.get("current_stage"), "created_at": t.get("created_at")}
        for t in tasks
    ]}


# ── §3.4 cancel_download_task ──
@mcp.tool()
async def cancel_download_task(task_id: str, delete_download: bool = False) -> dict:
    """取消任务：停 workflow → 删 qB 种子 → cleanup 关容器。"""
    t = db.get_task(task_id)
    if not t:
        return err(ErrorCode.DOWNLOAD_NOT_FOUND, f"任务不存在: {task_id}")
    # 停后台 workflow
    running = _running_tasks.get(task_id)
    if running and not running.done():
        running.cancel()
    # 删 qB 种子
    for h in db.get_qb_hashes(task_id):
        if h:
            qb = QbClient(cfg.qb_url, cfg.qb_username, cfg.qb_password)
            try:
                qb.delete(h, delete_files=delete_download)
            finally:
                qb.close()
    # cleanup 关容器
    svc = ServiceManager(cfg, DockerAdapter())
    try:
        cres = await svc.cleanup()
    except Exception as e:
        cres = {"error": str(e)}
    db.update_task(task_id, status=TaskStatus.CANCELLED.value, current_stage="CANCELLED",
                   cleanup_status="completed")
    db.add_event(task_id, "TASK_CANCELLED", cres)
    db.release_lock()
    return {"ok": True, "task_id": task_id, "cleanup": cres}


# ── §3.5 get_system_status ──
@mcp.tool()
def get_system_status() -> dict:
    """容器/服务健康 + 当前活跃任务。"""
    svc = ServiceManager(cfg, DockerAdapter())
    st = svc.status()
    st["active_task"] = db.current_lock_task()
    return st


# ── §6/§41 cleanup_orphaned_tasks（启动自动跑一次）──
@mcp.tool()
async def cleanup_orphaned_tasks() -> dict:
    """管理员：清理 MCP 重启后遗留的非终态任务。"""
    return await _do_orphan_cleanup()


async def _do_orphan_cleanup() -> dict:
    orphans = db.unfinished_tasks(_TERMINAL)
    if not orphans:
        return {"cleaned": 0, "tasks": []}
    handled = []
    for t in orphans:
        tid = t["id"]
        stage = t.get("current_stage") or ""
        # DOWNLOADING 且允许恢复 → 留着（第一版建议 recover=true）
        if stage == "DOWNLOADING" and cfg.recover_active_download:
            handled.append({"task_id": tid, "action": "kept_for_recovery"})
            continue
        # 其余（PROBING 等）→ 删 probe 种子 + 停服务 + 标失败
        for h in db.get_qb_hashes(tid):
            if h:
                qb = QbClient(cfg.qb_url, cfg.qb_username, cfg.qb_password)
                try:
                    qb.delete(h, delete_files=True)
                finally:
                    qb.close()
        svc = ServiceManager(cfg, DockerAdapter())
        try:
            await svc.cleanup()
        except Exception:
            pass
        db.update_task(tid, status=TaskStatus.FAILED.value, current_stage="FAILED",
                       error_code=ErrorCode.INTERNAL_ERROR.value,
                       error_message="MCP 重启，孤儿任务已清理", cleanup_status="completed")
        handled.append({"task_id": tid, "action": "cleaned"})
    db.release_lock()
    return {"cleaned": len(handled), "tasks": handled}


def main() -> None:
    # 启动崩溃恢复（§45）
    try:
        asyncio.run(_do_orphan_cleanup())
    except Exception as e:
        logger.warning("启动孤儿清理失败: %s", e)
    logger.info("nas-download-mcp 启动 %s:%s", cfg.mcp_host, cfg.mcp_port)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
