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

from core import path_guard

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
shadow_m = ShadowNameManager(config_manager=config_m)
indexer_m = IndexerPriorityManager(config_path=config_m.config_path)
indexer_m.load()
torrent_bl = TorrentBlacklist(path=os.path.join(config_m.data_dir, "torrent_blacklist.json"))
analysis_cache = AnalysisCache(path=os.path.join(config_m.data_dir, "analysis_cache.json"))
media_matcher = LocalMediaMatcher()

# 启动时构建媒体库索引
try:
    _init_lib = config_m.load_library()
    media_matcher.build_index(_init_lib)
except Exception as _e:
    logger.error(f"[Shared] 媒体库索引构建失败: {_e}")

# 注册回调：save_library 后仅在插件启用时刷新索引
def _refresh_media_match_index(library: list):
    import plugin_guard

    if plugin_guard.is_feature_allowed("local_match"):
        media_matcher.build_index(library)


config_m._on_library_save_callbacks.append(_refresh_media_match_index)

# 注册回调：save_library 后延迟刷新受影响的 TV 文件夹完整度
_completeness_prev_paths: set = set()
_completeness_timer = None
_completeness_lock = threading.Lock()

def _on_library_save_refresh_completeness(library: list):
    """save_library 回调：对比新旧库数据，找出变更的文件路径，延迟刷新完整度"""
    global _completeness_prev_paths, _completeness_timer
    import plugin_guard

    if not plugin_guard.is_feature_allowed("completeness"):
        return

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
                import plugin_guard

                if not plugin_guard.is_feature_allowed("completeness") or not plugin_guard.is_metadata_allowed("tmdb"):
                    return
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
finally:
    # media_matcher 已构建自己的索引，完整度也只需要路径集合；继续保留原始媒体库
    # list 会让同一批数据以“原始 JSON 对象 + 多套索引”重复常驻内存。
    try:
        del _init_lib
    except NameError:
        pass

_sub_manager: Optional[SubscriptionManager] = None
_download_manager: Optional[DownloadManager] = None
_pan_search_service: Optional[PanSearchService] = None
_recycle_bin: Optional[RecycleBin] = None
_file_relocator: Optional[FileRelocator] = None


def _get_pan_search_service() -> PanSearchService:
    global _pan_search_service
    if _pan_search_service is None:
        # 根据已安装插件过滤可用的网盘源
        from plugin_guard import get_allowed_pan_sources
        allowed = get_allowed_pan_sources()
        sources = {name: (name in allowed) for name in [
            "pansearch", "pansou", "gogopanso", "github",
            "sites", "slowread", "wnsearch", "rrdynb", "ddys",
        ]}
        _pan_search_service = PanSearchService(
            search_sources=sources,
            pansou_api_url="https://pansou.app",
            scraper_proxy=config_m.config.http_proxy or "",
        )
    return _pan_search_service


def reset_pan_search_service():
    """插件安装/卸载后重置网盘搜索服务单例"""
    global _pan_search_service
    _pan_search_service = None


def refresh_download_backends() -> bool:
    """插件安装/卸载后原子刷新下载后端，不要求重启后端。"""
    if _download_manager is None:
        return True
    backends, failed_channels = _build_download_backends()
    if failed_channels:
        previous = _download_manager.get_backends_snapshot()
        for channel in failed_channels:
            if channel in previous:
                backends[channel] = previous[channel]
        logger.warning(
            f"[Shared] 下载后端部分刷新失败，已保留仍安装通道的旧实例: {sorted(failed_channels)}"
        )
    _download_manager.replace_backends(backends)
    return not failed_channels


def _get_sub_manager() -> SubscriptionManager:
    """订阅管理器全局单例。所有调用方统一使用，避免多实例数据竞争。"""
    global _sub_manager
    if _sub_manager is None:
        _sub_manager = SubscriptionManager(
            base_path=config_m.data_dir
        )
    return _sub_manager


def _get_download_manager() -> DownloadManager:
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager(
            base_path=config_m.data_dir,
        )
        # 根据已安装插件注册下载后端
        _register_download_backends(_download_manager)
        _download_manager.on_startup()
    return _download_manager


