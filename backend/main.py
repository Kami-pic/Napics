import os
import json
import asyncio
import time
import shutil
import requests
import re
import subprocess
from typing import List, Optional, Dict

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

import scanner
import searcher
import downloader
import tmdb_client
import config_manager
import ai_organizer
import douban_client
import bangumi_client
import scraper
import organizer
from organize_history import history_m
from shadow_name_manager import ShadowNameManager
from indexer_priority_manager import IndexerPriorityManager
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask
from recycle_bin import RecycleBin
from file_relocator import FileRelocator
from torrent_blacklist import TorrentBlacklist
from analysis_cache import AnalysisCache
from pan_search_service import PanSearchService
from pan_models import PanSearchResponse, TransferRequest, TransferResult

app = FastAPI(title="NAS Video Upgrader API")

# 初始化配置管理器
config_m = config_manager.ConfigManager()

# 初始化影子名管理器和索引器优先级管理器
shadow_m = ShadowNameManager()
indexer_m = IndexerPriorityManager()
indexer_m.load()

# 初始化种子黑名单和分析缓存
torrent_bl = TorrentBlacklist()
analysis_cache = AnalysisCache()

# 初始化下载管理器（延迟到首次使用时创建，因为需要配置）
_download_manager: Optional[DownloadManager] = None

# 初始化网盘搜索服务（延迟到首次使用时创建）
_pan_search_service: Optional[PanSearchService] = None


def _get_pan_search_service() -> PanSearchService:
    """获取网盘搜索服务单例。"""
    global _pan_search_service
    if _pan_search_service is None:
        _pan_search_service = PanSearchService(
            search_sources={"pansearch": True, "rrdynb": False, "ddys": False, "pansou": False},
        )
    return _pan_search_service

def _get_download_manager() -> DownloadManager:
    """懒加载下载管理器，确保配置已就绪。"""
    global _download_manager
    if _download_manager is None:
        conf = config_m.config
        clients = get_clients()
        _download_manager = DownloadManager(
            qb_client=clients["qb"] if conf.qb_url else None,
            alist_client=clients["alist"] if conf.alist_url and conf.alist_token else None,
            base_path=os.path.dirname(os.path.abspath(__file__)),
        )
        _download_manager.on_startup()
    return _download_manager

_recycle_bin: Optional[RecycleBin] = None
_file_relocator: Optional[FileRelocator] = None

def _get_recycle_bin() -> RecycleBin:
    """懒加载回收站。"""
    global _recycle_bin
    if _recycle_bin is None:
        conf = config_m.config
        recycle_dir = conf.recycle_bin_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "recycle_bin"
        )
        _recycle_bin = RecycleBin(recycle_dir, conf.recycle_bin_retention_days)
    return _recycle_bin

def _get_file_relocator() -> FileRelocator:
    """懒加载文件归位器，注入异步整理流水线函数。"""
    global _file_relocator
    if _file_relocator is None:
        _file_relocator = FileRelocator(
            recycle_bin=_get_recycle_bin(),
            run_pipeline_fn=organize_full, # 直接注入异步函数
        )
    return _file_relocator



