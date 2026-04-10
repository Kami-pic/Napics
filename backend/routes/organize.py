"""
路由模块：organize
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

@router.post("/organize/rollback")
def rollback_rename(snapshot_id: int):
    """回滚重命名操作，同时更新媒体库路径"""
    # 先读快照拿到 old/new 映射
    snapshot_path = os.path.join("organize_snapshots", f"snapshot_{snapshot_id}.json")
    if not os.path.exists(snapshot_path):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_data = json.load(f)
    
    ok, res = history_m.rollback(snapshot_id)
    if not ok:
        raise HTTPException(status_code=500, detail=str(res))
    
    # 更新媒体库：new_path → old_path
    lib = config_m.load_library()
    changed = False
    for op in snapshot_data.get("ops", []):
        old_p = op["old_path"]
        new_p = op["new_path"]
        # 文件路径直接替换
        for v in lib:
            fp = v.get("file_path", "")
            if fp == new_p:
                v["file_path"] = old_p
                v["file_name"] = os.path.basename(old_p)
                changed = True
            elif fp.startswith(new_p + os.sep) or fp.startswith(new_p + "/"):
                v["file_path"] = old_p + fp[len(new_p):]
                changed = True
    if changed:
        config_m.save_library(lib)
    
    return {"status": "ok", "result": res}

@router.get("/analyze/folder")
def analyze_folder_api(path: str, enhanced: bool = False):
    """分析单个文件夹，返回完整诊断报告
    enhanced=True 时用 TMDB 增强改名预览
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_folder(path, library, client, category_hint=_get_category_from_path(path))

@router.get("/analyze/library")
def analyze_library_api(enhanced: bool = False):
    """分析整个媒体库"""
    config = config_m.config
    base_path = config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else ""
    if not base_path or not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail="NAS path not configured or not accessible")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_library(base_path, library, client)

@router.get("/organize/classify")
def classify_path(path: str):
    """判断文件夹类型"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    # 从路径推断一级分类名
    category_hint = _get_category_from_path(path)
    return organizer.classify_folder(path, library, category_hint=category_hint)


@router.post("/organize/rename")
def rename_videos(path: str, dry_run: bool = True, shadow_only: bool = False):
    """统一重命名
    支持文件夹和单个文件
    shadow_only=True 时不改文件名，只把标准名存到影子名中
    无论哪种模式，都会生成影子名"""
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    library = config_m.load_library()
    
    # 支持单个文件：取其父文件夹来处理（仅预览和影子名用）
    target_path = path
    single_file = False
    single_file_path = ""
    if not os.path.isdir(path):
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            target_path = parent
            single_file = True
            single_file_path = path
        else:
            raise HTTPException(status_code=404, detail="Path not found")
    
    result = organizer.rename_videos_in_folder(target_path, client, True, library, category_hint=_get_category_from_path(target_path))
    
    # 单文件模式：只保留目标文件的结果
    if single_file:
        result = [r for r in result if r.get("old_path") == single_file_path]
    
    if not result:
        return {"mode": "no_change", "message": "当前命名已是标准格式，无需修改", "items": []}
    
    # 始终填充影子名（无论 dry_run 还是 shadow_only）
    if not dry_run:
        shadow_filled = 0
        for r in result:
            old_path = r.get("old_path", "")
            shadow = r.get("shadow_name", "")
            if old_path and shadow:
                if shadow_m.auto_fill(old_path, shadow, source="parsed"):
                    shadow_filled += 1
        
        if shadow_only:
            return {"mode": "shadow_only", "filled": shadow_filled, "total": len(result), "items": result}
        
        # 正常重命名
        if single_file:
            # 单文件模式：只重命名这一个文件，不动其他文件
            actual_result = []
            for r in result:
                if r.get("unchanged"):
                    actual_result.append(r)
                    continue
                old_p = r.get("old_path", "")
                new_p = r.get("new_path", "")
                if old_p and new_p and old_p != new_p and os.path.exists(old_p) and not os.path.exists(new_p):
                    os.rename(old_p, new_p)
                    # 同步重命名关联文件
                    old_base = os.path.splitext(old_p)[0]
                    new_base = os.path.splitext(new_p)[0]
                    for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                        old_f = old_base + suffix
                        new_f = new_base + suffix
                        if os.path.exists(old_f):
                            try: os.rename(old_f, new_f)
                            except: pass
                    actual_result.append(r)
        else:
            actual_result = organizer.rename_videos_in_folder(target_path, client, False, library, category_hint=_get_category_from_path(target_path))
        
        # 创建快照（用于回滚）
        rename_ops = [{"old_path": r["old_path"], "new_path": r["new_path"]}
                      for r in actual_result if not r.get("unchanged") and r.get("old_path") != r.get("new_path")]
        snapshot_id = None
        if rename_ops:
            snapshot_id = history_m.create_snapshot(rename_ops)
        
        # 更新媒体库路径
        if isinstance(actual_result, list) and actual_result:
            file_renames = [(r["old_path"], r["new_path"]) for r in actual_result if not r.get("is_folder") and not r.get("unchanged")]
            folder_renames = [(r["old_path"], r["new_path"]) for r in actual_result if r.get("is_folder") and not r.get("unchanged")]
            
            lib = config_m.load_library()
            changed = False
            
            for old_p, new_p in file_renames:
                for v in lib:
                    if v.get("file_path") == old_p:
                        v["file_path"] = new_p
                        v["file_name"] = os.path.basename(new_p)
                        changed = True
                        break
            
            for old_folder, new_folder in folder_renames:
                for v in lib:
                    fp = v.get("file_path", "")
                    if fp.startswith(old_folder + os.sep) or fp.startswith(old_folder + "/"):
                        v["file_path"] = new_folder + fp[len(old_folder):]
                        changed = True
                    if changed:
                        base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                        if base and v.get("file_path", "").startswith(base):
                            rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                            v["folder_name"] = "" if rel == "." else rel
            
            if changed:
                config_m.save_library(lib)
        
        return {"mode": "renamed", "shadow_filled": shadow_filled, "items": actual_result, "snapshot_id": snapshot_id}
    
    # dry_run 模式：返回预览
    changed_items = [r for r in result if not r.get("unchanged")]
    unchanged_items = [r for r in result if r.get("unchanged")]
    # 统计有多少项可以生成影子名
    shadow_candidates = [r for r in result if r.get("shadow_name") and not r.get("is_folder")]
    has_shadow_work = any(
        not shadow_m.get(r.get("old_path", "")) or 
        (shadow_m.get(r.get("old_path", "")) and shadow_m.get(r.get("old_path", "")).source != "manual")
        for r in shadow_candidates
    ) if shadow_candidates else False
    
    if changed_items:
        msg = f"{len(changed_items)} 项需要重命名"
        if unchanged_items:
            msg += f"，{len(unchanged_items)} 项已是标准格式"
    else:
        msg = "当前命名已是标准格式，无需修改"
        if has_shadow_work:
            msg += f"（可为 {len(shadow_candidates)} 项生成影子名）"
    
    return {
        "mode": "preview",
        "items": result,
        "changed_count": len(changed_items),
        "unchanged_count": len(unchanged_items),
        "shadow_candidates": len(shadow_candidates),
        "has_shadow_work": has_shadow_work,
        "message": msg,
    }

@router.post("/organize/supplement")
def scrape_supplement(path: str):
    """刮削补充（只补缺少的字段）"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return organizer.scrape_supplement(path, client)

