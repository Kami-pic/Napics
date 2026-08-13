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
from shadow_name_manager import apply_auto_fill
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

            # 2. 增量识别：已有记录且文件大小没变的直接复用，跳过 ffprobe
            existing = config_m.load_library()
            existing_map = {}  # file_path → item dict
            for v in existing:
                fp = v.get("file_path", "")
                if fp:
                    existing_map[fp] = v

            reused = []
            need_probe = []
            for f in all_files:
                old = existing_map.get(f)
                if old and old.get("height", 0) > 0:
                    # 检查文件大小是否变化
                    try:
                        actual_size = round(os.path.getsize(f) / (1024**3), 2)
                        if abs(actual_size - old.get("size_gb", 0)) < 0.01:
                            reused.append((f, old))
                            continue
                    except OSError:
                        pass
                need_probe.append(f)

            if reused:
                yield "data: " + json.dumps({"type": "status", "message": f"复用 {len(reused)} 个已有记录，{len(need_probe)} 个需要分析"}) + "\n\n"

            # 复用的直接加入结果
            for f, old_item in reused:
                rel_dir = os.path.relpath(os.path.dirname(f), path)
                rel_dir = "" if rel_dir == "." else rel_dir
                item = dict(old_item)
                if library_name:
                    item["folder_name"] = os.path.join(library_name, rel_dir) if rel_dir else library_name
                else:
                    item["folder_name"] = rel_dir
                results.append(item)

            # 3. 并发 ffprobe 识别新增/变更文件
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading

            progress_count = len(reused)
            total_count = len(all_files)

            def _probe_one(fp):
                """单个文件的 ffprobe 处理"""
                try:
                    info = scanner.get_video_metadata(fp)
                    if info:
                        rel_dir = os.path.relpath(os.path.dirname(fp), path)
                        rel_dir = "" if rel_dir == "." else rel_dir
                        if library_name:
                            info.folder_name = os.path.join(library_name, rel_dir) if rel_dir else library_name
                        else:
                            info.folder_name = rel_dir
                        return ("ok", fp, info.dict())
                    return ("empty", fp, None)
                except Exception as e:
                    logger.error(f"[scan] 文件处理失败: {fp} — {e}")
                    fallback = scanner._fallback_info(fp)
                    if fallback:
                        rel_dir = os.path.relpath(os.path.dirname(fp), path)
                        rel_dir = "" if rel_dir == "." else rel_dir
                        if library_name:
                            fallback.folder_name = os.path.join(library_name, rel_dir) if rel_dir else library_name
                        else:
                            fallback.folder_name = rel_dir
                        return ("fallback", fp, fallback.dict())
                    return ("error", fp, None)

            # 并发度：SMB/UNC 路径受网络延迟限制固定用 6；
            # 本地路径（含 Docker 挂载卷）按 CPU 核数自适应 —— ffprobe 是独立进程，
            # 并发数超过核数只会互相抢 CPU，在低功耗 NAS 上反而更慢。
            if path.startswith("\\\\"):
                max_workers = 6
            else:
                max_workers = max(4, min(12, os.cpu_count() or 4))

            if need_probe:
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {pool.submit(_probe_one, fp): fp for fp in need_probe}
                    for future in as_completed(futures):
                        progress_count += 1
                        status, fp, item_dict = future.result()
                        if item_dict:
                            results.append(item_dict)
                            yield "data: " + json.dumps({"type": "progress", "file": item_dict, "current": progress_count, "total": total_count}) + "\n\n"
                        else:
                            yield "data: " + json.dumps({"type": "progress", "raw_file_name": os.path.basename(fp), "current": progress_count, "total": total_count}) + "\n\n"

            # 4. 保存阶段
            kept = [v for v in existing if not v.get("file_path", "").startswith(path)]
            final = kept + results

            from clean_name_system import clean_from_filename, safe_update_clean_name as _safe_update
            # 只对新扫描的文件生成清洗名 + 标准名（复用的已有）
            reused_paths = set(f for f, _ in reused)
            shadow_filled = 0
            for item in results:
                if item.get("file_path") in reused_paths:
                    continue  # 复用的已有清洗名
                fn = item.get("file_name", "")
                if fn:
                    result_cn = clean_from_filename(fn)
                    if result_cn.display:
                        item["clean_name"] = result_cn.display
                        item["clean_name_cn"] = result_cn.cn
                        item["clean_name_en"] = result_cn.en
                        item["clean_name_original"] = result_cn.original
                        item["clean_name_source"] = "parsed"
                        # 同时生成标准名（shadow_name）
                        # 直接在内存条目上应用：这些条目随后由 save_library(final) 一次性落盘，
                        # 避免每条都做一次全库读写
                        if result_cn.display:
                            if apply_auto_fill(item, result_cn.display, source="parsed"):
                                shadow_filled += 1

            # 清理不属于任何已配置路径的孤立条目
            _all_configured_paths = list(config_m.config.scan_paths or [])
            for lib in (config_m.config.media_libraries or []):
                _all_configured_paths.extend(lib.paths)
            if _all_configured_paths:
                final = [v for v in final if not v.get("file_path") or
                         any(v["file_path"].startswith(p) for p in _all_configured_paths)]

            config_m.save_library(final)
            yield "data: " + json.dumps({"type": "done", "total": len(results), "shadow_filled": shadow_filled}) + "\n\n"

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
                            # 在内存条目上应用，循环结束后统一落盘一次
                            if apply_auto_fill(item, shadow, source="nfo", tmdb_id=nfo_info.get("tmdb_id")):
                                shadow_filled += 1
                    except Exception:
                        pass

            # 影子名有变更才二次落盘（new_videos 的条目与 current_lib 共享同一对象）
            if shadow_filled:
                config_m.save_library(current_lib)

            yield "data: " + json.dumps({"type": "done", "added": len(new_videos), "removed": len(removed), "total": len(current_lib), "shadow_filled": shadow_filled}) + "\n\n"

        except Exception as e:
            logger.info(f"[sync] 快速同步异常: {e}")
            import traceback
            traceback.print_exc()
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
