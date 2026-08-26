"""
路由模块：library_crud
媒体库 CRUD（虚拟库增删改、路径移除、重置）+ 质量分刷新 + 字幕列举

清洗名拆到 library_clean_name.py，完整度拆到 library_completeness.py
"""
import os
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import config_m
import scanner, organizer

logger = logging.getLogger(__name__)
router = APIRouter()


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
    path_set = set(paths) if paths else None

    # 每条失败都要带原因回前端。这三种失败原来在界面上长得一模一样（接口永远返回
    # {"status":"ok"}，前端 catch {} 什么都不提示），用户点了「检测质量」看不出
    # 是文件已经不在了、还是文件本身读不了：
    #   missing     — 库里记的路径已经不存在（文件被移走/删了，重新同步就好）
    #   probe_failed— ffprobe 打不开或解析失败（文件损坏、假后缀、SMB 抖动）
    #   not_in_library — 传来的路径不在媒体库里
    failures: List[dict] = []

    # ffprobe 是子进程 + 读文件头，必须在锁外跑完再进临界区应用结果，
    # 否则一次质量检测就会把整个媒体库的写入卡住。
    probed = {}
    if path_set:
        for fp in path_set:
            if not os.path.exists(fp):
                failures.append({"path": fp, "reason": "missing"})
                continue
            try:
                info = scanner.get_video_metadata(fp)
                # height == 0 是 _fallback_info 的标记值：ffprobe 没跑通。
                # 这种结果不能写进库（会把已有的分辨率覆盖成 0），但必须让用户知道。
                if info and info.height > 0:
                    probed[fp] = info
                else:
                    failures.append({"path": fp, "reason": "probe_failed"})
            except Exception as e:
                logger.error(f"[refresh-quality] ffprobe 失败: {fp} — {e}")
                failures.append({"path": fp, "reason": "probe_failed"})

    total = 0
    updated = 0
    # 元数据有没有真的变过。落盘条件原来只看 quality_score 变没变 ——
    # ffprobe 成功但分数恰好不变时（分数本来就能从文件名标签解析出来），
    # 刚探到的 codec / height / container 会被整批丢弃，用户点了没反应。
    metadata_changed = False

    def _apply(library):
        nonlocal total, updated, metadata_changed
        total = len(library)
        if path_set:
            lib_map = {v.get("file_path", ""): v for v in library}
            for fp in path_set:
                v = lib_map.get(fp)
                if not v:
                    if not any(f["path"] == fp for f in failures):
                        failures.append({"path": fp, "reason": "not_in_library"})
                    continue
                info = probed.get(fp)
                if info is not None:
                    before = (v.get("codec"), v.get("height"), v.get("container"),
                              v.get("audio_codec"), v.get("duration_min"), v.get("resolution"))
                    v["resolution"] = info.resolution
                    v["height"] = info.height
                    v["width"] = info.width
                    # 字段名必须和 scanner.VideoInfo 一致（codec / duration_min）。
                    # 这里曾经写成 video_codec / duration，导致同一条记录里两套名字并存，
                    # 而前端只读其中一套 —— 表现为"点过检测质量的条目才显示编码"。
                    v["codec"] = info.codec
                    v["container"] = info.container
                    v["audio_codec"] = info.audio_codec
                    v["subtitle_count"] = info.subtitle_count
                    v["subtitle_text_count"] = info.subtitle_text_count
                    v["subtitle_graphic_count"] = info.subtitle_graphic_count
                    v["hdr_type"] = info.hdr_type
                    v["duration_min"] = info.duration_min
                    v["bitrate_kbps"] = info.bitrate_kbps
                    v["size_gb"] = info.size_gb
                    v["is_low_res"] = info.is_low_res
                    after = (v.get("codec"), v.get("height"), v.get("container"),
                             v.get("audio_codec"), v.get("duration_min"), v.get("resolution"))
                    if before != after:
                        metadata_changed = True
                new_score = compute_quality_score_from_video(v)
                if new_score != v.get("quality_score", 0):
                    v["quality_score"] = new_score
                    updated += 1
        else:
            for v in library:
                old_score = v.get("quality_score", 0)
                new_score = compute_quality_score_from_video(v)
                if new_score != old_score:
                    v["quality_score"] = new_score
                    updated += 1
        return None if (updated or metadata_changed) else False

    config_m.mutate_library(_apply)
    return {
        "status": "ok",
        "updated": updated,
        "total": total,
        # 探测成功的条数，和失败明细。前端据此决定提示什么。
        "probed": len(probed),
        "failed": failures,
    }


