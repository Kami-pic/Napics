"""
路由模块：library_sync
从 library.py 拆分 — /sync 快速同步（以文件系统为准对账媒体库）

拆分原因：library.py 越过 400 行红线。/scan 与 /sync 是两条独立流程，
只共用路径归属判断（已下沉到 shared.is_under_path）。
"""
import os
import logging
import json
from typing import Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from shared import config_m, shadow_m, _tmdb_client, is_under_path
from shadow_name_manager import apply_auto_fill
import scanner

logger = logging.getLogger(__name__)
router = APIRouter()

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
                    if not any(is_under_path(fp, base) for base in nas_paths):
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
                            if is_under_path(fp, base) and len(base) > len(best_base):
                                best_base = base
                        if best_base:
                            info.folder_name = _get_folder_name(fp, best_base)
                        new_videos.append(info.dict())
                except Exception as e:
                    logger.error(f"[sync] 文件处理失败: {fp} — {e}")

            current_lib.extend(new_videos)

            # 填名放在落盘之前。原先是「先落盘 → 再填名 → 只有影子名被填过才二次落盘」，
            # 于是"有检索名、无影子名"的新增视频，检索名永远不会持久化。
            # 合并成一次落盘同时省掉一次整库序列化。
            shadow_filled = 0
            sync_tmdb = _tmdb_client()
            from scan_name_filler import fill_search_index_name
            for item in new_videos:
                fp = item.get("file_path", "")
                if fp:
                    # 检索名此前在快速同步里完全没填，新增的视频要等目录树自愈才有名字
                    try:
                        fill_search_index_name(item)
                    except Exception:
                        pass
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

            _snapshot_paths = set(v.get("file_path", "") for v in library)
            _new_paths = set(v.get("file_path", "") for v in new_videos)

            def _merge_sync(latest):
                """同步只负责「文件系统里有 / 没有」这一件事。

                current_lib 派生自同步开始时的库快照，而文件系统遍历可能跑了几分钟。
                这期间别处对库做的三类改动都必须尊重：
                - 新增（下载归位入库）：不在快照里，直接补进来；
                - 删除（批处理 / 回收站）：不能因为快照里还有就复活；
                - 字段更新（刮削写 shadow_name / clean_name）：本次同步不改已有条目的
                  任何字段，所以保留下来的条目一律用最新库的版本，不用几分钟前的快照对象。
                """
                latest_map = {v["file_path"]: v for v in latest if v.get("file_path")}
                deleted_elsewhere = _snapshot_paths - set(latest_map)

                merged = []
                for v in current_lib:
                    fp = v.get("file_path", "")
                    if fp in _new_paths:
                        merged.append(v)          # 本次新增，只有这里有
                        continue
                    if fp in deleted_elsewhere:
                        continue                  # 别处已经删了，不复活
                    merged.append(latest_map.get(fp, v))

                # 期间别处新增的条目
                merged.extend(
                    v for v in latest
                    if v.get("file_path")
                    and v["file_path"] not in _snapshot_paths
                    and v["file_path"] not in _new_paths
                    and v["file_path"] not in removed
                )
                return merged

            config_m.mutate_library(_merge_sync)

            yield "data: " + json.dumps({"type": "done", "added": len(new_videos), "removed": len(removed), "total": len(current_lib), "shadow_filled": shadow_filled}) + "\n\n"

        except Exception as e:
            logger.info(f"[sync] 快速同步异常: {e}")
            import traceback
            traceback.print_exc()
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