def _tmdb_client():
    """统一创建 TMDBClient，自动带 proxy"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        return None
    return tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')

# 动态实例化客户端 (由配置驱动)
def get_clients():
    conf = config_m.config
    return {
        "search": searcher.ProwlarrClient(conf.prowlarr_url, conf.prowlarr_api_key),
        "tmdb": tmdb_client.TMDBClient(conf.tmdb_api_key, proxy=getattr(conf, 'http_proxy', '') or ''),
        "qb": downloader.QBittorrentClient(conf.qb_url, username="admin", password="z3858915"),
        "alist": downloader.AlistManager(conf.alist_url, conf.alist_token),
        "netdisk": searcher.NetdiskSearcher()
    }

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "NAS Video Upgrader API is running"}

@app.get("/scan")
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

@app.get("/sync")
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

@app.get("/library")
def get_library():
    """获取本地缓存的媒体库"""
    return config_m.load_library()

@app.post("/library/folder-type")
def set_folder_type(req: dict):
    """手动设置文件夹类型（覆盖自动判定）"""
    path = req.get("path", "")
    folder_type = req.get("folder_type", "")
    if not path or not folder_type:
        return {"status": "error", "message": "path and folder_type required"}
    
    ft_path = os.path.join(os.path.dirname(__file__), "folder_types.json")
    import json
    data = {}
    if os.path.exists(ft_path):
        with open(ft_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[path] = folder_type
    with open(ft_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"status": "ok"}

@app.post("/library/category-tag")
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

@app.post("/library/clean-name")
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

@app.get("/library/tree")
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
        # 文件夹级影子名：从 NFO 的 title + english_title 生成
        node["shadow_name"] = ""
        if node["path"] and node["path"] != base_path and not (node in root_node["children"] and node["children"]):
            try:
                # season/tv 文件夹不 fallback 到视频 NFO
                _no_fb = node.get("folder_type") in ("tv", "season") or category_tag == "tv"
                nfo = scraper.read_nfo(node["path"], no_fallback=_no_fb)
                if nfo and nfo.get("title"):
                    sn = nfo["title"]
                    en = nfo.get("english_title") or ""
                    orig = nfo.get("original_title") or ""
                    if not en and orig and orig != sn:
                        # 检查 original_title 是否为拉丁文
                        latin = sum(1 for c in orig if c.isascii() and c.isalpha())
                        total = sum(1 for c in orig if c.isalpha())
                        if total > 0 and latin / total > 0.5:
                            en = orig
                    if en and en != sn:
                        sn = f"{sn} {en}"
                    yr = nfo.get("year", "")
                    if yr:
                        sn = f"{sn} ({yr})"
                    node["shadow_name"] = sn
            except Exception:
                pass
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

@app.get("/movie/poster")
def get_movie_poster(name: str):
    """从 TMDB 获取电影海报并缓存到本地"""
    cache_dir = os.path.join(os.getcwd(), "posters")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    safe_name = "".join(x for x in name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(cache_dir, f"{safe_name}.jpg")
    
    if os.path.exists(cache_path):
        return FileResponse(cache_path)
        
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=404, detail="TMDB API Key not configured")

    try:
        # 先清洗文件名：去掉扩展名、质量标签、字幕组等杂质
        import re
        clean = name
        clean = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', clean)  # 去扩展名
        clean = re.sub(r'(?i)(BD|HD|4K|1080[pi]?|720[pi]?|2160[pi]?|REMUX|BluRay|WEB-?DL|DVDRip|BDRip|x264|x265|HEVC|AAC|DTS|FLAC|10bit)', '', clean)
        clean = re.sub(r'(?i)(日语|中字|中文|英文|双语|国语|粤语|字幕|简体|繁体|简繁|内嵌|外挂|特效)', '', clean)
        clean = re.sub(r'\[.*?\]', '', clean)  # 去方括号标签
        clean = re.sub(r'[._\-]+', ' ', clean).strip()
        clean = clean.strip() or name

        search_url = f"https://api.themoviedb.org/3/search/movie"
        params = {"api_key": api_key, "query": clean, "language": "zh-CN"}
        resp = requests.get(search_url, params=params, timeout=5)
        results = resp.json().get("results", [])
        
        if not results:
            search_url = f"https://api.themoviedb.org/3/search/tv"
            resp = requests.get(search_url, params=params, timeout=5)
            results = resp.json().get("results", [])

        if not results:
            raise HTTPException(status_code=404, detail="Not found")

        poster_path = results[0].get("poster_path")
        if not poster_path:
            raise HTTPException(status_code=404, detail="No poster path")
            
        img_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        img_resp = requests.get(img_url, stream=True, timeout=10)
        with open(cache_path, "wb") as f:
            shutil.copyfileobj(img_resp.raw, f)
            
        return FileResponse(cache_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/search")
def search_resources(
    query: str,
    enhanced: bool = True,
    media_type: str = "",
    year: str = "",
    shadow_name: str = "",
    clean_name: str = "",
    season: int = 0,
    total_episodes: int = 0,
):
    """搜索资源。增强搜索：回退链 + 二次匹配 + 全局过滤 + 综合排序。

    参数:
        query: 搜索关键词（TMDB 中文标题）
        media_type: "movie" / "tv" / "anime"
        year: 年份
        shadow_name: 影子名（回退链最高优先级）
        clean_name: 清洗名（回退链第二优先级）
        season: 季号（tv 类型时触发剧集搜索策略，暂预留）
        total_episodes: 总集数（tv 类型时用于整季包验证，暂预留）
    """
    clients = get_clients()
    conf = config_m.config

    # 构建全局过滤器
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        resolver = AliasResolver(douban_client, bangumi_client)
        aliases = resolver.resolve(query, "", media_type)  # 不传年份
        indexer_m.load()

        resp = searcher.enhanced_search(
            client=clients["search"],
            title=query,
            aliases=aliases,
            year="",  # 不传年份
            media_type=media_type,
            indexer_manager=indexer_m,
            shadow_name=shadow_name,
            clean_name=clean_name,
            global_filter=gf,
        )
        return {
            "query": query,
            "bt_count": len(resp.results),
            "bt_results": [r.dict() for r in resp.results],
            "hit_keyword": resp.hit_keyword,
            "total_raw": resp.total_raw,
            "total_filtered": resp.total_filtered,
            "enhanced": True,
        }
    except Exception as e:
        print(f"[Search] Enhanced search failed, fallback: {e}")

    # fallback 到普通搜索（不经过回退链和过滤）
    bt_results = clients["search"].search(query)
    return {
        "query": query,
        "bt_count": len(bt_results),
        "bt_results": [r.dict() for r in bt_results],
        "hit_keyword": query,
        "total_raw": len(bt_results),
        "total_filtered": len(bt_results),
        "enhanced": False,
    }

@app.get("/search/pan")
def search_pan(keyword: str, media_type: str = ""):
    """网盘搜索聚合接口。"""
    try:
        service = _get_pan_search_service()
        response = service.search_sync(keyword, media_type=media_type)
        return response.dict()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"results": [], "groups": {}, "source_statuses": [{"name": "error", "status": "failed", "count": 0, "error": str(e)}], "total": 0}

@app.get("/alist/mounts")
def get_alist_mounts():
    """获取 Alist 已挂载网盘列表。"""
    try:
        clients = get_clients()
        alist = clients.get("alist")
        if not alist:
            return {"mounts": [], "error": "Alist 未配置"}
        mounts = alist.get_mounts_list()
        return {"mounts": [m.dict() for m in mounts]}
    except Exception as e:
        return {"mounts": [], "error": str(e)}

@app.post("/alist/transfer")
def transfer_pan_resource(req: dict):
    """网盘资源转存接口。
    夸克链接 → 调用夸克转存 API 自动保存到自己的夸克网盘。
    其他网盘 → 返回提示让用户手动保存。
    """
    try:
        share_url = req.get("share_url", "")
        pan_type = req.get("pan_type", "")
        passcode = req.get("password", "")

        if not share_url:
            return {"success": False, "error_code": "missing_url", "error_message": "缺少分享链接"}

        # 夸克链接 → 自动转存
        if pan_type == "quark":
            from quark_transfer import QuarkTransfer
            conf = config_m.config
            qt = QuarkTransfer.from_alist(conf.alist_url, conf.alist_token)
            if not qt:
                return {"success": False, "error_code": "no_cookie", "error_message": "无法获取夸克 Cookie，请检查 Alist 夸克存储配置"}
            result = qt.transfer(share_url, passcode)
            return result

        # 其他网盘 → 暂不支持自动转存
        return {"success": False, "error_code": "unsupported",
                "error_message": f"{pan_type} 暂不支持自动转存，请手动打开链接保存"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error_code": "server_error", "error_message": str(e)}

@app.get("/search/single")
def search_single_keyword(
    keyword: str,
    media_type: str = "",
    skip_filter: bool = False,
):
    """单关键词搜索。

    skip_filter=False（默认）：含二次匹配+全局过滤（不含年份匹配）
    skip_filter=True：Prowlarr 裸搜，不做任何过滤
    """
    clients = get_clients()

    # 搜索 Prowlarr
    try:
        raw_results = clients["search"].search(keyword)
    except Exception as e:
        print(f"[Search/Single] Prowlarr error: {e}")
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    total_raw = len(raw_results)
    if not raw_results:
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    # 去重
    seen = set()
    deduped = []
    for r in raw_results:
        if r.download_url and r.download_url not in seen:
            seen.add(r.download_url)
            deduped.append(r)

    # 裸搜模式：跳过所有过滤
    if skip_filter:
        return {
            "keyword": keyword,
            "bt_count": len(deduped),
            "bt_results": [r.dict() for r in deduped],
            "total_raw": total_raw,
            "total_filtered": len(deduped),
        }

    # 智能过滤模式
    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        from secondary_matcher import SecondaryMatcher

        # 二次匹配（仅标题匹配，不含年份）
        if media_type:
            resolver = AliasResolver(douban_client, bangumi_client)
            aliases = resolver.resolve(keyword, "", media_type)
            target_titles = [keyword]
            if aliases:
                target_titles.extend(aliases.cn_names or [])
                target_titles.extend(aliases.en_names or [])
            target_titles = list(dict.fromkeys(t for t in target_titles if t))

            matcher = SecondaryMatcher()
            passed = matcher.batch_filter(
                bt_titles=[r.title for r in deduped],
                target_titles=target_titles,
                target_year="",
                media_type=media_type,
            )
            deduped = [deduped[i] for i in passed]

        # 全局过滤
        if deduped:
            filter_passed = gf.apply([r.title for r in deduped])
            deduped = [deduped[i] for i in filter_passed]

        return {
            "keyword": keyword,
            "bt_count": len(deduped),
            "bt_results": [r.dict() for r in deduped],
            "total_raw": total_raw,
            "total_filtered": len(deduped),
        }
    except Exception as e:
        print(f"[Search/Single] error: {e}")
        # fallback 到裸搜
        raw = clients["search"].search(keyword)
        return {"keyword": keyword, "bt_count": len(raw), "bt_results": [r.dict() for r in raw], "total_raw": len(raw), "total_filtered": len(raw)}

@app.get("/config")
def get_config():
    return config_m.config

@app.get("/cache/info")
def cache_info():
    """获取缓存目录大小和文件数"""
    cache_dir = "scrape_cache"
    if not os.path.exists(cache_dir):
        return {"size_mb": 0, "file_count": 0}
    total_size = 0
    file_count = 0
    for f in os.listdir(cache_dir):
        fp = os.path.join(cache_dir, f)
        if os.path.isfile(fp):
            total_size += os.path.getsize(fp)
            file_count += 1
    return {"size_mb": round(total_size / (1024 * 1024), 2), "file_count": file_count}

@app.post("/cache/clear")
def cache_clear():
    """清空缓存目录"""
    cache_dir = "scrape_cache"
    if not os.path.exists(cache_dir):
        return {"cleared": 0}
    count = 0
    for f in os.listdir(cache_dir):
        fp = os.path.join(cache_dir, f)
        if os.path.isfile(fp):
            try:
                os.remove(fp)
                count += 1
            except:
                pass
    return {"cleared": count}

@app.get("/no-scrape")
def get_no_scrape():
    return list(config_m.load_no_scrape())

@app.post("/no-scrape")
def set_no_scrape(path: str, enabled: bool = True):
    config_m.set_no_scrape(path, enabled)
    # 递归：对目录下所有子目录也设置
    if os.path.isdir(path):
        for dirpath, dirnames, _ in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for d in dirnames:
                config_m.set_no_scrape(os.path.join(dirpath, d), enabled)
    return {"status": "ok", "path": path, "no_scrape": enabled}

@app.post("/config")
def update_config(conf: config_manager.AppConfig):
    config_m.save(conf)
    return {"message": "Success"}

# ── 搜索过滤规则配置 API ──

@app.get("/config/search-filter")
def get_search_filter():
    """获取当前搜索过滤规则配置"""
    conf = config_m.config
    return {
        "must_include": conf.search_filter.must_include,
        "must_exclude": conf.search_filter.must_exclude,
        "preferred_codec": conf.preferred_codec,
        "download_channel_auto": conf.download_channel_auto,
        "recycle_bin_path": conf.recycle_bin_path,
        "recycle_bin_retention_days": conf.recycle_bin_retention_days,
    }

class SearchFilterUpdateRequest(BaseModel):
    must_include: Optional[List[str]] = None
    must_exclude: Optional[List[str]] = None
    preferred_codec: Optional[str] = None
    download_channel_auto: Optional[bool] = None
    recycle_bin_path: Optional[str] = None
    recycle_bin_retention_days: Optional[int] = None

@app.post("/config/search-filter")
def save_search_filter(req: SearchFilterUpdateRequest):
    """保存搜索过滤规则配置（增量更新，只更新传入的字段）"""
    conf = config_m.config
    if req.must_include is not None:
        conf.search_filter.must_include = req.must_include
    if req.must_exclude is not None:
        conf.search_filter.must_exclude = req.must_exclude
    if req.preferred_codec is not None:
        conf.preferred_codec = req.preferred_codec
    if req.download_channel_auto is not None:
        conf.download_channel_auto = req.download_channel_auto
    if req.recycle_bin_path is not None:
        conf.recycle_bin_path = req.recycle_bin_path
    if req.recycle_bin_retention_days is not None:
        conf.recycle_bin_retention_days = req.recycle_bin_retention_days
    config_m.save(conf)
    return {"message": "Success"}

@app.post("/backup")
def create_backup():
    """备份所有配置和媒体库数据"""
    import zipfile
    from io import BytesIO
    from datetime import datetime
    
    buf = BytesIO()
    files_to_backup = ["config.json", "media_library.json", "no_scrape.json", "excluded_paths.json"]
    
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in files_to_backup:
            if os.path.exists(fname):
                zf.write(fname)
    
    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from fastapi.responses import Response
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=nas_media_backup_{ts}.zip"}
    )

@app.post("/restore")
async def restore_backup(file: UploadFile = File(...)):
    """从备份 zip 恢复配置"""
    import zipfile
    from io import BytesIO
    
    content = await file.read()
    buf = BytesIO(content)
    
    allowed = {"config.json", "media_library.json", "no_scrape.json", "excluded_paths.json"}
    restored = []
    
    with zipfile.ZipFile(buf, 'r') as zf:
        for name in zf.namelist():
            if name in allowed:
                zf.extract(name, ".")
                restored.append(name)
    
    # 重新加载配置
    config_m._config = config_m.load()
    
    return {"status": "ok", "restored": restored}

class DownloadRequest(BaseModel):
    url: str
    save_path: str
    download_type: str = "qb"  # "qb" | "alist"

@app.post("/download")
def trigger_download(req: DownloadRequest):
    conf = config_m.config
    if req.download_type == "qb":
        if not conf.qb_url:
            return {"success": False, "message": "qBittorrent 未配置"}
        clients = get_clients()
        success = clients["qb"].add_torrent(req.url, req.save_path)
    elif req.download_type == "alist":
        if not conf.alist_url or not conf.alist_token:
            return {"success": False, "message": "Alist 未配置"}
        clients = get_clients()
        success = clients["alist"].transfer_link(req.url, req.save_path)
    else:
        return {"success": False, "message": f"不支持的下载类型: {req.download_type}"}
    return {"success": success, "message": "任务已下达" if success else "执行异常"}

# ── 批量搜索升级 ──

class BatchSearchItem(BaseModel):
    name: str
    path: str
    current_resolution: str = ""

class BatchSearchRequest(BaseModel):
    items: List[BatchSearchItem]

def _select_best_match(results: list):
    """从搜索结果中选择做种数 > 0 且 quality_rank 最高的结果"""
    candidates = [r for r in results if r.seeders > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.quality_rank)

@app.post("/batch-search")
async def batch_search(req: BatchSearchRequest):
    """EventSource 流式返回批量搜索进度"""
    clients = get_clients()
    total = len(req.items)

    async def event_gen():
        found = 0
        not_found = 0
        for i, item in enumerate(req.items):
            # 发送 searching 进度
            yield "data: " + json.dumps({
                "type": "progress", "index": i, "total": total,
                "name": item.name, "status": "searching"
            }, ensure_ascii=False) + "\n\n"

            try:
                results = clients["search"].search(item.name)
                best = _select_best_match(results)
                if best:
                    found += 1
                else:
                    not_found += 1
                yield "data: " + json.dumps({
                    "type": "result", "index": i, "name": item.name,
                    "best_match": best.dict() if best else None,
                    "all_results": [r.dict() for r in results]
                }, ensure_ascii=False) + "\n\n"
            except Exception as e:
                not_found += 1
                yield "data: " + json.dumps({
                    "type": "result", "index": i, "name": item.name,
                    "best_match": None, "all_results": [],
                    "error": str(e)
                }, ensure_ascii=False) + "\n\n"

            # 间隔 2 秒避免 API 限流（最后一个不等待）
            if i < total - 1:
                await asyncio.sleep(2)

        yield "data: " + json.dumps({
            "type": "done", "found": found, "not_found": not_found
        }, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

class BatchDownloadTask(BaseModel):
    download_url: str
    save_path: str
    download_type: str = "qb"

class BatchDownloadRequest(BaseModel):
    tasks: List[BatchDownloadTask]

@app.post("/batch-download")
def batch_download(req: BatchDownloadRequest):
    """批量推送下载任务"""
    conf = config_m.config
    clients = get_clients()
    results = []
    for i, task in enumerate(req.tasks):
        try:
            if task.download_type == "qb":
                if not conf.qb_url:
                    results.append({"index": i, "success": False, "message": "qBittorrent 未配置"})
                    continue
                success = clients["qb"].add_torrent(task.download_url, task.save_path)
            elif task.download_type == "alist":
                if not conf.alist_url or not conf.alist_token:
                    results.append({"index": i, "success": False, "message": "Alist 未配置"})
                    continue
                success = clients["alist"].transfer_link(task.download_url, task.save_path)
            else:
                results.append({"index": i, "success": False, "message": f"不支持的下载类型: {task.download_type}"})
                continue
            results.append({"index": i, "success": success, "message": "任务已下达" if success else "执行异常"})
        except Exception as e:
            results.append({"index": i, "success": False, "message": str(e)})
    return {"results": results}

# ── 下载管理 API ──

class DownloadSubmitRequest(BaseModel):
    media_name: str
    download_url: str
    save_path: str
    channel: str = "qb"
    category_hint: str = ""
    is_season_pack: bool = False
    season_number: int = 0

@app.post("/download-manager/submit")
def submit_download(req: DownloadSubmitRequest):
    """提交下载任务到 DownloadManager 队列。自动检查黑名单。"""
    # 黑名单检查
    if torrent_bl.is_blocked(req.download_url):
        return {"success": False, "error": "该种子在黑名单中（24h 内曾提交失败），请稍后重试或手动移除黑名单"}

    dm = _get_download_manager()
    task = DownloadTask(
        media_name=req.media_name,
        download_url=req.download_url,
        save_path=req.save_path,
        channel=req.channel,
        category_hint=req.category_hint,
        is_season_pack=req.is_season_pack,
        season_number=req.season_number,
    )
    result = dm.submit(task)

    # 提交失败自动加入黑名单
    if result.status == "failed":
        torrent_bl.add(req.download_url, reason=result.error or "submit failed")

    return {"success": result.status != "failed", "task": result.dict()}

@app.get("/download-manager/tasks")
def get_download_tasks(status: str = ""):
    """查询下载任务列表，支持按状态过滤。"""
    dm = _get_download_manager()
    tasks = dm.get_tasks(status=status if status else None)
    return {"tasks": [t.dict() for t in tasks]}

@app.get("/download-manager/progress")
def get_download_progress():
    """获取所有活跃任务的进度信息。"""
    dm = _get_download_manager()
    # 先同步一次进度
    dm.sync_progress()
    active = dm.get_tasks(status="downloading")
    return {"tasks": [t.dict() for t in active]}

@app.post("/download-manager/sync")
def sync_download_progress():
    """手动触发一次进度同步。"""
    dm = _get_download_manager()
    dm.sync_progress()
    return {"message": "ok"}

@app.post("/download-manager/sync-from-qb")
def sync_from_qb():
    """从 qBittorrent 全量同步：
    1. 把'推送失败'但实际在 qB 里的任务状态更新为 downloading
    2. 把 qB 里有但 download_tasks.json 里没有的种子导入为新任务
    3. 更新所有 downloading 任务的进度
    """
    dm = _get_download_manager()
    clients = get_clients()
    qb = clients.get("qb")
    if not qb:
        return {"updated": 0, "imported": 0, "error": "qBittorrent 未配置"}

    try:
        if not qb._login():
            return {"updated": 0, "imported": 0, "error": "qBittorrent 登录失败"}
        r = qb.session.get(f"{qb.url}/api/v2/torrents/info", timeout=10)
        if r.status_code != 200:
            return {"updated": 0, "imported": 0, "error": f"qB API 返回 {r.status_code}"}

        qb_torrents = r.json()
        qb_hash_map = {t.get("hash", ""): t for t in qb_torrents}
        qb_hashes = set(qb_hash_map.keys())

        # 已有任务的 hash 集合
        existing_hashes = {t.downloader_hash for t in dm.tasks if t.downloader_hash}

        updated = 0
        imported = 0

        with dm._lock:
            # 1. 更新已有任务的状态
            for task in dm.tasks:
                if task.status in ("failed", "unknown", "lost") and "推送失败" in (task.error or ""):
                    # 尝试通过名字匹配
                    name_lower = task.media_name.lower()
                    for qb_hash, qt in qb_hash_map.items():
                        qb_name = qt.get("name", "").lower()
                        if name_lower in qb_name or qb_name in name_lower:
                            task.status = "downloading"
                            task.downloader_hash = qb_hash
                            task.error = ""
                            updated += 1
                            break

                # 2. 更新 downloading 任务的进度
                if task.status == "downloading" and task.downloader_hash in qb_hash_map:
                    qt = qb_hash_map[task.downloader_hash]
                    task.progress = round(qt.get("progress", 0), 4)
                    dl_speed = qt.get("dlspeed", 0)
                    task.speed = f"{dl_speed/1024/1024:.1f} MB/s" if dl_speed >= 1024*1024 else (f"{dl_speed/1024:.0f} KB/s" if dl_speed > 0 else "")
                    eta = qt.get("eta", 0)
                    if eta and eta < 8640000:
                        h2, rem = divmod(int(eta), 3600)
                        m, s = divmod(rem, 60)
                        task.eta = f"{h2:02d}:{m:02d}:{s:02d}"
                    qb_state = qt.get("state", "")
                    if task.progress >= 1.0 or qb_state in ("uploading", "stalledUP", "pausedUP", "forcedUP", "queuedUP", "stoppedUP"):
                        task.status = "completed"
                        task.progress = 1.0
                        task.speed = ""
                        task.eta = ""
                    elif qb_state in ("pausedDL", "stoppedDL"):
                        task.status = "downloading"  # 暂停中，保持 downloading 状态（前端可显示暂停图标）
                        task.speed = "已暂停"
                        task.eta = ""
                    elif qb_state in ("error", "missingFiles"):
                        task.status = "failed"
                        task.error = f"qB 状态: {qb_state}"
                    updated += 1

            # 3. 导入 qB 里有但 download_tasks.json 里没有的所有种子
            from download_manager import DownloadTask
            import datetime

            # qB state → 我们的 status 映射
            QB_STATE_MAP = {
                "downloading": "downloading", "stalledDL": "downloading",
                "metaDL": "downloading", "checkingDL": "downloading", "forcedDL": "downloading",
                "uploading": "completed", "stalledUP": "completed",
                "pausedUP": "completed", "forcedUP": "completed", "stoppedUP": "completed",
                "queuedUP": "completed",
                "pausedDL": "downloading",  # 暂停中，但还是下载任务
                "stoppedDL": "downloading",
                "error": "failed", "missingFiles": "failed",
                "checkingUP": "completed", "checkingResumeData": "downloading",
                "moving": "downloading", "unknown": "unknown",
            }

            for qb_hash, qt in qb_hash_map.items():
                if qb_hash in existing_hashes:
                    continue
                qb_state = qt.get("state", "unknown")
                our_status = QB_STATE_MAP.get(qb_state, "downloading")
                name = qt.get("name", "")
                save_path = qt.get("save_path", "")
                progress = round(qt.get("progress", 0), 4)
                dl_speed = qt.get("dlspeed", 0)
                speed = f"{dl_speed/1024/1024:.1f} MB/s" if dl_speed >= 1024*1024 else (f"{dl_speed/1024:.0f} KB/s" if dl_speed > 0 else "")
                eta_secs = qt.get("eta", 0)
                eta = ""
                if eta_secs and eta_secs < 8640000:
                    h2, rem = divmod(int(eta_secs), 3600)
                    m, s = divmod(rem, 60)
                    eta = f"{h2:02d}:{m:02d}:{s:02d}"
                new_task = DownloadTask(
                    id=f"qb_import_{qb_hash[:8]}",
                    media_name=name,
                    download_url="",
                    save_path=save_path,
                    channel="qb",
                    downloader_hash=qb_hash,
                    status=our_status,
                    progress=progress,
                    speed=speed,
                    eta=eta,
                    created_at=datetime.datetime.now().isoformat(),
                    updated_at=datetime.datetime.now().isoformat(),
                )
                dm.tasks.append(new_task)
                imported += 1

        if updated or imported:
            dm._save_now()

        return {"updated": updated, "imported": imported, "qb_torrents": len(qb_torrents)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"updated": 0, "imported": 0, "error": str(e)}

@app.delete("/download-manager/task")
def delete_download_task(task_id: str):
    """删除单个下载任务记录。"""
    dm = _get_download_manager()
    ok = dm.delete_task(task_id)
    return {"success": ok}

@app.post("/download-manager/delete-tasks")
def delete_download_tasks(task_ids: List[str]):
    """批量删除下载任务记录。"""
    dm = _get_download_manager()
    removed = dm.delete_tasks(task_ids)
    return {"removed": removed}

@app.get("/download-manager/recommend-channel")
def recommend_download_channel(seeders: int = 0, size_gb: float = 0):
    """推荐下载通道。"""
    dm = _get_download_manager()
    channel = dm.recommend_channel(seeders, size_gb)
    return {"channel": channel}

# ── 归位与替换 API ──

class ConfirmReplaceRequest(BaseModel):
    task_id: str
    action_plan: Optional[dict] = None

@app.post("/download-manager/confirm-replace")
def confirm_replace(req: ConfirmReplaceRequest):
    """确认替换：旧文件入回收站 → V3 落盘。"""
    dm = _get_download_manager()
    fr = _get_file_relocator()
    task = dm.get_task(req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    plan = req.action_plan or {}
    result = fr.confirm_replace(task, plan)

    if result.success:
        dm.update_status(req.task_id, "archived")
    else:
        dm.update_status(req.task_id, "failed", result.error)

    return result.dict()

@app.post("/download-manager/cancel-replace")
def cancel_replace(task_id: str):
    """取消替换：新文件入回收站。"""
    dm = _get_download_manager()
    fr = _get_file_relocator()
    task = dm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = fr.cancel_replace(task)
    dm.update_status(task_id, "cancelled")
    return result.dict()

# ── 回收站 API ──

@app.get("/recycle-bin")
def list_recycle_bin():
    """列出回收站所有文件。"""
    rb = _get_recycle_bin()
    return {"entries": [e.dict() for e in rb.list_entries()]}

@app.post("/recycle-bin/restore")
def restore_from_bin(entry_id: str):
    """从回收站恢复文件到原始路径。"""
    rb = _get_recycle_bin()
    ok = rb.restore(entry_id)
    if not ok:
        raise HTTPException(status_code=400, detail="恢复失败：文件不存在或原始路径已被占用")
    return {"success": True}

@app.post("/recycle-bin/cleanup")
def cleanup_recycle_bin():
    """手动触发过期清理。"""
    rb = _get_recycle_bin()
    cleaned = rb.cleanup_expired()
    return {"cleaned": cleaned}

# ── 批量管理 ──

class BatchRequest(BaseModel):
    action: str  # "delete" | "move" | "copy" | "remove"
    paths: List[str]
    target_dir: Optional[str] = None

@app.post("/batch_manage")
def batch_manage(req: BatchRequest):
    success = []
    failed = []
    
    if req.action == "delete":
        for p in req.paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "File not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
        # 同步从媒体库中移除
        library = config_m.load_library()
        deleted_set = set(success)
        library = [v for v in library if v.get("file_path") not in deleted_set]
        config_m.save_library(library)
    
    elif req.action == "move":
        if not req.target_dir:
            raise HTTPException(status_code=400, detail="target_dir required")
        os.makedirs(req.target_dir, exist_ok=True)
        path_map = {}  # old_path → new_path
        for p in req.paths:
            try:
                if os.path.exists(p):
                    new_path = os.path.join(req.target_dir, os.path.basename(p))
                    # 同步移动关联文件（NFO/poster/fanart）
                    if os.path.isfile(p):
                        old_base = os.path.splitext(p)[0]
                        new_base = os.path.splitext(new_path)[0]
                        for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                            old_f = old_base + suffix
                            if os.path.exists(old_f):
                                try:
                                    shutil.move(old_f, os.path.join(req.target_dir, os.path.basename(old_f)))
                                except Exception:
                                    pass
                    shutil.move(p, new_path)
                    path_map[p] = new_path
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "File not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
        # 更新 media_library.json 中的路径
        if path_map:
            library = config_m.load_library()
            base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
            for v in library:
                fp = v.get("file_path", "")
                if fp in path_map:
                    v["file_path"] = path_map[fp]
                    v["file_name"] = os.path.basename(path_map[fp])
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
            config_m.save_library(library)
    
    elif req.action == "copy":
        if not req.target_dir:
            raise HTTPException(status_code=400, detail="target_dir required")
        os.makedirs(req.target_dir, exist_ok=True)
        for p in req.paths:
            try:
                if os.path.exists(p):
                    dest = os.path.join(req.target_dir, os.path.basename(p))
                    if os.path.isdir(p):
                        shutil.copytree(p, dest)
                    else:
                        shutil.copy2(p, dest)
                    success.append(p)
                else:
                    failed.append({"path": p, "error": "Not found"})
            except Exception as e:
                failed.append({"path": p, "error": str(e)})
    
    elif req.action == "remove":
        # 从媒体库中移除（不删除文件），并记录到排除列表防止同步拉回
        library = config_m.load_library()
        remove_set = set(req.paths)
        # 收集要排除的文件夹路径（去重）
        excluded_folders = set()
        for v in library:
            fp = v.get("file_path", "")
            if fp in remove_set:
                folder = os.path.dirname(fp)
                excluded_folders.add(folder)
        library = [v for v in library if v.get("file_path") not in remove_set]
        config_m.save_library(library)
        # 保存排除列表
        config_m.add_excluded_paths(list(remove_set | excluded_folders))
        success = req.paths
    
    return {"success": success, "failed": failed}

@app.get("/ai/suggest")
def get_ai_suggestions():
    videos = config_m.load_library()
    suggestions = ai_organizer.organize_by_ai(config_m.config.dict(), videos)
    return suggestions

@app.post("/ai/execute")
def execute_ai_suggestions(suggestions: List[Dict]):
    ops = []
    success = []
    failed = []
    for s in suggestions:
        old_p = s.get("original_path")
        new_rel = s.get("suggested_rel_path")
        if not old_p or not new_rel: continue
        base_dir = os.path.dirname(old_p)
        new_p = os.path.join(base_dir, new_rel)
        if os.path.exists(old_p):
            try:
                os.makedirs(os.path.dirname(new_p), exist_ok=True)
                shutil.move(old_p, new_p)
                ops.append({"old_path": old_p, "new_path": new_p})
                success.append(old_p)
            except Exception as e:
                failed.append({"path": old_p, "error": str(e)})
    if ops:
        history_m.create_snapshot(ops)
    return {"success": success, "failed": failed}

@app.get("/ai/history")
def get_ai_history():
    return history_m.list_snapshots()

@app.post("/ai/history/clear")
def clear_ai_history(keep_monthly: bool = True):
    """清空操作历史，keep_monthly=True 时每月保留最新一条"""
    return history_m.clear_all(keep_monthly)

@app.post("/ai/rollback")
def rollback_ai_history(snapshot_id: int):
    ok, res = history_m.rollback(snapshot_id)
    if not ok: raise HTTPException(status_code=404, detail=res)
    return res

@app.post("/organize/rollback")
def rollback_rename(snapshot_id: int):
    """回滚重命名操作，同时更新媒体库路径"""
    # 先读快照拿到 old/new 映射
    snapshot_path = os.path.join("organize_snapshots", f"snapshot_{snapshot_id}.json")
    if not os.path.exists(snapshot_path):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_data = json.load(f)
    
    ok, res = history_m.rollback(snapshot_id)
    if not ok:
        raise HTTPException(status_code=500, detail=str(res))
    
    # 更新媒体库：new_path → old_path
    lib = config_m.load_library()
    changed = False
    for op in snapshot_data.get("ops", []):
        old_p = op["old_path"]
        new_p = op["new_path"]
        # 文件路径直接替换
        for v in lib:
            fp = v.get("file_path", "")
            if fp == new_p:
                v["file_path"] = old_p
                v["file_name"] = os.path.basename(old_p)
                changed = True
            elif fp.startswith(new_p + os.sep) or fp.startswith(new_p + "/"):
                v["file_path"] = old_p + fp[len(new_p):]
                changed = True
    if changed:
        config_m.save_library(lib)
    
    return {"status": "ok", "result": res}

@app.get("/play")
def play_video(path: str):
    try:
        if os.path.exists(path):
            subprocess.Popen(['C:\\Program Files\\DAUM\\PotPlayer\\PotPlayerMini64.exe', path])
            return {"success": True}
        else:
            os.startfile(path)
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 影子名管理 API ──

class ShadowNameRequest(BaseModel):
    path: str
    shadow_name: str
    source: str = "manual"

@app.post("/media/shadow-name")
def set_shadow_name(req: ShadowNameRequest):
    """设置影子名"""
    shadow_m.set(req.path, req.shadow_name, source=req.source)
    return {"status": "ok", "path": req.path, "shadow_name": req.shadow_name, "source": req.source}

class ShadowNameDeleteRequest(BaseModel):
    path: str

@app.delete("/media/shadow-name")
def clear_shadow_name(req: ShadowNameDeleteRequest):
    """清除影子名"""
    shadow_m.clear(req.path)
    return {"status": "ok", "path": req.path}

@app.post("/media/shadow-name/batch")
def batch_generate_shadow_names():
    """批量生成影子名（NFO + TMDB 搜索）"""
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    stats = shadow_m.batch_generate(tmdb_client=client)
    return {"status": "ok", **stats}

# ── 索引器优先级管理 API ──

@app.get("/config/indexers")
def get_indexer_priorities():
    """获取索引器优先级列表，自动从 Prowlarr 同步已有索引器"""
    from indexer_priority_manager import IndexerConfig
    indexer_m.load()
    
    # 如果本地没有配置，从 Prowlarr 拉取索引器列表
    if not indexer_m.indexers:
        try:
            prowlarr_url = config_m.config.prowlarr_url.rstrip("/")
            prowlarr_key = config_m.config.prowlarr_api_key
            if prowlarr_url and prowlarr_key:
                import requests
                resp = requests.get(f"{prowlarr_url}/api/v1/indexer",
                                    params={"apikey": prowlarr_key}, timeout=5)
                resp.raise_for_status()
                prowlarr_indexers = resp.json()
                configs = []
                for idx in prowlarr_indexers:
                    if idx.get("enable", True):
                        name = idx.get("name", "")
                        # 根据名字猜测类型偏好
                        types = []
                        name_lower = name.lower()
                        if "nyaa" in name_lower:
                            types = ["anime"]
                        elif "yts" in name_lower:
                            types = ["movie"]
                        configs.append(IndexerConfig(
                            indexer_id=idx.get("id", 0),
                            name=name,
                            priority=50,
                            enabled=True,
                            preferred_types=types,
                            supports_chinese="chinese" in name_lower or "dmhy" in name_lower,
                        ))
                if configs:
                    indexer_m.save(configs)
                    indexer_m.indexers = configs
        except Exception as e:
            print(f"[Indexers] Failed to fetch from Prowlarr: {e}")
    
    return [
        {
            "indexer_id": idx.indexer_id,
            "name": idx.name,
            "priority": idx.priority,
            "enabled": idx.enabled,
            "preferred_types": idx.preferred_types,
            "supports_chinese": idx.supports_chinese,
        }
        for idx in indexer_m.indexers
    ]

class IndexerPriorityItem(BaseModel):
    indexer_id: int = 0
    name: str = ""
    priority: int = 50
    enabled: bool = True
    preferred_types: List[str] = []
    supports_chinese: bool = False

class IndexerPrioritySaveRequest(BaseModel):
    indexers: List[IndexerPriorityItem]

@app.post("/config/indexers")
def save_indexer_priorities(req: IndexerPrioritySaveRequest):
    """保存索引器优先级配置"""
    from indexer_priority_manager import IndexerConfig
    configs = [
        IndexerConfig(
            indexer_id=item.indexer_id,
            name=item.name,
            priority=item.priority,
            enabled=item.enabled,
            preferred_types=item.preferred_types,
            supports_chinese=item.supports_chinese,
        )
        for item in req.indexers
    ]
    indexer_m.save(configs)
    return {"status": "ok", "count": len(configs)}

# ── 刮削 API ──

@app.get("/scrape")
def scrape_by_name(name: str, path: str = "", enhanced: bool = False):
    """根据名字刮削，如果提供 path 则写入 NFO + 海报
    enhanced=True 时使用增强刮削流程，返回置信度信息"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if path and os.path.exists(path):
        if os.path.isdir(path):
            result = scraper.scrape_folder(path, client)
        else:
            result = scraper.scrape_video(path, client)
        return result
    
    # 增强刮削模式：使用影子名 + 别名 + 增强评分
    if enhanced:
        try:
            match_result = client.enhanced_scrape_by_filename(name, file_path=path or "")
            return {
                "status": "ok" if match_result.tmdb_id else "not_found",
                "data": match_result.item if match_result.item else {},
                "confidence": {
                    "level": match_result.confidence,
                    "score": match_result.score,
                    "details": match_result.match_details,
                },
                "tmdb_id": match_result.tmdb_id,
                "media_type": match_result.media_type,
            }
        except Exception as e:
            # 增强刮削失败时降级到普通刮削
            print(f"[Scrape] Enhanced scrape failed, fallback: {e}")
    
    # 普通刮削
    result = client.scrape_by_filename(name)
    return {"status": "ok" if result.tmdb_id else "not_found", "data": result.dict()}