def _build_download_backends() -> tuple[Dict[str, object], set[str]]:
    """根据已安装插件和配置构建下载后端，不修改正在使用的实例。"""
    from download_provider_adapter import DownloadProviderAdapter
    from plugin_guard import is_plugin_installed
    from provider_models import ProviderKind, ProviderMetadata

    conf = config_m.config
    backends: Dict[str, object] = {}
    failed_channels: set[str] = set()

    if is_plugin_installed("download-qbittorrent") and conf.qb_url:
        try:
            qb_metadata = ProviderMetadata(
                id="qbittorrent", name="qBittorrent", kind=ProviderKind.DOWNLOAD,
                type="download", enabled=True, defaultEnabled=True, capabilities=["submit", "progress"],
            )
            qb_client = downloader.QBittorrentClient(conf.qb_url, conf.qb_username, conf.qb_password)
            backends["qb"] = DownloadProviderAdapter(qb_metadata, lambda: qb_client)
        except Exception as e:
            failed_channels.add("qb")
            logger.error(f"[Shared] qB 后端构建失败: {e}")

    if is_plugin_installed("download-openlist") and conf.alist_url and conf.alist_token:
        try:
            alist_metadata = ProviderMetadata(
                id="openlist", name="OpenList", kind=ProviderKind.DOWNLOAD,
                type="download", enabled=True, defaultEnabled=True, capabilities=["submit", "progress"],
            )
            alist_client = downloader.AlistManager(conf.alist_url, conf.alist_token)
            backends["alist"] = DownloadProviderAdapter(alist_metadata, lambda: alist_client)
        except Exception as e:
            failed_channels.add("alist")
            logger.error(f"[Shared] Alist 后端构建失败: {e}")

    return backends, failed_channels


def _register_download_backends(dm: DownloadManager):
    """初始化 DownloadManager 的插件下载后端。"""
    backends, _ = _build_download_backends()
    dm.replace_backends(backends)


