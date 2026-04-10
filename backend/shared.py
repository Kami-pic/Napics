"""
全局单例和共享辅助函数。
所有路由模块通过 from shared import ... 获取依赖。
"""
import os
import sys
import json
import re
import requests
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Dict

# 强制重配置 Windows 端的 stdout 编码，防止 GBK 崩溃
if sys.platform == "win32":
    try:
        import io
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

import scanner
import searcher
import downloader
import tmdb_client
import config_manager
import ai_organizer
import douban_client
import bangumi_client
import scraper
from path_utils import normalize_path
import organizer
import analyzer
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

# ── 全局单例 ──

config_m = config_manager.ConfigManager()
shadow_m = ShadowNameManager()
indexer_m = IndexerPriorityManager()
indexer_m.load()
torrent_bl = TorrentBlacklist()
analysis_cache = AnalysisCache()

_download_manager: Optional[DownloadManager] = None
_pan_search_service: Optional[PanSearchService] = None
_recycle_bin: Optional[RecycleBin] = None
_file_relocator: Optional[FileRelocator] = None


def _get_pan_search_service() -> PanSearchService:
    global _pan_search_service
    if _pan_search_service is None:
        _pan_search_service = PanSearchService(
            search_sources={
                "pansearch": True,
                "pansou": True,
                "gogopanso": True,   # 狗狗盘搜：公开 API，每日更新，无反爬
                "github": True,      # GitHub 资源仓库：QuarkShare + quark-share
                "sites": False,      # 通用站点：大多需登录或被反爬，暂关
                "slowread": False,   # 慢读：纯 JS 渲染，需逆向 API，暂关
                "wnsearch": False,   # 我能搜：纯 JS 渲染，需逆向 API，暂关
                "rrdynb": False,
                "ddys": False,
            },
            pansou_api_url="https://pansou.app",
        )
    return _pan_search_service


def _get_download_manager() -> DownloadManager:
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


def _get_recycle_bin() -> RecycleBin:
    global _recycle_bin
    if _recycle_bin is None:
        conf = config_m.config
        recycle_dir = conf.recycle_bin_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "recycle_bin"
        )
        _recycle_bin = RecycleBin(recycle_dir, conf.recycle_bin_retention_days)
    return _recycle_bin


def _get_file_relocator() -> FileRelocator:
    """懒加载文件归位器。注意：organize_full 在 routes/organize.py 中定义，
    这里用延迟导入避免循环依赖。"""
    global _file_relocator
    if _file_relocator is None:
        from routes.organize import organize_full
        _file_relocator = FileRelocator(
            recycle_bin=_get_recycle_bin(),
            run_pipeline_fn=organize_full,
        )
    return _file_relocator


def _tmdb_client():
    """统一创建 TMDBClient，自动带 proxy"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        return None
    return tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')


def get_clients():
    """动态实例化客户端（由配置驱动）"""
    conf = config_m.config
    return {
        "search": searcher.ProwlarrClient(conf.prowlarr_url, conf.prowlarr_api_key),
        "tmdb": tmdb_client.TMDBClient(conf.tmdb_api_key, proxy=getattr(conf, 'http_proxy', '') or ''),
        "qb": downloader.QBittorrentClient(conf.qb_url, username=conf.qb_username, password=conf.qb_password),
        "alist": downloader.AlistManager(conf.alist_url, conf.alist_token),
        "netdisk": searcher.NetdiskSearcher()
    }


# ── 共享辅助函数 ──

def _get_category_from_path(path: str) -> str:
    """从文件路径推断一级分类标签（movie/tv）"""
    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
    if not base:
        return ""
    norm_path = os.path.normpath(path)
    norm_base = os.path.normpath(base)
    if not norm_path.startswith(norm_base):
        return ""
    rel = os.path.relpath(norm_path, norm_base)
    parts = rel.split(os.sep)
    if not parts or parts[0] == ".":
        return ""
    category_dir_name = parts[0]
    category_dir_path = os.path.join(base, category_dir_name)
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
                    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
                    if base:
                        rel = os.path.relpath(os.path.dirname(op["new"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                    changed = True
    if changed:
        config_m.save_library(library)


def _update_clean_names_after_scrape(path: str, scrape_result: dict):
    """刮削成功后，用刮削结果更新 clean_name"""
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