@app.get("/scrape/candidates")
def scrape_candidates(name: str):
    """搜索 TMDB 返回多个候选结果供用户选择"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    # 优先用清洗后的名字搜索（任务 7）
    from analyzer import _clean_filename_for_folder
    clean = _clean_filename_for_folder(name)
    if clean and len(clean) >= 2:
        query = clean
    else:
        parsed = tmdb_client.parse_filename(name)
        query = parsed["clean_name"] or name
    search_query = query.replace("-", " ").replace("–", " ").replace("—", " ").strip()
    
    movies = client.search_movie(search_query)
    tvs = client.search_tv(search_query)
    
    def _is_latin(text):
        if not text: return False
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        total = sum(1 for c in text if c.isalpha())
        return total > 0 and latin / total > 0.5
    
    candidates = []
    for m in movies[:8]:
        orig = m.get("original_title", "")
        en_title = ""
        if orig and _is_latin(orig):
            en_title = orig
        else:
            try:
                en_title = client._get_english_title("movie", m["id"], orig) or ""
            except Exception:
                en_title = ""
        candidates.append({
            "tmdb_id": m["id"], "media_type": "movie",
            "title": m.get("title", ""), "original_title": orig,
            "english_title": en_title,
            "year": (m.get("release_date", "") or "")[:4],
            "overview": (m.get("overview", "") or "")[:120],
            "poster_url": f"https://image.tmdb.org/t/p/w200{m['poster_path']}" if m.get("poster_path") else None,
            "popularity": m.get("popularity", 0),
        })
    for t in tvs[:5]:
        orig = t.get("original_name", "")
        en_title = ""
        if orig and _is_latin(orig):
            en_title = orig
        else:
            try:
                en_title = client._get_english_title("tv", t["id"], orig) or ""
            except Exception:
                en_title = ""
        candidates.append({
            "tmdb_id": t["id"], "media_type": "tv",
            "title": t.get("name", ""), "original_title": orig,
            "english_title": en_title,
            "year": (t.get("first_air_date", "") or "")[:4],
            "overview": (t.get("overview", "") or "")[:120],
            "poster_url": f"https://image.tmdb.org/t/p/w200{t['poster_path']}" if t.get("poster_path") else None,
            "popularity": t.get("popularity", 0),
        })
    
    return {"query": query, "candidates": candidates}

@app.get("/scrape/douban")
def scrape_douban_candidates(name: str):
    """搜索豆瓣返回候选结果"""
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name
    results = douban_client.search(query)
    # 保留原始 URL 用于下载，代理 URL 用于前端显示
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    return {"query": query, "candidates": results}

@app.get("/proxy/image")
def proxy_image(url: str):
    """代理外部图片请求（绕过防盗链 + 走 HTTP 代理）"""
    try:
        headers = {"Referer": "https://movie.douban.com/", "User-Agent": "Mozilla/5.0"}
        proxies = None
        http_proxy = getattr(config_m.config, 'http_proxy', '') or ''
        if http_proxy:
            proxies = {"http": http_proxy, "https": http_proxy}
        resp = requests.get(url, headers=headers, stream=True, timeout=10, proxies=proxies)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        from fastapi.responses import Response
        return Response(content=resp.content, media_type=content_type)
    except Exception:
        raise HTTPException(status_code=404, detail="Image fetch failed")

@app.post("/scrape/douban-select")
def scrape_douban_select(path: str, douban_id: str, title: str = "", year: str = "", poster_url: str = "", subtitle: str = ""):
    """用户选择豆瓣候选后，用搜索结果数据写入 NFO + 海报"""
    from tmdb_client import ScrapeResult
    
    # 尝试拉取详情，失败则用搜索结果的基本信息
    detail = douban_client.get_detail(douban_id)
    if detail and detail.get("title"):
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type="movie",
            title=detail.get("title", "") or title,
            original_title=detail.get("original_title", "") or subtitle,
            year=detail.get("year", "") or year,
            overview=detail.get("overview", ""),
            rating=detail.get("rating", 0),
            genres=detail.get("genres", []),
            director=detail.get("director", ""),
            cast=detail.get("cast", []),
            runtime=detail.get("runtime", 0),
            poster_url=detail.get("poster_url", "") or poster_url,
        )
    else:
        # 详情解析失败，用搜索结果的基本信息
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type="movie",
            title=title,
            original_title=subtitle,
            year=year,
            poster_url=poster_url,
        )
    
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        scraper.write_movie_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url)
    elif os.path.isfile(path):
        scraper._write_movie_nfo_for_video(path, result)
        base = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.dirname(path)
        if result.poster_url:
            scraper.download_poster(folder, result.poster_url, base + "-poster.jpg")
    
    return {"status": "ok", "data": result.dict()}

@app.get("/scrape/bangumi")
def scrape_bangumi_candidates(name: str):
    """搜索 Bangumi 返回候选结果"""
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name
    results = bangumi_client.search(query)
    return {"query": query, "candidates": results}

@app.post("/scrape/bangumi-select")
def scrape_bangumi_select(path: str, bgm_id: int):
    """用户选择 Bangumi 候选后，拉取详情写入 NFO + 海报"""
    detail = bangumi_client.get_detail(bgm_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Bangumi detail not found")
    
    from tmdb_client import ScrapeResult
    result = ScrapeResult(
        tmdb_id=bgm_id,
        media_type="movie" if detail.get("total_episodes", 0) <= 1 else "tv",
        title=detail.get("title", ""),
        original_title=detail.get("original_title", ""),
        year=detail.get("year", ""),
        overview=detail.get("overview", ""),
        rating=detail.get("rating", 0),
        genres=detail.get("genres", []),
        director=detail.get("director", ""),
        cast=detail.get("cast", []),
        poster_url=detail.get("poster_url", ""),
    )
    
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        if result.media_type == "tv":
            scraper.write_tvshow_nfo(path, result)
        else:
            scraper.write_movie_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url)
    elif os.path.isfile(path):
        scraper._write_movie_nfo_for_video(path, result)
        base = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.dirname(path)
        if result.poster_url:
            scraper.download_poster(folder, result.poster_url, base + "-poster.jpg")
    
    return {"status": "ok", "data": result.dict()}

@app.post("/scrape/select")
def scrape_select(path: str, tmdb_id: int, media_type: str):
    """用户选择候选后，用指定 TMDB ID 执行刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if media_type == "movie":
        result = client.get_movie_detail(tmdb_id)
    elif media_type in ("tv", "tvshow"):
        result = client.get_tv_detail(tmdb_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid media_type")
    
    if not result.tmdb_id:
        raise HTTPException(status_code=404, detail="TMDB detail not found")
    
    # 写入 NFO + 海报（先清理旧的标准 NFO 避免冲突）
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        if result.media_type == "movie":
            scraper.write_movie_nfo(path, result)
        else:
            scraper.write_tvshow_nfo(path, result)
        proxy = getattr(config_m.config, 'http_proxy', '') or ''
        if result.poster_url:
            scraper.download_poster(path, result.poster_url, proxy=proxy)
        if result.backdrop_url:
            scraper.download_poster(path, result.backdrop_url, "fanart.jpg", proxy=proxy)
        
        # 单视频文件夹：同步影子名到 media_library.json
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(path)
            videos = [f for f in items if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subdirs = [f for f in items if os.path.isdir(os.path.join(path, f)) and not f.startswith('.')]
            if len(videos) == 1 and len(subdirs) == 0:
                vf = videos[0]
                vp = os.path.join(path, vf)
                # 写视频同名 NFO（给 Kodi/Emby 用）
                old_vnfo = os.path.splitext(vp)[0] + ".nfo"
                if os.path.exists(old_vnfo):
                    os.remove(old_vnfo)
                if result.media_type == "movie":
                    scraper._write_movie_nfo_for_video(vp, result)
                # 同步影子名
                library = config_m.load_library()
                for v in library:
                    if v.get("file_path") == vp:
                        en = result.english_title or ""
                        orig = result.original_title or ""
                        if not en and orig and orig != result.title:
                            latin = sum(1 for c in orig if c.isascii() and c.isalpha())
                            total = sum(1 for c in orig if c.isalpha())
                            if total > 0 and latin / total > 0.5:
                                en = orig
                        sn = result.title
                        if en and en != result.title:
                            sn += " " + en
                        if result.year:
                            sn += f" ({result.year})"
                        v["shadow_name"] = sn
                        v["shadow_name_source"] = "tmdb"
                        v["shadow_tmdb_id"] = result.tmdb_id
                        config_m.save_library(library)
                        break
        except OSError:
            pass
    elif os.path.isfile(path):
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        # 单视频文件夹：写到文件夹级别（和文件夹路径调用一致）
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            is_single_video_folder = len(vids) <= 1 and len(subs) == 0
        except OSError:
            is_single_video_folder = False
        
        if is_single_video_folder:
            # 清理旧 NFO 和旧封面（包括视频同名的）
            for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
                old_p = os.path.join(folder, old_nfo)
                if os.path.exists(old_p):
                    os.remove(old_p)
            # 清理旧封面
            for old_poster in ["poster.jpg", "poster.png", "fanart.jpg", "folder.jpg", "cover.jpg"]:
                old_p = os.path.join(folder, old_poster)
                if os.path.exists(old_p):
                    os.remove(old_p)
            try:
                for f in os.listdir(folder):
                    fl = f.lower()
                    if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg') or fl.endswith('-fanart.jpg'):
                        os.remove(os.path.join(folder, f))
            except OSError:
                pass
            if result.media_type == "movie":
                scraper.write_movie_nfo(folder, result)
            else:
                scraper.write_tvshow_nfo(folder, result)
            proxy = getattr(config_m.config, 'http_proxy', '') or ''
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, proxy=proxy)
            if result.backdrop_url:
                scraper.download_poster(folder, result.backdrop_url, "fanart.jpg", proxy=proxy)
            # 同步影子名
            library = config_m.load_library()
            for v in library:
                if v.get("file_path") == path:
                    en = result.english_title or ""
                    orig = result.original_title or ""
                    if not en and orig and orig != result.title:
                        latin = sum(1 for c in orig if c.isascii() and c.isalpha())
                        total = sum(1 for c in orig if c.isalpha())
                        if total > 0 and latin / total > 0.5:
                            en = orig
                    sn = result.title
                    if en and en != result.title:
                        sn += " " + en
                    if result.year:
                        sn += f" ({result.year})"
                    v["shadow_name"] = sn
                    v["shadow_name_source"] = "tmdb"
                    v["shadow_tmdb_id"] = result.tmdb_id
                    config_m.save_library(library)
                    break
        else:
            # 多视频文件夹中的单个视频：写视频级别
            if result.media_type == "movie":
                scraper._write_movie_nfo_for_video(path, result)
            else:
                scraper.write_episode_nfo(path, result)
            base = os.path.splitext(os.path.basename(path))[0]
            proxy = getattr(config_m.config, 'http_proxy', '') or ''
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, base + "-poster.jpg", proxy=proxy)
            if result.backdrop_url:
                scraper.download_poster(folder, result.backdrop_url, base + "-fanart.jpg", proxy=proxy)
    
    return {"status": "ok", "data": result.dict()}

