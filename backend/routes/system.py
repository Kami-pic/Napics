"""
路由模块：system
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

router = APIRouter()

@router.get("/api/config")
def get_config_api():
    """获取当前系统配置"""
    return config_m.config.dict()

@router.post("/api/config")
def save_config_api(new_config: dict):
    """保存并应用新配置"""
    from config_manager import AppConfig
    try:
        cfg = AppConfig(**new_config)
        config_m.save(cfg)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置保存失败: {str(e)}")

@router.get("/recycle-bin")
def list_recycle_bin():
    """列出回收站所有文件。"""
    rb = _get_recycle_bin()
    return {"entries": [e.dict() for e in rb.list_entries()]}

@router.post("/recycle-bin/restore")
def restore_from_bin(entry_id: str):
    """从回收站恢复文件到原始路径。"""
    rb = _get_recycle_bin()
    ok = rb.restore(entry_id)
    if not ok:
        raise HTTPException(status_code=400, detail="恢复失败：文件不存在或原始路径已被占用")
    return {"success": True}

@router.post("/recycle-bin/cleanup")
def cleanup_recycle_bin():
    """手动触发过期清理。"""
    rb = _get_recycle_bin()
    cleaned = rb.cleanup_expired()
    return {"cleaned": cleaned}

# ── 批量管理 ──

class BatchRequest(BaseModel):
    action: str  # "delete" | "move" | "copy" | "remove"
    paths: List[str]
    target_dir: Optional[str] = None

@router.get("/torrent-blacklist")
def list_torrent_blacklist():
    """列出所有黑名单条目"""
    return {"entries": torrent_bl.list_entries(), "count": torrent_bl.count}

@router.post("/torrent-blacklist/add")
def add_to_blacklist(url: str, reason: str = ""):
    """手动添加种子到黑名单"""
    torrent_bl.add(url, reason)
    return {"status": "ok"}

@router.post("/torrent-blacklist/remove")
def remove_from_blacklist(url: str):
    """从黑名单移除"""
    torrent_bl.remove(url)
    return {"status": "ok"}

@router.post("/torrent-blacklist/cleanup")
def cleanup_blacklist():
    """清理过期黑名单"""
    removed = torrent_bl.cleanup()
    return {"status": "ok", "removed": removed}


# ── 全库分析报告（含缓存） ──
@router.get("/analysis/report")
def get_analysis_report(force: bool = False):
    """获取全库分析报告，优先返回缓存。force=True 强制重新分析。"""
    if not force:
        cached = analysis_cache.get()
        if cached:
            age = analysis_cache.get_age_hours()
            return {**cached, "from_cache": True, "cache_age_hours": round(age, 1)}

    # 全量分析
    library = config_m.load_library()
    conf = config_m.config
    all_results = []
    for base in conf.nas_paths:
        if os.path.isdir(base):
            report = analyzer.analyze_library(base, library)
            all_results.append(report)

    # 合并多路径结果
    merged = {
        "results": [],
        "cross_folder_issues": [],
        "summary": {
            "total_folders": 0, "structure_issues": 0, "rename_issues": 0,
            "scrape_issues": 0, "quality_issues": 0, "filename_issues": 0,
            "shadow_name_issues": 0, "cross_folder_issues": 0,
        }
    }
    for r in all_results:
        merged["results"].extend(r.get("results", []))
        merged["cross_folder_issues"].extend(r.get("cross_folder_issues", []))
        s = r.get("summary", {})
        for k in merged["summary"]:
            merged["summary"][k] += s.get(k, 0)

    analysis_cache.update(merged)
    return {**merged, "from_cache": False, "cache_age_hours": 0}

@router.post("/analysis/invalidate")
def invalidate_analysis_cache():
    """清除分析缓存"""
    analysis_cache.invalidate()
    return {"status": "ok"}


# ── 一键整理进度反馈（SSE 流式） ──
@router.get("/torrent-blacklist/check")
def check_blacklist(url: str):
    """检查种子是否在黑名单中"""
    return {"blocked": torrent_bl.is_blocked(url)}


class RelocateRequest(BaseModel):
    task_id: str
    auto_replace: bool = False

class ExecuteRelocateRequest(BaseModel):
    task_id: str
    plan: dict

@router.get("/api/config")
def get_config():
    """获取当前系统配置"""
    return config_m.config.dict()

@router.post("/api/config")
def save_config(new_config: dict):
    """保存并应用新配置"""
    from config_manager import AppConfig
    try:
        cfg = AppConfig(**new_config)
        config_m.save(cfg)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置保存失败: {str(e)}")

@router.post("/api/system/restart")
async def restart_system():
    """重启前后端服务 — 调用项目根目录的 restart.bat"""
    def do_restart():
        time.sleep(0.3)  # 让响应先发回前端
        # restart.bat 在项目根目录（backend 的上一级）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bat_path = os.path.join(project_root, "restart.bat")
        if not os.path.exists(bat_path):
            # 兜底：只重启后端
            bat_path = os.path.join(project_root, "backend", "_restart_backend.bat")
        subprocess.Popen(
            ["cmd", "/c", bat_path, "silent"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            cwd=project_root,
        )
        os._exit(0)

    threading.Thread(target=do_restart).start()
    return {"message": "正在重启前后端，约 5-8 秒后自动恢复..."}

