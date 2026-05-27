"""
路由模块：relocate — 归位替换
从 routes/organize.py 拆分而来
"""
import os
import logging
import re
import shutil
import asyncio
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import (
    config_m, _get_download_manager, _get_file_relocator, _get_recycle_bin,
    _tmdb_client,
    _get_category_from_path, _is_top_category, _sync_library_paths,
)
from download_provider_factory import get_download_provider_map
import scraper, organizer

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_qb_torrent_files(downloader_hash: str) -> list[dict]:
    if not downloader_hash:
        return []
    provider = get_download_provider_map().get("qbittorrent")
    if not provider:
        return []
    return [
        {"name": item.name, "size_bytes": item.size_bytes}
        for item in provider.list_files(downloader_hash)
    ]


# ── 数据模型 ──

class RelocateRequest(BaseModel):
    task_id: str
    auto_replace: bool = False

class ExecuteRelocateRequest(BaseModel):
    task_id: str
    plan: dict


# ── 树状结构构建工具（已下沉到 relocate_tree_builder.py）──
from relocate_tree_builder import _build_old_tree, _build_new_tree, _build_plan_tree


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
        nas_roots = config_m.config.scan_paths or []
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
                file_info_list = _get_qb_torrent_files(task.downloader_hash)
            except Exception as qe:
                logger.error(f"[DryRun] qB 获取文件列表失败: {qe}")
        
        # 提取纯路径名作为白名单（如果为空则传 None，触发 relocator 的全量探测逻辑）
        new_files = [f["name"] for f in file_info_list] if file_info_list else None
        
        try:
            logger.info(f"\n[DryRun] task={task.media_name}, save_path={task.save_path}, whitelist={len(new_files) if new_files else 'None'}")
        except UnicodeEncodeError:
            logger.info("\n[DryRun] task=<UnicodeName>, whitelist=", len(new_files) if new_files else 'None')

        rel = _get_file_relocator()
        res = await rel.relocate(task, new_files_whitelist=new_files)

        try:
            logger.info(f"[DryRun] result: status={res.status}, pairs={len(res.coexist_pairs)}, error={res.error}")
            if res.action_plan and isinstance(res.action_plan, dict):
                plan_items = res.action_plan.get("plan", [])
                ft = res.action_plan.get("folder_type", "")
                logger.info(f"[DryRun] plan: {len(plan_items)} items, folder_type={ft}")
        except UnicodeEncodeError:
            logger.info(f"[DryRun] result: status={res.status}, pairs={len(res.coexist_pairs)}")

        if res.status == "awaiting_confirm":
            # 🛡️ 兜底逻辑：如果 qB 没给文件列表，从推演计划中提取已识别的视频
            display_new_files = file_info_list
            if not display_new_files and res.action_plan:
                fallback_plan = res.action_plan.get("plan", []) if isinstance(res.action_plan, dict) else []
                display_new_files = [
                    {"name": os.path.relpath(item["source_path"], task.save_path), "size": 0}
                    for item in fallback_plan
                ]
            
            # 构建三栏树状数据
            old_tree = _build_old_tree(res.coexist_pairs, task.save_path)
            new_tree = _build_new_tree(display_new_files)
            plan_tree = _build_plan_tree(res.action_plan, res.coexist_pairs, task.save_path, display_new_files)
            
            return {
                "status": "awaiting_confirm",
                "message": "发现库中存量旧版本，建议执行整理替换",
                "coexist_pairs": [p.model_dump() for p in res.coexist_pairs],
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
            # 无冲突但有整理计划（如电影重命名）→ 返回 plan 供前端展示和执行
            if res.action_plan and isinstance(res.action_plan, dict):
                plan_items = res.action_plan.get("plan", [])
                has_actions = any(
                    item.get("actions") and not item.get("skip_reason")
                    for item in plan_items if item
                )
                if has_actions:
                    display_new_files = file_info_list
                    if not display_new_files and res.action_plan:
                        fallback_plan = res.action_plan.get("plan", [])
                        display_new_files = [
                            {"name": item.get("original_filename", ""), "size": 0}
                            for item in fallback_plan if item
                        ]
                    plan_tree = _build_plan_tree(res.action_plan, [], task.save_path, display_new_files)
                    new_tree = _build_new_tree(display_new_files)
                    return {
                        "status": "awaiting_confirm",
                        "message": "未发现旧版本冲突，可直接整理归档",
                        "coexist_pairs": [],
                        "plan": res.action_plan,
                        "new_files_all": display_new_files,
                        "old_tree": [],
                        "new_tree": new_tree,
                        "plan_tree": plan_tree,
                    }
            
        return {"status": res.status, "message": "未发现冲突，可直接归档", "coexist_pairs": []}
    except Exception as e:
        tb = traceback.format_exc()
        try:
            logger.info(tb)
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
        file_info = _get_qb_torrent_files(task.downloader_hash)
        if file_info:
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
        file_info = _get_qb_torrent_files(task.downloader_hash)
        new_files = [f["name"] for f in file_info]
            
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
        file_info = _get_qb_torrent_files(task.downloader_hash)
        new_files = [f["name"] for f in file_info]
    
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
