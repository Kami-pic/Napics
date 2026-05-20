"""
路由模块：library
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

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/scan")
async def scan_path(path: str, library_name: str = ""):
    """EventSource 实时返回扫描进度。
    library_name: 如果指定，folder_name 会以该名称为前缀（用于虚拟媒体库）"""
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Path does not exist")
    
    def event_generator():
        results = []
        try:
            # 1. 发现阶段
            yield "data: " + json.dumps({"type": "start", "total": 0, "message": "正在获取文件列表..."}) + "\n\n"
            
            all_files = []
            extensions = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"]
            # 获取排除目录（库级 + 全局）
            _scan_excludes = set()
            if library_name:
                for lib in (config_m.config.media_libraries or []):
                    if lib.name == library_name:
                        _scan_excludes.update(lib.exclude_dirs)
                        break
            _global_excl = set(
                d.strip() for d in (config_m.config.exclude_dirs or "").split(",") if d.strip()
            )
            _scan_excludes.update(_global_excl)
            for root, dirs, files in os.walk(path):
                if "@eaDir" in root or "#recycle" in root: continue
                dirs[:] = [d for d in dirs if d not in _scan_excludes]
                for f in files:
                    if any(f.lower().endswith(ext) for ext in extensions):
                        all_files.append(os.path.join(root, f))
            
            yield "data: " + json.dumps({"type": "start", "total": len(all_files), "message": f"找到 {len(all_files)} 个视频"}) + "\n\n"
        
            # 2. 逐个识别阶段
            for i, f in enumerate(all_files):
                try:
                    info = scanner.get_video_metadata(f)
                    if info:
                        rel_dir = os.path.relpath(os.path.dirname(f), path)
                        rel_dir = "" if rel_dir == "." else rel_dir
                        # 虚拟媒体库：folder_name 以库名为前缀
                        if library_name:
                            info.folder_name = os.path.join(library_name, rel_dir) if rel_dir else library_name
                        else:
                            info.folder_name = rel_dir
                        results.append(info.dict())
                        yield "data: " + json.dumps({"type": "progress", "file": info.dict()}) + "\n\n"
                    else:
                        yield "data: " + json.dumps({"type": "progress", "raw_file_name": os.path.basename(f)}) + "\n\n"
                except Exception as e:
                    logger.error(f"[scan] 文件处理失败: {f} — {e}")
                    fallback = scanner._fallback_info(f)
                    if fallback:
                        rel_dir = os.path.relpath(os.path.dirname(f), path)
                        rel_dir = "" if rel_dir == "." else rel_dir
                        if library_name:
                            fallback.folder_name = os.path.join(library_name, rel_dir) if rel_dir else library_name
                        else:
                            fallback.folder_name = rel_dir
                        results.append(fallback.dict())
                    yield "data: " + json.dumps({"type": "progress", "raw_file_name": os.path.basename(f)}) + "\n\n"
            
            # 3. 保存阶段
            scanned_paths = set(r.get("file_path") for r in results)
            existing = config_m.load_library()
            kept = [v for v in existing if not v.get("file_path", "").startswith(path)]
            final = kept + results
            
            from clean_name_system import clean_from_filename, safe_update_clean_name as _safe_update
            for item in final:
                if not item.get("clean_name"):
                    fn = item.get("file_name", "")
                    if fn:
                        result = clean_from_filename(fn, source="parsed")
                        if result.display:
                            item["clean_name"] = result.display
                            item["clean_name_cn"] = result.cn
                            item["clean_name_en"] = result.en
                            item["clean_name_original"] = result.original
                            item["clean_name_source"] = "parsed"
            
            config_m.save_library(final)
            yield "data: " + json.dumps({"type": "done", "total": len(results)}) + "\n\n"

        except Exception as e:
            logger.info(f"[scan] 扫描异常: {e}")
            import traceback
            traceback.print_exc()
            if results:
                try:
                    existing = config_m.load_library()
                    kept = [v for v in existing if not v.get("file_path", "").startswith(path)]
                    config_m.save_library(kept + results)
                except Exception:
                    pass
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/sync")
def quick_sync():
    """快速同步（EventSource 流式进度）"""
    library = config_m.load_library()
    # 合并 scan_paths 和 media_libraries 的路径（去重）
    _scan = config_m.config.scan_paths or []
    _lib_paths = []
    for lib in (config_m.config.media_libraries or []):
        _lib_paths.extend(lib.paths)
    nas_paths = list(dict.fromkeys(_scan + _lib_paths))  # 保序去重
    extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    excluded = config_m.load_excluded()

    def is_excluded(fp):
        """检查文件或其所在文件夹是否在排除列表中"""
        if fp in excluded:
            return True
        # 检查文件夹路径是否被排除
        folder = os.path.dirname(fp)
        while folder:
            if folder in excluded:
                return True
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
        return False

    # 构建 scan_path → media_library 名称的映射（用于 folder_name 前缀）
    _sync_lib_name_map: Dict[str, str] = {}
    # 构建 scan_path → exclude_dirs 映射（用于扫描时过滤）
    _sync_lib_exclude_map: Dict[str, set] = {}
    for lib in (config_m.config.media_libraries or []):
        for lp in lib.paths:
            norm_lp = lp.replace("/", "\\").rstrip("\\")
            _sync_lib_name_map[norm_lp] = lib.name
            if lib.exclude_dirs:
                _sync_lib_exclude_map[norm_lp] = set(lib.exclude_dirs)
    # 全局排除目录（逗号分隔）
    _global_exclude_dirs = set(
        d.strip() for d in (config_m.config.exclude_dirs or "").split(",") if d.strip()
    )

    def _get_folder_name(fp: str, base: str) -> str:
        """计算视频的 folder_name，如果 base 属于某个 media_library 则加库名前缀"""
        rel_dir = os.path.relpath(os.path.dirname(fp), base)
        rel_dir = "" if rel_dir == "." else rel_dir
        norm_base = base.replace("/", "\\").rstrip("\\")
        lib_name = _sync_lib_name_map.get(norm_base, "")
        if lib_name:
            return os.path.join(lib_name, rel_dir) if rel_dir else lib_name
        return rel_dir

    def event_gen():
        try:
            yield "data: " + json.dumps({"type": "status", "message": "扫描文件系统..."}) + "\n\n"

            fs_files = set()
            for base in nas_paths:
                if not base or not os.path.exists(base): continue
                norm_base = base.replace("/", "\\").rstrip("\\")
                lib_excludes = _sync_lib_exclude_map.get(norm_base, set())
                for root, dirs, files in os.walk(base):
                    if "@eaDir" in root or "#recycle" in root: continue
                    # 过滤排除目录（全局 + 库级）
                    dirs[:] = [d for d in dirs if d not in _global_exclude_dirs and d not in lib_excludes]
                    for f in files:
                        if os.path.splitext(f)[1].lower() in extensions:
                            fp = os.path.join(root, f)
                            if not is_excluded(fp):
                                fs_files.add(fp)

            lib_paths = set(v.get("file_path", "") for v in library)
            added = fs_files - lib_paths
            removed = lib_paths - fs_files

            yield "data: " + json.dumps({"type": "status", "message": f"发现 {len(added)} 个新增，{len(removed)} 个移除"}) + "\n\n"

            # 删除已不存在的
            current_lib = [v for v in library if v.get("file_path", "") not in removed]

            # 检测已有文件的大小变化（替换了更高清版本但路径不变的情况）
            changed_files = []
            for v in current_lib:
                fp = v.get("file_path", "")
                if fp and fp in fs_files:
                    try:
                        actual_size = round(os.path.getsize(fp) / (1024**3), 2)
                        lib_size = v.get("size_gb", 0)
                        # 大小差异超过 5% 视为文件已被替换
                        if lib_size > 0 and abs(actual_size - lib_size) / lib_size > 0.05:
                            changed_files.append(fp)
                    except OSError:
                        pass

            if changed_files:
                yield "data: " + json.dumps({"type": "status", "message": f"检测到 {len(changed_files)} 个文件大小变化，重新分析"}) + "\n\n"
                # 从 current_lib 中移除变化的文件，当作新增重新扫描
                current_lib = [v for v in current_lib if v.get("file_path", "") not in set(changed_files)]
                added = added | set(changed_files)

            # 新增的逐个跑 ffprobe（超过 50 个时用快速模式跳过 ffprobe）
            total_new = len(added)
            new_videos = []
            use_fast_mode = total_new > 50  # 新增太多时用快速模式
            if use_fast_mode:
                yield "data: " + json.dumps({"type": "status", "message": f"快速模式：{total_new} 个新文件（跳过详细分析）"}) + "\n\n"

            for i, fp in enumerate(added):
                if i % 10 == 0 or not use_fast_mode:
                    yield "data: " + json.dumps({"type": "progress", "current": i + 1, "total": total_new, "file": os.path.basename(fp)}) + "\n\n"
                try:
                    if use_fast_mode:
                        # 快速模式：只读文件名+大小，不跑 ffprobe
                        info = scanner._fallback_info(fp)
                    else:
                        info = scanner.get_video_metadata(fp)
                    if info:
                        # 优先匹配最长的路径（子路径优先于父路径）
                        best_base = ""
                        for base in nas_paths:
                            if fp.startswith(base) and len(base) > len(best_base):
                                best_base = base
                        if best_base:
                            info.folder_name = _get_folder_name(fp, best_base)
                        new_videos.append(info.dict())
                except Exception as e:
                    logger.error(f"[sync] 文件处理失败: {fp} — {e}")

            current_lib.extend(new_videos)
            config_m.save_library(current_lib)

            # 扫描后自动从 NFO 填充影子名（仅新增的视频，优先英文名）
            shadow_filled = 0
            sync_tmdb = _tmdb_client()
            for item in new_videos:
                fp = item.get("file_path", "")
                if fp:
                    try:
                        nfo_info = shadow_m._read_nfo_originaltitle(fp)
                        if nfo_info and nfo_info.get("original_title"):
                            orig = nfo_info["original_title"]
                            yr = nfo_info.get("year", "")
                            if not shadow_m._is_latin(orig) and nfo_info.get("tmdb_id") and sync_tmdb:
                                try:
                                    en = sync_tmdb.get_english_title("movie", nfo_info["tmdb_id"], orig)
                                    if not en:
                                        en = sync_tmdb.get_english_title("tv", nfo_info["tmdb_id"], orig)
                                    if en:
                                        orig = en
                                except Exception:
                                    pass
                            shadow = f"{orig} ({yr})" if yr else orig
                            if shadow_m.auto_fill(fp, shadow, source="nfo", tmdb_id=nfo_info.get("tmdb_id")):
                                shadow_filled += 1
                    except Exception:
                        pass

            yield "data: " + json.dumps({"type": "done", "added": len(new_videos), "removed": len(removed), "total": len(current_lib), "shadow_filled": shadow_filled}) + "\n\n"

        except Exception as e:
            logger.info(f"[sync] 快速同步异常: {e}")
            import traceback
            traceback.print_exc()
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@router.get("/library")
def get_library():
    """获取本地缓存的媒体库"""
    return config_m.load_library()

@router.post("/library/refresh-quality")
def refresh_quality_score(paths: List[str] = None):
    """刷新质量分数。
    paths 非空：单文件/少量文件检测，重新跑 ffprobe 获取真实元数据后重算。
    paths 为空：全局检测，只根据现有数据重算质量分（不跑 ffprobe）。
    """
    from quality_parser import compute_quality_score_from_video
    library = config_m.load_library()
    updated = 0
    path_set = set(paths) if paths else None

    if path_set:
        # 单文件检测：重新跑 ffprobe 更新元数据
        lib_map = {v.get("file_path", ""): v for v in library}
        for fp in path_set:
            v = lib_map.get(fp)
            if not v or not os.path.exists(fp):
                continue
            try:
                info = scanner.get_video_metadata(fp)
                if info and info.height > 0:
                    v["resolution"] = info.resolution
                    v["height"] = info.height
                    v["width"] = info.width
                    v["video_codec"] = info.codec
                    v["audio_codec"] = info.audio_codec
                    v["subtitle_count"] = info.subtitle_count
                    v["hdr_type"] = info.hdr_type
                    v["duration"] = info.duration_min
                    v["bitrate_kbps"] = info.bitrate_kbps
                    v["size_gb"] = info.size_gb
                    v["is_low_res"] = info.is_low_res
            except Exception as e:
                logger.error(f"[refresh-quality] ffprobe 失败: {fp} — {e}")
            new_score = compute_quality_score_from_video(v)
            if new_score != v.get("quality_score", 0):
                v["quality_score"] = new_score
                updated += 1
    else:
        # 全局检测：只根据现有数据重算质量分
        for v in library:
            old_score = v.get("quality_score", 0)
            new_score = compute_quality_score_from_video(v)
            if new_score != old_score:
                v["quality_score"] = new_score
                updated += 1

    if updated:
        config_m.save_library(library)
    return {"status": "ok", "updated": updated, "total": len(library)}

@router.post("/library/folder-type")
def set_folder_type(req: dict):
    """手动设置文件夹类型（覆盖自动判定）"""
    path = req.get("path", "")
    folder_type = req.get("folder_type", "")
    if not path or not folder_type:
        return {"status": "error", "message": "path and folder_type required"}
    
    ft_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "folder_types.json")
    import json
    data = {}
    if os.path.exists(ft_path):
        with open(ft_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[path] = folder_type
    with open(ft_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"status": "ok"}

@router.post("/library/category-tag")
def set_category_tag(req: dict):
    """设置一级分类目录的标签"""
    path = req.get("path", "")
    tag = req.get("tag", "")
    valid_tags = ("movie", "tv", "anime_tv", "anime_movie", "variety", "other")
    if not path or tag not in valid_tags:
        return {"status": "error", "message": f"path and valid tag ({'/'.join(valid_tags)}) required"}
    config = config_m.config
    tags = dict(config.category_tags or {})
    tags[path] = tag
    config.category_tags = tags
    config_m.save(config)
    return {"status": "ok"}


# ── 虚拟媒体库 CRUD ──

class AddLibraryRequest(BaseModel):
    name: str
    category_tag: str = "movie"
    paths: List[str]
    exclude_dirs: List[str] = []


@router.post("/library/add")
def add_media_library(req: AddLibraryRequest):
    """添加虚拟媒体库"""
    valid_tags = ("movie", "tv", "anime_tv", "anime_movie", "variety", "other")
    if req.category_tag not in valid_tags:
        return {"status": "error", "message": f"invalid category_tag, must be one of {valid_tags}"}
    if not req.paths or not any(p.strip() for p in req.paths):
        return {"status": "error", "message": "at least one path required"}
    # 清理路径
    clean_paths = [p.strip() for p in req.paths if p.strip()]
    name = req.name.strip() or os.path.basename(clean_paths[0].rstrip("\\/"))
    config = config_m.config
    libs = list(config.media_libraries)
    # 检查同名库是否已存在 → 合并路径
    existing = next((lib for lib in libs if lib.name == name), None)
    if existing:
        for p in clean_paths:
            if p not in existing.paths:
                existing.paths.append(p)
        if req.exclude_dirs:
            for d in req.exclude_dirs:
                if d not in existing.exclude_dirs:
                    existing.exclude_dirs.append(d)
    else:
        from config_manager import MediaLibraryConfig
        libs.append(MediaLibraryConfig(
            name=name,
            category_tag=req.category_tag,
            paths=clean_paths,
            exclude_dirs=req.exclude_dirs or [],
        ))
    config.media_libraries = libs
    config_m.save(config)
    return {"status": "ok", "name": name}


@router.put("/library/{name}")
def update_media_library(name: str, req: dict):
    """修改虚拟媒体库（改名/改标签/增删路径/改排除）"""
    config = config_m.config
    libs = list(config.media_libraries)
    target = next((lib for lib in libs if lib.name == name), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"library '{name}' not found")
    old_name = target.name
    if "name" in req and req["name"].strip():
        target.name = req["name"].strip()
    if "category_tag" in req:
        valid_tags = ("movie", "tv", "anime_tv", "anime_movie", "variety", "other")
        if req["category_tag"] in valid_tags:
            target.category_tag = req["category_tag"]
    if "paths" in req:
        target.paths = [p.strip() for p in req["paths"] if p.strip()]
    if "exclude_dirs" in req:
        target.exclude_dirs = req["exclude_dirs"]
    config.media_libraries = libs
    config_m.save(config)
    # 改名时同步更新 media_library.json 中的 folder_name 前缀
    new_name = target.name
    if new_name != old_name:
        library = config_m.load_library()
        updated = 0
        old_prefix = old_name + os.sep
        old_prefix_slash = old_name + "/"
        for v in library:
            fn = v.get("folder_name", "")
            if fn == old_name:
                v["folder_name"] = new_name
                updated += 1
            elif fn.startswith(old_prefix) or fn.startswith(old_prefix_slash):
                v["folder_name"] = new_name + fn[len(old_name):]
                updated += 1
        if updated > 0:
            config_m.save_library(library)
            logger.info(f"[library] 媒体文件夹改名 '{old_name}' → '{new_name}'，更新 {updated} 条记录的 folder_name")
    return {"status": "ok"}


@router.delete("/library/{name}")
def delete_media_library(name: str):
    """删除虚拟媒体库（同时清理该库路径下的媒体数据）"""
    config = config_m.config
    libs = list(config.media_libraries)
    target = next((lib for lib in libs if lib.name == name), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"library '{name}' not found")
    # 清理该库所有路径下的媒体数据
    library = config_m.load_library()
    paths_to_remove = set(target.paths)
    kept = [v for v in library if not any(v.get("file_path", "").startswith(p) for p in paths_to_remove)]
    if len(kept) < len(library):
        config_m.save_library(kept)
        logger.info(f"[library] 删除媒体库 '{name}'，清理 {len(library) - len(kept)} 条媒体记录")
    # 从 config 中移除
    new_libs = [lib for lib in libs if lib.name != name]
    config.media_libraries = new_libs
    config_m.save(config)
    return {"status": "ok", "removed_videos": len(library) - len(kept)}


@router.post("/library/remove-path")
def remove_library_path(req: dict):
    """删除指定路径下的媒体数据（设置页删除路径时调用）"""
    path = req.get("path", "").strip()
    if not path:
        return {"status": "error", "message": "path required"}
    library = config_m.load_library()
    kept = [v for v in library if not v.get("file_path", "").startswith(path)]
    removed = len(library) - len(kept)
    if removed > 0:
        config_m.save_library(kept)
        logger.info(f"[library] 删除路径 '{path}' 下 {removed} 条媒体记录")
    return {"status": "ok", "removed": removed}


@router.get("/library/list")
def list_media_libraries():
    """列出所有媒体库（含 scan_paths 的自动识别库 + media_libraries 的分类库）"""
    config = config_m.config
    result = []
    # scan_paths 作为"自动识别"类型的库
    for p in (config.scan_paths or []):
        if p.strip():
            result.append({
                "name": os.path.basename(p.rstrip("\\/")),
                "type": "scan",
                "category_tag": "",
                "paths": [p],
                "exclude_dirs": [],
            })
    # media_libraries 作为"分类添加"类型的库
    for lib in (config.media_libraries or []):
        result.append({
            "name": lib.name,
            "type": "library",
            "category_tag": lib.category_tag,
            "paths": lib.paths,
            "exclude_dirs": lib.exclude_dirs,
        })
    return {"libraries": result}


@router.post("/library/reset")
def reset_library():
    """重置媒体库（清空扫描记录），用于测试首次引导"""
    config_m.save_library([])
    return {"status": "ok"}

@router.post("/library/clean-name")
def set_clean_name(req: dict):
    """手动修改清洗名（manual 来源，最高优先级）
    
    支持字段：clean_name（display/cn）、clean_name_en（英文名）
    支持 is_folder=true 时按文件夹路径匹配其下所有视频
    """
    file_path = req.get("file_path", "")
    clean_name = req.get("clean_name", "")
    clean_name_en = req.get("clean_name_en")  # None 表示不修改，"" 表示清空
    is_folder = req.get("is_folder", False)
    if not file_path:
        return {"status": "error", "message": "file_path required"}
    
    library = config_m.load_library()
    
    if is_folder:
        # 文件夹模式：更新该文件夹下所有视频的 clean_name/clean_name_en
        # 规范化路径用于前缀匹配
        folder_norm = file_path.replace("\\", "/").rstrip("/") + "/"
        updated = 0
        for v in library:
            v_folder = v.get("file_path", "").replace("\\", "/")
            # 视频在该文件夹下（直接子文件或更深层）
            if v_folder.startswith(folder_norm) or os.path.dirname(v_folder).replace("\\", "/") + "/" == folder_norm:
                if clean_name_en is not None:
                    v["clean_name_en"] = clean_name_en
                    v["clean_name_source"] = "manual"
                    updated += 1
                if clean_name:
                    v["clean_name"] = clean_name
                    v["clean_name_source"] = "manual"
                    # 同步更新 clean_name_cn（从 display 中提取中文部分）
                    import re
                    cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', clean_name)
                    if cn_parts:
                        v["clean_name_cn"] = "".join(cn_parts)
                    updated += 1
        if updated > 0:
            config_m.save_library(library)
            return {"status": "ok", "updated": updated}
        # 文件夹下没有视频，尝试直接匹配（兼容旧逻辑）
        for v in library:
            if v.get("file_path") == file_path:
                if clean_name:
                    v["clean_name"] = clean_name
                    v["clean_name_source"] = "manual"
                    import re
                    cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', clean_name)
                    if cn_parts:
                        v["clean_name_cn"] = "".join(cn_parts)
                if clean_name_en is not None:
                    v["clean_name_en"] = clean_name_en
                    v["clean_name_source"] = "manual"
                config_m.save_library(library)
                return {"status": "ok"}
        return {"status": "ok", "updated": 0}
    
    # 视频模式：精确匹配 file_path
    for v in library:
        if v.get("file_path") == file_path:
            if clean_name is not None:
                v["clean_name"] = clean_name
                v["clean_name_source"] = "manual" if clean_name else ""
                # 同步更新 clean_name_cn
                if clean_name:
                    import re
                    cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', clean_name)
                    if cn_parts:
                        v["clean_name_cn"] = "".join(cn_parts)
            if clean_name_en is not None:
                v["clean_name_en"] = clean_name_en
                v["clean_name_source"] = "manual"
            config_m.save_library(library)
            return {"status": "ok"}
    return {"status": "not_found"}

@router.get("/library/tree")
def get_library_tree():
    """生成嵌套的目录树结构"""
    videos = config_m.load_library()
    root_node = {
        "name": "媒体库",
        "path": "",
        "children": [],
        "videos": [],
        "video_count": 0,
        "has_cover": False,
        "_child_index": {},
    }
    
    config = config_m.config
    base_path = config.scan_paths[0] if config.scan_paths else ""

    # 构建 media_libraries 的库名 → 实际路径映射
    _lib_path_map: Dict[str, str] = {}
    for lib in (config.media_libraries or []):
        if lib.paths:
            _lib_path_map[lib.name] = lib.paths[0]

    for v in videos:
        rel_dir = v.get("folder_name", "")  # "Movies/Action" 或 "电影/复仇者联盟"
        rel_dir = rel_dir.replace("\\", "/")
        parts = [p for p in rel_dir.split("/") if p]
        
        current_node = root_node
        current_rel = ""
        # 判断该视频是否属于某个 media_library
        is_lib_video = parts and parts[0] in _lib_path_map
        lib_base = _lib_path_map.get(parts[0], "") if is_lib_video else ""

        for i, part in enumerate(parts):
            current_rel = os.path.join(current_rel, part) if current_rel else part
            child = current_node["_child_index"].get(part)
            if not child:
                # 计算节点的绝对路径
                if is_lib_video:
                    if i == 0:
                        # 库名节点：path 用库的第一个路径
                        node_path = lib_base
                    else:
                        # 库内子节点：相对于库路径
                        sub_rel = os.path.join(*parts[1:i+1])
                        node_path = os.path.join(lib_base, sub_rel)
                else:
                    node_path = os.path.join(base_path, current_rel) if base_path else current_rel
                child = {
                    "name": part,
                    "path": node_path,
                    "children": [],
                    "videos": [],
                    "video_count": 0,
                    "has_cover": False,
                    "_child_index": {},
                }
                current_node["children"].append(child)
                current_node["_child_index"][part] = child
            current_node = child
        current_node["videos"].append(v)
    
    # 读取用户配置的 category_tags（路径 → 标签）
    configured_tags = config.category_tags or {}

    # 预计算一级分类路径集合
    # 只有目录名能被识别为分类关键词（非默认 movie）或在 configured_tags 中配置过的才算
    # media_libraries 的库名节点也算一级分类
    top_category_paths = set()
    # media_libraries 的库名 → category_tag 映射
    _lib_category_tags: Dict[str, str] = {}
    for lib in (config.media_libraries or []):
        _lib_category_tags[lib.name] = lib.category_tag

    for child in root_node["children"]:
        child_path = child["path"]
        child_name = child["name"]
        # media_libraries 的库名节点 → 一定是一级分类（无论是否有子目录）
        if child_name in _lib_category_tags:
            top_category_paths.add(child_path)
        elif child["children"]:
            # 已配置的标签 → 一定是一级分类
            if child_path in configured_tags:
                top_category_paths.add(child_path)
            else:
                # 目录名能被识别为非默认标签 → 一级分类
                name_lower = child_name.strip().lower()
                if name_lower in organizer._CATEGORY_KEYWORD_MAP:
                    top_category_paths.add(child_path)
                elif any(kw in name_lower for kw in organizer._CATEGORY_KEYWORD_MAP):
                    top_category_paths.add(child_path)

    def _resolve_category_tag(node_path: str, node_name: str) -> str:
        """解析一级分类目录的标签：配置优先，否则自动推断"""
        # media_libraries 的库名节点：使用配置的 category_tag
        if node_name in _lib_category_tags:
            return _lib_category_tags[node_name]
        if node_path in configured_tags:
            return configured_tags[node_path]
        return organizer.infer_category_tag(node_name)

    # 季目录名正则（用于自主推断）
    _SEASON_DIR_PAT = re.compile(
        r'(?:S\d+|第\d+季|第[一二三四五六七八九十]+季|Season\s*\d+|特别篇|SP|OVA|OAD|剧[場场]版|Specials?)',
        re.I
    )
    # 集号文件名正则
    _EPISODE_PAT = re.compile(
        r'(?:S\d+E\d+|EP?\d+|第\d+[集话話]|\b\d{2,3}\b(?=\s*[\.\-\[\(]))',
        re.I
    )

    def _guess_structure_type_from_tree(node) -> str:
        """无 category_tag 时，从树结构特征自主推断底层结构类型（movie/tv）。
        核心信号：
        1. 子目录名匹配季目录模式 → tv
        2. 视频文件名含集号特征 → tv
        3. 多视频 + 短时长（<45min）→ tv
        4. 单视频或少量视频 + 无集号 → movie
        5. 文件夹名含 tv 类关键词 → tv
        """
        children = node.get("children", [])
        videos = node.get("videos", [])

        # 信号1：子目录名匹配季目录模式
        if children:
            season_like = sum(1 for c in children if _SEASON_DIR_PAT.search(c["name"]))
            if season_like >= 1 and season_like >= len(children) * 0.3:
                return "tv"

        # 信号2：视频文件名含集号特征
        if videos:
            ep_count = sum(1 for v in videos if _EPISODE_PAT.search(v.get("file_name", "")))
            if ep_count >= len(videos) * 0.5 and len(videos) >= 2:
                return "tv"

        # 信号3：多视频 + 平均时长短
        if videos and len(videos) >= 3:
            durations = [v.get("duration", 0) for v in videos if v.get("duration", 0) > 0]
            if durations:
                avg_min = (sum(durations) / len(durations)) / 60
                if avg_min < 45:
                    return "tv"

        # 信号4：文件夹名含 tv 类关键词
        folder_name = node.get("name", "")
        if folder_name:
            tag = organizer.infer_category_tag(folder_name)
            if tag and organizer.category_tag_to_structure_type(tag) == "tv":
                return "tv"

        # 信号5：子目录各自有多视频且含集号 → tv（聚合多部剧）
        if children and not videos:
            tv_like_children = 0
            for c in children:
                c_videos = c.get("videos", [])
                if c_videos and len(c_videos) >= 2:
                    c_ep = sum(1 for v in c_videos if _EPISODE_PAT.search(v.get("file_name", "")))
                    if c_ep >= len(c_videos) * 0.5:
                        tv_like_children += 1
                elif c.get("children"):
                    # 子目录有子目录（可能是季结构）
                    c_season = sum(1 for cc in c["children"] if _SEASON_DIR_PAT.search(cc["name"]))
                    if c_season >= 1:
                        tv_like_children += 1
            if tv_like_children >= len(children) * 0.5 and tv_like_children >= 1:
                return "tv"

        # 默认 movie（更宽松，不会强行改变结构）
        return "movie"

    def _infer_folder_type_from_tree(node, category_tag: str) -> str:
        """从树结构推断 folder_type，不依赖文件系统。
        使用树节点的 children 和 videos 信息判断。
        当 category_tag 为空时，自主从结构特征推断。"""
        children = node.get("children", [])
        videos = node.get("videos", [])
        has_children = len(children) > 0
        has_videos = len(videos) > 0
        video_count = node.get("video_count", 0)

        # 将标签映射到底层结构类型（movie/tv）
        # 如果没有 category_tag，先尝试自主推断
        if category_tag:
            structure_type = organizer.category_tag_to_structure_type(category_tag)
        else:
            structure_type = _guess_structure_type_from_tree(node)

        if structure_type == "movie":
            # movie 标签下
            if not has_children:
                if not has_videos:
                    return ""
                if len(videos) == 1:
                    return "movie"
                # 多视频：检查是否同系列
                vnames = [v.get("file_name", "") for v in videos]
                if organizer._is_series_collection(vnames, node["name"]):
                    return "series"
                return "collection"
            if has_videos:
                # 有子目录 + 有散落视频 → collection
                return "collection"
            # 有子目录无散落视频
            # 检查子目录是否都是单视频（封装电影）
            all_single = all(len(c.get("videos", [])) <= 1 and not c.get("children") for c in children)
            if all_single:
                child_names = [c["name"] for c in children]
                if organizer._is_series_collection(child_names, node["name"]):
                    return "series"
                return "collection"
            # 有更深层嵌套 → mixed
            return "mixed"

        elif structure_type == "tv":
            # tv 标签下
            if not has_children:
                if has_videos:
                    return "tv"  # 扁平 tv
                return ""
            # 有子目录：判断是 tv 还是 mixed（多部不同剧聚合）
            # 核心规则：tv 是两层结构（剧名/季/集），季目录下直接是视频
            # mixed 是三层结构（聚合/剧名/季/集），子目录各自还有子目录
            
            _SPECIAL_PAT = re.compile(r'(?:Season\s*0+|Specials?|SP|OVA|OAD|特别篇|剧[場场]版)', re.I)
            
            # 只有1个子目录 → 不可能是聚合
            if len(children) == 1:
                return "tv"
            
            # 检查子目录结构：如果子目录自己还有子目录（三层），说明是多个 tv 聚合
            children_with_subdirs = 0
            for c in children:
                if _SPECIAL_PAT.search(c["name"]):
                    continue  # 特别篇豁免
                if c.get("children") and len(c["children"]) > 0:
                    children_with_subdirs += 1
            
            # 多个子目录各自有子目录 → mixed（多部不同 tv 聚合）
            if children_with_subdirs >= 2:
                return "mixed"
            
            # 子目录都是末端（直接包含视频，没有更深子目录）→ tv
            return "tv"

        return ""

    def finalize(node, parent_category_tag=""):
        count = len(node["videos"])
        has_cover = count > 0
        # 确定当前节点的一级分类标签
        category_tag = parent_category_tag
        if node["path"] in top_category_paths:
            category_tag = _resolve_category_tag(node["path"], node["name"])
        # 所有节点都设置 parent_category_tag（由 post_process 统一处理）
        for child in node["children"]:
            c_count, c_cover = finalize(child, category_tag)
            count += c_count
            if c_cover: has_cover = True
        node["video_count"] = count
        node["has_cover"] = has_cover
        # 标记分类聚合文件夹（末端 + 多视频 + 文件名差异大）
        if not node["children"] and len(node["videos"]) > 1:
            vfiles = [v.get("file_name", "") for v in node["videos"]]
            node["is_category"] = scraper._is_category_folder(node["name"], vfiles)
        else:
            node["is_category"] = False
        # 添加 folder_type：从树结构推断，不依赖文件系统
        # 一级分类目录显示 category_tag
        if node["path"] and node["path"] != base_path:
            if node["path"] in top_category_paths:
                node["category_tag"] = category_tag
                node["is_top_category"] = True
                # 标记虚拟媒体库文件夹
                node["is_virtual_library"] = node["name"] in _lib_category_tags
                # 所有一级节点都推断 folder_type（让子目录能被正确标记）
                node["folder_type"] = _infer_folder_type_from_tree(node, category_tag)
            else:
                node["category_tag"] = ""
                node["is_top_category"] = False
                # 检查手动覆盖
                _ft_override = None
                try:
                    _ft_override = organizer._load_folder_type_override(node["path"])
                except Exception:
                    pass
                if _ft_override:
                    node["folder_type"] = _ft_override
                else:
                    # 从树结构推断 folder_type
                    node["folder_type"] = _infer_folder_type_from_tree(node, category_tag)
        else:
            node["folder_type"] = ""
            node["category_tag"] = ""
            node["is_top_category"] = False
        # 文件夹级影子名：优先从该目录下已有的视频条目中提取数据库存量的译名
        node["shadow_name"] = ""
        node["shadow_tmdb_id"] = None
        
        # 1. 尝试从当前节点的视频中提取
        if node.get("videos"):
            for v in node["videos"]:
                if v.get("shadow_name"):
                    _raw_shadow = v["shadow_name"]
                    # TV/season 文件夹冒泡时去掉尾部季集号（S01E01 等），只保留剧名
                    if node.get("folder_type") in ("tv", "season"):
                        import re as _re_shadow
                        _raw_shadow = _re_shadow.sub(r'\s+S\d+E\d+\s*$', '', _raw_shadow, flags=_re_shadow.IGNORECASE).strip()
                        _raw_shadow = _re_shadow.sub(r'\s+S\d+\s*$', '', _raw_shadow, flags=_re_shadow.IGNORECASE).strip()
                        _raw_shadow = _re_shadow.sub(r'\s+E\d+\s*$', '', _raw_shadow, flags=_re_shadow.IGNORECASE).strip()
                    node["shadow_name"] = _raw_shadow
                    node["shadow_tmdb_id"] = v.get("shadow_tmdb_id")
                    break
        
        # 2. 如果当前节点没视频或没译名，尝试从子节点“冒泡”提取
        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    _raw_shadow2 = child["shadow_name"]
                    # TV 文件夹从 season 子节点冒泡时去掉尾部季集号
                    if node.get("folder_type") in ("tv",):
                        import re as _re_shadow2
                        _raw_shadow2 = _re_shadow2.sub(r'\s+S\d+E\d+\s*$', '', _raw_shadow2, flags=_re_shadow2.IGNORECASE).strip()
                        _raw_shadow2 = _re_shadow2.sub(r'\s+S\d+\s*$', '', _raw_shadow2, flags=_re_shadow2.IGNORECASE).strip()
                        _raw_shadow2 = _re_shadow2.sub(r'\s+E\d+\s*$', '', _raw_shadow2, flags=_re_shadow2.IGNORECASE).strip()
                    node["shadow_name"] = _raw_shadow2
                    node["shadow_tmdb_id"] = child.get("shadow_tmdb_id")
                    break

        # 文件夹级 clean_name：只用缓存的库数据和树内信息推导，避免首屏读取 NAS 上的 NFO
        if node["path"] and node["path"] != base_path:
            from clean_name_system import clean_for_folder, parse_legacy_clean_name
            from organizer import _extract_season_number
            _season_num = _extract_season_number(node["name"]) if node.get("folder_type") == "season" else None
            _folder_result = clean_for_folder(
                folder_name=node["name"],
                shadow_name=node.get("shadow_name", ""),
                folder_type=node.get("folder_type", ""),
                season_num=_season_num,
            )
            node["clean_name"] = _folder_result.display or node["name"]
            node["clean_name_cn"] = _folder_result.cn
            node["clean_name_en"] = _folder_result.en
            node["clean_name_original"] = _folder_result.original

            # ── 手动覆盖：视频条目有 manual 来源时，用手动值覆盖文件夹计算值 ──
            for video in node.get("videos", []):
                if video.get("clean_name_source") == "manual":
                    if video.get("clean_name"):
                        node["clean_name"] = video["clean_name"]
                        # 从 display 中拆分 cn（取中文部分）
                        import re as _re_manual
                        _cn_parts = _re_manual.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', video["clean_name"])
                        if _cn_parts:
                            node["clean_name_cn"] = "".join(_cn_parts)
                    if video.get("clean_name_en"):
                        node["clean_name_en"] = video["clean_name_en"]
                    break

            # 垃圾英文名检测：季号碎片、纯数字、太短的、常见非作品名不算有效英文名
            # 手动设置的英文名不做垃圾检测（用户明确指定的值应尊重）
            _has_manual = any(v.get("clean_name_source") == "manual" and v.get("clean_name_en") for v in node.get("videos", []))
            _en = node["clean_name_en"]
            if _en and not _has_manual and node.get("folder_type") in ("tv", "season", "movie", "mixed", ""):
                import re as _re_en
                _JUNK_EN = {"season", "seasons", "sps", "sp", "extra", "extras", "ncop", "nced",
                            "pv", "menu", "tv", "ova", "oad", "bonus", "specials"}
                _en_stripped = _re_en.sub(r'[sS]\s*\d+', '', _en).strip()
                _en_stripped = _re_en.sub(r'\d+', '', _en_stripped).strip()
                if len(_en_stripped) <= 3 or _en.lower().strip() in _JUNK_EN:
                    node["clean_name_en"] = ""

            # ── 自愈层1：视频条目缺失结构化字段时，从 clean_name 反向解析 ──
            # 这样视频冒泡时才有 cn/en 可冒
            for video in node.get("videos", []):
                if not video.get("clean_name_cn") and not video.get("clean_name_en") and video.get("clean_name"):
                    _legacy = parse_legacy_clean_name(video)
                    if _legacy.cn:
                        video["clean_name_cn"] = _legacy.cn
                    if _legacy.en:
                        video["clean_name_en"] = _legacy.en
                    if _legacy.original:
                        video["clean_name_original"] = _legacy.original
                    if _legacy.cn or _legacy.en:
                        library_dirty[0] = True

            # ── 自愈层2：从视频条目冒泡补全文件夹 ──
            # 如果文件夹的 en 为空或明显是垃圾（比视频的 en 短很多），用视频的覆盖
            _folder_en_len = len(node["clean_name_en"])
            for video in node.get("videos", []):
                if not node["clean_name_cn"] and video.get("clean_name_cn"):
                    node["clean_name_cn"] = video["clean_name_cn"]
                v_en = video.get("clean_name_en", "")
                if v_en and (not node["clean_name_en"] or (len(v_en) > _folder_en_len + 3)):
                    # 冒泡前做垃圾英文名检测：纯数字、太短的不冒泡
                    import re as _re_bubble
                    _v_en_stripped = _re_bubble.sub(r'[sS]\s*\d+', '', v_en).strip()
                    _v_en_stripped = _re_bubble.sub(r'\d+', '', _v_en_stripped).strip()
                    if len(_v_en_stripped) > 3:
                        node["clean_name_en"] = v_en
                        _folder_en_len = len(v_en)
                if not node["clean_name_original"] and video.get("clean_name_original"):
                    node["clean_name_original"] = video["clean_name_original"]
                if node["clean_name_cn"] and node["clean_name_en"] and node["clean_name_original"]:
                    break

            # ── 自愈层3：跳过（首屏不读 NAS 上的 NFO，避免 SMB 超时阻塞树构建）──
            # NFO 补全在用户点击文件夹详情时按需执行

            # ── 自愈层4：从子树冒泡（仅 tv/season，同一部剧的不同季）──
            if node.get("folder_type") in ("tv", "season"):
                for child in node.get("children", []):
                    if not node["clean_name_cn"] and child.get("clean_name_cn"):
                        node["clean_name_cn"] = child["clean_name_cn"]
                    if not node["clean_name_en"] and child.get("clean_name_en"):
                        node["clean_name_en"] = child["clean_name_en"]
                    if not node["clean_name_original"] and child.get("clean_name_original"):
                        node["clean_name_original"] = child["clean_name_original"]
                    if node["clean_name_cn"] and node["clean_name_en"] and node["clean_name_original"]:
                        break
        else:
            node["clean_name"] = node.get("name", "")
            node["clean_name_cn"] = ""
            node["clean_name_en"] = ""
            node["clean_name_original"] = ""
        return count, has_cover

    # 自愈标志：视频条目的结构化清洗名被补全时标记为 dirty，最后持久化
    library_dirty = [False]
    finalize(root_node)

    # 二次遍历：标记 season + 传播 parent_category_tag + 计算层级 clean_name
    def post_process(node, inherited_tag="", parent_cn="", parent_en="", parent_original=""):
        from clean_name_system import clean_for_folder, clean_from_filename
        from organizer import _extract_season_number
        import re as _re_pp


        cat = node.get("category_tag", "") or inherited_tag
        node["parent_category_tag"] = cat
        
        # 深度修正：如果父节点没影子名，尝试从子节点反向追溯（处理聚合文件夹）
        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    node["shadow_name"] = child["shadow_name"]
                    break

        # 当前节点的结构化名称，用于传递给子节点
        # 一级分类目录不向下传播（子节点是不同作品）
        if node.get("is_top_category"):
            cur_cn = ""
            cur_en = ""
            cur_original = ""
        else:
            cur_cn = node.get("clean_name_cn", "") or parent_cn
            cur_en = node.get("clean_name_en", "") or parent_en
            cur_original = node.get("clean_name_original", "") or parent_original

        # tv 的子目录标记为 season + 计算季 clean_name
        if node.get("folder_type") == "tv":
            for child in node.get("children", []):
                if child.get("folder_type") != "mixed":
                    child["folder_type"] = "season"
                # 检查 season 子目录下是否有手动设置的清洗名
                _child_has_manual = any(v.get("clean_name_source") == "manual" for v in child.get("videos", []))
                if _child_has_manual:
                    # 手动值已在 finalize 中设置，不覆盖
                    continue
                # 季文件夹 clean_name：用新系统，传入父级剧名
                season_num = _extract_season_number(child["name"])
                folder_result = clean_for_folder(
                    folder_name=child["name"],
                    shadow_name=child.get("shadow_name", ""),
                    parent_cn=cur_cn,
                    parent_en=cur_en,
                    folder_type="season",
                    season_num=season_num,
                )
                child["clean_name"] = folder_result.display or child["name"]
                child["clean_name_cn"] = folder_result.cn
                child["clean_name_en"] = folder_result.en
                child["clean_name_original"] = folder_result.original

        # 视频的 clean_name：用新系统，继承父文件夹的结构化名称
        if node.get("folder_type") in ("tv", "season", "movie") and node.get("videos"):
            for v in node["videos"]:
                # 尊重已有的高优先级 clean_name（manual/nfo/tmdb 不覆盖）
                existing_source = v.get("clean_name_source", "")
                if existing_source in ("manual", "nfo", "tmdb"):
                    continue
                if cur_cn or cur_en:
                    result = clean_from_filename(
                        v.get("file_name", ""),
                        folder_name=node.get("name", ""),
                        parent_cn=cur_cn,
                        parent_en=cur_en,
                        parent_original=cur_original,
                    )
                    if result.display:
                        v["clean_name"] = result.display
                        v["clean_name_cn"] = result.cn
                        v["clean_name_en"] = result.en
                        v["clean_name_original"] = result.original
                        library_dirty[0] = True

        for child in node.get("children", []):
            post_process(child, cat, cur_cn, cur_en, cur_original)
    post_process(root_node)

    def cleanup(node):
        node.pop("_child_index", None)
        for child in node.get("children", []):
            cleanup(child)

    cleanup(root_node)

    # 自愈持久化：视频条目的结构化清洗名被补全后回写 media_library.json
    if library_dirty[0]:
        try:
            config_m.save_library(videos)
            logger.info("[tree] 自愈：已补全视频条目的结构化清洗名并持久化")
        except Exception as e:
            logger.warning(f"[tree] 自愈持久化失败: {e}")

    return root_node



@router.get("/library/completeness")
def get_completeness(path: str, tmdb_id: Optional[int] = None, refresh: bool = False):
    """获取 TV 文件夹的季集完整度（基于 TMDB 数据源）
    默认读缓存秒返回，refresh=true 时清除 TMDB 缓存后重新请求
    """
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("completeness"):
        return {"status": "plugin_not_installed", "message": "请先安装「季集完整性检测」插件"}

    from completeness import (
        collect_local_episodes, get_tmdb_id_from_folder, compute_completeness,
        get_cached_completeness, save_completeness_to_cache, refresh_completeness_for_path,
    )

    if not path:
        raise HTTPException(400, "缺少 path 参数")

    logger.info(f"[completeness] API 请求: path={path}, refresh={refresh}, tmdb_id={tmdb_id}")

    # 非刷新模式：优先读缓存
    if not refresh:
        cached = get_cached_completeness(path)
        if cached and cached.get("status") == "ok":
            logger.info(f"[completeness] 返回缓存: {cached.get('completeness_pct')}%")
            return cached

    # 获取 TMDB ID：参数传入 > NFO 读取
    tid = tmdb_id
    if not tid:
        tid = get_tmdb_id_from_folder(path)
    if not tid:
        logger.warning(f"[completeness] 无 TMDB ID: {path}")
        return {"status": "no_tmdb_id", "message": "未找到 TMDB ID，请先刮削此文件夹"}

    # 获取 TMDB 客户端
    tc = _tmdb_client()
    if not tc:
        return {"status": "no_tmdb_client", "message": "TMDB 未配置"}

    # 刷新模式或无缓存：计算并缓存
    logger.info(f"[completeness] 重新计算: tmdb_id={tid}, refresh={refresh}")
    result = refresh_completeness_for_path(tc, path, clear_tmdb_cache=refresh)
    if result:
        logger.info(f"[completeness] 计算完成: {result.get('completeness_pct')}%, local={result.get('local_total')}")
        return result

    # 兜底：直接计算
    logger.info(f"[completeness] 兜底计算")
    local_episodes = collect_local_episodes(path)
    result = compute_completeness(tc, tid, local_episodes)
    if result.get("status") == "ok":
        save_completeness_to_cache(path, result)
    return result


@router.post("/library/completeness/refresh-all")
def refresh_all_completeness():
    """批量预计算所有 TV 文件夹的完整度（后台运行）"""
    from completeness import batch_refresh_all

    tc = _tmdb_client()
    if not tc:
        return {"status": "error", "message": "TMDB 未配置"}

    nas_paths = config_m.config.scan_paths or []
    category_tags = config_m.config.category_tags or {}

    # 后台线程执行，避免阻塞
    def _run():
        try:
            batch_refresh_all(tc, nas_paths, category_tags)
        except Exception as e:
            logger.error(f"[completeness] 批量预计算异常: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "started", "message": "批量预计算已启动，请查看后端日志"}
