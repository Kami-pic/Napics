"""
路由模块：library
"""
import os
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

router = APIRouter()

@router.get("/scan")
async def scan_path(path: str):
    """EventSource 实时返回扫描进度"""
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Path does not exist")
    
    def event_generator():
        results = []
        try:
            # 1. 发现阶段
            yield "data: " + json.dumps({"type": "start", "total": 0, "message": "正在获取文件列表..."}) + "\n\n"
            
            all_files = []
            extensions = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"]
            for root, dirs, files in os.walk(path):
                if "@eaDir" in root or "#recycle" in root: continue
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
                        info.folder_name = "" if rel_dir == "." else rel_dir
                        results.append(info.dict())
                        yield "data: " + json.dumps({"type": "progress", "file": info.dict()}) + "\n\n"
                    else:
                        yield "data: " + json.dumps({"type": "progress", "raw_file_name": os.path.basename(f)}) + "\n\n"
                except Exception as e:
                    print(f"[scan] 文件处理失败: {f} — {e}")
                    fallback = scanner._fallback_info(f)
                    if fallback:
                        rel_dir = os.path.relpath(os.path.dirname(f), path)
                        fallback.folder_name = "" if rel_dir == "." else rel_dir
                        results.append(fallback.dict())
                    yield "data: " + json.dumps({"type": "progress", "raw_file_name": os.path.basename(f)}) + "\n\n"
            
            # 3. 保存阶段
            scanned_paths = set(r.get("file_path") for r in results)
            existing = config_m.load_library()
            kept = [v for v in existing if not v.get("file_path", "").startswith(path)]
            final = kept + results
            
            from analyzer import _clean_filename_for_folder
            for item in final:
                if not item.get("clean_name"):
                    fn = item.get("file_name", "")
                    if fn:
                        cleaned = _clean_filename_for_folder(fn)
                        item["clean_name"] = cleaned if cleaned else os.path.splitext(fn)[0]
            
            config_m.save_library(final)
            yield "data: " + json.dumps({"type": "done", "total": len(results)}) + "\n\n"

        except Exception as e:
            print(f"[scan] 扫描异常: {e}")
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
    nas_paths = config_m.config.nas_paths or ([config_m.config.nas_path] if config_m.config.nas_path else [])
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

    def event_gen():
        try:
            yield "data: " + json.dumps({"type": "status", "message": "扫描文件系统..."}) + "\n\n"

            fs_files = set()
            for base in nas_paths:
                if not base or not os.path.exists(base): continue
                for root, dirs, files in os.walk(base):
                    if "@eaDir" in root or "#recycle" in root: continue
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
                        for base in nas_paths:
                            if fp.startswith(base):
                                rel_dir = os.path.relpath(os.path.dirname(fp), base)
                                info.folder_name = "" if rel_dir == "." else rel_dir
                                break
                        new_videos.append(info.dict())
                except Exception as e:
                    print(f"[sync] 文件处理失败: {fp} — {e}")

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
                                    en = sync_tmdb._get_english_title("movie", nfo_info["tmdb_id"], orig)
                                    if not en:
                                        en = sync_tmdb._get_english_title("tv", nfo_info["tmdb_id"], orig)
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
            print(f"[sync] 快速同步异常: {e}")
            import traceback
            traceback.print_exc()
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@router.get("/library")
def get_library():
    """获取本地缓存的媒体库"""
    return config_m.load_library()

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
    """设置一级分类目录的标签（movie/tv/variety/anime/other）"""
    path = req.get("path", "")
    tag = req.get("tag", "")
    if not path or tag not in ("movie", "tv"):
        return {"status": "error", "message": "path and valid tag (movie/tv) required"}
    config = config_m.config
    tags = dict(config.category_tags or {})
    tags[path] = tag
    config.category_tags = tags
    config_m.save(config)
    return {"status": "ok"}

@router.post("/library/clean-name")
def set_clean_name(req: dict):
    """手动修改清洗名"""
    file_path = req.get("file_path", "")
    clean_name = req.get("clean_name", "")
    if not file_path:
        return {"status": "error", "message": "file_path required"}
    
    library = config_m.load_library()
    for v in library:
        if v.get("file_path") == file_path:
            v["clean_name"] = clean_name
            config_m.save_library(library)
            return {"status": "ok"}
    return {"status": "not_found"}

