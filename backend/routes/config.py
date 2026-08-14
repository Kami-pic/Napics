"""
路由模块：config
"""
import os
import json
import logging
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
    invalidate_allowed_roots_cache,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/config")
def get_config():
    return config_m.config

@router.get("/cache/info")
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

@router.post("/cache/clear")
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

@router.get("/no-scrape")
def get_no_scrape():
    return list(config_m.load_no_scrape())

@router.post("/no-scrape")
def set_no_scrape(path: str, enabled: bool = True):
    config_m.set_no_scrape(path, enabled)
    # 递归：对目录下所有子目录也设置
    if os.path.isdir(path):
        for dirpath, dirnames, _ in os.walk(path):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for d in dirnames:
                config_m.set_no_scrape(os.path.join(dirpath, d), enabled)
    return {"status": "ok", "path": path, "no_scrape": enabled}

@router.post("/config")
def update_config(conf: config_manager.AppConfig):
    config_m.save(conf)
    # 保存后失效路径白名单缓存，让新配置的媒体库路径立即生效
    invalidate_allowed_roots_cache()

    # 校验配置的媒体库路径在后端进程里是否真实可见。
    # Docker 部署最常见的翻车点：填了宿主机路径，但容器里并没有挂载该路径，
    # 于是扫描永远扫不到东西又不报错。这里把无效路径回给前端，便于提示用户。
    unreachable = []
    for p in (conf.scan_paths or []):
        if p and not os.path.isdir(p):
            unreachable.append(p)
    for lib in (conf.media_libraries or []):
        for p in (lib.paths or []):
            if p and not os.path.isdir(p):
                unreachable.append(p)

    if unreachable:
        logger.warning(
            f"[Config] 以下媒体库路径在后端不可访问，扫描将扫不到内容: {unreachable}"
            "（Docker 部署时请确认该路径已挂载进容器，且容器内路径与此处填写的一致）"
        )
        return {
            "message": "Success",
            "unreachable_paths": unreachable,
            "warning": "以下路径无法访问，扫描将没有结果。Docker 部署请确认该目录已挂载进容器，"
                       "并且容器内路径与填写的路径一致。",
        }

    return {"message": "Success"}


# 说明：原 /config/browse-folder 已移除。
# 它在服务端弹出系统对话框（Windows 走 PowerShell，其他平台走 tkinter），
# 只有"后端跑在用户自己的桌面上"才成立；Docker 容器与 NAS 上都无法弹窗。
# 现由 routes/filesystem.py 的 /fs/list 提供目录列举，前端渲染网页版选择器，
# 所有平台统一。


# ── 搜索过滤规则配置 API ──

@router.get("/config/search-filter")
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

@router.post("/config/search-filter")
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

@router.post("/backup")
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

@router.post("/restore")
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

@router.get("/no-scrape")
def get_no_scrape_list():
    """获取不刮削列表"""
    return config_m.load_no_scrape()

@router.get("/config/sort-weights")
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

@router.post("/config/sort-weights")
def save_sort_weights(req: SortWeightsUpdateRequest):
    """保存种子排序权重配置"""
    conf = config_m.config
    conf.sort_weights = config_manager.SortWeightsConfig(**req.dict())
    config_m.save(conf)
    return {"status": "ok"}


# ── 种子黑名单 ──


# ── License Key 授权管理 ──


class LicenseKeyRequest(BaseModel):
    license_key: str


@router.get("/config/license")
def get_license_status():
    """获取当前 License 授权状态（本地读取，不联网）"""
    conf = config_m.config
    return {
        "license_key": conf.license_key[:8] + "..." if len(conf.license_key) > 8 else conf.license_key,
        "status": conf.license_status,
        "email": conf.license_email,
        "plan": conf.license_plan,
        "validated_at": conf.license_validated_at,
        "is_pro": conf.license_status == "valid" and bool(conf.license_key),
    }


@router.post("/config/license/validate")
def validate_license(req: LicenseKeyRequest):
    """验证并激活 License Key（联网验证）"""
    from license_service import validate_license_key, activate_license_key, save_license_to_config

    key = req.license_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail={"error": "empty_key", "message": "License Key 不能为空"})

    # 先尝试验证
    info = validate_license_key(key)

    # 如果验证失败且不是"已过期"，尝试激活（首次使用）
    if not info.valid and info.status != "expired":
        info = activate_license_key(key)

    if info.valid:
        save_license_to_config(config_m, info, key)
        return {
            "success": True,
            "status": info.status,
            "email": info.email,
            "plan": info.plan,
            "product_name": info.product_name,
            "message": "授权验证成功",
        }
    else:
        return {
            "success": False,
            "status": info.status,
            "error": info.error or "验证失败",
            "message": info.error or "License Key 无效或已过期",
        }


@router.post("/config/license/clear")
def clear_license():
    """清除 License Key 授权"""
    from license_service import clear_license_from_config
    clear_license_from_config(config_m)
    return {"success": True, "message": "已清除授权信息"}