@app.get("/scrape/read")
def read_scrape_data(path: str, no_fallback: bool = False):
    """读取文件夹或视频的已有刮削数据（NFO）
    no_fallback=True 时不 fallback 到子文件的 NFO（用于 tv/season 文件夹）"""
    if not os.path.exists(path):
        return {"status": "not_found", "data": None}
    
    if os.path.isdir(path):
        data = scraper.read_nfo(path, no_fallback=no_fallback)
        # 文件夹级 NFO 不存在且允许 fallback：尝试文件夹内视频同名 NFO
        if not data and not no_fallback:
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            try:
                for f in os.listdir(path):
                    if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in video_exts:
                        vdata = scraper.read_video_nfo(os.path.join(path, f))
                        if vdata:
                            data = vdata
                            break
            except OSError:
                pass
    else:
        # 先读视频同名 NFO，没有则 fallback 到文件夹级 NFO
        data = scraper.read_video_nfo(path)
        if not data:
            folder = os.path.dirname(path)
            data = scraper.read_nfo(folder)
    
    if data:
        return {"status": "ok", "data": data}
    return {"status": "not_found", "data": None}

@app.get("/scrape/poster")
def get_local_poster(path: str, cover: bool = False):
    """返回本地海报文件。cover=True 时只查找 cover.jpg（聚合容器独立封面）"""
    import re
    from fastapi.responses import Response

    def _poster_response(file_path: str):
        with open(file_path, "rb") as f:
            content = f.read()
        ext = os.path.splitext(file_path)[1].lower()
        mt = "image/png" if ext == ".png" else "image/jpeg"
        return Response(content=content, media_type=mt,
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # 聚合容器模式：只查找 cover.jpg/cover.png
    if cover:
        if os.path.isdir(path):
            for name in ["cover.jpg", "cover.png"]:
                p = os.path.join(path, name)
                if os.path.exists(p):
                    return _poster_response(p)
        raise HTTPException(status_code=404, detail="No cover found")

    if not os.path.isdir(path):
        # 视频文件：找同名 poster 或文件夹的 poster.jpg
        base = os.path.splitext(path)[0]
        for ext in ["-poster.jpg", "-poster.png", "-thumb.jpg"]:
            p = base + ext
            if os.path.exists(p):
                return _poster_response(p)
        # fallback 到文件夹的 poster.jpg
        folder = os.path.dirname(path)
        for name in ["poster.jpg", "poster.png"]:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                return _poster_response(p)
        raise HTTPException(status_code=404, detail="No poster found")
    
    # 文件夹（刮削单元）：poster.jpg 优先，cover.jpg 兜底
    for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
        p = os.path.join(path, name)
        if os.path.exists(p):
            return _poster_response(p)
    
    # season-poster（在 *-poster.jpg 之前检查，避免误读视频同名封面）
    folder_name = os.path.basename(path)
    season_match = re.search(r'(?:S(\d+)|第(\d+)季|Season\s*(\d+))', folder_name, re.I)
    if season_match:
        sn = season_match.group(1) or season_match.group(2) or season_match.group(3)
        for fmt in [f"season{sn.zfill(2)}-poster.jpg", f"season{sn}-poster.jpg"]:
            p = os.path.join(path, fmt)
            if os.path.exists(p):
                return _poster_response(p)
        # 季文件夹没有自己的封面：fallback 到父目录的 poster
        parent = os.path.dirname(path)
        if parent and os.path.isdir(parent):
            for name in ["poster.jpg", "poster.png"]:
                p = os.path.join(parent, name)
                if os.path.exists(p):
                    return _poster_response(p)
        # 季文件夹不 fallback 到 *-poster.jpg（那是集的封面）
        raise HTTPException(status_code=404, detail="No poster found")
    
    # 非季文件夹：找 *-poster.jpg（视频同名封面）
    try:
        for f in os.listdir(path):
            fl = f.lower()
            if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                return _poster_response(os.path.join(path, f))
    except OSError:
        pass
    
    raise HTTPException(status_code=404, detail="No poster found")

@app.post("/scrape/execute")
def execute_scrape(path: str, force: bool = True):
    """一键刮削 — 递归刮削指定路径及其所有子文件夹/子文件"""
    # 检查禁止刮削列表
    no_scrape = config_m.load_no_scrape()
    if path in no_scrape:
        return {"self": {"status": "no_scrape", "data": None}}
    
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if os.path.isdir(path):
        category_hint = _get_category_from_path(path)
        # 判断 folder_type
        ft = organizer.classify_folder(path, category_hint=category_hint).get("type", "")
        
        # tv 类型扁平目录：先强制季化再刮削
        if category_hint == "tv" and ft == "tv":
            reorg = organizer.reorganize_seasons(path, client, dry_run=False, category_hint=category_hint)
            if reorg.get("ops"):
                _sync_library_paths(reorg["ops"])
        
        # 递归刮削（max_depth=10 确保深层嵌套也能覆盖）
        result = scraper.scrape_folder(path, client, force=force, folder_type=ft, max_depth=10)
        # 刮削成功后：用刮削结果的 title 更新子视频的 clean_name
        _update_clean_names_after_scrape(path, result)
        return result
    elif os.path.isfile(path):
        # 单视频文件：用文件夹路径调 scrape_folder（写文件夹级 NFO + poster）
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            if len(vids) <= 1 and len(subs) == 0:
                result = scraper.scrape_folder(folder, client, force=force)
                _update_clean_names_after_scrape(folder, result)
                return result
        except OSError:
            pass
        return scraper.scrape_video(path, client, force=force)
    else:
        raise HTTPException(status_code=404, detail="Path not found")

@app.post("/scrape/batch")
def batch_scrape_api(paths: List[str]):
    """批量刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return scraper.batch_scrape(paths, client)


@app.post("/scrape/upload-poster")
async def upload_poster(path: str, file: UploadFile = File(...), cover: bool = False):
    """手动上传海报到指定文件夹。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    ext = os.path.splitext(file.filename or "poster.jpg")[1] or ".jpg"
    # 视频文件：写同名 poster
    if not os.path.isdir(path) and os.path.isfile(path):
        base = os.path.splitext(path)[0]
        target = base + f"-poster{ext}"
    else:
        filename = f"cover{ext}" if cover else f"poster{ext}"
        target = os.path.join(folder, filename)
    content = await file.read()
    with open(target, "wb") as f:
        f.write(content)
    return {"status": "ok", "path": target}

@app.post("/scrape/poster-url")
def set_poster_from_url(path: str, url: str, cover: bool = False):
    """通过 URL 拉取海报保存到本地。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    try:
        resp = requests.get(url, stream=True, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        
        if os.path.isdir(path):
            filename = f"cover{ext}" if cover else f"poster{ext}"
            target = os.path.join(path, filename)
        elif os.path.isfile(path):
            base = os.path.splitext(path)[0]
            target = base + f"-poster{ext}"
        else:
            raise HTTPException(status_code=404, detail="Path not found")
        
        with open(target, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return {"status": "ok", "path": target}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scrape/delete-poster")
def delete_poster(path: str):
    """删除本地海报 — 模拟 get_local_poster 的查找逻辑，找到实际显示的封面并删除"""
    deleted = []
    errors = []
    
    target_dir = path if os.path.isdir(path) else os.path.dirname(path)
    
    def _try_delete(filepath: str):
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                deleted.append(filepath)
                return True
            except Exception as e:
                errors.append(f"{filepath}: {e}")
        return False
    
    if os.path.isdir(target_dir):
        folder_name = os.path.basename(target_dir)
        
        # 1. 当前目录标准封面
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg", "folder.png", "cover.png"]:
            _try_delete(os.path.join(target_dir, name))
        
        # 2. 当前目录 *-poster.jpg/png
        try:
            for f in os.listdir(target_dir):
                fl = f.lower()
                if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                    _try_delete(os.path.join(target_dir, f))
        except OSError:
            pass
        
        # 3. 如果当前目录没删到任何封面，检查父目录（和 get_local_poster 的 fallback 一致）
        if not deleted:
            parent = os.path.dirname(target_dir)
            if parent and os.path.isdir(parent):
                for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
                    _try_delete(os.path.join(parent, name))
                try:
                    for f in os.listdir(parent):
                        fl = f.lower()
                        if fl.endswith('-poster.jpg') or fl.endswith('-poster.png'):
                            _try_delete(os.path.join(parent, f))
                except OSError:
                    pass
    
    # 文件路径：删同名封面
    if not os.path.isdir(path):
        base = os.path.splitext(path)[0]
        for suffix in ["-poster.jpg", "-poster.png", "-thumb.jpg", ".jpg"]:
            _try_delete(base + suffix)
    
    # 删 TMDB 缓存
    folder_name = os.path.basename(target_dir)
    safe_name = "".join(x for x in folder_name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(os.getcwd(), "posters", f"{safe_name}.jpg")
    _try_delete(cache_path)
    
    print(f"[DeletePoster] path={path} deleted={len(deleted)} errors={errors}")
    return {"status": "ok", "deleted": deleted, "errors": errors}

@app.post("/scrape/delete-scrape")
def delete_scrape(path: str, recursive: bool = False):
    """删除刮削数据（NFO + 封面）
    recursive=False（默认）：只删文件夹级别的刮削（movie.nfo/tvshow.nfo/poster.jpg等）
    recursive=True：同时删除视频同名的刮削文件
    """
    deleted = []
    print(f"[DeleteScrape] path={path} isdir={os.path.isdir(path)} recursive={recursive}")
    if os.path.isdir(path):
        # 文件夹级别刮削：删除标准文件
        for name in ["movie.nfo", "tvshow.nfo", "season.nfo", "poster.jpg", "poster.png",
                      "fanart.jpg", "folder.jpg", "cover.jpg", "folder.png", "cover.png", ".no-poster"]:
            p = os.path.join(path, name)
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
        # 始终删除 *-poster.jpg 等视频同名刮削文件（单视频文件夹里这些也是刮削产物）
        try:
            for f in os.listdir(path):
                fl = f.lower()
                if (fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or 
                    fl.endswith('-thumb.jpg') or fl.endswith('-fanart.jpg') or
                    fl.endswith('-clearlogo.png')):
                    p = os.path.join(path, f)
                    os.remove(p)
                    deleted.append(p)
        except OSError:
            pass
        # recursive 模式：也删视频同名 NFO 文件
        if recursive:
            try:
                for f in os.listdir(path):
                    fl = f.lower()
                    if fl.endswith('.nfo') and fl not in ('movie.nfo', 'tvshow.nfo', 'season.nfo'):
                        p = os.path.join(path, f)
                        os.remove(p)
                        deleted.append(p)
            except OSError:
                pass
    elif os.path.isfile(path):
        base = os.path.splitext(path)[0]
        for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
            p = base + suffix
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
        # 单视频文件夹：同时删除文件夹级刮削（movie.nfo/poster.jpg 等）
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            if len(vids) <= 1 and len(subs) == 0:
                for name in ["movie.nfo", "tvshow.nfo", "season.nfo", "poster.jpg", "poster.png",
                              "fanart.jpg", "folder.jpg", "cover.jpg", "folder.png", "cover.png", ".no-poster"]:
                    p = os.path.join(folder, name)
                    if os.path.exists(p):
                        os.remove(p)
                        deleted.append(p)
        except OSError:
            pass
    # 也清 TMDB 缓存
    name = os.path.basename(os.path.splitext(path)[0] if os.path.isfile(path) else path)
    safe_name = "".join(x for x in name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(os.getcwd(), "posters", f"{safe_name}.jpg")
    if os.path.exists(cache_path):
        os.remove(cache_path)
        deleted.append(cache_path)
    return {"status": "ok", "deleted": deleted}


# ── 整理 API ──

import organizer
import analyzer

@app.get("/analyze/folder")
def analyze_folder_api(path: str, enhanced: bool = False):
    """分析单个文件夹，返回完整诊断报告
    enhanced=True 时用 TMDB 增强改名预览
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_folder(path, library, client, category_hint=_get_category_from_path(path))

@app.get("/analyze/library")
def analyze_library_api(enhanced: bool = False):
    """分析整个媒体库"""
    config = config_m.config
    base_path = config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else ""
    if not base_path or not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail="NAS path not configured or not accessible")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_library(base_path, library, client)

