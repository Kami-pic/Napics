"""
路由模块：library
/scan 扫描（SSE 流式进度）

快速同步在 library_sync.py，目录树在 library_tree.py，CRUD 在 library_crud.py
"""
import os
import logging
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import config_m, is_under_path
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
            from scan_name_filler import fill_names_for_item, needs_refill
            # 生成检索名 + 标准名，来源优先级 NFO → 文件夹名 → 文件名。
            # 复用的旧条目也要按当前算法补算一次：同尺寸文件走复用分支时会整份沿用旧值，
            # 只处理新文件的话，算法改好后老库重扫看不到任何变化。
            # 补算受 manual/nfo 优先级保护，不会覆盖用户手填的名字；
            # 算过的条目打上版本号，后续扫描不再重复读 NFO。
            reused_paths = set(f for f, _ in reused)
            shadow_filled = 0
            names_refilled = 0
            for item in results:
                is_reused = item.get("file_path") in reused_paths
                if is_reused and not needs_refill(item):
                    continue
                # 直接在内存条目上应用：这些条目随后在保存阶段一次性落盘，
                # 避免每条都做一次全库读写
                _, item_shadow_filled = fill_names_for_item(item)
                if item_shadow_filled:
                    shadow_filled += 1
                if is_reused:
                    names_refilled += 1
            if names_refilled:
                logger.info(f"[scan] 按当前取名算法补算了 {names_refilled} 个旧条目的名字")

            # 清理不属于任何已配置路径的孤立条目
            _all_configured_paths = list(config_m.config.scan_paths or [])
            for lib in (config_m.config.media_libraries or []):
                _all_configured_paths.extend(lib.paths)

            # 同目录一致性自检：一个目录下各集算出的作品名必须一致。
            # 不一致说明取到的是分集级信息，整组标存疑（照常写入，只是打标）
            try:
                from name_conflicts import annotate_group_conflicts
                marked = annotate_group_conflicts(results)
                if marked:
                    logger.info(f"[scan] 同目录作品名不一致，{marked} 条标记为存疑")
            except Exception as e:
                logger.warning(f"[scan] 同目录一致性自检失败: {e}")

            from scan_name_filler import merge_scanned_names

            def _merge(latest):
                """本次扫描只对 path 下的条目负责，其余一律沿用最新落盘内容。

                合并必须基于**锁内重新读到的**库，不能用扫描开始时的 existing 快照 ——
                ffprobe 可能跑了好几分钟，期间下载归位、刮削、桌面整理写进去的条目
                都会被那份旧快照抹掉。
                """
                latest_map = {v["file_path"]: v for v in latest if v.get("file_path")}
                kept = [v for v in latest if not is_under_path(v.get("file_path", ""), path)]

                rebuilt = []
                for item in results:
                    fp = item.get("file_path", "")
                    base = latest_map.get(fp) if fp in reused_paths else None
                    if base is None:
                        # 新 probe 出来的条目，扫描结果就是全部事实
                        rebuilt.append(item)
                        continue
                    # 复用分支的 item 是扫描开始时的旧快照。整份写回会把期间
                    # 刮削写进这条的东西回滚掉，所以以最新条目为底做字段级合并。
                    rebuilt.append(merge_scanned_names(base, item))

                merged = kept + rebuilt
                if _all_configured_paths:
                    merged = [v for v in merged if not v.get("file_path") or
                              any(is_under_path(v["file_path"], p) for p in _all_configured_paths)]
                return merged

            config_m.mutate_library(_merge)
            yield "data: " + json.dumps({"type": "done", "total": len(results), "shadow_filled": shadow_filled}) + "\n\n"

        except Exception as e:
            logger.info(f"[scan] 扫描异常: {e}")
            import traceback
            traceback.print_exc()
            if results:
                try:
                    # 与正常分支同一套合并规则，只是不做孤立条目清理
                    config_m.mutate_library(
                        lambda latest: [v for v in latest
                                        if not is_under_path(v.get("file_path", ""), path)] + results
                    )
                except Exception:
                    pass
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


