"""
全局单例和共享辅助函数。
所有路由模块通过 from shared import ... 获取依赖。
"""
import os
import sys
import json
import logging
import re
import requests
import shutil
import subprocess
import threading
import time
from typing import List, Optional, Dict

# ── 统一 logging 配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)

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
import metadata_service
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
from local_media_matcher import LocalMediaMatcher
from subscriber import SubscriptionManager

logger = logging.getLogger(__name__)
# ── 全局单例 ──

config_m = config_manager.ConfigManager()
shadow_m = ShadowNameManager()
indexer_m = IndexerPriorityManager()
indexer_m.load()
torrent_bl = TorrentBlacklist()
analysis_cache = AnalysisCache()
media_matcher = LocalMediaMatcher()

# 启动时构建媒体库索引
try:
    _init_lib = config_m.load_library()
    media_matcher.build_index(_init_lib)
except Exception as _e:
    logger.error(f"[Shared] 媒体库索引构建失败: {_e}")

# 注册回调：save_library 后自动刷新索引
config_m._on_library_save_callbacks.append(lambda lib: media_matcher.build_index(lib))

# 注册回调：save_library 后延迟刷新受影响的 TV 文件夹完整度
_completeness_prev_paths: set = set()
_completeness_timer = None
_completeness_lock = threading.Lock()

def _on_library_save_refresh_completeness(library: list):
    """save_library 回调：对比新旧库数据，找出变更的文件路径，延迟刷新完整度"""
    global _completeness_prev_paths, _completeness_timer

    current_paths = set(v.get("file_path", "") for v in library if v.get("file_path"))
    with _completeness_lock:
        prev = _completeness_prev_paths
        _completeness_prev_paths = current_paths

    if not prev:
        return  # 首次加载，不触发刷新

    # 找出变更的路径（新增 + 删除）
    changed = (current_paths - prev) | (prev - current_paths)
    if not changed:
        return

    # 防抖：取消之前的 timer，延迟 3 秒执行
    with _completeness_lock:
        if _completeness_timer is not None:
            _completeness_timer.cancel()

        def _do_refresh():
            try:
                from completeness import refresh_affected_folders
                tc = _tmdb_client()
                if tc:
                    refresh_affected_folders(tc, list(changed))
            except Exception as e:
                logger.warning(f"[completeness] 自动刷新失败: {e}")

        _completeness_timer = threading.Timer(3.0, _do_refresh)
        _completeness_timer.daemon = True
        _completeness_timer.start()

config_m._on_library_save_callbacks.append(_on_library_save_refresh_completeness)

# 初始化完整度的路径快照
try:
    _completeness_prev_paths = set(v.get("file_path", "") for v in _init_lib if v.get("file_path"))
except Exception:
    pass

_sub_manager: Optional[SubscriptionManager] = None
_download_manager: Optional[DownloadManager] = None
_pan_search_service: Optional[PanSearchService] = None
_recycle_bin: Optional[RecycleBin] = None
_file_relocator: Optional[FileRelocator] = None
_bitsearch_scraper = None


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
                "rrdynb": True,      # 人人电影：搜索+详情页提取，多次请求后限频
                "ddys": True,        # 低端影视：JSON API，单次100+条
            },
            pansou_api_url="https://pansou.app",
        )
    return _pan_search_service


def _get_sub_manager() -> SubscriptionManager:
    """订阅管理器全局单例。所有调用方统一使用，避免多实例数据竞争。"""
    global _sub_manager
    if _sub_manager is None:
        _sub_manager = SubscriptionManager(
            base_path=os.path.dirname(os.path.abspath(__file__))
        )
    return _sub_manager


def _get_download_manager() -> DownloadManager:
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager(
            base_path=os.path.dirname(os.path.abspath(__file__)),
        )
        # 根据已安装插件注册下载后端
        _register_download_backends(_download_manager)
        _download_manager.on_startup()
    return _download_manager


def _register_download_backends(dm: DownloadManager):
    """根据已安装插件和配置注册下载后端到 DownloadManager"""
    from plugin_guard import is_plugin_installed
    conf = config_m.config

    if is_plugin_installed("download-qbittorrent") and conf.qb_url:
        try:
            from download_provider_adapter import DownloadProviderAdapter
            from provider_models import ProviderKind, ProviderMetadata
            qb_metadata = ProviderMetadata(
                id="qbittorrent", name="qBittorrent", kind=ProviderKind.DOWNLOAD,
                type="download", enabled=True, defaultEnabled=True, capabilities=["submit", "progress"],
            )
            qb_client = downloader.QBittorrentClient(conf.qb_url, conf.qb_username, conf.qb_password)
            dm.register_backend("qb", DownloadProviderAdapter(qb_metadata, lambda: qb_client))
        except Exception as e:
            logging.getLogger(__name__).error(f"[Shared] qB 后端注册失败: {e}")

    if is_plugin_installed("download-openlist") and conf.alist_url and conf.alist_token:
        try:
            from download_provider_adapter import DownloadProviderAdapter
            from provider_models import ProviderKind, ProviderMetadata
            alist_metadata = ProviderMetadata(
                id="openlist", name="OpenList", kind=ProviderKind.DOWNLOAD,
                type="download", enabled=True, defaultEnabled=True, capabilities=["submit", "progress"],
            )
            alist_client = downloader.AlistManager(conf.alist_url, conf.alist_token)
            dm.register_backend("alist", DownloadProviderAdapter(alist_metadata, lambda: alist_client))
        except Exception as e:
            logging.getLogger(__name__).error(f"[Shared] Alist 后端注册失败: {e}")