def _get_recycle_bin() -> RecycleBin:
    global _recycle_bin
    if _recycle_bin is None:
        conf = config_m.config
        recycle_dir = (conf.recycle_bin_path or "").strip()
        _recycle_bin = RecycleBin(
            recycle_dir=recycle_dir,
            retention_days=conf.recycle_bin_retention_days,
            library_roots=conf.scan_paths,
            meta_path=os.path.join(config_m.data_dir, "recycle_bin.json"),
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


def _tmdb_client():
    """统一创建 MetadataService（包装 TMDBClient），自动带 proxy。"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("tmdb"):
        return None
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        return None
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, "http_proxy", "") or "")
    return metadata_service.MetadataService(client)


def get_clients():
    """动态实例化客户端（由配置和插件安装状态驱动）。"""
    conf = config_m.config
    tmdb = _tmdb_client()
    return {
        "search": searcher.ProwlarrClient(conf.prowlarr_url, conf.prowlarr_api_key),
        "tmdb": tmdb,
        "qb": downloader.QBittorrentClient(conf.qb_url, username=conf.qb_username, password=conf.qb_password),
        "alist": downloader.AlistManager(conf.alist_url, conf.alist_token),
        "netdisk": searcher.NetdiskSearcher()
    }


# ── 共享辅助函数 ──

def _get_category_from_path(path: str) -> str:
    """从文件路径推断一级分类标签（movie/tv）"""
    base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
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
    """判断 path 是否是扫描根目录的直接子目录（一级分类目录）"""
    base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
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
    def _apply(library):
        changed = False
        for op in ops:
            if op.get("action") == "move" and op.get("old") and op.get("new"):
                for v in library:
                    if v.get("file_path") == op["old"]:
                        v["file_path"] = op["new"]
                        base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
                        if base:
                            rel = os.path.relpath(os.path.dirname(op["new"]), base)
                            v["folder_name"] = "" if rel == "." else rel
                        changed = True
        return None if changed else False

    config_m.mutate_library(_apply)


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

        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        norm_path = os.path.normpath(path)

        def _apply(library):
            changed = False
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
            return None if changed else False

        config_m.mutate_library(_apply)
    except Exception:
        pass


def is_under_path(file_path: str, base: str) -> bool:
    """file_path 是否位于 base 目录之下（或就是它本身）。

    不能直接用 `startswith(base)`：那样 `D:\\影视2\\a.mkv` 会被当成
    `D:\\影视` 的子路径。扫描 / 同步判断"这条属于哪个库"时踩过这个坑 ——
    两个名字有共同前缀的平级目录会互相误判，扫一个库会连带处理另一个库的条目。
    """
    if not file_path or not base:
        return False
    trimmed = base.rstrip("\\/")
    if file_path == trimmed:
        return True
    return file_path.startswith(trimmed + os.sep) or file_path.startswith(trimmed + "/")


# ── 路径访问白名单 ──
# 后端有大量路由接受用户传入的 path 参数后直接读写/删除文件。由于后端不做鉴权
# 且 CORS 全开，任何网页都能调用这些接口。没有白名单的话，构造一个 path 就能
# 让后端往任意位置写文件或删除任意目录。
#
# 白名单必须覆盖所有"正常功能会碰到"的路径，否则会把自己挡在外面。
# 覆盖范围见 _collect_allowed_roots 内注释。

_allowed_roots_cache: Dict[str, object] = {"roots": None, "at": 0.0}
# 白名单缓存存活时间：足够挡掉高频接口的重复组装，又能让设置页改完很快生效
_ALLOWED_ROOTS_TTL = 5.0


def _collect_allowed_roots() -> List[str]:
    """组装当前允许操作的根路径列表（带短期缓存）。

    /scrape/poster 这类接口一屏要调几十次，每次重新组装列表是浪费；
    但也不能永久缓存，否则用户在设置页改了媒体库路径后要重启才生效。
    """
    now = time.time()
    cached = _allowed_roots_cache.get("roots")
    if cached is not None and now - float(_allowed_roots_cache["at"]) < _ALLOWED_ROOTS_TTL:
        return cached  # type: ignore[return-value]

    conf = config_m.config
    roots: List[str] = []

    # 1. 媒体库根：自动识别模式的 scan_paths + 分类模式的 media_libraries
    roots.extend([p for p in (conf.scan_paths or []) if p])
    for lib in (conf.media_libraries or []):
        roots.extend([p for p in (lib.paths or []) if p])

    library_roots = list(roots)

    # 2. 回收站：显式配置的路径，以及默认位置（媒体库根的上一级 + #recycle）
    if (conf.recycle_bin_path or "").strip():
        roots.append(conf.recycle_bin_path.strip())
    for root in library_roots:
        parent = os.path.dirname(os.path.normpath(root).rstrip("\\/"))
        if parent:
            roots.append(os.path.join(parent, "#recycle"))

    # 3. 下载监控目录
    roots.extend([p for p in (conf.download_watch_dirs or []) if p])

    # 4. 后端自管目录：data_dir 覆盖 downloads/ 沙盒、organize_snapshots/ 与各 JSON
    roots.append(config_m.data_dir)

    # 5. 海报与刮削缓存：历史实现分别用了进程 CWD 和模块目录，两者都要放行
    _backend_dir = os.path.dirname(os.path.abspath(__file__))
    for base in {os.getcwd(), _backend_dir}:
        roots.append(os.path.join(base, "posters"))
        roots.append(os.path.join(base, "scrape_cache"))

    result = [r for r in roots if r]
    _allowed_roots_cache["roots"] = result
    _allowed_roots_cache["at"] = now
    return result


def invalidate_allowed_roots_cache() -> None:
    """配置变更后立即失效白名单缓存（设置页保存路径时调用）。"""
    _allowed_roots_cache["roots"] = None
    _allowed_roots_cache["at"] = 0.0


def is_path_allowed(path: str) -> bool:
    """判断路径是否落在允许操作的范围内。"""
    if not path:
        return False
    return path_guard.is_within_any(path, _collect_allowed_roots())


def guard_path(path: str, action: str = "访问") -> str:
    """校验路径合法性，非法则抛 403。合法时返回原路径便于链式调用。

    说明：这里直接抛 HTTPException 是为了让各路由一行接入。校验只加在路由层，
    不下沉到业务层 —— 业务层函数被大量单元测试以临时目录直接调用。
    """
    from fastapi import HTTPException

    if not path:
        raise HTTPException(status_code=400, detail="路径不能为空")
    if not is_path_allowed(path):
        logger.warning(f"[PathGuard] 拒绝{action}媒体库范围外的路径: {path}")
        raise HTTPException(
            status_code=403,
            detail="路径不在已配置的媒体库范围内，操作被拒绝",
        )
    return path