@app.get("/organize/classify")
def classify_path(path: str):
    """判断文件夹类型"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    # 从路径推断一级分类名
    category_hint = _get_category_from_path(path)
    return organizer.classify_folder(path, library, category_hint=category_hint)


def _get_category_from_path(path: str) -> str:
    """从文件路径推断一级分类标签（movie/tv）。
    优先从 config.category_tags 查找，否则用目录名自动推断。
    """
    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
    if not base:
        return ""
    # 规范化路径
    norm_path = os.path.normpath(path)
    norm_base = os.path.normpath(base)
    if not norm_path.startswith(norm_base):
        return ""
    rel = os.path.relpath(norm_path, norm_base)
    # 取第一层目录名
    parts = rel.split(os.sep)
    if not parts or parts[0] == ".":
        return ""
    category_dir_name = parts[0]
    category_dir_path = os.path.join(base, category_dir_name)
    # 优先从配置查找
    configured_tags = config_m.config.category_tags or {}
    if category_dir_path in configured_tags:
        return configured_tags[category_dir_path]
    return organizer.infer_category_tag(category_dir_name)


def _is_top_category(path: str) -> bool:
    """判断 path 是否是 NAS 根目录的直接子目录（一级分类目录）"""
    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
    if not base:
        return False
    norm_path = os.path.normpath(path)
    norm_base = os.path.normpath(base)
    if not norm_path.startswith(norm_base):
        return False
    rel = os.path.relpath(norm_path, norm_base)
    parts = rel.split(os.sep)
    # 一级分类目录 = 相对路径只有一层
    return len(parts) == 1 and parts[0] != "."


def _sync_library_paths(ops: list):
    """整理操作后同步更新 media_library.json 中的文件路径"""
    library = config_m.load_library()
    changed = False
    for op in ops:
        if op.get("action") == "move" and op.get("old") and op.get("new"):
            for v in library:
                if v.get("file_path") == op["old"]:
                    v["file_path"] = op["new"]
                    # 更新 folder_name
                    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                    if base:
                        rel = os.path.relpath(os.path.dirname(op["new"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                    changed = True
    if changed:
        config_m.save_library(library)


def _update_clean_names_after_scrape(path: str, scrape_result: dict):
    """刮削成功后，用刮削结果更新 clean_name。
    剧名只取中文部分，集名格式为 中文名 SxxExx。
    """
    try:
        self_data = scrape_result.get("self", {}).get("data") or {}
        title = self_data.get("title", "")
        if not title:
            return
        
        from analyzer import _extract_chinese_name, clean_episode_name
        cn_title = _extract_chinese_name(title)
        
        library = config_m.load_library()
        changed = False
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        
        norm_path = os.path.normpath(path)
        for v in library:
            fp = v.get("file_path", "")
            fp_dir = os.path.normpath(os.path.dirname(fp))
            if fp_dir == norm_path or fp_dir.startswith(norm_path + os.sep):
                ext = os.path.splitext(fp)[1].lower()
                if ext in video_exts:
                    # 用新的清洗规则：中文剧名 + SxxExx
                    new_clean = clean_episode_name(v.get("file_name", ""), cn_title)
                    if new_clean:
                        v["clean_name"] = new_clean
                    else:
                        v["clean_name"] = cn_title
                    changed = True
        
        if changed:
            config_m.save_library(library)
    except Exception:
        pass


@app.post("/organize/rename")
def rename_videos(path: str, dry_run: bool = True, shadow_only: bool = False):
    """统一重命名
    支持文件夹和单个文件
    shadow_only=True 时不改文件名，只把标准名存到影子名中
    无论哪种模式，都会生成影子名"""
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    library = config_m.load_library()
    
    # 支持单个文件：取其父文件夹来处理（仅预览和影子名用）
    target_path = path
    single_file = False
    single_file_path = ""
    if not os.path.isdir(path):
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            target_path = parent
            single_file = True
            single_file_path = path
        else:
            raise HTTPException(status_code=404, detail="Path not found")
    
    result = organizer.rename_videos_in_folder(target_path, client, True, library, category_hint=_get_category_from_path(target_path))
    
    # 单文件模式：只保留目标文件的结果
    if single_file:
        result = [r for r in result if r.get("old_path") == single_file_path]
    
    if not result:
        return {"mode": "no_change", "message": "当前命名已是标准格式，无需修改", "items": []}
    
    # 始终填充影子名（无论 dry_run 还是 shadow_only）
    if not dry_run:
        shadow_filled = 0
        for r in result:
            old_path = r.get("old_path", "")
            shadow = r.get("shadow_name", "")
            if old_path and shadow:
                if shadow_m.auto_fill(old_path, shadow, source="parsed"):
                    shadow_filled += 1
        
        if shadow_only:
            return {"mode": "shadow_only", "filled": shadow_filled, "total": len(result), "items": result}
        
        # 正常重命名
        if single_file:
            # 单文件模式：只重命名这一个文件，不动其他文件
            actual_result = []
            for r in result:
                if r.get("unchanged"):
                    actual_result.append(r)
                    continue
                old_p = r.get("old_path", "")
                new_p = r.get("new_path", "")
                if old_p and new_p and old_p != new_p and os.path.exists(old_p) and not os.path.exists(new_p):
                    os.rename(old_p, new_p)
                    # 同步重命名关联文件
                    old_base = os.path.splitext(old_p)[0]
                    new_base = os.path.splitext(new_p)[0]
                    for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                        old_f = old_base + suffix
                        new_f = new_base + suffix
                        if os.path.exists(old_f):
                            try: os.rename(old_f, new_f)
                            except: pass
                    actual_result.append(r)
        else:
            actual_result = organizer.rename_videos_in_folder(target_path, client, False, library, category_hint=_get_category_from_path(target_path))
        
        # 创建快照（用于回滚）
        rename_ops = [{"old_path": r["old_path"], "new_path": r["new_path"]}
                      for r in actual_result if not r.get("unchanged") and r.get("old_path") != r.get("new_path")]
        snapshot_id = None
        if rename_ops:
            snapshot_id = history_m.create_snapshot(rename_ops)
        
        # 更新媒体库路径
        if isinstance(actual_result, list) and actual_result:
            file_renames = [(r["old_path"], r["new_path"]) for r in actual_result if not r.get("is_folder") and not r.get("unchanged")]
            folder_renames = [(r["old_path"], r["new_path"]) for r in actual_result if r.get("is_folder") and not r.get("unchanged")]
            
            lib = config_m.load_library()
            changed = False
            
            for old_p, new_p in file_renames:
                for v in lib:
                    if v.get("file_path") == old_p:
                        v["file_path"] = new_p
                        v["file_name"] = os.path.basename(new_p)
                        changed = True
                        break
            
            for old_folder, new_folder in folder_renames:
                for v in lib:
                    fp = v.get("file_path", "")
                    if fp.startswith(old_folder + os.sep) or fp.startswith(old_folder + "/"):
                        v["file_path"] = new_folder + fp[len(old_folder):]
                        changed = True
                    if changed:
                        base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                        if base and v.get("file_path", "").startswith(base):
                            rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                            v["folder_name"] = "" if rel == "." else rel
            
            if changed:
                config_m.save_library(lib)
        
        return {"mode": "renamed", "shadow_filled": shadow_filled, "items": actual_result, "snapshot_id": snapshot_id}
    
    # dry_run 模式：返回预览
    changed_items = [r for r in result if not r.get("unchanged")]
    unchanged_items = [r for r in result if r.get("unchanged")]
    # 统计有多少项可以生成影子名
    shadow_candidates = [r for r in result if r.get("shadow_name") and not r.get("is_folder")]
    has_shadow_work = any(
        not shadow_m.get(r.get("old_path", "")) or 
        (shadow_m.get(r.get("old_path", "")) and shadow_m.get(r.get("old_path", "")).source != "manual")
        for r in shadow_candidates
    ) if shadow_candidates else False
    
    if changed_items:
        msg = f"{len(changed_items)} 项需要重命名"
        if unchanged_items:
            msg += f"，{len(unchanged_items)} 项已是标准格式"
    else:
        msg = "当前命名已是标准格式，无需修改"
        if has_shadow_work:
            msg += f"（可为 {len(shadow_candidates)} 项生成影子名）"
    
    return {
        "mode": "preview",
        "items": result,
        "changed_count": len(changed_items),
        "unchanged_count": len(unchanged_items),
        "shadow_candidates": len(shadow_candidates),
        "has_shadow_work": has_shadow_work,
        "message": msg,
    }

@app.post("/organize/supplement")
def scrape_supplement(path: str):
    """刮削补充（只补缺少的字段）"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return organizer.scrape_supplement(path, client)

