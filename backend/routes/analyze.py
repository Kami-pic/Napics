"""
路由模块：analyze — 分析诊断
从 routes/organize.py 拆分而来
"""
import os
from fastapi import APIRouter, HTTPException

from shared import (
    config_m, _tmdb_client, get_clients,
    _get_category_from_path,
)
import organizer, analyzer

router = APIRouter()


@router.get("/analyze/folder")
def analyze_folder_api(path: str, enhanced: bool = False):
    """分析单个文件夹，返回完整诊断报告
    enhanced=True 时用 TMDB 增强改名预览
    """
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_folder(path, library, client, category_hint=_get_category_from_path(path))

@router.get("/analyze/library")
def analyze_library_api(enhanced: bool = False):
    """分析整个媒体库"""
    config = config_m.config
    base_path = config.nas_paths[0] if config.nas_paths else config.nas_path if config.nas_path else ""
    if not base_path or not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail="NAS path not configured or not accessible")
    library = config_m.load_library()
    client = _tmdb_client() if enhanced else None
    return analyzer.analyze_library(base_path, library, client)

@router.get("/organize/classify")
def classify_path(path: str):
    """判断文件夹类型"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Not a directory")
    library = config_m.load_library()
    # 从路径推断一级分类名
    category_hint = _get_category_from_path(path)
    return organizer.classify_folder(path, library, category_hint=category_hint)
