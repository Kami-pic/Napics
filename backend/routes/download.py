"""
路由模块：download
"""
import os
import json
import re
import time
import asyncio
import shutil
import requests
import subprocess
import sys
import threading
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, Response
from pydantic import BaseModel

from shared import (
    config_m, shadow_m, indexer_m, torrent_bl, analysis_cache,
    _get_download_manager, _get_pan_search_service, _get_recycle_bin, _get_file_relocator,
    _tmdb_client, get_clients,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask
from download_provider_factory import get_download_provider_map
from provider_models import DownloadRequest as ProviderDownloadRequest, DownloadTaskInfo

router = APIRouter()


class DownloadRequest(BaseModel):
    url: str
    save_path: str
    download_type: str = "qb"


def _provider_id_for_download_type(download_type: str) -> str:
    if download_type == "qb":
        return "qbittorrent"
    if download_type == "alist":
        return "openlist"
    return ""


def _submit_via_download_provider(download_type: str, url: str, save_path: str):
    provider_id = _provider_id_for_download_type(download_type)
    if not provider_id:
        return None
    providers = get_download_provider_map()
    provider = providers.get(provider_id)
    if provider is None:
        return None
    return provider.submit(ProviderDownloadRequest(url=url, savePath=save_path))


def _qb_task_info_to_legacy_dict(task: DownloadTaskInfo) -> dict:
    return {
        "hash": task.external_task_id,
        "name": task.name,
        "save_path": task.save_path,
        "progress": task.progress,
        "dlspeed": task.extra.get("dlspeed", 0),
        "eta": task.extra.get("eta", 0),
        "state": task.status,
    }

@router.post("/download")
def trigger_download(req: DownloadRequest):
    from plugin_guard import is_download_allowed
    conf = config_m.config
    if req.download_type == "qb":
        if not is_download_allowed("qb"):
            return {"success": False, "message": "请先在插件中心安装 qBittorrent 插件"}
        if not conf.qb_url:
            return {"success": False, "message": "qBittorrent 未配置"}
    elif req.download_type == "alist":
        if not is_download_allowed("alist"):
            return {"success": False, "message": "请先在插件中心安装 OpenList 插件"}
        if not conf.alist_url or not conf.alist_token:
            return {"success": False, "message": "Alist 未配置"}
    else:
        return {"success": False, "message": f"不支持的下载类型: {req.download_type}"}
    result = _submit_via_download_provider(req.download_type, req.url, req.save_path)
    success = bool(result and result.success)
    return {"success": success, "message": "任务已下达" if success else "执行异常"}

# ── 批量搜索升级 ──

class BatchSearchItem(BaseModel):
    name: str
    path: str
    current_resolution: str = ""

class BatchSearchRequest(BaseModel):
    items: List[BatchSearchItem]

def _select_best_match(results: list):
    """从搜索结果中选择做种数 > 0 且 quality_rank 最高的结果"""
    candidates = [r for r in results if r.seeders > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.quality_rank)

@router.post("/batch-search")
async def batch_search(req: BatchSearchRequest):
    """EventSource 流式返回批量搜索进度"""
    clients = get_clients()
    total = len(req.items)

    async def event_gen():
        found = 0
        not_found = 0
        for i, item in enumerate(req.items):
            # 发送 searching 进度
            yield "data: " + json.dumps({
                "type": "progress", "index": i, "total": total,
                "name": item.name, "status": "searching"
            }, ensure_ascii=False) + "\n\n"

            try:
                results = clients["search"].search(item.name)
                best = _select_best_match(results)
                if best:
                    found += 1
                else:
                    not_found += 1
                yield "data: " + json.dumps({
                    "type": "result", "index": i, "name": item.name,
                    "best_match": best.dict() if best else None,
                    "all_results": [r.dict() for r in results]
                }, ensure_ascii=False) + "\n\n"
            except Exception as e:
                not_found += 1
                yield "data: " + json.dumps({
                    "type": "result", "index": i, "name": item.name,
                    "best_match": None, "all_results": [],
                    "error": str(e)
                }, ensure_ascii=False) + "\n\n"

            # 间隔 2 秒避免 API 限流（最后一个不等待）
            if i < total - 1:
                await asyncio.sleep(2)

        yield "data: " + json.dumps({
            "type": "done", "found": found, "not_found": not_found
        }, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

class BatchDownloadTask(BaseModel):
    download_url: str
    save_path: str
    download_type: str = "qb"

class BatchDownloadRequest(BaseModel):
    tasks: List[BatchDownloadTask]

@router.post("/batch-download")
def batch_download(req: BatchDownloadRequest):
    """批量推送下载任务"""
    conf = config_m.config
    results = []
    for i, task in enumerate(req.tasks):
        try:
            if task.download_type == "qb":
                if not conf.qb_url:
                    results.append({"index": i, "success": False, "message": "qBittorrent 未配置"})
                    continue
            elif task.download_type == "alist":
                if not conf.alist_url or not conf.alist_token:
                    results.append({"index": i, "success": False, "message": "Alist 未配置"})
                    continue
            else:
                results.append({"index": i, "success": False, "message": f"不支持的下载类型: {task.download_type}"})
                continue
            result = _submit_via_download_provider(task.download_type, task.download_url, task.save_path)
            success = bool(result and result.success)
            results.append({"index": i, "success": success, "message": "任务已下达" if success else "执行异常"})
        except Exception as e:
            results.append({"index": i, "success": False, "message": str(e)})
    return {"results": results}

# ── 下载管理 API ──

class DownloadSubmitRequest(BaseModel):
    media_name: str
    download_url: str
    save_path: str
    channel: str = "qb"
    category_hint: str = ""
    is_season_pack: bool = False
    season_number: int = 0

@router.post("/download-manager/submit")
def submit_download(req: DownloadSubmitRequest):
    """提交下载任务到 DownloadManager 队列。自动检查黑名单。"""
    # 黑名单检查
    if torrent_bl.is_blocked(req.download_url):
        return {"success": False, "error": "该种子在黑名单中（24h 内曾提交失败），请稍后重试或手动移除黑名单"}

    dm = _get_download_manager()
    task = DownloadTask(
        media_name=req.media_name,
        download_url=req.download_url,
        save_path=req.save_path,
        channel=req.channel,
        category_hint=req.category_hint,
        is_season_pack=req.is_season_pack,
        season_number=req.season_number,
    )
    result = dm.submit(task)

    # 提交失败自动加入黑名单
    if result.status == "failed":
        torrent_bl.add(req.download_url, reason=result.error or "submit failed")

    return {"success": result.status != "failed", "task": result.dict()}


@router.get("/download-manager/status")
def get_download_status():
    """获取下载系统状态：可用后端、监控目录等"""
    from plugin_guard import is_download_allowed, has_any_download_backend
    dm = _get_download_manager()
    conf = config_m.config
    return {
        "has_backend": has_any_download_backend(),
        "available_backends": dm.get_available_backends(),
        "qb_installed": is_download_allowed("qb"),
        "alist_installed": is_download_allowed("alist"),
        "watch_dirs": conf.download_watch_dirs or [],
    }


@router.get("/download-manager/tasks")
def get_download_tasks(status: str = ""):
    """查询下载任务列表，支持按状态过滤。"""
    dm = _get_download_manager()
    tasks = dm.get_tasks(status=status if status else None)
    return {"tasks": [t.dict() for t in tasks]}

@router.get("/download-manager/progress")
def get_download_progress():
    """获取所有活跃任务的进度信息。"""
    dm = _get_download_manager()
    # 先同步一次进度
    dm.sync_progress()
    # 同时获取 downloading 和 unknown (正在对账) 的任务
    with dm._lock:
        active = [t for t in dm.tasks if t.status in ("downloading", "unknown")]
    return {"tasks": [t.dict() for t in active]}

@router.post("/download-manager/sync")
def sync_download_progress():
    """手动触发一次进度同步。"""
    dm = _get_download_manager()
    dm.sync_progress()
    return {"message": "ok"}

@router.post("/download-manager/sync-from-qb")
def sync_from_qb():
    """从 qBittorrent 全量同步：
    1. 把'推送失败'但实际在 qB 里的任务状态更新为 downloading
    2. 把 qB 里有但 download_tasks.json 里没有的种子导入为新任务
    3. 更新所有 downloading 任务的进度
    """
    dm = _get_download_manager()
    provider = get_download_provider_map().get("qbittorrent")
    if not provider:
        return {"updated": 0, "imported": 0, "error": "qBittorrent 未配置"}

    try:
        qb_tasks = provider.list_tasks()
        qb_torrents = [_qb_task_info_to_legacy_dict(task) for task in qb_tasks]
        qb_hash_map = {t.get("hash", ""): t for t in qb_torrents}
        qb_hashes = set(qb_hash_map.keys())

        # 已有任务的 hash 集合
        existing_hashes = {t.downloader_hash for t in dm.tasks if t.downloader_hash}

        updated = 0
        imported = 0

        with dm._lock:
            # 1. 更新已有任务的状态
            for task in dm.tasks:
                # 已整理的任务跳过 qB 状态同步（文件可能已被重命名/移动）
                if task.organized:
                    continue

                if task.status in ("failed", "unknown", "lost") and "推送失败" in (task.error or ""):
                    # 尝试通过名字匹配
                    name_lower = task.media_name.lower()
                    for qb_hash, qt in qb_hash_map.items():
                        qb_name = qt.get("name", "").lower()
                        if name_lower in qb_name or qb_name in name_lower:
                            task.status = "downloading"
                            task.downloader_hash = qb_hash
                            task.error = ""
                            updated += 1
                            break

                # 2. 更新 downloading 任务的进度
                if task.status == "downloading" and task.downloader_hash in qb_hash_map:
                    qt = qb_hash_map[task.downloader_hash]
                    task.progress = round(qt.get("progress", 0), 4)
                    dl_speed = qt.get("dlspeed", 0)
                    task.speed = f"{dl_speed/1024/1024:.1f} MB/s" if dl_speed >= 1024*1024 else (f"{dl_speed/1024:.0f} KB/s" if dl_speed > 0 else "")
                    eta = qt.get("eta", 0)
                    if eta and eta < 8640000:
                        h2, rem = divmod(int(eta), 3600)
                        m, s = divmod(rem, 60)
                        task.eta = f"{h2:02d}:{m:02d}:{s:02d}"
                    qb_state = qt.get("state", "")
                    if task.progress >= 1.0 or qb_state in ("uploading", "stalledUP", "pausedUP", "forcedUP", "queuedUP", "stoppedUP"):
                        task.status = "completed"
                        task.progress = 1.0
                        task.speed = ""
                        task.eta = ""
                    elif qb_state in ("pausedDL", "stoppedDL"):
                        task.status = "downloading"  # 暂停中，保持 downloading 状态（前端可显示暂停图标）
                        task.speed = "已暂停"
                        task.eta = ""
                    elif qb_state in ("error", "missingFiles"):
                        task.status = "failed"
                        task.error = f"qB 状态: {qb_state}"
                    updated += 1

            # 3. 导入 qB 里有但 download_tasks.json 里没有的所有种子
            from download_manager import DownloadTask
            import datetime

            # qB state → 我们的 status 映射
            QB_STATE_MAP = {
                "downloading": "downloading", "stalledDL": "downloading", "allocating": "downloading",
                "metaDL": "downloading", "checkingDL": "downloading", "forcedDL": "downloading",
                "queuedDL": "downloading",
                "uploading": "completed", "stalledUP": "completed",
                "pausedUP": "completed", "forcedUP": "completed", "stoppedUP": "completed",
                "queuedUP": "completed",
                "pausedDL": "downloading",  # 暂停中，但还是下载任务
                "stoppedDL": "downloading",
                "error": "failed", "missingFiles": "failed",
                "checkingUP": "completed", "checkingResumeData": "downloading",
                "moving": "downloading", "unknown": "unknown",
            }

            # 已删除 hash 黑名单：用户手动删除过的任务不再重新导入
            deleted_hashes = dm._deleted_hashes

            for qb_hash, qt in qb_hash_map.items():
                if qb_hash in existing_hashes:
                    continue
                if qb_hash in deleted_hashes:
                    continue
                qb_state = qt.get("state", "unknown")
                our_status = QB_STATE_MAP.get(qb_state, "downloading")
                name = qt.get("name", "")
                save_path = qt.get("save_path", "")
                progress = round(qt.get("progress", 0), 4)
                dl_speed = qt.get("dlspeed", 0)
                speed = f"{dl_speed/1024/1024:.1f} MB/s" if dl_speed >= 1024*1024 else (f"{dl_speed/1024:.0f} KB/s" if dl_speed > 0 else "")
                eta_secs = qt.get("eta", 0)
                eta = ""
                if eta_secs and eta_secs < 8640000:
                    h2, rem = divmod(int(eta_secs), 3600)
                    m, s = divmod(rem, 60)
                    eta = f"{h2:02d}:{m:02d}:{s:02d}"
                new_task = DownloadTask(
                    id=f"qb_import_{qb_hash[:8]}",
                    media_name=name,
                    download_url="",
                    save_path=save_path,
                    channel="qb",
                    downloader_hash=qb_hash,
                    status=our_status,
                    progress=progress,
                    speed=speed,
                    eta=eta,
                    created_at=datetime.datetime.now().isoformat(),
                    updated_at=datetime.datetime.now().isoformat(),
                )
                dm.tasks.append(new_task)
                imported += 1

        if updated or imported:
            dm._save_now()

        return {"updated": updated, "imported": imported, "qb_torrents": len(qb_torrents)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"updated": 0, "imported": 0, "error": str(e)}

@router.delete("/download-manager/task")
def delete_download_task(task_id: str):
    """删除单个下载任务记录。"""
    dm = _get_download_manager()
    ok = dm.delete_task(task_id)
    return {"success": ok}

@router.post("/download-manager/delete-tasks")
def delete_download_tasks(task_ids: List[str]):
    """批量删除下载任务记录。"""
    dm = _get_download_manager()
    removed = dm.delete_tasks(task_ids)
    return {"removed": removed}


@router.post("/download-manager/archive")
def archive_download_task(task_id: str):
    """手动将已完成的任务标记为已归档。"""
    dm = _get_download_manager()
    task = dm.get_task(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    if task.status not in ("completed", "awaiting_confirm"):
        return {"success": False, "message": f"当前状态 {task.status} 不支持归档"}
    dm.archive_task(task_id, organized=False)
    return {"success": True}


@router.get("/download-manager/recommend-channel")
def recommend_download_channel(seeders: int = 0, size_gb: float = 0):
    """推荐下载通道。"""
    dm = _get_download_manager()
    channel = dm.recommend_channel(seeders, size_gb)
    return {"channel": channel}

class ConfirmReplaceRequest(BaseModel):
    """确认替换请求（原先误留在 routes/config.py，那里并没有使用它）"""
    task_id: str
    action_plan: Optional[dict] = None


@router.post("/download-manager/confirm-replace")
def confirm_replace(req: ConfirmReplaceRequest):
    """确认替换：旧文件入回收站 → V3 落盘。"""
    dm = _get_download_manager()
    fr = _get_file_relocator()
    task = dm.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    plan = req.action_plan or {}
    result = fr.confirm_replace(task, plan)

    if result.success:
        dm.update_status(req.task_id, "archived")
    else:
        dm.update_status(req.task_id, "failed", result.error)

    return result.dict()

@router.post("/download-manager/cancel-replace")
def cancel_replace(task_id: str):
    """取消替换：新文件入回收站。"""
    dm = _get_download_manager()
    fr = _get_file_relocator()
    task = dm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = fr.cancel_replace(task)
    dm.update_status(task_id, "cancelled")
    return result.dict()

# ── 回收站 API ──