def _get_recycle_bin() -> RecycleBin:
    global _recycle_bin
    if _recycle_bin is None:
        conf = config_m.config
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        recycle_dir = (conf.recycle_bin_path or "").strip()
        _recycle_bin = RecycleBin(
            recycle_dir=recycle_dir,
            retention_days=conf.recycle_bin_retention_days,
            library_roots=conf.nas_paths,
            meta_path=os.path.join(backend_dir, "recycle_bin.json"),
        )
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


def _get_bitsearch_scraper():
    """懒加载 Bitsearch BT 搜索爬虫。"""
    global _bitsearch_scraper
    if _bitsearch_scraper is None:
        from bt_scraper_bitsearch import BitsearchScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("bitsearch")
        _bitsearch_scraper = BitsearchScraper(proxy=proxy)
    return _bitsearch_scraper


_cilixiong_scraper = None
_xl720_scraper = None
_nyaa_scraper = None


def _get_cilixiong_scraper():
    """懒加载磁力熊 BT 搜索爬虫。"""
    global _cilixiong_scraper
    if _cilixiong_scraper is None:
        from bt_scraper_cilixiong import CilixiongScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("cilixiong")
        _cilixiong_scraper = CilixiongScraper(proxy=proxy)
    return _cilixiong_scraper


def _get_xl720_scraper():
    """懒加载 XL720 BT 搜索爬虫。"""
    global _xl720_scraper
    if _xl720_scraper is None:
        from bt_scraper_xl720 import XL720Scraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("xl720")
        _xl720_scraper = XL720Scraper(proxy=proxy)
    return _xl720_scraper


def _get_nyaa_scraper():
    """懒加载 Nyaa BT 搜索爬虫。"""
    global _nyaa_scraper
    if _nyaa_scraper is None:
        from bt_scraper_nyaa import NyaaScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("nyaa")
        _nyaa_scraper = NyaaScraper(proxy=proxy)
    return _nyaa_scraper


_mikan_scraper = None


def _get_mikan_scraper():
    """懒加载蜜柑计划 BT 搜索爬虫。"""
    global _mikan_scraper
    if _mikan_scraper is None:
        from bt_scraper_mikan import MikanScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("mikan")
        _mikan_scraper = MikanScraper(proxy=proxy)
    return _mikan_scraper