@router.post("/organize/seasons")
def reorganize_seasons(path: str, dry_run: bool = True):
    """多季规整"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    result = organizer.reorganize_seasons(path, client, dry_run, category_hint=_get_category_from_path(path))
    if not dry_run and result.get("ops"):
        _sync_library_paths(result["ops"])
    return result

@router.post("/organize/one-click")
async def one_click_organize(path: str, dry_run: bool = True):
    """一键整理 — 旧路由，内部重定向到 V3 /organize/full"""
    return await organize_full(path=path, dry_run=dry_run, use_ai=False, request=None)


@router.post("/organize/folder")
def organize_folder(path: str, dry_run: bool = True):
    """归类整理 — 消费分析层输出执行（旧路由，兼容）"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    library = config_m.load_library()
    category_hint = _get_category_from_path(path)
    result = organizer.organize_folder(path, client, dry_run, library, category_hint=category_hint)
    if not dry_run and result.get("ops"):
        _sync_library_paths(result["ops"])
    return result


# ── V3 整理 API ──

@router.post("/organize/structure")
def organize_structure(path: str, dry_run: bool = True):
    """V3 入口 A：纯结构整理（离线，不联网）。
    只做物理收纳：基础封装 + 结构归位 + 季目录创建。
    降级策略：没有 episode.nfo 时，用正则从文件名猜季号归位。
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path not found or not a directory")

    category_hint = _get_category_from_path(path)
    result = {"status": "ok", "mode": "structure_only", "ops": [], "count": 0}

    # Step 0: 基础封装（仅一级分类 + movie 标签）
    if _is_top_category(path) and category_hint == "movie":
        wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=dry_run, category_tag=category_hint)
        if wrap_result.get("ops"):
            result["ops"].extend(wrap_result["ops"])
            if not dry_run:
                _sync_library_paths(wrap_result["ops"])

    # 结构归位：散装视频封装 + 孤立刮削归位（对所有类型都做）
    library = config_m.load_library()
    org_result = organizer.organize_folder(path, tmdb_client=None, dry_run=dry_run,
                                           library_data=library, category_hint=category_hint)
    if org_result.get("ops"):
        result["ops"].extend(org_result["ops"])
        if not dry_run:
            _sync_library_paths(org_result["ops"])

    # 季目录归位：优先用 NFO，降级用正则
    reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=dry_run)
    if reorg.get("ops"):
        result["ops"].extend(reorg["ops"])
        if not dry_run:
            _sync_library_paths(reorg["ops"])
    else:
        # 降级：没有 NFO 时用旧的正则归位（从文件名猜季号）
        reorg_fallback = organizer.reorganize_seasons(path, tmdb_client=None, dry_run=dry_run, category_hint=category_hint)
        if reorg_fallback.get("ops"):
            result["ops"].extend(reorg_fallback["ops"])
            if not dry_run:
                _sync_library_paths(reorg_fallback["ops"])

    result["count"] = len(result["ops"])
    return result


@router.post("/organize/full")
async def organize_full(path: str, dry_run: bool = True, use_ai: bool = False,
                        request: Request = None, whitelist: List[str] = None):
    """V3 入口 B：一键完全整理（两段式提交）。
    dry_run=True：推演模式，返回 Action Plan（严禁任何文件系统写操作）。
    dry_run=False：确权执行，接收前端回传的 action_plan 直接执行。
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path not found or not a directory")

    category_hint = _get_category_from_path(path)
    client = _tmdb_client()

    if dry_run:
        # ══ 推演模式：只计算，严禁落盘 ══
        library = config_m.load_library()

        result = {
            "status": "ok", "mode": "full_organize", "dry_run": True,
            "path": path, "category_hint": category_hint,
        }

        # Step 0 推演：扫描散落视频，生成封装 plan
        wrap_plan = []
        if _is_top_category(path) and category_hint == "movie":
            wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=True, category_tag=category_hint)
            wrap_plan = wrap_result.get("ops", [])
        result["wrap_plan"] = wrap_plan

        # Step 1 推演：扫描旧刮削，生成清理 plan
        archive_plan = organizer.smart_archive_plan(path)
        result["archive_plan"] = archive_plan

        # Step 2：分析判定（只读）
        report = analyzer.analyze_folder(path, library, category_hint=category_hint)
        folder_type = report.get("folder_type", "")
        result["folder_type"] = folder_type
        result["analyze"] = {
            "structure_ops": len(report.get("structure_ops", [])),
            "rename_ops": len(report.get("rename_ops", [])),
            "scrape_issues": len(report.get("scrape_issues", [])),
        }

        # Step 3 推演：刮削计算（只读）
        if client:
            scrape_result = scraper.scrape_folder(
                path, client, force=True, folder_type=folder_type,
                dry_run=True, use_ai=use_ai, whitelist=whitelist
            )
            result["tmdb_match"] = scrape_result.get("tmdb_match", {})
            result["plan"] = scrape_result.get("plan", [])
            result["summary"] = scrape_result.get("summary", {})
        else:
            result["tmdb_match"] = {}
            result["plan"] = []
            result["summary"] = {"error": "TMDB API key not configured"}

        return result

    else:
        # ══ 确权执行模式：接收 Plan 直接执行 ══
        # 从 request body 获取 action_plan（前端回传）
        action_plan = None
        try:
            body = await request.json() if request else None
            if body and "action_plan" in body:
                action_plan = body["action_plan"]
        except Exception:
            pass

        result = {
            "status": "ok", "mode": "full_organize", "dry_run": False,
            "path": path, "steps": {},
        }

        if action_plan:
            # 有 Plan → 所见即所得执行
            tmdb_match = action_plan.get("tmdb_match", {})
            plan_items = action_plan.get("plan", [])
            folder_type = action_plan.get("folder_type", "")

            # 执行 wrap_plan
            wrap_plan = action_plan.get("wrap_plan", [])
            if wrap_plan:
                for op in wrap_plan:
                    if op.get("action") == "move":
                        if op.get("mkdir"):
                            os.makedirs(op["mkdir"], exist_ok=True)
                        if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                            shutil.move(op["old"], op["new"])
                _sync_library_paths(wrap_plan)
                result["steps"]["wrap"] = len(wrap_plan)

            # 执行 archive_plan
            archive_plan = action_plan.get("archive_plan", [])
            if archive_plan:
                organizer.execute_archive_plan(archive_plan)
                result["steps"]["archive"] = len(archive_plan)

            # 执行 scrape（写 NFO）
            tmdb_id = tmdb_match.get("tmdb_id", 0)
            if tmdb_id and client:
                # 写 tvshow.nfo
                tv_detail = client.get_tv_detail(tmdb_id)
                if tv_detail and tv_detail.tmdb_id:
                    proxy = getattr(client, 'proxy', '') or ''
                    for old in ["movie.nfo", "tvshow.nfo"]:
                        p = os.path.join(path, old)
                        if os.path.exists(p):
                            try: os.remove(p)
                            except: pass
                    scraper.write_tvshow_nfo(path, tv_detail)
                    if tv_detail.poster_url:
                        scraper.download_poster(path, tv_detail.poster_url, proxy=proxy)

                # 写 episode.nfo
                nfo_written = 0
                showtitle = tv_detail.title if tv_detail else ""
                for item in plan_items:
                    if "write_episode_nfo" not in item.get("actions", []):
                        continue
                    mapped = item.get("mapped")
                    if not mapped:
                        continue
                    s, e = mapped["season"], mapped["episode"]
                    vpath = item["original_path"]
                    if not os.path.exists(vpath):
                        continue
                    ep_scrape = tmdb_client.ScrapeResult(
                        tmdb_id=tmdb_id, media_type="episode",
                        title=item.get("episode_title") or showtitle,
                        episode_title=item.get("episode_title", ""),
                        season_number=s, episode_number=e,
                    )
                    scraper.write_episode_nfo(vpath, ep_scrape, showtitle=showtitle)
                    nfo_written += 1
                result["steps"]["scrape"] = {"nfo_written": nfo_written}

            # Reload library
            library = config_m.load_library()

            # 执行结构归位（读 NFO 建季目录）
            if folder_type == "tv":
                reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
                if reorg.get("ops"):
                    _sync_library_paths(reorg["ops"])
                result["steps"]["structure"] = {"moved": len(reorg.get("ops", []))}

            # Reload library
            library = config_m.load_library()

            # 执行影子名写入
            shadow_filled = 0
            for item in plan_items:
                shadow = item.get("target_shadow_name")
                vpath = item.get("original_path", "")
                if shadow and vpath:
                    # 文件可能已被移动到季目录，用 target_path
                    actual_path = item.get("target_path", vpath)
                    if os.path.exists(actual_path):
                        if shadow_m.auto_fill(actual_path, shadow, source="parsed"):
                            shadow_filled += 1
                    elif os.path.exists(vpath):
                        if shadow_m.auto_fill(vpath, shadow, source="parsed"):
                            shadow_filled += 1
            result["steps"]["shadow"] = shadow_filled

        else:
            # 无 Plan → 完整跑一遍（兼容旧调用方式）
            library = config_m.load_library()

            # Step 0
            if _is_top_category(path) and category_hint == "movie":
                wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=False, category_tag=category_hint)
                if wrap_result.get("ops"):
                    _sync_library_paths(wrap_result["ops"])
                result["steps"]["wrap"] = wrap_result.get("count", 0)

            # Step 1
            archived = organizer.smart_archive_recursive(path)
            result["steps"]["archive"] = archived

            # Step 2
            report = analyzer.analyze_folder(path, library, category_hint=category_hint)
            folder_type = report.get("folder_type", "")
            result["steps"]["analyze"] = folder_type

            # Step 3
            if client:
                scrape_result = scraper.scrape_folder(
                    path, client, force=True, folder_type=folder_type,
                    dry_run=False, use_ai=use_ai
                )
                result["steps"]["scrape"] = scrape_result.get("summary", {})

            # Reload + Step 4
            library = config_m.load_library()
            if folder_type == "tv":
                reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
                if reorg.get("ops"):
                    _sync_library_paths(reorg["ops"])
                result["steps"]["structure"] = len(reorg.get("ops", []))

            # Reload + Step 5
            library = config_m.load_library()
            shadow_filled = 0
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            for root_dir, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if os.path.splitext(f)[1].lower() not in video_exts:
                        continue
                    vpath = os.path.join(root_dir, f)
                    shadow = organizer.generate_shadow_name_from_nfo(vpath, path, folder_type)
                    if shadow:
                        if shadow_m.auto_fill(vpath, shadow, source="parsed"):
                            shadow_filled += 1
            result["steps"]["shadow"] = shadow_filled

        return result