@app.post("/organize/seasons")
def reorganize_seasons(path: str, dry_run: bool = True):
    """多季规整"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    result = organizer.reorganize_seasons(path, client, dry_run, category_hint=_get_category_from_path(path))
    if not dry_run and result.get("ops"):
        _sync_library_paths(result["ops"])
    return result

@app.post("/organize/one-click")
async def one_click_organize(path: str, dry_run: bool = True):
    """一键整理 — 旧路由，内部重定向到 V3 /organize/full"""
    return await organize_full(path=path, dry_run=dry_run, use_ai=False, request=None)


@app.post("/organize/folder")
def organize_folder(path: str, dry_run: bool = True):
    """归类整理 — 消费分析层输出执行（旧路由，兼容）"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    library = config_m.load_library()
    category_hint = _get_category_from_path(path)
    result = organizer.organize_folder(path, client, dry_run, library, category_hint=category_hint)
    if not dry_run and result.get("ops"):
        _sync_library_paths(result["ops"])
    return result


# ── V3 整理 API ──

@app.post("/organize/structure")
def organize_structure(path: str, dry_run: bool = True):
    """V3 入口 A：纯结构整理（离线，不联网）。
    只做物理收纳：基础封装 + 结构归位 + 季目录创建。
    降级策略：没有 episode.nfo 时，用正则从文件名猜季号归位。
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path not found or not a directory")

    category_hint = _get_category_from_path(path)
    result = {"status": "ok", "mode": "structure_only", "ops": [], "count": 0}

    # Step 0: 基础封装（仅一级分类 + movie 标签）
    if _is_top_category(path) and category_hint == "movie":
        wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=dry_run, category_tag=category_hint)
        if wrap_result.get("ops"):
            result["ops"].extend(wrap_result["ops"])
            if not dry_run:
                _sync_library_paths(wrap_result["ops"])

    # 结构归位：散装视频封装 + 孤立刮削归位（对所有类型都做）
    library = config_m.load_library()
    org_result = organizer.organize_folder(path, tmdb_client=None, dry_run=dry_run,
                                           library_data=library, category_hint=category_hint)
    if org_result.get("ops"):
        result["ops"].extend(org_result["ops"])
        if not dry_run:
            _sync_library_paths(org_result["ops"])

    # 季目录归位：优先用 NFO，降级用正则
    reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=dry_run)
    if reorg.get("ops"):
        result["ops"].extend(reorg["ops"])
        if not dry_run:
            _sync_library_paths(reorg["ops"])
    else:
        # 降级：没有 NFO 时用旧的正则归位（从文件名猜季号）
        reorg_fallback = organizer.reorganize_seasons(path, tmdb_client=None, dry_run=dry_run, category_hint=category_hint)
        if reorg_fallback.get("ops"):
            result["ops"].extend(reorg_fallback["ops"])
            if not dry_run:
                _sync_library_paths(reorg_fallback["ops"])

    result["count"] = len(result["ops"])
    return result


@app.post("/organize/full")
async def organize_full(path: str, dry_run: bool = True, use_ai: bool = False,
                        request: Request = None, whitelist: List[str] = None):
    """V3 入口 B：一键完全整理（两段式提交）。
    dry_run=True：推演模式，返回 Action Plan（严禁任何文件系统写操作）。
    dry_run=False：确权执行，接收前端回传的 action_plan 直接执行。
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path not found or not a directory")

    category_hint = _get_category_from_path(path)
    client = _tmdb_client()

    if dry_run:
        # ══ 推演模式：只计算，严禁落盘 ══
        library = config_m.load_library()

        result = {
            "status": "ok", "mode": "full_organize", "dry_run": True,
            "path": path, "category_hint": category_hint,
        }

        # Step 0 推演：扫描散落视频，生成封装 plan
        wrap_plan = []
        if _is_top_category(path) and category_hint == "movie":
            wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=True, category_tag=category_hint)
            wrap_plan = wrap_result.get("ops", [])
        result["wrap_plan"] = wrap_plan

        # Step 1 推演：扫描旧刮削，生成清理 plan
        archive_plan = _smart_archive_plan(path)
        result["archive_plan"] = archive_plan

        # Step 2：分析判定（只读）
        report = analyzer.analyze_folder(path, library, category_hint=category_hint)
        folder_type = report.get("folder_type", "")
        result["folder_type"] = folder_type
        result["analyze"] = {
            "structure_ops": len(report.get("structure_ops", [])),
            "rename_ops": len(report.get("rename_ops", [])),
            "scrape_issues": len(report.get("scrape_issues", [])),
        }

        # Step 3 推演：刮削计算（只读）
        if client:
            scrape_result = scraper.scrape_folder(
                path, client, force=True, folder_type=folder_type,
                dry_run=True, use_ai=use_ai, whitelist=whitelist
            )
            result["tmdb_match"] = scrape_result.get("tmdb_match", {})
            result["plan"] = scrape_result.get("plan", [])
            result["summary"] = scrape_result.get("summary", {})
        else:
            result["tmdb_match"] = {}
            result["plan"] = []
            result["summary"] = {"error": "TMDB API key not configured"}

        return result

    else:
        # ══ 确权执行模式：接收 Plan 直接执行 ══
        # 从 request body 获取 action_plan（前端回传）
        action_plan = None
        try:
            body = await request.json() if request else None
            if body and "action_plan" in body:
                action_plan = body["action_plan"]
        except Exception:
            pass

        result = {
            "status": "ok", "mode": "full_organize", "dry_run": False,
            "path": path, "steps": {},
        }

        if action_plan:
            # 有 Plan → 所见即所得执行
            tmdb_match = action_plan.get("tmdb_match", {})
            plan_items = action_plan.get("plan", [])
            folder_type = action_plan.get("folder_type", "")

            # 执行 wrap_plan
            wrap_plan = action_plan.get("wrap_plan", [])
            if wrap_plan:
                for op in wrap_plan:
                    if op.get("action") == "move":
                        if op.get("mkdir"):
                            os.makedirs(op["mkdir"], exist_ok=True)
                        if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                            shutil.move(op["old"], op["new"])
                _sync_library_paths(wrap_plan)
                result["steps"]["wrap"] = len(wrap_plan)

            # 执行 archive_plan
            archive_plan = action_plan.get("archive_plan", [])
            if archive_plan:
                _execute_archive_plan(archive_plan)
                result["steps"]["archive"] = len(archive_plan)

            # 执行 scrape（写 NFO）
            tmdb_id = tmdb_match.get("tmdb_id", 0)
            if tmdb_id and client:
                # 写 tvshow.nfo
                tv_detail = client.get_tv_detail(tmdb_id)
                if tv_detail and tv_detail.tmdb_id:
                    proxy = getattr(client, 'proxy', '') or ''
                    for old in ["movie.nfo", "tvshow.nfo"]:
                        p = os.path.join(path, old)
                        if os.path.exists(p):
                            try: os.remove(p)
                            except: pass
                    scraper.write_tvshow_nfo(path, tv_detail)
                    if tv_detail.poster_url:
                        scraper.download_poster(path, tv_detail.poster_url, proxy=proxy)

                # 写 episode.nfo
                nfo_written = 0
                showtitle = tv_detail.title if tv_detail else ""
                for item in plan_items:
                    if "write_episode_nfo" not in item.get("actions", []):
                        continue
                    mapped = item.get("mapped")
                    if not mapped:
                        continue
                    s, e = mapped["season"], mapped["episode"]
                    vpath = item["original_path"]
                    if not os.path.exists(vpath):
                        continue
                    ep_scrape = tmdb_client.ScrapeResult(
                        tmdb_id=tmdb_id, media_type="episode",
                        title=item.get("episode_title") or showtitle,
                        episode_title=item.get("episode_title", ""),
                        season_number=s, episode_number=e,
                    )
                    scraper.write_episode_nfo(vpath, ep_scrape, showtitle=showtitle)
                    nfo_written += 1
                result["steps"]["scrape"] = {"nfo_written": nfo_written}

            # Reload library
            library = config_m.load_library()

            # 执行结构归位（读 NFO 建季目录）
            if folder_type == "tv":
                reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
                if reorg.get("ops"):
                    _sync_library_paths(reorg["ops"])
                result["steps"]["structure"] = {"moved": len(reorg.get("ops", []))}

            # Reload library
            library = config_m.load_library()

            # 执行影子名写入
            shadow_filled = 0
            for item in plan_items:
                shadow = item.get("target_shadow_name")
                vpath = item.get("original_path", "")
                if shadow and vpath:
                    # 文件可能已被移动到季目录，用 target_path
                    actual_path = item.get("target_path", vpath)
                    if os.path.exists(actual_path):
                        if shadow_m.auto_fill(actual_path, shadow, source="parsed"):
                            shadow_filled += 1
                    elif os.path.exists(vpath):
                        if shadow_m.auto_fill(vpath, shadow, source="parsed"):
                            shadow_filled += 1
            result["steps"]["shadow"] = shadow_filled

        else:
            # 无 Plan → 完整跑一遍（兼容旧调用方式）
            library = config_m.load_library()

            # Step 0
            if _is_top_category(path) and category_hint == "movie":
                wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=False, category_tag=category_hint)
                if wrap_result.get("ops"):
                    _sync_library_paths(wrap_result["ops"])
                result["steps"]["wrap"] = wrap_result.get("count", 0)

            # Step 1
            archived = _smart_archive_recursive(path)
            result["steps"]["archive"] = archived

            # Step 2
            report = analyzer.analyze_folder(path, library, category_hint=category_hint)
            folder_type = report.get("folder_type", "")
            result["steps"]["analyze"] = folder_type

            # Step 3
            if client:
                scrape_result = scraper.scrape_folder(
                    path, client, force=True, folder_type=folder_type,
                    dry_run=False, use_ai=use_ai
                )
                result["steps"]["scrape"] = scrape_result.get("summary", {})

            # Reload + Step 4
            library = config_m.load_library()
            if folder_type == "tv":
                reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
                if reorg.get("ops"):
                    _sync_library_paths(reorg["ops"])
                result["steps"]["structure"] = len(reorg.get("ops", []))

            # Reload + Step 5
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
                    if shadow:
                        if shadow_m.auto_fill(vpath, shadow, source="parsed"):
                            shadow_filled += 1
            result["steps"]["shadow"] = shadow_filled

        return result