def _tmdb_client():
    """统一创建 MetadataService（包装 TMDBClient），自动带 proxy"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        return None
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return metadata_service.MetadataService(client)


# ── 新增直搜源 getter ──

_yts_scraper = None
_limetorrents_scraper = None
_acgrip_scraper = None
_bangumi_moe_scraper = None
_eztv_scraper = None
_dmhy_scraper = None
_x1337x_scraper = None


def _get_yts_scraper():
    """懒加载 YTS BT 搜索爬虫（需代理）。"""
    global _yts_scraper
    if _yts_scraper is None:
        from bt_scraper_yts import YTSScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("yts")
        _yts_scraper = YTSScraper(proxy=proxy)
    return _yts_scraper


def _get_limetorrents_scraper():
    """懒加载 LimeTorrents BT 搜索爬虫（需代理）。"""
    global _limetorrents_scraper
    if _limetorrents_scraper is None:
        from bt_scraper_limetorrents import LimeTorrentsScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("limetorrents")
        _limetorrents_scraper = LimeTorrentsScraper(proxy=proxy)
    return _limetorrents_scraper


def _get_acgrip_scraper():
    """懒加载 ACG.RIP BT 搜索爬虫（国内可直连）。"""
    global _acgrip_scraper
    if _acgrip_scraper is None:
        from bt_scraper_acgrip import ACGRipScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("acgrip")
        _acgrip_scraper = ACGRipScraper(proxy=proxy)
    return _acgrip_scraper


def _get_bangumi_moe_scraper():
    """懒加载 Bangumi Moe BT 搜索爬虫（国内可直连）。"""
    global _bangumi_moe_scraper
    if _bangumi_moe_scraper is None:
        from bt_scraper_bangumi_moe import BangumiMoeScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("bangumi_moe")
        _bangumi_moe_scraper = BangumiMoeScraper(proxy=proxy)
    return _bangumi_moe_scraper


def _get_eztv_scraper():
    """懒加载 EZTV BT 搜索爬虫（需代理）。"""
    global _eztv_scraper
    if _eztv_scraper is None:
        from bt_scraper_eztv import EZTVScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("eztv")
        _eztv_scraper = EZTVScraper(proxy=proxy)
    return _eztv_scraper


def _get_dmhy_scraper():
    """懒加载动漫花园 BT 搜索爬虫（需代理）。"""
    global _dmhy_scraper
    if _dmhy_scraper is None:
        from bt_scraper_dmhy import DMHYScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("dmhy")
        _dmhy_scraper = DMHYScraper(proxy=proxy)
    return _dmhy_scraper


def _get_1337x_scraper():
    """懒加载 1337x BT 搜索爬虫（需代理）。"""
    global _x1337x_scraper
    if _x1337x_scraper is None:
        from bt_scraper_1337x import X1337xScraper
        from search_service import get_source_proxy
        proxy = get_source_proxy("1337x")
        _x1337x_scraper = X1337xScraper(proxy=proxy)
    return _x1337x_scraper


def get_clients():
    """动态实例化客户端（由配置驱动）"""
    conf = config_m.config
    raw_tmdb = tmdb_client.TMDBClient(conf.tmdb_api_key, proxy=getattr(conf, 'http_proxy', '') or '')
    return {
        "search": searcher.ProwlarrClient(conf.prowlarr_url, conf.prowlarr_api_key),
        "tmdb": metadata_service.MetadataService(raw_tmdb),
        "qb": downloader.QBittorrentClient(conf.qb_url, username=conf.qb_username, password=conf.qb_password),
        "alist": downloader.AlistManager(conf.alist_url, conf.alist_token),
        "netdisk": searcher.NetdiskSearcher()
    }


# ── 共享辅助函数 ──

def _get_category_from_path(path: str) -> str:
    """从文件路径推断一级分类标签（movie/tv）"""
    base = config_m.config.nas_paths[0] if config_m.config.nas_paths else ""
    configured_tags = config_m.config.category_tags or {}
    norm_path = os.path.normpath(path)

    if base:
        norm_base = os.path.normpath(base)
        if norm_path.startswith(norm_base):
            rel = os.path.relpath(norm_path, norm_base)
            parts = rel.split(os.sep)
            if parts and parts[0] != ".":
                category_dir_name = parts[0]
                category_dir_path = os.path.join(base, category_dir_name)
                if category_dir_path in configured_tags:
                    return configured_tags[category_dir_path]
                return organizer.infer_category_tag(category_dir_name)

    # 影子副本等非正式库路径：按路径分段回收已知一级分类名
    configured_names = {
        os.path.basename(os.path.normpath(category_dir_path)): tag
        for category_dir_path, tag in configured_tags.items()
    }
    for part in norm_path.split(os.sep):
        clean_part = part.strip()
        if not clean_part:
            continue
        if clean_part in configured_names:
            return configured_names[clean_part]
        inferred = organizer.infer_category_tag(clean_part)
        if inferred != "movie":
            return inferred
    return ""


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


# ── 名称可信度优先级 ──

# 统一优先级表：manual > nfo > tmdb = douban = bangumi > scrape > parsed > ""
NAME_SOURCE_PRIORITY = {
    "manual": 4,
    "nfo": 3,
    "tmdb": 3,
    "douban": 2,
    "bangumi": 2,
    "scrape": 2,
    "parsed": 1,
    "": 0,
}


def safe_set_clean_name(item: dict, new_name: str, source: str) -> bool:
    """安全设置 clean_name，低优先级不覆盖高优先级。
    返回 True 表示设置成功，False 表示被拒绝。"""
    if not new_name:
        return False
    existing_source = item.get("clean_name_source", "")
    existing_priority = NAME_SOURCE_PRIORITY.get(existing_source, 0)
    new_priority = NAME_SOURCE_PRIORITY.get(source, 0)
    if existing_priority > new_priority:
        return False
    item["clean_name"] = new_name
    item["clean_name_source"] = source
    return True


def _update_clean_names_after_scrape(path: str, scrape_result: dict):
    """刮削成功后，用刮削结果更新 clean_name（受优先级保护）"""
    try:
        self_data = scrape_result.get("self", {}).get("data") or {}
        title = self_data.get("title", "")
        if not title:
            return
        from clean_name_system import clean_from_scrape, safe_update_clean_name
        # 提取刮削结果的多语言信息
        original_title = self_data.get("original_title", "")
        english_title = self_data.get("english_title", "")
        year = self_data.get("year", "")

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
                    result = clean_from_scrape(
                        title=title,
                        original_title=original_title,
                        english_title=english_title,
                        year=year,
                        filename=v.get("file_name", ""),
                        source="scrape",
                    )
                    if safe_update_clean_name(v, result):
                        changed = True
        if changed:
            config_m.save_library(library)
    except Exception:
        pass