@router.get("/library/tree")
def get_library_tree():
    """生成嵌套的目录树结构"""
    videos = config_m.load_library()
    root_node = {"name": "媒体库", "path": "", "children": [], "videos": [], "video_count": 0, "has_cover": False}
    
    config = config_m.config
    base_path = config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else ""

    for v in videos:
        rel_dir = v.get("folder_name", "")  # "Movies/Action"
        rel_dir = rel_dir.replace("\\", "/")
        parts = [p for p in rel_dir.split("/") if p]
        
        current_node = root_node
        current_rel = ""
        for part in parts:
            current_rel = os.path.join(current_rel, part) if current_rel else part
            child = next((c for c in current_node["children"] if c["name"] == part), None)
            if not child:
                child = {
                    "name": part,
                    "path": os.path.join(base_path, current_rel),
                    "children": [],
                    "videos": [],
                    "video_count": 0,
                    "has_cover": False
                }
                current_node["children"].append(child)
            current_node = child
        current_node["videos"].append(v)
    
    # 预计算一级分类路径集合
    top_category_paths = set()
    for child in root_node["children"]:
        if child["children"]:
            top_category_paths.add(child["path"])

    # 读取用户配置的 category_tags（路径 → 标签）
    configured_tags = config.category_tags or {}

    def _resolve_category_tag(node_path: str, node_name: str) -> str:
        """解析一级分类目录的标签：配置优先，否则自动推断"""
        if node_path in configured_tags:
            return configured_tags[node_path]
        return organizer.infer_category_tag(node_name)

    def _infer_folder_type_from_tree(node, category_tag: str) -> str:
        """从树结构推断 folder_type，不依赖文件系统。
        使用树节点的 children 和 videos 信息判断。"""
        children = node.get("children", [])
        videos = node.get("videos", [])
        has_children = len(children) > 0
        has_videos = len(videos) > 0
        video_count = node.get("video_count", 0)

        if category_tag == "movie":
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

        elif category_tag == "tv":
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
                node["folder_type"] = ""
                node["category_tag"] = category_tag
                node["is_top_category"] = True
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
                    node["shadow_name"] = v["shadow_name"]
                    node["shadow_tmdb_id"] = v.get("shadow_tmdb_id")
                    break
        
        # 2. 如果当前节点没视频或没译名，尝试从子节点“冒泡”提取
        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    # 继承子节点的译名（通常用于 TV Show 根目录继承 Season/Episode 信息）
                    node["shadow_name"] = child["shadow_name"]
                    node["shadow_tmdb_id"] = child.get("shadow_tmdb_id")
                    break

        # 文件夹级 clean_name：优先用 shadow_name 去年份，否则清洗原始名
        if node["path"] and node["path"] != base_path:
            if node.get("shadow_name"):
                # 刮削过的文件夹：用 shadow_name 去掉年份
                import re as _re_cn
                cn = _re_cn.sub(r'\s*\(\d{4}\)\s*$', '', node["shadow_name"]).strip()
                node["clean_name"] = cn or node["shadow_name"]
            else:
                # 未刮削：用 _clean_filename_for_folder 清洗原始文件夹名
                from analyzer import _clean_filename_for_folder
                cleaned = _clean_filename_for_folder(node["name"] + ".tmp")
                node["clean_name"] = cleaned if cleaned else node["name"]
        else:
            node["clean_name"] = node.get("name", "")
        return count, has_cover

    finalize(root_node)

    # 二次遍历：标记 season + 传播 parent_category_tag + 计算层级 clean_name
    def post_process(node, inherited_tag="", parent_show_clean=""):
        import re as _re_pp
        cat = node.get("category_tag", "") or inherited_tag
        node["parent_category_tag"] = cat
        
        # 深度修正：如果父节点没影子名，尝试从子节点反向追溯（处理聚合文件夹）
        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    node["shadow_name"] = child["shadow_name"]
                    break

        # 当前节点的纯剧名（去年份、去 Season XX）用于传递给子节点
        raw_clean = node.get("clean_name", "") or parent_show_clean
        # 去掉尾部年份 (2016)
        show_clean = _re_pp.sub(r'\s*\(\d{4}\)\s*$', '', raw_clean).strip()
        # 去掉尾部 Season XX
        show_clean = _re_pp.sub(r'\s*Season\s*\d+\s*$', '', show_clean, flags=_re_pp.I).strip()
        if not show_clean:
            show_clean = parent_show_clean

        # tv 的子目录标记为 season + 计算季 clean_name
        if node.get("folder_type") == "tv":
            from analyzer import clean_season_name
            for child in node.get("children", []):
                if child.get("folder_type") != "mixed":
                    child["folder_type"] = "season"
                # 季文件夹 clean_name：剧名 + Season XX（剧名不含年份）
                if not child.get("shadow_name"):
                    child["clean_name"] = clean_season_name(child["name"], show_clean)

        # 视频的 clean_name：纯剧名 + SxxExx（不含年份、不含 Season）
        if node.get("folder_type") in ("tv", "season") and node.get("videos"):
            from analyzer import clean_episode_name
            for v in node["videos"]:
                if show_clean:
                    new_clean = clean_episode_name(v.get("file_name", ""), show_clean)
                    if new_clean:
                        v["clean_name"] = new_clean

        for child in node.get("children", []):
            post_process(child, cat, show_clean)
    post_process(root_node)

    return root_node

