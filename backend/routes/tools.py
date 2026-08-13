"""
路由模块：tools
"""
import os
import logging
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

from core.file_ops.sidecars import copy_sidecars, move_sidecars
from shared import (
    config_m, shadow_m, indexer_m, torrent_bl, analysis_cache,
    _get_download_manager, _get_pan_search_service, _get_recycle_bin, _get_file_relocator,
    _tmdb_client, get_clients,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
    guard_path,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask

logger = logging.getLogger(__name__)
# 批量管理请求模型（移动/复制/删除）
class BatchRequest(BaseModel):
    action: str  # "delete" | "move" | "copy" | "remove"
    paths: List[str]
    target_dir: Optional[str] = None

router = APIRouter()

@router.post("/batch_manage")
def batch_manage(req: BatchRequest):
    # 批量删除/移动/复制的入口：paths 与 target_dir 全部来自请求体，
    # 不校验的话可以对任意目录执行删除与移动
    for _p in (req.paths or []):
        guard_path(_p, req.action)
    if req.target_dir:
        guard_path(req.target_dir, f"{req.action} 目标目录")

    success = []
    failed = []
    
    if req.action == "delete":
        recycle = _get_recycle_bin()
        for p in req.paths:
            try:
                if os.path.isdir(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            success.append(os.path.join(root, f))
                    entry = recycle.move_to_bin(p, "batch_delete")
                    if entry:
                        success.append(p)
                    else:
                        failed.append({"path": p, "error": "移入回收站失败"})
                elif os.path.isfile(p):
                    parent_dir = os.path.dirname(p)
                    parent_name = os.path.basename(parent_dir)
                    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                    try:
                        siblings = os.listdir(parent_dir)
                        sibling_videos = [f for f in siblings if os.path.splitext(f)[1].lower() in video_exts]
                        sibling_dirs = [f for f in siblings if os.path.isdir(os.path.join(parent_dir, f)) and not f.startswith('.')]
                    except OSError:
                        sibling_videos = []
                        sibling_dirs = []
                    _TOP_CATS = {"电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"}
                    is_wrapped = len(sibling_videos) == 1 and len(sibling_dirs) == 0 and parent_name not in _TOP_CATS

                    if is_wrapped:
                        for root, _, files in os.walk(parent_dir):
                            for f in files:
                                success.append(os.path.join(root, f))
                        entry = recycle.move_to_bin(parent_dir, "batch_delete")
                        if entry:
                            success.append(parent_dir)
                        else:
                            failed.append({"path": parent_dir, "error": "移入回收站失败"})
                        logger.info(f"[batch_manage] 封装文件夹移入回收站: {parent_dir}")
                    else:
                        entry = recycle.move_to_bin(p, "batch_delete")
                        if entry:
                            success.append(p)
                        else:
                            failed.append({"path": p, "error": "移入回收站失败"})
                else:
                    failed.append({"path": p, "error": "Path not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})

        # 删除后清理空壳目录（向上逐级检查，不删一级分类目录）
        _TOP_CATS = {"电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"}
        cleaned_dirs = set()
        for p in req.paths:
            check_dir = os.path.dirname(p) if os.path.sep in p or "/" in p else ""
            while check_dir and os.path.basename(check_dir) not in _TOP_CATS:
                if not os.path.isdir(check_dir):
                    break
                if check_dir in cleaned_dirs:
                    break
                try:
                    remaining = os.listdir(check_dir)
                    remaining = [f for f in remaining if not f.startswith('.')]
                    if not remaining:
                        entry = recycle.move_to_bin(check_dir, "batch_delete_cleanup")
                        if entry:
                            success.append(check_dir)
                            cleaned_dirs.add(check_dir)
                            logger.info(f"[batch_manage] 清理空目录: {check_dir}")
                        check_dir = os.path.dirname(check_dir)
                        continue
                    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                    has_video = any(
                        os.path.splitext(f)[1].lower() in video_exts
                        for f in remaining if os.path.isfile(os.path.join(check_dir, f))
                    )
                    has_subdir_with_video = False
                    for f in remaining:
                        sub = os.path.join(check_dir, f)
                        if os.path.isdir(sub):
                            for _, _, files in os.walk(sub):
                                if any(os.path.splitext(ff)[1].lower() in video_exts for ff in files):
                                    has_subdir_with_video = True
                                    break
                        if has_subdir_with_video:
                            break
                    if not has_video and not has_subdir_with_video:
                        for root, _, files in os.walk(check_dir):
                            for f in files:
                                success.append(os.path.join(root, f))
                        entry = recycle.move_to_bin(check_dir, "batch_delete_cleanup")
                        if entry:
                            success.append(check_dir)
                            cleaned_dirs.add(check_dir)
                            logger.info(f"[batch_manage] 清理无视频残留目录: {check_dir}")
                        check_dir = os.path.dirname(check_dir)
                        continue
                except OSError:
                    pass
                break

        # 同步从媒体库中移除（匹配文件路径和文件夹前缀）
        library = config_m.load_library()
        deleted_set = set(success)
        # deleted_dirs：包含请求中的路径 + 实际删除的封装文件夹路径
        deleted_dirs = [s for s in success if os.path.sep in s or "/" in s]
        library = [v for v in library if v.get("file_path") not in deleted_set
                   and not any(v.get("file_path", "").startswith(d + os.sep) or v.get("file_path", "").startswith(d + "/") for d in deleted_dirs)]
        config_m.save_library(library)
    
    elif req.action == "move":
        if not req.target_dir:
            raise HTTPException(status_code=400, detail="target_dir required")
        os.makedirs(req.target_dir, exist_ok=True)
        path_map = {}  # old_path → new_path（文件级）
        dir_map = {}   # old_dir → new_dir（文件夹级）
        for p in req.paths:
            try:
                if not os.path.exists(p):
                    failed.append({"path": p, "error": "Path not found"})
                    continue
                new_path = os.path.join(req.target_dir, os.path.basename(p))
                if os.path.isdir(p):
                    # 文件夹移动：整个文件夹搬过去
                    shutil.move(p, new_path)
                    dir_map[p] = new_path
                    success.append(p)
                else:
                    # 文件移动：检查是否在封装文件夹中（单视频+关联文件）
                    parent_dir = os.path.dirname(p)
                    parent_name = os.path.basename(parent_dir)
                    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                    try:
                        siblings = os.listdir(parent_dir)
                        sibling_videos = [f for f in siblings if os.path.splitext(f)[1].lower() in video_exts]
                        sibling_dirs = [f for f in siblings if os.path.isdir(os.path.join(parent_dir, f)) and not f.startswith('.')]
                    except OSError:
                        sibling_videos = []
                        sibling_dirs = []

                    # 封装文件夹判定：只有 1 个视频 + 0 个子目录 + 父目录不是一级分类目录
                    _TOP_CATS = {"电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"}
                    is_wrapped = len(sibling_videos) == 1 and len(sibling_dirs) == 0 and parent_name not in _TOP_CATS

                    is_movie_category = _get_category_from_path(p) == "movie"

                    if is_wrapped:
                        # 移动整个封装文件夹
                        new_dir = os.path.join(req.target_dir, parent_name)
                        shutil.move(parent_dir, new_dir)
                        dir_map[parent_dir] = new_dir
                        success.append(p)
                        logger.info(f"[batch_manage] 封装文件夹移动: {parent_dir} → {new_dir}")
                    elif is_movie_category:
                        movie_dir = os.path.join(req.target_dir, os.path.splitext(os.path.basename(p))[0])
                        os.makedirs(movie_dir, exist_ok=True)
                        movie_path = os.path.join(movie_dir, os.path.basename(p))
                        move_sidecars(p, movie_path, shutil.move)
                        shutil.move(p, movie_path)
                        path_map[p] = movie_path
                        success.append(p)
                        logger.info(f"[batch_manage] 散装电影封装移动: {p} → {movie_path}")
                    else:
                        # 散装文件：移动视频 + 同名关联文件
                        move_sidecars(
                            p,
                            os.path.join(req.target_dir, os.path.basename(p)),
                            shutil.move,
                        )
                        shutil.move(p, new_path)
                        path_map[p] = new_path
                        success.append(p)
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
        # 更新 media_library.json 中的路径
        if path_map or dir_map:
            library = config_m.load_library()
            base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
            for v in library:
                fp = v.get("file_path", "")
                # 文件级匹配
                if fp in path_map:
                    v["file_path"] = path_map[fp]
                    v["file_name"] = os.path.basename(path_map[fp])
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                else:
                    # 文件夹级前缀匹配
                    for old_dir, new_dir in dir_map.items():
                        if fp.startswith(old_dir + os.sep) or fp.startswith(old_dir + "/"):
                            v["file_path"] = new_dir + fp[len(old_dir):]
                            if base:
                                rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                                v["folder_name"] = "" if rel == "." else rel
                            break
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
                        success.append(p)
                    else:
                        # 检查是否在封装文件夹中
                        parent_dir = os.path.dirname(p)
                        parent_name = os.path.basename(parent_dir)
                        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                        try:
                            siblings = os.listdir(parent_dir)
                            sibling_videos = [f for f in siblings if os.path.splitext(f)[1].lower() in video_exts]
                            sibling_dirs = [f for f in siblings if os.path.isdir(os.path.join(parent_dir, f)) and not f.startswith('.')]
                        except OSError:
                            sibling_videos = []
                            sibling_dirs = []
                        _TOP_CATS = {"电影", "动画电影", "电视剧", "动画番", "其他视频", "综艺", "纪录片"}
                        is_wrapped = len(sibling_videos) == 1 and len(sibling_dirs) == 0 and parent_name not in _TOP_CATS
                        if is_wrapped:
                            shutil.copytree(parent_dir, os.path.join(req.target_dir, parent_name))
                        else:
                            copy_sidecars(p, dest, shutil.copy2)
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

# ── AI 路由 ──

@router.post("/ai/test")
def test_ai_connection():
    """测试 AI 连接是否正常"""
    from ai_client import get_ai_client
    client = get_ai_client()
    if not client.enabled:
        return {"success": False, "error": "AI 未启用或配置不完整（需要 API Key、Base URL、模型名，且总开关开启）"}
    content = client.chat(
        [{"role": "user", "content": "请回复 ok"}],
        temperature=0, timeout=10, scene="test",
    )
    if content is None:
        return {"success": False, "error": "AI 服务无响应，请检查 API Key 和 Base URL"}
    return {"success": True, "response": content.strip()[:100]}


@router.get("/ai/status")
def get_ai_status():
    """获取 AI 配置状态、各场景开关、调用统计"""
    from ai_client import get_ai_client, get_usage_stats
    client = get_ai_client()
    conf = config_m.config
    return {
        "enabled": client.enabled,
        "master_switch": conf.ai_enabled,
        "has_credentials": bool(conf.openai_api_key and conf.openai_base_url and conf.openai_model),
        "features": conf.ai_features.dict() if hasattr(conf.ai_features, "dict") else {},
        "usage": get_usage_stats(),
    }


@router.post("/ai/diagnosis")
def ai_diagnosis():
    """AI 媒体库健康诊断"""
    result = ai_organizer.ai_library_diagnosis()
    if result is None:
        raise HTTPException(status_code=400, detail="AI 诊断功能未启用或调用失败")
    return result


class SearchRecommendRequest(BaseModel):
    query: str
    results: List[Dict]
    local_info: Optional[Dict] = None


@router.post("/ai/search-recommend")
def ai_search_recommend(req: SearchRecommendRequest):
    """AI 搜索结果推荐"""
    result = ai_organizer.ai_search_recommend(req.query, req.results, req.local_info)
    if result is None:
        return {"recommended": []}
    return {"recommended": result}


@router.get("/ai/suggest")
def get_ai_suggestions():
    """旧版 AI 整理建议（保留兼容）"""
    from ai_client import get_ai_client
    client = get_ai_client()
    if not client.enabled:
        return []
    videos = config_m.load_library()
    # 旧逻辑保留，后续可替换为新的 AI 流程
    from ai_prompts import prompt_extract_episode
    return []  # TODO: 旧版整理建议待重构为新架构

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
    # 不校验的话这个接口等于"以后端进程权限启动任意本地可执行文件"
    guard_path(path, "播放")
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

