"""
路由模块：library_completeness
从 library_crud.py 拆分 — 季集完整度（TMDB 差集）

拆分原因：library_crud.py 越过 400 行红线，而完整度是一个自洽的功能域，
和媒体库 CRUD 没有共享状态。
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException

from shared import config_m, _tmdb_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/library/completeness")
def get_completeness(path: str, tmdb_id: Optional[int] = None, refresh: bool = False):
    """获取 TV 文件夹的季集完整度（基于 TMDB 数据源）"""
    from plugin_guard import is_feature_allowed, is_metadata_allowed
    if not is_feature_allowed("completeness"):
        return {"status": "plugin_not_installed", "message": "请先安装「季集完整性检测」插件"}
    if not is_metadata_allowed("tmdb"):
        return {"status": "metadata_plugin_not_installed", "message": "请先安装「TMDB 元数据」插件"}

    from completeness import (
        collect_local_episodes, get_tmdb_id_from_folder, compute_completeness,
        get_cached_completeness, save_completeness_to_cache, refresh_completeness_for_path,
    )

    if not path:
        raise HTTPException(400, "缺少 path 参数")

    logger.info(f"[completeness] API 请求: path={path}, refresh={refresh}, tmdb_id={tmdb_id}")

    if not refresh:
        cached = get_cached_completeness(path)
        if cached and cached.get("status") == "ok":
            logger.info(f"[completeness] 返回缓存: {cached.get('completeness_pct')}%")
            return cached

    tid = tmdb_id
    if not tid:
        tid = get_tmdb_id_from_folder(path)
    if not tid:
        logger.warning(f"[completeness] 无 TMDB ID: {path}")
        return {"status": "no_tmdb_id", "message": "未找到 TMDB ID，请先刮削此文件夹"}

    tc = _tmdb_client()
    if not tc:
        return {"status": "no_tmdb_client", "message": "TMDB 未配置"}

    logger.info(f"[completeness] 重新计算: tmdb_id={tid}, refresh={refresh}")
    result = refresh_completeness_for_path(tc, path, clear_tmdb_cache=refresh)
    if result:
        logger.info(f"[completeness] 计算完成: {result.get('completeness_pct')}%, local={result.get('local_total')}")
        return result

    logger.info(f"[completeness] 兜底计算")
    local_episodes = collect_local_episodes(path)
    result = compute_completeness(tc, tid, local_episodes)
    if result.get("status") == "ok":
        save_completeness_to_cache(path, result)
    return result


@router.post("/library/completeness/refresh-all")
def refresh_all_completeness():
    """批量预计算所有 TV 文件夹的完整度（后台运行）"""
    import plugin_guard
    from completeness import batch_refresh_all

    if not plugin_guard.is_feature_allowed("completeness"):
        return {"status": "plugin_not_installed", "message": "请先安装「季集完整性检测」插件"}
    if not plugin_guard.is_metadata_allowed("tmdb"):
        return {"status": "metadata_plugin_not_installed", "message": "请先安装「TMDB 元数据」插件"}

    tc = _tmdb_client()
    if not tc:
        return {"status": "error", "message": "TMDB 未配置"}

    nas_paths = config_m.config.scan_paths or []
    category_tags = config_m.config.category_tags or {}

    def _run():
        try:
            if not plugin_guard.is_feature_allowed("completeness") or not plugin_guard.is_metadata_allowed("tmdb"):
                return
            batch_refresh_all(tc, nas_paths, category_tags)
        except Exception as e:
            logger.error(f"[completeness] 批量预计算异常: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "started", "message": "批量预计算已启动，请查看后端日志"}
