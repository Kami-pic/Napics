"""
路由模块：tools
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

@router.post("/batch_manage")
def batch_manage(req: BatchRequest):
    success = []
    failed = []
    
    if req.action == "delete":
        for p in req.paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "File not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
        # 同步从媒体库中移除
        library = config_m.load_library()
        deleted_set = set(success)
        library = [v for v in library if v.get("file_path") not in deleted_set]
        config_m.save_library(library)
    
    elif req.action == "move":
        if not req.target_dir:
            raise HTTPException(status_code=400, detail="target_dir required")
        os.makedirs(req.target_dir, exist_ok=True)
        path_map = {}  # old_path → new_path
        for p in req.paths:
            try:
                if os.path.exists(p):
                    new_path = os.path.join(req.target_dir, os.path.basename(p))
                    # 同步移动关联文件（NFO/poster/fanart）
                    if os.path.isfile(p):
                        old_base = os.path.splitext(p)[0]
                        new_base = os.path.splitext(new_path)[0]
                        for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                            old_f = old_base + suffix
                            if os.path.exists(old_f):
                                try:
                                    shutil.move(old_f, os.path.join(req.target_dir, os.path.basename(old_f)))
                                except Exception:
                                    pass
                    shutil.move(p, new_path)
                    path_map[p] = new_path
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "File not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
        # 更新 media_library.json 中的路径
        if path_map:
            library = config_m.load_library()
            base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
            for v in library:
                fp = v.get("file_path", "")
                if fp in path_map:
                    v["file_path"] = path_map[fp]
                    v["file_name"] = os.path.basename(path_map[fp])
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
            config_m.save_library(library)
    
    elif req.action == "copy":
        if not req.target_dir:
            raise HTTPException(status_code=400, detail="target_dir required")
        os.makedirs(req.target_dir, exist_ok=True)
        for p in req.paths:
            try:
                if os.path.exists(p):
                    dest = os.path.join(req.target_dir, os.path.basename(p))
                    if os.path.isdir(p):
                        shutil.copytree(p, dest)
                    else:
                        shutil.copy2(p, dest)
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "Not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
    
    elif req.action == "remove":
        # 从媒体库中移除（不删除文件），并记录到排除列表防止同步拉回
        library = config_m.load_library()
        remove_set = set(req.paths)
        # 收集要排除的文件夹路径（去重）
        excluded_folders = set()
        for v in library:
            fp = v.get("file_path", "")
            if fp in remove_set:
                folder = os.path.dirname(fp)
                excluded_folders.add(folder)
        library = [v for v in library if v.get("file_path") not in remove_set]
        config_m.save_library(library)
        # 保存排除列表
        config_m.add_excluded_paths(list(remove_set | excluded_folders))
        success = req.paths
    
    return {"success": success, "failed": failed}

@router.get("/ai/suggest")
def get_ai_suggestions():
    videos = config_m.load_library()
    suggestions = ai_organizer.organize_by_ai(config_m.config.dict(), videos)
    return suggestions

@router.post("/ai/execute")
def execute_ai_suggestions(suggestions: List[Dict]):
    ops = []
    success = []
    failed = []
    for s in suggestions:
        old_p = s.get("original_path")
        new_rel = s.get("suggested_rel_path")
        if not old_p or not new_rel: continue
        base_dir = os.path.dirname(old_p)
        new_p = os.path.join(base_dir, new_rel)
        if os.path.exists(old_p):
            try:
                os.makedirs(os.path.dirname(new_p), exist_ok=True)
                shutil.move(old_p, new_p)
                ops.append({"old_path": old_p, "new_path": new_p})
                success.append(old_p)
            except Exception as e:
                failed.append({"path": old_p, "error": str(e)})
    if ops:
        history_m.create_snapshot(ops)
    return {"success": success, "failed": failed}

@router.get("/ai/history")
def get_ai_history():
    return history_m.list_snapshots()

@router.post("/ai/history/clear")
def clear_ai_history(keep_monthly: bool = True):
    """清空操作历史，keep_monthly=True 时每月保留最新一条"""
    return history_m.clear_all(keep_monthly)

@router.post("/ai/rollback")
def rollback_ai_history(snapshot_id: int):
    ok, res = history_m.rollback(snapshot_id)
    if not ok: raise HTTPException(status_code=404, detail=res)
    return res

@router.get("/play")
def play_video(path: str):
    try:
        conf = config_m.config
        player = conf.player_path if hasattr(conf, 'player_path') and conf.player_path else r'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe'
        if os.path.exists(path):
            subprocess.Popen([player, path])
            return {"success": True}
        else:
            os.startfile(path)
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 影子名管理 API ──

class ShadowNameRequest(BaseModel):
    path: str
    shadow_name: str
    source: str = "manual"

