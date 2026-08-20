"""
路由模块：library_crud
从 library.py 拆分 — 媒体库 CRUD + 完整度 + 质量分 + clean_name
"""
import os
import re
import logging
import threading
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import config_m, _tmdb_client
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
    library = config_m.load_library()
    updated = 0
    path_set = set(paths) if paths else None

    if path_set:
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
            except Exception as e:
                logger.error(f"[refresh-quality] ffprobe 失败: {fp} — {e}")
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

    if updated:
        config_m.save_library(library)
    return {"status": "ok", "updated": updated, "total": len(library)}


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
    library = config_m.load_library()
    paths_to_remove = set(target.paths)
    kept = [v for v in library if not any(v.get("file_path", "").startswith(p) for p in paths_to_remove)]
    if len(kept) < len(library):
        config_m.save_library(kept)
        logger.info(f"[library] 删除媒体库 '{name}'，清理 {len(library) - len(kept)} 条媒体记录")
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
    clean_name_en = req.get("clean_name_en")
    is_folder = req.get("is_folder", False)
    if not file_path:
        return {"status": "error", "message": "file_path required"}

    library = config_m.load_library()

    if is_folder:
        folder_norm = file_path.replace("\\", "/").rstrip("/") + "/"
        updated = 0
        for v in library:
            v_folder = v.get("file_path", "").replace("\\", "/")
            if v_folder.startswith(folder_norm) or os.path.dirname(v_folder).replace("\\", "/") + "/" == folder_norm:
                if clean_name_en is not None:
                    v["clean_name_en"] = clean_name_en
                    v["clean_name_source"] = "manual"
                    updated += 1
                if clean_name:
                    v["clean_name"] = clean_name
                    v["clean_name_source"] = "manual"
                    cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', clean_name)
                    if cn_parts:
                        v["clean_name_cn"] = "".join(cn_parts)
                    updated += 1
        if updated > 0:
            config_m.save_library(library)
            return {"status": "ok", "updated": updated}
        # 文件夹下没有视频，尝试直接匹配
        for v in library:
            if v.get("file_path") == file_path:
                if clean_name:
                    v["clean_name"] = clean_name
                    v["clean_name_source"] = "manual"
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
                if clean_name:
                    cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', clean_name)
                    if cn_parts:
                        v["clean_name_cn"] = "".join(cn_parts)
            if clean_name_en is not None:
                v["clean_name_en"] = clean_name_en
                v["clean_name_source"] = "manual"
            config_m.save_library(library)
            return {"status": "ok"}
    return {"status": "not_found"}


@router.get("/media/subtitles")
def get_media_subtitles(path: str):
    """列出视频的外挂字幕文件（下载字幕后前端据此刷新字幕状态）"""
    from core.file_ops.sidecars import list_subtitle_files

    if not path:
        return {"status": "error", "files": [], "count": 0}
    files = list_subtitle_files(path)
    return {"status": "ok", "files": files, "count": len(files)}


@router.post("/library/clean-name/generate")
def generate_clean_name(req: dict):
    """按文件名自动生成搜索索引名（中文+英文），用户点按钮显式触发"""
    from clean_name_system import regenerate_clean_names

    file_path = req.get("file_path", "")
    if not file_path:
        return {"status": "error", "message": "file_path required"}

    library = config_m.load_library()
    result = regenerate_clean_names(library, file_path, req.get("is_folder", False))
    if result["updated"]:
        config_m.save_library(library)
        return {"status": "ok", **result}

    # 把失败原因说清楚：路径对不上和解析失败要分开，否则线上排查只能靠猜
    reason = result.get("reason", "")
    if reason == "not_in_library":
        message = f"媒体库里没有这条记录，路径可能不一致：{file_path}"
    elif reason == "unparsable":
        message = f"匹配到 {result.get('matched', 0)} 条记录，但从 NFO / 文件夹名 / 文件名都解析不出名称"
    else:
        message = "缺少 file_path"
    logger.warning(f"[clean-name/generate] 失败({reason}): {file_path}")
    return {"status": "failed", "message": message, **result}


@router.get("/library/completeness")
def get_completeness(path: str, tmdb_id: Optional[int] = None, refresh: bool = False):
    """获取 TV 文件夹的季集完整度（基于 TMDB 数据源）"""
    from plugin_guard import is_feature_allowed, is_metadata_allowed
    if not is_feature_allowed("completeness"):
        return {"status": "plugin_not_installed", "message": "请先安装「季集完整性检测」插件"}
    if not is_metadata_allowed("tmdb"):
        return {"status": "metadata_plugin_not_installed", "message": "请先安装「TMDB 元数据」插件"}

    from completeness import (
        collect_local_episodes, get_tmdb_id_from_folder, compute_completeness,
        get_cached_completeness, save_completeness_to_cache, refresh_completeness_for_path,
    )

    if not path:
        raise HTTPException(400, "缺少 path 参数")

    logger.info(f"[completeness] API 请求: path={path}, refresh={refresh}, tmdb_id={tmdb_id}")

    if not refresh:
        cached = get_cached_completeness(path)
        if cached and cached.get("status") == "ok":
            logger.info(f"[completeness] 返回缓存: {cached.get('completeness_pct')}%")
            return cached

    tid = tmdb_id
    if not tid:
        tid = get_tmdb_id_from_folder(path)
    if not tid:
        logger.warning(f"[completeness] 无 TMDB ID: {path}")
        return {"status": "no_tmdb_id", "message": "未找到 TMDB ID，请先刮削此文件夹"}

    tc = _tmdb_client()
    if not tc:
        return {"status": "no_tmdb_client", "message": "TMDB 未配置"}

    logger.info(f"[completeness] 重新计算: tmdb_id={tid}, refresh={refresh}")
    result = refresh_completeness_for_path(tc, path, clear_tmdb_cache=refresh)
    if result:
        logger.info(f"[completeness] 计算完成: {result.get('completeness_pct')}%, local={result.get('local_total')}")
        return result

    logger.info(f"[completeness] 兜底计算")
    local_episodes = collect_local_episodes(path)
    result = compute_completeness(tc, tid, local_episodes)
    if result.get("status") == "ok":
        save_completeness_to_cache(path, result)
    return result


@router.post("/library/completeness/refresh-all")
def refresh_all_completeness():
    """批量预计算所有 TV 文件夹的完整度（后台运行）"""
    import plugin_guard
    from completeness import batch_refresh_all

    if not plugin_guard.is_feature_allowed("completeness"):
        return {"status": "plugin_not_installed", "message": "请先安装「季集完整性检测」插件"}
    if not plugin_guard.is_metadata_allowed("tmdb"):
        return {"status": "metadata_plugin_not_installed", "message": "请先安装「TMDB 元数据」插件"}

    tc = _tmdb_client()
    if not tc:
        return {"status": "error", "message": "TMDB 未配置"}

    nas_paths = config_m.config.scan_paths or []
    category_tags = config_m.config.category_tags or {}

    def _run():
        try:
            if not plugin_guard.is_feature_allowed("completeness") or not plugin_guard.is_metadata_allowed("tmdb"):
                return
            batch_refresh_all(tc, nas_paths, category_tags)
        except Exception as e:
            logger.error(f"[completeness] 批量预计算异常: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "started", "message": "批量预计算已启动，请查看后端日志"}
