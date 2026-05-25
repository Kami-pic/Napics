"""
路由模块：library
扫描与同步（scan_path / quick_sync）
其余路由已拆分到 library_tree.py 和 library_crud.py
"""
import os
import logging
import json
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import config_m, shadow_m, _tmdb_client
import scanner

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
                        result = clean_from_filename(fn)
                        if result.display:
                            item["clean_name"] = result.display
                            item["clean_name_cn"] = result.cn
                            item["clean_name_en"] = result.en
                            item["clean_name_original"] = result.original
                            item["clean_name_source"] = "parsed"
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
        folder = os.path.dirname(fp)
        while folder:
            if folder in excluded:
                return True
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
        return False

    # 构建 scan_path → media_library 名称的映射
    _sync_lib_name_map: Dict[str, str] = {}
    _sync_lib_exclude_map: Dict[str, set] = {}
    for lib in (config_m.config.media_libraries or []):
        for lp in lib.paths:
            norm_lp = lp.replace("/", "\\").rstrip("\\")
            _sync_lib_name_map[norm_lp] = lib.name
            if lib.exclude_dirs:
                _sync_lib_exclude_map[norm_lp] = set(lib.exclude_dirs)
    _global_exclude_dirs = set(
        d.strip() for d in (config_m.config.exclude_dirs or "").split(",") if d.strip()
    )

    def _get_folder_name(fp: str, base: str) -> str:
        """计算视频的 folder_name"""
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
                    dirs[:] = [d for d in dirs if d not in _global_exclude_dirs and d not in lib_excludes]
                    for f in files:
                        if os.path.splitext(f)[1].lower() in extensions:
                            fp = os.path.join(root, f)
                            if not is_excluded(fp):
                                fs_files.add(fp)

            lib_paths = set(v.get("file_path", "") for v in library)
            added = fs_files - lib_paths
            removed = lib_paths - fs_files

            # 额外清理：不属于任何已配置路径的孤立条目
            if nas_paths:
                orphaned = set()
                for fp in lib_paths:
                    if not fp:
                        continue
                    if not any(fp.startswith(base) for base in nas_paths):
                        orphaned.add(fp)
                removed = removed | orphaned

            yield "data: " + json.dumps({"type": "status", "message": f"发现 {len(added)} 个新增，{len(removed)} 个移除"}) + "\n\n"

            current_lib = [v for v in library if v.get("file_path", "") not in removed]

            # 检测已有文件的大小变化
            changed_files = []
            for v in current_lib:
                fp = v.get("file_path", "")
                if fp and fp in fs_files:
                    try:
                        actual_size = round(os.path.getsize(fp) / (1024**3), 2)
                        lib_size = v.get("size_gb", 0)
                        if lib_size > 0 and abs(actual_size - lib_size) / lib_size > 0.05:
                            changed_files.append(fp)
                    except OSError:
                        pass

            if changed_files:
                yield "data: " + json.dumps({"type": "status", "message": f"检测到 {len(changed_files)} 个文件大小变化，重新分析"}) + "\n\n"
                current_lib = [v for v in current_lib if v.get("file_path", "") not in set(changed_files)]
                added = added | set(changed_files)

            # 新增的逐个跑 ffprobe
            total_new = len(added)
            new_videos = []
            use_fast_mode = total_new > 50
            if use_fast_mode:
                yield "data: " + json.dumps({"type": "status", "message": f"快速模式：{total_new} 个新文件（跳过详细分析）"}) + "\n\n"

            for i, fp in enumerate(added):
                if i % 10 == 0 or not use_fast_mode:
                    yield "data: " + json.dumps({"type": "progress", "current": i + 1, "total": total_new, "file": os.path.basename(fp)}) + "\n\n"
                try:
                    if use_fast_mode:
                        info = scanner._fallback_info(fp)
                    else:
                        info = scanner.get_video_metadata(fp)
                    if info:
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

            # 扫描后自动从 NFO 填充影子名
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