@router.post("/library/folder-type")
def set_folder_type(req: dict):
    """手动设置文件夹类型（覆盖自动判定）"""
    import json
    path = req.get("path", "")
    folder_type = req.get("folder_type", "")
    if not path or not folder_type:
        return {"status": "error", "message": "path and folder_type required"}

    ft_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "folder_types.json")
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
    clean_paths = [p.strip() for p in req.paths if p.strip()]
    name = req.name.strip() or os.path.basename(clean_paths[0].rstrip("\\/"))
    config = config_m.config
    libs = list(config.media_libraries)
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
        updated = 0
        old_prefix = old_name + os.sep
        old_prefix_slash = old_name + "/"

        def _rename_prefix(library):
            nonlocal updated
            for v in library:
                fn = v.get("folder_name", "")
                if fn == old_name:
                    v["folder_name"] = new_name
                    updated += 1
                elif fn.startswith(old_prefix) or fn.startswith(old_prefix_slash):
                    v["folder_name"] = new_name + fn[len(old_name):]
                    updated += 1
            return None if updated else False

        if config_m.mutate_library(_rename_prefix):
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
    paths_to_remove = set(target.paths)
    removed = 0

    def _drop_paths(library):
        nonlocal removed
        kept = [v for v in library
                if not any(v.get("file_path", "").startswith(p) for p in paths_to_remove)]
        removed = len(library) - len(kept)
        return kept if removed else False

    if config_m.mutate_library(_drop_paths):
        logger.info(f"[library] 删除媒体库 '{name}'，清理 {removed} 条媒体记录")
    new_libs = [lib for lib in libs if lib.name != name]
    config.media_libraries = new_libs
    config_m.save(config)
    return {"status": "ok", "removed_videos": removed}


@router.post("/library/remove-path")
def remove_library_path(req: dict):
    """删除指定路径下的媒体数据（设置页删除路径时调用）"""
    path = req.get("path", "").strip()
    if not path:
        return {"status": "error", "message": "path required"}
    removed = 0

    def _drop_path(library):
        nonlocal removed
        kept = [v for v in library if not v.get("file_path", "").startswith(path)]
        removed = len(library) - len(kept)
        return kept if removed else False

    if config_m.mutate_library(_drop_path):
        logger.info(f"[library] 删除路径 '{path}' 下 {removed} 条媒体记录")
    return {"status": "ok", "removed": removed}


@router.get("/library/list")
def list_media_libraries():
    """列出所有媒体库（含 scan_paths 的自动识别库 + media_libraries 的分类库）"""
    config = config_m.config
    result = []
    for p in (config.scan_paths or []):
        if p.strip():
            result.append({
                "name": os.path.basename(p.rstrip("\\/")),
                "type": "scan",
                "category_tag": "",
                "paths": [p],
                "exclude_dirs": [],
            })
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
    # 整库清空也要持锁：否则可能插在别处的 load → save 中间，
    # 那次 save 会把刚清空的库整份写回来。
    with config_m.library_lock:
        config_m.save_library([])
    return {"status": "ok"}


@router.get("/media/subtitles")
def get_media_subtitles(path: str):
    """列出视频的外挂字幕文件（下载字幕后前端据此刷新字幕状态）"""
    from core.file_ops.sidecars import list_subtitle_files

    if not path:
        return {"status": "error", "files": [], "count": 0}
    files = list_subtitle_files(path)
    return {"status": "ok", "files": files, "count": len(files)}
