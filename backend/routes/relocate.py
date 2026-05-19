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


def _build_plan_tree(action_plan, coexist_pairs=None, save_path: str = "", new_files_all=None) -> list:
    """构建"执行后目录快照"树：新文件去向 + 附属文件 + 旧文件删除。
    
    展示内容：
    - 📁 新建目录（Season 01）+ 内部重命名的视频
    - ✅ 重命名的视频 / ⏭ 跳过的视频
    - 📁 附属文件夹（SPs、CDs）+ 内部文件（字幕、音乐等）
    - 💬 字幕文件（跟随对应视频）
    - 🗑 将被删除的旧视频（红色删除线）
    """
    tree = []
    
    plan_items = []
    if action_plan:
        plan_items = action_plan.get("plan", []) if isinstance(action_plan, dict) else []
    
    # 收集 plan 中已处理的文件名（用于后面排除）
    plan_filenames = set()
    
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
        
        plan_filenames.add(original_name.lower())
        
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
    
    # 新种子中不在 plan 里的附属文件（字幕、SPs、CDs 等）
    # 模拟 _apply_action_plan_moves 的逻辑，计算每个附属文件的实际目标位置
    if new_files_all:
        from organize_executor import _PLAN_SUBTITLE_EXTS, _PLAN_POSTER_SUFFIXES
        from tmdb_client import parse_filename

        def _classify_ext(name):
            ext = os.path.splitext(name)[1].lower()
            if ext in {".mp4",".mkv",".avi",".mov",".wmv",".rmvb",".rm",".flv",".ts",".m4v"}:
                return "video"
            if ext in {".ass",".srt",".ssa",".sub",".idx",".sup"}:
                return "subtitle"
            return "other"

        # 构建 plan 中视频的源→目标映射，用于匹配同名字幕
        video_source_bases = {}  # {source_base_lower: (source_dir, target_dir, target_base)}
        episode_target_map = {}  # {(season, episode): target_base}
        plan_source_dirs = set()
        plan_target_dirs = set()
        plan_target_dirs_original = {}  # {normcase_path: original_path}
        for item in (plan_items or []):
            if item is None:
                continue
            original_path = item.get("original_path") or ""
            target_path = item.get("target_path") or ""
            if not original_path or not target_path:
                continue
            s_dir = os.path.dirname(original_path)
            t_dir = os.path.dirname(target_path)
            s_base = os.path.splitext(os.path.basename(original_path))[0]
            t_base = os.path.splitext(os.path.basename(target_path))[0]
            video_source_bases[s_base.lower()] = (s_dir, t_dir, t_base)
            plan_source_dirs.add(os.path.normcase(os.path.abspath(s_dir)))
            norm_t_dir = os.path.normcase(os.path.abspath(t_dir))
            plan_target_dirs.add(norm_t_dir)
            plan_target_dirs_original[norm_t_dir] = os.path.abspath(t_dir)
            mapped = item.get("mapped") or {}
            s, e = mapped.get("season"), mapped.get("episode")
            if s is not None and e is not None:
                episode_target_map[(s, e)] = t_base

        # 计算每个附属文件的目标位置
        # 结果：{相对于 save_path 的目标路径: {name, type, action, ...}}
        planned_extras = []  # [(target_rel_path, node)]
        for f in new_files_all:
            name = f.get("name", "")
            size = f.get("size_bytes", f.get("size", 0))
            parts = name.replace("/", os.sep).replace("\\", os.sep).split(os.sep)
            fname = parts[-1] if parts else name
            if fname.lower() in plan_filenames:
                continue

            ft = _classify_ext(fname)
            file_ext = os.path.splitext(fname)[1].lower()
            abs_path = os.path.join(save_path, name) if save_path else name
            file_dir = os.path.dirname(abs_path)
            file_dir_norm = os.path.normcase(os.path.abspath(file_dir))

            # 第一阶段：同目录同名字幕/海报（跟随视频）
            handled = False
            if file_dir_norm in plan_source_dirs:
                f_base_lower = os.path.splitext(fname)[0].lower()
                # 检查海报后缀
                for suffix in _PLAN_POSTER_SUFFIXES:
                    check_base = fname[:len(fname)-len(suffix)].lower() if fname.lower().endswith(suffix) else None
                    if check_base and check_base in video_source_bases:
                        _, t_dir, t_base = video_source_bases[check_base]
                        target_name = t_base + suffix
                        target_rel = os.path.relpath(os.path.join(t_dir, target_name), save_path) if save_path else target_name
                        planned_extras.append((target_rel, {
                            "name": target_name, "type": "other", "action": "move",
                            "original_name": fname, "size_bytes": size,
                        }))
                        handled = True
                        break
                if not handled:
                    # 检查同名字幕
                    for src_base_lower, (s_dir, t_dir, t_base) in video_source_bases.items():
                        if f_base_lower.startswith(src_base_lower + ".") and file_ext in _PLAN_SUBTITLE_EXTS:
                            suffix = fname[len(src_base_lower):]
                            target_name = t_base + suffix
                            target_rel = os.path.relpath(os.path.join(t_dir, target_name), save_path) if save_path else target_name
                            planned_extras.append((target_rel, {
                                "name": target_name, "type": "subtitle", "action": "move",
                                "original_name": fname, "size_bytes": size,
                            }))
                            handled = True
                            break

            if handled:
                continue

            # 第二阶段：子目录中的文件
            if file_ext in _PLAN_SUBTITLE_EXTS:
                # 字幕文件：扁平化到 Season 目录，尝试用视频标准名
                target_dir_norm = next(iter(plan_target_dirs), None)
                target_dir_orig = plan_target_dirs_original.get(target_dir_norm, target_dir_norm) if target_dir_norm else None
                if target_dir_orig:
                    # 剥离语言标签解析集号
                    lang_suffix = ""
                    temp_name = fname
                    while True:
                        base_part, ext_part = os.path.splitext(temp_name)
                        if ext_part.lower() in _PLAN_SUBTITLE_EXTS:
                            lang_suffix = ext_part + lang_suffix
                            temp_name = base_part
                        elif ext_part.lower() in {".chs",".cht",".sc",".tc",".zh",
                                                  ".en",".jp",".ja",".ko",
                                                  ".chi",".eng",".jpn",".kor",
                                                  ".zh-hans",".zh-hant",
                                                  ".simplified",".traditional",
                                                  ".chinese",".japanese",".english",
                                                  ".chn"}:
                            lang_suffix = ext_part + lang_suffix
                            temp_name = base_part
                        else:
                            break
                    parsed_sub = parse_filename(temp_name)
                    sub_ep = parsed_sub.get("episode")
                    sub_s = parsed_sub.get("season")
                    matched_base = None
                    if sub_ep is not None:
                        lookup_s = sub_s if sub_s is not None else 1
                        matched_base = episode_target_map.get((lookup_s, sub_ep))
                    if matched_base and lang_suffix:
                        target_name = matched_base + lang_suffix
                    else:
                        target_name = fname
                    target_rel = os.path.relpath(
                        os.path.join(os.path.normpath(target_dir_orig), target_name), save_path
                    ) if save_path else target_name
                    planned_extras.append((target_rel, {
                        "name": target_name, "type": "subtitle", "action": "move",
                        "original_name": fname, "size_bytes": size,
                    }))
                    continue

            # 非字幕文件（SPs/CDs 等）：提升到剧集根目录
            # 从种子子目录结构中提取相对路径
            if len(parts) > 1:
                # 跳过种子目录名（第一层），保留后续子目录结构
                rel_parts = parts[1:] if len(parts) > 1 else parts
                target_rel = os.path.join(*rel_parts)
            else:
                target_rel = fname
            planned_extras.append((target_rel, {
                "name": fname, "type": ft, "action": "keep",
                "size_bytes": size,
            }))

        # 将附属文件按目标路径组织到树中
        extra_by_dir = {}  # {dir_rel: [nodes]}
        for target_rel, node in planned_extras:
            dir_rel = os.path.dirname(target_rel)
            if not dir_rel:
                tree.append(node)
            else:
                extra_by_dir.setdefault(dir_rel, []).append(node)

        # 将附属文件合并到已有的季目录节点中，或创建新的目录节点
        for dir_rel, nodes in sorted(extra_by_dir.items()):
            dir_parts = dir_rel.replace("\\", "/").split("/")
            top_dir = dir_parts[0] if dir_parts else dir_rel

            # 尝试合并到已有的季目录节点（大小写不敏感比较）
            merged = False
            for t_node in tree:
                if t_node.get("type") == "dir" and t_node.get("name", "").lower() == top_dir.lower():
                    if len(dir_parts) == 1:
                        t_node.setdefault("children", []).extend(nodes)
                    else:
                        # 需要在季目录下创建子路径
                        sub_path = os.path.join(*dir_parts[1:]) if len(dir_parts) > 1 else ""
                        if sub_path:
                            sub_node = {
                                "name": sub_path, "type": "dir", "action": "keep",
                                "children": nodes,
                            }
                            t_node.setdefault("children", []).append(sub_node)
                        else:
                            t_node.setdefault("children", []).extend(nodes)
                    merged = True
                    break

            if not merged:
                # 创建新的目录节点
                if len(dir_parts) == 1:
                    tree.append({
                        "name": top_dir, "type": "dir", "action": "keep",
                        "skip_reason": "附属文件夹",
                        "children": nodes,
                    })
                else:
                    # 多层嵌套
                    inner = nodes
                    for p in reversed(dir_parts[1:]):
                        inner = [{"name": p, "type": "dir", "action": "keep", "children": inner}]
                    tree.append({
                        "name": top_dir, "type": "dir", "action": "keep",
                        "skip_reason": "附属文件夹",
                        "children": inner,
                    })
    
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