@router.post("/organize/merge-scattered")
def merge_scattered_seasons_api(path: str = "", dry_run: bool = True):
    """合并散落的同剧多季目录"""
    config = config_m.config
    base_path = path or (config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else "")
    if not base_path or not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail="Path not configured or not accessible")
    library = config_m.load_library()
    report = analyzer.analyze_library(base_path, library)
    results = []
    for issue in report.get("cross_folder_issues", []):
        if issue.get("type") == "scattered_seasons":
            r = organizer.merge_scattered_seasons(issue, dry_run)
            results.append(r)
            if not dry_run and r.get("ops"):
                _sync_library_paths([op for op in r["ops"] if op.get("action") == "move_dir"])
    return {"results": results, "total_issues": len(results)}

@router.post("/rename")
def rename_item(old_path: str, new_name: str):
    """手动重命名文件或文件夹"""
    print(f"[rename] old_path={old_path}")
    print(f"[rename] new_name={new_name}")
    print(f"[rename] exists={os.path.exists(old_path)}")
    if not os.path.exists(old_path):
        # 尝试修复路径分隔符
        alt_path = old_path.replace("/", "\\")
        print(f"[rename] 尝试替换分隔符: {alt_path} exists={os.path.exists(alt_path)}")
        if os.path.exists(alt_path):
            old_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"Path not found: {old_path}")
    
    parent = os.path.dirname(old_path)
    new_path = os.path.join(parent, new_name)
    
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Target name already exists")
    
    try:
        os.rename(old_path, new_path)
        
        # 同步 media_library.json
        library = config_m.load_library()
        changed = False
        if os.path.isdir(new_path):
            # 文件夹重命名：更新所有子文件的路径
            for v in library:
                fp = v.get("file_path", "")
                if fp.startswith(old_path + os.sep) or fp.startswith(old_path + "/"):
                    v["file_path"] = new_path + fp[len(old_path):]
                    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                    changed = True
            
            # movie 类型（单视频文件夹）：同时重命名视频文件和关联文件
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            try:
                items = os.listdir(new_path)
                videos = [f for f in items if os.path.isfile(os.path.join(new_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                subdirs = [f for f in items if os.path.isdir(os.path.join(new_path, f)) and not f.startswith('.')]
                if len(videos) == 1 and len(subdirs) == 0:
                    # 单视频文件夹：重命名视频文件为文件夹名 + 原扩展名
                    old_video = videos[0]
                    ext = os.path.splitext(old_video)[1]
                    if not ext:
                        pass  # 视频没有扩展名，跳过
                    else:
                        new_video = new_name + ext
                        if old_video != new_video:
                            old_vp = os.path.join(new_path, old_video)
                            new_vp = os.path.join(new_path, new_video)
                            if not os.path.exists(new_vp):
                                os.rename(old_vp, new_vp)
                                # 更新 library 中的文件路径和文件名
                                old_vp_norm = old_vp.replace("/", os.sep)
                                for v in library:
                                    vfp = v.get("file_path", "").replace("/", os.sep)
                                    if vfp == old_vp_norm:
                                        v["file_path"] = new_vp
                                        v["file_name"] = new_video
                                        changed = True
                                # 重命名关联文件（NFO、poster 等）
                                old_base = os.path.splitext(old_vp)[0]
                                new_base = os.path.splitext(new_vp)[0]
                                for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                                    old_f = old_base + suffix
                                    new_f = new_base + suffix
                                    if os.path.exists(old_f):
                                        try:
                                            os.rename(old_f, new_f)
                                        except Exception:
                                            pass
            except OSError:
                pass
        else:
            # 文件重命名
            for v in library:
                if v.get("file_path") == old_path:
                    v["file_path"] = new_path
                    v["file_name"] = new_name
                    changed = True
                    break
            
            # 同时重命名对应的 .nfo / -poster.jpg 等关联文件
            old_base = os.path.splitext(old_path)[0]
            new_base = os.path.splitext(new_path)[0]
            for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                old_f = old_base + suffix
                new_f = new_base + suffix
                if os.path.exists(old_f):
                    try:
                        os.rename(old_f, new_f)
                    except Exception:
                        pass
            
            # 单视频文件夹（仅 movie 类型）：同步重命名父文件夹
            # TV 类型绝不联动改文件夹名（多集共用一个文件夹）
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            file_ext = os.path.splitext(new_name)[1].lower()
            if file_ext in video_exts:
                folder_path = os.path.dirname(new_path)
                # 检查文件夹类型：如果是 TV/season 类型，跳过
                folder_type = ""
                for v in library:
                    fp = v.get("file_path", "")
                    if fp.startswith(folder_path):
                        folder_type = v.get("folder_type", "")
                        break
                # 只有 movie 类型（或未分类的单视频文件夹）才同步改文件夹名
                is_tv = folder_type in ("tv", "season", "anime")
                if not is_tv:
                    try:
                        items = os.listdir(folder_path)
                        videos_in_folder = [f for f in items if os.path.isfile(os.path.join(folder_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                        subdirs_in_folder = [f for f in items if os.path.isdir(os.path.join(folder_path, f)) and not f.startswith('.')]
                        if len(videos_in_folder) == 1 and len(subdirs_in_folder) == 0:
                            new_folder_name = os.path.splitext(new_name)[0]
                            old_folder_name = os.path.basename(folder_path)
                            if old_folder_name != new_folder_name:
                                new_folder_path = os.path.join(os.path.dirname(folder_path), new_folder_name)
                                if not os.path.exists(new_folder_path):
                                    os.rename(folder_path, new_folder_path)
                                    for v in library:
                                        fp = v.get("file_path", "")
                                        if fp.startswith(folder_path + os.sep) or fp.startswith(folder_path + "/") or fp == new_path:
                                            v["file_path"] = new_folder_path + fp[len(folder_path):]
                                            base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                                            if base:
                                                rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                                                v["folder_name"] = "" if rel == "." else rel
                                            changed = True
                                    new_path = os.path.join(new_folder_path, new_name)
                    except OSError:
                        pass
        
        if changed:
            config_m.save_library(library)
        
        return {"status": "ok", "old_path": old_path, "new_path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 豆瓣热榜与新增影片 API ──

@router.post("/organize/full-stream")
async def organize_full_stream(path: str, dry_run: bool = True, use_ai: bool = False):
    """V3 一键整理 SSE 流式进度反馈版本。
    5 步串行：wrap → archive → analyze → scrape → structure
    每步完成发送进度事件。
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path not found")

    category_hint = _get_category_from_path(path)
    client = _tmdb_client()

    async def event_stream():
        import traceback
        try:
            library = config_m.load_library()
            total_steps = 5
            result = {"path": path, "dry_run": dry_run, "steps": {}}

            # Step 1: 散装封装
            yield f"data: {json.dumps({'step': 1, 'total': total_steps, 'label': '散装视频封装', 'status': 'running'})}\n\n"
            wrap_plan = []
            if _is_top_category(path) and category_hint == "movie":
                wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=dry_run, category_tag=category_hint)
                wrap_plan = wrap_result.get("ops", [])
                if not dry_run and wrap_plan:
                    _sync_library_paths(wrap_plan)
            result["steps"]["wrap"] = len(wrap_plan)
            yield f"data: {json.dumps({'step': 1, 'total': total_steps, 'label': '散装视频封装', 'status': 'done', 'count': len(wrap_plan)})}\n\n"

            # Step 2: 旧刮削清理
            yield f"data: {json.dumps({'step': 2, 'total': total_steps, 'label': '旧刮削清理', 'status': 'running'})}\n\n"
            if dry_run:
                archive_plan = organizer.smart_archive_plan(path)
                result["steps"]["archive"] = len(archive_plan)
            else:
                archived = organizer.smart_archive_recursive(path)
                result["steps"]["archive"] = archived
            yield f"data: {json.dumps({'step': 2, 'total': total_steps, 'label': '旧刮削清理', 'status': 'done', 'count': result['steps']['archive']})}\n\n"

            # Step 3: 分析判定
            yield f"data: {json.dumps({'step': 3, 'total': total_steps, 'label': '分析判定', 'status': 'running'})}\n\n"
            library = config_m.load_library()
            report = analyzer.analyze_folder(path, library, category_hint=category_hint)
            folder_type = report.get("folder_type", "")
            result["steps"]["analyze"] = {
                "folder_type": folder_type,
                "structure_ops": len(report.get("structure_ops", [])),
                "rename_ops": len(report.get("rename_ops", [])),
            }
            yield f"data: {json.dumps({'step': 3, 'total': total_steps, 'label': '分析判定', 'status': 'done', 'folder_type': folder_type})}\n\n"

            # Step 4: 刮削
            yield f"data: {json.dumps({'step': 4, 'total': total_steps, 'label': '刮削确权', 'status': 'running'})}\n\n"
            scrape_summary = {}
            if client:
                scrape_result = scraper.scrape_folder(
                    path, client, force=True, folder_type=folder_type,
                    dry_run=dry_run, use_ai=use_ai
                )
                scrape_summary = scrape_result.get("summary", {})
            result["steps"]["scrape"] = scrape_summary
            yield f"data: {json.dumps({'step': 4, 'total': total_steps, 'label': '刮削确权', 'status': 'done', 'summary': scrape_summary})}\n\n"

            # Step 5: 结构归位 + 影子名
            yield f"data: {json.dumps({'step': 5, 'total': total_steps, 'label': '结构归位', 'status': 'running'})}\n\n"
            if not dry_run:
                library = config_m.load_library()
                if folder_type == "tv":
                    reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
                    if reorg.get("ops"):
                        _sync_library_paths(reorg["ops"])
                    result["steps"]["structure"] = len(reorg.get("ops", []))

                # 影子名
                library = config_m.load_library()
                shadow_filled = 0
                video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                for root_dir, dirs, files in os.walk(path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for f in files:
                        if os.path.splitext(f)[1].lower() not in video_exts:
                            continue
                        vpath = os.path.join(root_dir, f)
                        shadow = organizer.generate_shadow_name_from_nfo(vpath, path, folder_type)
                        if shadow and shadow_m.auto_fill(vpath, shadow, source="parsed"):
                            shadow_filled += 1
                result["steps"]["shadow"] = shadow_filled
            yield f"data: {json.dumps({'step': 5, 'total': total_steps, 'label': '结构归位', 'status': 'done'})}\n\n"

            # 完成
            yield f"data: {json.dumps({'step': total_steps, 'total': total_steps, 'status': 'completed', 'result': result})}\n\n"

            # 整理完成后自动更新分析缓存
            analysis_cache.invalidate()

        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── 整理历史记录 ──
@router.get("/organize/history")
def get_organize_history(limit: int = 50):
    """获取整理历史记录"""
    snapshots = history_m.list_snapshots()
    # 按时间倒序，限制数量
    snapshots.sort(key=lambda x: x.get("time", ""), reverse=True)
    return {"snapshots": snapshots[:limit], "total": len(snapshots)}

@router.get("/organize/history/{snapshot_id}")
def get_organize_history_detail(snapshot_id: int):
    """获取单条整理历史详情"""
    snapshots = history_m.list_snapshots()
    for s in snapshots:
        if s.get("id") == snapshot_id:
            return s
    raise HTTPException(status_code=404, detail="Snapshot not found")


# ── 整理替换数据模型 ──
class RelocateRequest(BaseModel):
    task_id: str
    auto_replace: bool = False

class ExecuteRelocateRequest(BaseModel):
    task_id: str
    plan: dict


# ── 树状结构构建工具 ──

def _build_old_tree(coexist_pairs, save_path: str) -> list:
    """将旧资源冲突列表构建为树状结构。
    返回 [{name, type, size_bytes, category, children?}, ...]
    """
    root_name = os.path.basename(save_path) or save_path
    children = []
    for p in coexist_pairs:
        old_path = p.old_file if isinstance(p, dict) else getattr(p, "old_file", "")
        category = p.get("category", "video") if isinstance(p, dict) else getattr(p, "category", "video")
        is_folder = p.get("is_folder", False) if isinstance(p, dict) else getattr(p, "is_folder", False)
        old_size = p.get("old_size_gb", 0) if isinstance(p, dict) else getattr(p, "old_size_gb", 0)
        
        name = os.path.basename(old_path)
        # 计算相对于 save_path 的路径
        try:
            rel = os.path.relpath(old_path, save_path)
        except ValueError:
            rel = name
        
        node = {
            "name": name,
            "rel_path": rel,
            "type": "dir" if is_folder else "file",
            "category": category,  # "video" | "folder" | "non_video"
            "size_bytes": int(old_size * 1024 * 1024 * 1024),
        }
        
        # 文件夹节点：扫描子内容
        if is_folder and os.path.isdir(old_path):
            sub_children = []
            try:
                for item in sorted(os.listdir(old_path)):
                    item_path = os.path.join(old_path, item)
                    ext = os.path.splitext(item)[1].lower()
                    is_video = ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                    is_sub = ext in {".ass", ".srt", ".ssa", ".sub", ".idx", ".sup"}
                    ftype = "video" if is_video else ("subtitle" if is_sub else "other")
                    sz = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                    sub_children.append({"name": item, "type": ftype, "size_bytes": sz})
            except Exception:
                pass
            node["children"] = sub_children
        
        children.append(node)
    
    return [{"name": root_name, "type": "root", "children": children}]


def _build_new_tree(new_files_all) -> list:
    """将新资源文件列表构建为多层树状结构（递归按目录分组）。"""
    if not new_files_all:
        return []
    
    def _classify_ext(name):
        ext = os.path.splitext(name)[1].lower()
        if ext in {".mp4",".mkv",".avi",".mov",".wmv",".rmvb",".rm",".flv",".ts",".m4v"}:
            return "video"
        if ext in {".ass",".srt",".ssa",".sub",".idx",".sup"}:
            return "subtitle"
        return "other"
    
    # 构建嵌套字典树
    root = {}  # {name: {"__files__": [...], "subdir": {...}}}
    
    for f in new_files_all:
        name = f.get("name", "")
        size = f.get("size_bytes", f.get("size", 0))
        parts = name.replace("/", os.sep).replace("\\", os.sep).split(os.sep)
        
        current = root
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # 叶子节点（文件）
                if "__files__" not in current:
                    current["__files__"] = []
                current["__files__"].append({"name": part, "size_bytes": size})
            else:
                # 目录节点
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    def _dict_to_tree(d) -> list:
        """递归将嵌套字典转为树节点列表"""
        nodes = []
        # 先处理子目录
        for key, val in sorted(d.items()):
            if key == "__files__":
                continue
            children = _dict_to_tree(val)
            dir_size = sum(c.get("size_bytes", 0) for c in children)
            nodes.append({
                "name": key,
                "type": "dir",
                "size_bytes": dir_size,
                "children": children,
            })
        # 再处理文件
        for f in sorted(d.get("__files__", []), key=lambda x: x["name"]):
            nodes.append({
                "name": f["name"],
                "type": _classify_ext(f["name"]),
                "size_bytes": f["size_bytes"],
            })
        return nodes
    
    return _dict_to_tree(root)


def _build_plan_tree(action_plan, coexist_pairs=None, save_path: str = "") -> list:
    """构建"执行后目录快照"树：新文件去向 + 旧文件删除 + 保留的文件夹。"""
    tree = []
    
    plan_items = []
    if action_plan:
        plan_items = action_plan.get("plan", []) if isinstance(action_plan, dict) else []
    
    season_groups = {}
    root_new_items = []
    
    for item in (plan_items or []):
        if item is None:
            continue
        season_dir = item.get("target_season_dir")
        actions = item.get("actions", [])
        skip = item.get("skip_reason") or ""
        target_name = item.get("target_filename") or item.get("original_filename", "?")
        original_name = item.get("original_filename", "?")
        mapped = item.get("mapped")
        
        node = {
            "name": target_name,
            "original_name": original_name,
            "type": "video",
            "action": "rename" if "write_episode_nfo" in actions else ("skip" if skip else "keep"),
            "skip_reason": skip,
            "season": mapped.get("season") if mapped else None,
            "episode": mapped.get("episode") if mapped else None,
        }
        
        if season_dir and str(season_dir) != "None":
            if season_dir not in season_groups:
                season_groups[season_dir] = []
            season_groups[season_dir].append(node)
        else:
            root_new_items.append(node)
    
    # 季目录节点（新建）
    for season_dir in sorted(season_groups.keys()):
        items = season_groups[season_dir]
        tree.append({
            "name": season_dir,
            "type": "dir",
            "action": "create",
            "children": sorted(items, key=lambda x: (x.get("episode") or 999)),
        })
    
    # 根级新文件（跳过的等）
    for ri in root_new_items:
        tree.append(ri)
    
    # 旧资源：标记删除或保留
    if coexist_pairs:
        for p in coexist_pairs:
            old_file = p.old_file if hasattr(p, "old_file") else p.get("old_file", "")
            category = p.category if hasattr(p, "category") else p.get("category", "video")
            is_folder = p.is_folder if hasattr(p, "is_folder") else p.get("is_folder", False)
            old_size = p.old_size_gb if hasattr(p, "old_size_gb") else p.get("old_size_gb", 0)
            name = os.path.basename(old_file)
            
            if category == "non_video":
                tree.append({
                    "name": name,
                    "type": "dir" if is_folder else "other",
                    "action": "keep",
                    "skip_reason": "非视频，保留不动",
                })
            else:
                tree.append({
                    "name": name,
                    "type": "dir" if is_folder else "video",
                    "action": "delete",
                    "size_bytes": int(old_size * 1024 * 1024 * 1024),
                })
    
    return tree


# ── 下载提交时检查黑名单 ──
@router.post("/organize/dry-run")
async def organize_dry_run(req: RelocateRequest):
    """阶段一：整理替换探测（原地识别模式）"""
    import traceback
    try:
        dm = _get_download_manager()
        task = dm.get_task(req.task_id)
        if not task:
            return {"status": "failed", "message": f"任务不存在: {req.task_id}", "coexist_pairs": []}

        # 安全检查：save_path 不能是一级分类目录或 NAS 根目录
        # 这些路径下文件太多，整理替换探测会卡死
        if _is_top_category(task.save_path):
            return {
                "status": "failed",
                "message": f"该任务的保存路径是一级分类目录（{os.path.basename(task.save_path)}），"
                           f"无法进行整理替换探测。请手动将文件移到正确的子目录后重试。",
                "coexist_pairs": []
            }
        nas_roots = config_m.config.nas_paths or []
        if any(os.path.normpath(task.save_path).lower() == os.path.normpath(r).lower() for r in nas_roots):
            return {
                "status": "failed",
                "message": "该任务的保存路径是 NAS 根目录，无法进行整理替换探测。",
                "coexist_pairs": []
            }

        # 获取新资源文件列表（含大小）
        file_info_list = []   # [{name, size_bytes}, ...]
        if task.downloader_hash:
            try:
                clients = get_clients()
                qb = clients.get("qb")
                if qb:
                    file_info_list = qb.get_torrent_files(task.downloader_hash)
            except Exception as qe:
                print(f"[DryRun] qB 获取文件列表失败: {qe}")
        
        # 提取纯路径名作为白名单（如果为空则传 None，触发 relocator 的全量探测逻辑）
        new_files = [f["name"] for f in file_info_list] if file_info_list else None
        
        try:
            print(f"\n[DryRun] task={task.media_name}, save_path={task.save_path}, whitelist={len(new_files) if new_files else 'None'}")
        except UnicodeEncodeError:
            print("\n[DryRun] task=<UnicodeName>, whitelist=", len(new_files) if new_files else 'None')

        rel = _get_file_relocator()
        res = await rel.relocate(task, new_files_whitelist=new_files)

        try:
            print(f"[DryRun] result: status={res.status}, pairs={len(res.coexist_pairs)}, error={res.error}")
        except UnicodeEncodeError:
            print(f"[DryRun] result: status={res.status}, pairs={len(res.coexist_pairs)}")

        if res.status == "awaiting_confirm":
            # 🛡️ 兜底逻辑：如果 qB 没给文件列表，从推演计划中提取已识别的视频
            display_new_files = file_info_list
            if not display_new_files and res.action_plan:
                display_new_files = [
                    {"name": os.path.relpath(item["source_path"], task.save_path), "size": 0}
                    for item in res.action_plan
                ]
            
            # 构建三栏树状数据
            old_tree = _build_old_tree(res.coexist_pairs, task.save_path)
            new_tree = _build_new_tree(display_new_files)
            plan_tree = _build_plan_tree(res.action_plan, res.coexist_pairs, task.save_path)
            
            return {
                "status": "awaiting_confirm",
                "message": "发现库中存量旧版本，建议执行整理替换",
                "coexist_pairs": [p.dict() for p in res.coexist_pairs],
                "plan": res.action_plan,
                "new_files_all": display_new_files,
                # 树状结构数据（前端优先使用）
                "old_tree": old_tree,
                "new_tree": new_tree,
                "plan_tree": plan_tree,
            }
        
        if res.status == "failed":
            return {"status": "failed", "message": f"探测失败: {res.error}", "coexist_pairs": []}
        
        if res.status == "archived":
            # 探测阶段禁止自动归档，仅返回状态供 UI 提示
            pass
            
        return {"status": res.status, "message": "未发现冲突，可直接归档", "coexist_pairs": []}
    except Exception as e:
        tb = traceback.format_exc()
        try:
            print(tb)
        except UnicodeEncodeError:
            # 安全打印以防 gbk 错误
            pass
        # 截取 traceback 最后 3 行供前端显示
        tb_lines = tb.strip().split("\n")
        tb_tail = "\n".join(tb_lines[-3:])
        return {"status": "failed", "message": f"服务端异常: {e}\n\n{tb_tail}", "coexist_pairs": []}




@router.post("/organize/execute")
async def organize_execute(req: ExecuteRelocateRequest):
    """阶段二：执行整理替换。包含：清理旧资源 -> 新资源整理 -> 重新刮削"""
    dm = _get_download_manager()
    task = dm.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
        
    rel = _get_file_relocator()
    # 注入白名单到 plan 中，供 confirm_replace 使用
    # 这样 confirm_replace 就不需要重新查白名单了
    if task.downloader_hash:
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            file_info = qb.get_torrent_files(task.downloader_hash)
            req.plan["whitelist"] = [f["name"] for f in file_info]

    execute_res = await rel.confirm_replace(task, req.plan)
    
    if execute_res.success:
        dm.archive_task(task.id, organized=True)
        
    return {"status": execute_res.status, "message": execute_res.error or "整理替换任务执行完毕"}

@router.post("/organize/archive-both")
async def organize_archive_both(req: ExecuteRelocateRequest):
    """阶段二：执行共存归档。包含：旧资源封箱 -> 新资源原样归档"""
    dm = _get_download_manager()
    task = dm.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
        
    rel = _get_file_relocator()
    
    # 重新探测冲突以获取旧资源列表
    new_files = []
    if task.downloader_hash:
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            new_files = qb.get_torrent_files(task.downloader_hash)
            
    res = await rel.relocate(task, new_files_whitelist=new_files)
    
    execute_res = await rel.archive_both(task, res.coexist_pairs)
    
    if execute_res.success:
        dm.archive_task(task.id, organized=True)
        
    return {"status": execute_res.status, "message": execute_res.error or "共存归档任务执行完毕"}

@router.post("/organize/purge-old")
async def organize_purge_old(task_id: str):
    """辅助：只清理旧数据。回收所有非新资源文件。"""
    dm = _get_download_manager()
    task = dm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
        
    new_files = []
    if task.downloader_hash:
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            new_files = qb.get_torrent_files(task.downloader_hash)
    
    if not new_files:
        return {"status": "failed", "message": "无法识别新任务文件，为防误删，停止清理"}

    rel = _get_file_relocator()
    # 执行推演探测旧资源
    res = await rel.relocate(task, new_files_whitelist=new_files)
    if res.coexist_pairs:
        # 回收旧资源
        for pair in res.coexist_pairs:
            rel._recycle_old_files(pair, task.id)
        return {"status": "ok", "message": f"已清理 {len(res.coexist_pairs)} 组旧存量数据"}
        
    return {"status": "ok", "message": "未发现需要清理的旧数据"}