def _smart_archive_plan(path: str) -> list:
    """推演模式：扫描旧刮削，返回清理 plan（不执行）"""
    import xml.etree.ElementTree as ET
    plan = []
    scrape_names = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                    'clearlogo.png', 'folder.jpg', 'movie.nfo', 'tvshow.nfo',
                    'season.nfo', 'theme.mp3'}
    poster_suffixes = ['-poster.jpg', '-poster.png', '-fanart.jpg', '-fanart.png',
                       '-clearlogo.png', '-thumb.jpg']

    def _scan_dir(dir_path):
        try:
            items = os.listdir(dir_path)
        except OSError:
            return
        # 检查 NFO 是否有效
        nfo_valid = False
        for nfo_name in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            nfo_path = os.path.join(dir_path, nfo_name)
            if os.path.exists(nfo_path):
                try:
                    tree = ET.parse(nfo_path)
                    title = tree.getroot().findtext("title", "").strip()
                    if title:
                        nfo_valid = True
                except Exception:
                    pass
                break

        if nfo_valid:
            return  # 有效 NFO → 保留，不清理

        # 无效 NFO 或无 NFO → 收集要清理的刮削文件
        files_to_archive = []
        for f in items:
            fp = os.path.join(dir_path, f)
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(f)[1].lower()
            if f in scrape_names or ext == '.nfo' or \
               (ext in {'.jpg', '.png'} and any(f.endswith(s) for s in poster_suffixes)):
                files_to_archive.append(f)

        if files_to_archive:
            plan.append({
                "dir": dir_path,
                "files": files_to_archive,
                "action": "archive_and_delete",
                "desc": f"清理 {len(files_to_archive)} 个无效刮削文件",
            })

        # 递归子目录
        for item in items:
            sub = os.path.join(dir_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                _scan_dir(sub)

    _scan_dir(path)
    return plan


def _smart_archive_recursive(path: str) -> int:
    """执行模式：递归清理无效旧刮削，保留有效 NFO"""
    import zipfile
    import xml.etree.ElementTree as ET
    total_archived = 0
    scrape_names = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                    'clearlogo.png', 'folder.jpg', 'cover.jpg', 'movie.nfo',
                    'tvshow.nfo', 'season.nfo', 'theme.mp3'}
    poster_suffixes = ['-poster.jpg', '-poster.png', '-fanart.jpg', '-fanart.png',
                       '-clearlogo.png', '-thumb.jpg']

    def _process_dir(dir_path):
        nonlocal total_archived
        try:
            items = os.listdir(dir_path)
        except OSError:
            return

        # 检查 NFO 是否有效
        nfo_valid = False
        for nfo_name in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            nfo_path = os.path.join(dir_path, nfo_name)
            if os.path.exists(nfo_path):
                try:
                    tree = ET.parse(nfo_path)
                    title = tree.getroot().findtext("title", "").strip()
                    if title:
                        nfo_valid = True
                except Exception:
                    pass
                break

        if not nfo_valid:
            # 收集要清理的刮削文件
            files = []
            for f in items:
                fp = os.path.join(dir_path, f)
                if not os.path.isfile(fp):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if f in scrape_names or ext == '.nfo' or \
                   (ext in {'.jpg', '.png'} and any(f.endswith(s) for s in poster_suffixes)):
                    files.append(f)

            if files:
                zp = os.path.join(dir_path, '.old_scrape.zip')
                if not os.path.exists(zp):
                    try:
                        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for f in files:
                                zf.write(os.path.join(dir_path, f), f)
                        for f in files:
                            try:
                                os.remove(os.path.join(dir_path, f))
                            except OSError:
                                pass
                        total_archived += len(files)
                    except Exception:
                        pass

        # 递归子目录
        for item in items:
            sub = os.path.join(dir_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                _process_dir(sub)

    _process_dir(path)
    return total_archived


def _execute_archive_plan(archive_plan: list):
    """执行旧刮削清理 plan"""
    import zipfile
    for item in archive_plan:
        dir_path = item.get("dir", "")
        files = item.get("files", [])
        if not dir_path or not files:
            continue
        zp = os.path.join(dir_path, '.old_scrape.zip')
        if os.path.exists(zp):
            continue
        try:
            with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    fp = os.path.join(dir_path, f)
                    if os.path.exists(fp):
                        zf.write(fp, f)
            for f in files:
                try:
                    os.remove(os.path.join(dir_path, f))
                except OSError:
                    pass
        except Exception:
            pass

@app.post("/organize/merge-scattered")
def merge_scattered_seasons_api(path: str = "", dry_run: bool = True):
    """合并散落的同剧多季目录"""
    config = config_m.config
    base_path = path or (config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else "")
    if not base_path or not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail="Path not configured or not accessible")
    library = config_m.load_library()
    report = analyzer.analyze_library(base_path, library)
    results = []
    for issue in report.get("cross_folder_issues", []):
        if issue.get("type") == "scattered_seasons":
            r = organizer.merge_scattered_seasons(issue, dry_run)
            results.append(r)
            if not dry_run and r.get("ops"):
                _sync_library_paths([op for op in r["ops"] if op.get("action") == "move_dir"])
    return {"results": results, "total_issues": len(results)}

