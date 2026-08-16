"""
路由模块：organize_stream — 一键整理 SSE 流式进度反馈
"""
import os
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from shared import (
    config_m, shadow_m, analysis_cache,
    _tmdb_client,
    _get_category_from_path, _is_top_category, _sync_library_paths,
)
import organizer, analyzer, scraper

logger = logging.getLogger(__name__)
router = APIRouter()


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
            else:
                import plugin_guard

                scrape_summary = {
                    "error": "TMDB API key not configured"
                    if plugin_guard.is_metadata_allowed("tmdb")
                    else "plugin_not_installed"
                }
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