@app.post("/rename")
def rename_item(old_path: str, new_name: str):
    """手动重命名文件或文件夹"""
    print(f"[rename] old_path={old_path}")
    print(f"[rename] new_name={new_name}")
    print(f"[rename] exists={os.path.exists(old_path)}")
    if not os.path.exists(old_path):
        # 尝试修复路径分隔符
        alt_path = old_path.replace("/", "\\")
        print(f"[rename] 尝试替换分隔符: {alt_path} exists={os.path.exists(alt_path)}")
        if os.path.exists(alt_path):
            old_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"Path not found: {old_path}")
    
    parent = os.path.dirname(old_path)
    new_path = os.path.join(parent, new_name)
    
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Target name already exists")
    
    try:
        os.rename(old_path, new_path)
        
        # 同步 media_library.json
        library = config_m.load_library()
        changed = False
        if os.path.isdir(new_path):
            # 文件夹重命名：更新所有子文件的路径
            for v in library:
                fp = v.get("file_path", "")
                if fp.startswith(old_path + os.sep) or fp.startswith(old_path + "/"):
                    v["file_path"] = new_path + fp[len(old_path):]
                    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                    changed = True
            
            # movie 类型（单视频文件夹）：同时重命名视频文件和关联文件
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            try:
                items = os.listdir(new_path)
                videos = [f for f in items if os.path.isfile(os.path.join(new_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                subdirs = [f for f in items if os.path.isdir(os.path.join(new_path, f)) and not f.startswith('.')]
                if len(videos) == 1 and len(subdirs) == 0:
                    # 单视频文件夹：重命名视频文件为文件夹名 + 原扩展名
                    old_video = videos[0]
                    ext = os.path.splitext(old_video)[1]
                    if not ext:
                        pass  # 视频没有扩展名，跳过
                    else:
                        new_video = new_name + ext
                        if old_video != new_video:
                            old_vp = os.path.join(new_path, old_video)
                            new_vp = os.path.join(new_path, new_video)
                            if not os.path.exists(new_vp):
                                os.rename(old_vp, new_vp)
                                # 更新 library 中的文件路径和文件名
                                old_vp_norm = old_vp.replace("/", os.sep)
                                for v in library:
                                    vfp = v.get("file_path", "").replace("/", os.sep)
                                    if vfp == old_vp_norm:
                                        v["file_path"] = new_vp
                                        v["file_name"] = new_video
                                        changed = True
                                # 重命名关联文件（NFO、poster 等）
                                old_base = os.path.splitext(old_vp)[0]
                                new_base = os.path.splitext(new_vp)[0]
                                for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                                    old_f = old_base + suffix
                                    new_f = new_base + suffix
                                    if os.path.exists(old_f):
                                        try:
                                            os.rename(old_f, new_f)
                                        except Exception:
                                            pass
            except OSError:
                pass
        else:
            # 文件重命名
            for v in library:
                if v.get("file_path") == old_path:
                    v["file_path"] = new_path
                    v["file_name"] = new_name
                    changed = True
                    break
            
            # 同时重命名对应的 .nfo / -poster.jpg 等关联文件
            old_base = os.path.splitext(old_path)[0]
            new_base = os.path.splitext(new_path)[0]
            for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                old_f = old_base + suffix
                new_f = new_base + suffix
                if os.path.exists(old_f):
                    try:
                        os.rename(old_f, new_f)
                    except Exception:
                        pass
            
            # 单视频文件夹（仅 movie 类型）：同步重命名父文件夹
            # TV 类型绝不联动改文件夹名（多集共用一个文件夹）
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            file_ext = os.path.splitext(new_name)[1].lower()
            if file_ext in video_exts:
                folder_path = os.path.dirname(new_path)
                # 检查文件夹类型：如果是 TV/season 类型，跳过
                folder_type = ""
                for v in library:
                    fp = v.get("file_path", "")
                    if fp.startswith(folder_path):
                        folder_type = v.get("folder_type", "")
                        break
                # 只有 movie 类型（或未分类的单视频文件夹）才同步改文件夹名
                is_tv = folder_type in ("tv", "season", "anime")
                if not is_tv:
                    try:
                        items = os.listdir(folder_path)
                        videos_in_folder = [f for f in items if os.path.isfile(os.path.join(folder_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                        subdirs_in_folder = [f for f in items if os.path.isdir(os.path.join(folder_path, f)) and not f.startswith('.')]
                        if len(videos_in_folder) == 1 and len(subdirs_in_folder) == 0:
                            new_folder_name = os.path.splitext(new_name)[0]
                            old_folder_name = os.path.basename(folder_path)
                            if old_folder_name != new_folder_name:
                                new_folder_path = os.path.join(os.path.dirname(folder_path), new_folder_name)
                                if not os.path.exists(new_folder_path):
                                    os.rename(folder_path, new_folder_path)
                                    for v in library:
                                        fp = v.get("file_path", "")
                                        if fp.startswith(folder_path + os.sep) or fp.startswith(folder_path + "/") or fp == new_path:
                                            v["file_path"] = new_folder_path + fp[len(folder_path):]
                                            base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                                            if base:
                                                rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                                                v["folder_name"] = "" if rel == "." else rel
                                            changed = True
                                    new_path = os.path.join(new_folder_path, new_name)
                    except OSError:
                        pass
        
        if changed:
            config_m.save_library(library)
        
        return {"status": "ok", "old_path": old_path, "new_path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 豆瓣热榜与新增影片 API ──

@app.get("/douban/hot")
def douban_hot(type: str = "movie", page_start: int = 0, tag: str = "热门"):
    """获取热榜列表。动画 tab 用 Bangumi，其他用豆瓣+TMDB（文件缓存+并发）"""
    import concurrent.futures
    import hashlib, time as _time

    # 动画 tab 走 Bangumi
    if tag == "动画":
        items = bangumi_client.get_hot_anime(page_start, 12)
        return {"type": type, "items": items}

    # 文件缓存：1 小时内直接返回
    cache_key = hashlib.md5(f"hot_{type}_{tag}_{page_start}".encode()).hexdigest()[:12]
    cache_path = os.path.join("scrape_cache", f"hot_{cache_key}.json")
    if os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            if _time.time() - mtime < 604800:  # 7 天
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass

    items = douban_client.get_hot_list(type, page_start, tag)
    if not items:
        return {"type": type, "items": items}

    # 先把豆瓣封面走代理（作为 fallback）
    for item in items:
        cover = item.get("cover_url", "")
        if cover and "doubanio.com" in cover:
            item["cover_url_proxy"] = f"/proxy/image?url={requests.utils.quote(cover)}"

    # 并发搜索 TMDB 补充封面和年份
    clients = get_clients()
    tmdb = clients["tmdb"]

    def enrich_item(item):
        title = item.get("title", "")
        if not title:
            return
        try:
            results = tmdb.search_movie(title) if type == "movie" else tmdb.search_tv(title)
            if results:
                best = results[0]
                poster_path = best.get("poster_path")
                if poster_path:
                    item["cover_url"] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                if not item.get("year"):
                    tmdb_date = best.get("release_date") or best.get("first_air_date") or ""
                    if tmdb_date:
                        item["year"] = tmdb_date[:4]
                return
        except:
            pass
        # TMDB 搜不到，用代理封面
        if item.get("cover_url_proxy"):
            item["cover_url"] = item["cover_url_proxy"]
        # 补充 year
        if not item.get("year"):
            try:
                suggest = douban_client.search(title)
                if suggest:
                    item["year"] = suggest[0].get("year", "")
                    if not item.get("subtitle"):
                        item["subtitle"] = suggest[0].get("subtitle", "")
            except:
                pass

    # 最多 4 个并发线程，超时 8 秒
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(enrich_item, item) for item in items]
        concurrent.futures.wait(futures, timeout=4)

    # 清理临时字段 + 确保所有豆瓣封面都走代理
    for item in items:
        cover = item.get("cover_url", "")
        proxy = item.get("cover_url_proxy", "")
        # 如果 cover_url 还是豆瓣原始 URL（TMDB 超时没替换），用代理 URL
        if cover and "doubanio.com" in cover and proxy:
            item["cover_url"] = proxy
        item.pop("cover_url_proxy", None)

    # 保存缓存
    result = {"type": type, "items": items}
    try:
        os.makedirs("scrape_cache", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except:
        pass

    return result

@app.get("/douban/search")
def douban_search(query: str):
    """搜索豆瓣影片"""
    results = douban_client.search(query)
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    return {"query": query, "candidates": results}

@app.get("/media/info")
def get_media_info(title: str, year: str = "", type: str = "movie", subtitle: str = ""):
    """通过 TMDB 搜索获取影片详细信息。搜索策略：中文标题 → subtitle（外文名）→ 豆瓣搜索获取外文名重试"""
    clients = get_clients()
    tmdb = clients["tmdb"]

    def _search(query: str):
        if type == "tv":
            return tmdb.search_tv(query)
        return tmdb.search_movie(query)

    def _search_nolang(query: str):
        """不带语言限制搜索，覆盖更多翻译版本"""
        try:
            if type == "tv":
                return tmdb._get("/search/tv", {"query": query, "language": "en-US"}).get("results", [])[:10]
            return tmdb._get("/search/movie", {"query": query, "language": "en-US"}).get("results", [])[:10]
        except:
            return []

    def _pick_best(results: list, yr: str):
        if not results:
            return None
        best = results[0]
        if yr:
            for r in results:
                r_year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
                if r_year == yr:
                    best = r
                    break
        return best

    try:
        # 1. 用中文标题搜
        best = _pick_best(_search(title), year)

        # 2. 没找到且有 subtitle（外文名），用 subtitle 搜
        if not best and subtitle and subtitle != title:
            best = _pick_best(_search(subtitle), year)

        # 3. 还没找到，用豆瓣搜索接口获取外文名重试
        if not best:
            douban_results = douban_client.search(title)
            for dr in douban_results:
                alt_name = dr.get("subtitle", "")
                if alt_name and alt_name != title and alt_name != subtitle:
                    best = _pick_best(_search(alt_name), year)
                    if best:
                        break
                    # 外文名也用英文搜索试试
                    best = _pick_best(_search_nolang(alt_name), year)
                    if best:
                        break

        # 4. 还没找到，用英文搜索中文标题（TMDB 有时只有英文条目）
        if not best:
            best = _pick_best(_search_nolang(title), year)

        if not best:
            return {"found": False}

        tmdb_id = best.get("id", 0)
        if type == "tv":
            detail = tmdb.get_tv_detail(tmdb_id)
        else:
            detail = tmdb.get_movie_detail(tmdb_id)
        return {
            "found": True,
            "tmdb_id": detail.tmdb_id,
            "title": detail.title,
            "original_title": detail.original_title,
            "year": detail.year,
            "poster_url": detail.poster_url,
            "backdrop_url": detail.backdrop_url,
            "overview": detail.overview,
            "rating": detail.rating,
            "genres": detail.genres,
            "director": detail.director,
            "cast": detail.cast[:6],
            "runtime": detail.runtime,
            "imdb_id": detail.imdb_id,
            "total_seasons": detail.total_seasons,
            "episode_count": detail.episode_count,
            "status": detail.status,
            "countries": detail.countries,
        }
    except Exception as e:
        print(f"[MediaInfo] error: {e}")
        return {"found": False}

class AddMediaRequest(BaseModel):
    title: str
    original_title: str = ""
    year: str = ""
    douban_id: str = ""
    rating: float = 0
    overview: str = ""
    genres: List[str] = []
    director: str = ""
    cast: List[str] = []
    poster_url: str = ""
    save_path: str

@app.post("/add-media")
def add_media(req: AddMediaRequest):
    """在目标目录创建影片文件夹并生成预刮削 NFO + 封面"""
    from tmdb_client import ScrapeResult

    # 创建以影片名命名的文件夹
    folder_name = req.title.strip() or "Unknown"
    if req.year:
        folder_name = f"{folder_name} ({req.year})"
    # 清理文件名中不合法的字符
    folder_name = "".join(c for c in folder_name if c not in r'\/:*?"<>|').strip()
    folder_path = os.path.join(req.save_path, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # 构造 ScrapeResult 用于写入 NFO
    result = ScrapeResult(
        tmdb_id=int(req.douban_id) if req.douban_id.isdigit() else 0,
        media_type="movie",
        title=req.title,
        original_title=req.original_title,
        year=req.year,
        overview=req.overview,
        rating=req.rating,
        genres=req.genres,
        director=req.director,
        cast=req.cast,
        poster_url=req.poster_url,
    )

    # 写入 NFO
    nfo_written = False
    try:
        scraper.write_movie_nfo(folder_path, result)
        nfo_written = True
    except Exception as e:
        print(f"[AddMedia] NFO write error: {e}")

    # 下载封面（豆瓣图片需带 Referer 头，scraper.download_poster 已处理）
    poster_downloaded = False
    if req.poster_url:
        try:
            poster_downloaded = scraper.download_poster(folder_path, req.poster_url)
        except Exception as e:
            print(f"[AddMedia] poster download error: {e}")

    return {
        "status": "ok",
        "folder_path": folder_path,
        "nfo_written": nfo_written,
        "poster_downloaded": poster_downloaded,
    }


# ══════════════════════════════════════════════════════════════
# 二期功能 API
# ══════════════════════════════════════════════════════════════

# ── 种子排序权重配置 ──
@app.get("/config/sort-weights")
def get_sort_weights():
    """获取种子排序权重配置"""
    conf = config_m.config
    return conf.sort_weights.dict()

class SortWeightsUpdateRequest(BaseModel):
    title_match: float = 0.30
    resolution_upgrade: float = 0.25
    codec_match: float = 0.15
    seeder_health: float = 0.15
    chinese_sub: float = 0.10
    size_reasonable: float = 0.05

@app.post("/config/sort-weights")
def save_sort_weights(req: SortWeightsUpdateRequest):
    """保存种子排序权重配置"""
    conf = config_m.config
    conf.sort_weights = config_manager.SortWeightsConfig(**req.dict())
    config_m.save(conf)
    return {"status": "ok"}


# ── 种子黑名单 ──
@app.get("/torrent-blacklist")
def list_torrent_blacklist():
    """列出所有黑名单条目"""
    return {"entries": torrent_bl.list_entries(), "count": torrent_bl.count}

@app.post("/torrent-blacklist/add")
def add_to_blacklist(url: str, reason: str = ""):
    """手动添加种子到黑名单"""
    torrent_bl.add(url, reason)
    return {"status": "ok"}

@app.post("/torrent-blacklist/remove")
def remove_from_blacklist(url: str):
    """从黑名单移除"""
    torrent_bl.remove(url)
    return {"status": "ok"}

@app.post("/torrent-blacklist/cleanup")
def cleanup_blacklist():
    """清理过期黑名单"""
    removed = torrent_bl.cleanup()
    return {"status": "ok", "removed": removed}


# ── 全库分析报告（含缓存） ──
@app.get("/analysis/report")
def get_analysis_report(force: bool = False):
    """获取全库分析报告，优先返回缓存。force=True 强制重新分析。"""
    if not force:
        cached = analysis_cache.get()
        if cached:
            age = analysis_cache.get_age_hours()
            return {**cached, "from_cache": True, "cache_age_hours": round(age, 1)}

    # 全量分析
    library = config_m.load_library()
    conf = config_m.config
    all_results = []
    for base in conf.nas_paths:
        if os.path.isdir(base):
            report = analyzer.analyze_library(base, library)
            all_results.append(report)

    # 合并多路径结果
    merged = {
        "results": [],
        "cross_folder_issues": [],
        "summary": {
            "total_folders": 0, "structure_issues": 0, "rename_issues": 0,
            "scrape_issues": 0, "quality_issues": 0, "filename_issues": 0,
            "shadow_name_issues": 0, "cross_folder_issues": 0,
        }
    }
    for r in all_results:
        merged["results"].extend(r.get("results", []))
        merged["cross_folder_issues"].extend(r.get("cross_folder_issues", []))
        s = r.get("summary", {})
        for k in merged["summary"]:
            merged["summary"][k] += s.get(k, 0)

    analysis_cache.update(merged)
    return {**merged, "from_cache": False, "cache_age_hours": 0}

@app.post("/analysis/invalidate")
def invalidate_analysis_cache():
    """清除分析缓存"""
    analysis_cache.invalidate()
    return {"status": "ok"}


# ── 一键整理进度反馈（SSE 流式） ──
@app.post("/organize/full-stream")
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
                archive_plan = _smart_archive_plan(path)
                result["steps"]["archive"] = len(archive_plan)
            else:
                archived = _smart_archive_recursive(path)
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


# ── 整理历史记录 ──
@app.get("/organize/history")
def get_organize_history(limit: int = 50):
    """获取整理历史记录"""
    snapshots = history_m.list_snapshots()
    # 按时间倒序，限制数量
    snapshots.sort(key=lambda x: x.get("time", ""), reverse=True)
    return {"snapshots": snapshots[:limit], "total": len(snapshots)}

@app.get("/organize/history/{snapshot_id}")
def get_organize_history_detail(snapshot_id: int):
    """获取单条整理历史详情"""
    snapshots = history_m.list_snapshots()
    for s in snapshots:
        if s.get("id") == snapshot_id:
            return s
    raise HTTPException(status_code=404, detail="Snapshot not found")


# ── 下载提交时检查黑名单 ──
@app.get("/torrent-blacklist/check")
def check_blacklist(url: str):
    """检查种子是否在黑名单中"""
    return {"blocked": torrent_bl.is_blocked(url)}


class RelocateRequest(BaseModel):
    task_id: str
    auto_replace: bool = False

class ExecuteRelocateRequest(BaseModel):
    task_id: str
    plan: dict

@app.post("/organize/dry-run")
async def organize_dry_run(req: RelocateRequest):
    """阶段一：整理替换探测（原地识别模式）"""
    import traceback
    try:
        dm = _get_download_manager()
        task = dm.get_task(req.task_id)
        if not task:
            return {"status": "failed", "message": f"任务不存在: {req.task_id}", "coexist_pairs": []}
            
        # 获取新资源白名单
        new_files = []
        if task.downloader_hash:
            try:
                clients = get_clients()
                qb = clients.get("qb")
                if qb:
                    new_files = qb.get_torrent_files(task.downloader_hash)
            except Exception as qe:
                print(f"[DryRun] qB 获取文件列表失败: {qe}")
        
        print(f"\n[DryRun] task={task.media_name}, save_path={task.save_path}, hash={task.downloader_hash}, whitelist={len(new_files)}")
        
        rel = _get_file_relocator()
        res = await rel.relocate(task, new_files_whitelist=new_files)

        print(f"[DryRun] result: status={res.status}, pairs={len(res.coexist_pairs)}, error={res.error}")

        if res.status == "awaiting_confirm":
            return {
                "status": "awaiting_confirm",
                "message": "发现库中存量旧版本，建议执行整理替换",
                "coexist_pairs": [p.dict() for p in res.coexist_pairs],
                "plan": res.action_plan
            }
        
        if res.status == "failed":
            return {"status": "failed", "message": f"探测失败: {res.error}", "coexist_pairs": []}
        
        # 无冲突，直接入库记录
        if res.status == "archived":
            dm.archive_task(task.id)
            
        return {"status": res.status, "message": "未发现冲突，已完成标准化归档", "coexist_pairs": []}
    except Exception as e:
        traceback.print_exc()
        return {"status": "failed", "message": f"服务端异常: {e}", "coexist_pairs": []}


@app.post("/organize/execute")
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
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            req.plan["whitelist"] = qb.get_torrent_files(task.downloader_hash)

    execute_res = await rel.confirm_replace(task, req.plan)
    
    if execute_res.success:
        dm.archive_task(task.id)
        
    return {"status": execute_res.status, "message": execute_res.error or "整理替换任务执行完毕"}

@app.post("/organize/archive-both")
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
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            new_files = qb.get_torrent_files(task.downloader_hash)
            
    res = await rel.relocate(task, new_files_whitelist=new_files)
    
    execute_res = await rel.archive_both(task, res.coexist_pairs)
    
    if execute_res.success:
        dm.archive_task(task.id)
        
    return {"status": execute_res.status, "message": execute_res.error or "共存归档任务执行完毕"}

@app.post("/organize/purge-old")
async def organize_purge_old(task_id: str):
    """辅助：只清理旧数据。回收所有非新资源文件。"""
    dm = _get_download_manager()
    task = dm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
        
    new_files = []
    if task.downloader_hash:
        clients = get_clients()
        qb = clients.get("qb")
        if qb:
            new_files = qb.get_torrent_files(task.downloader_hash)
    
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


if __name__ == "__main__":
    import uvicorn
    file_name = os.path.basename(__file__).replace(".py", "")
    uvicorn.run(f"{file_name}:app", host="127.0.0.1", port=8000, reload=True)
