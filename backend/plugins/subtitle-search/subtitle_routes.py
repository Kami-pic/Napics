"""字幕搜索与下载路由。

- GET  /subtitle/search   — 三源并发搜索（assrt + SubHD + SubDL）
- GET  /subtitle/detail   — 字幕详情（assrt 专有，含压缩包文件列表）
- POST /subtitle/download — 下载字幕到视频同目录
- GET  /subtitle/sources  — 各源配置状态
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import subtitle_search_service as service
from subtitle_models import (
    SubtitleDetailResponse,
    SubtitleDownloadRequest,
    SubtitleSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subtitle", tags=["subtitle"])


# ── 搜索 ──

@router.get("/search", response_model=SubtitleSearchResponse)
async def search_subtitles(
    query: str = "",
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    folder_type: str = "",
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
    episode_tag: str = "",
    is_file: bool = False,
    no_muxer: bool = True,
    cnt: int = 15,
):
    """三源并发搜索字幕。

    搜索词规则与「搜索升级」一致：中文 / 中文+英文 / 英文 三类变体，
    季集号按语言拼接。各源按自身语言偏好走回退链（中文源 cn 优先，SubDL en 优先）。
    """
    results, sources, keyword = service.search_all_sources(
        query=query,
        cn_name=cn_name,
        en_name=en_name,
        original_name=original_name,
        folder_type=folder_type,
        season_number=season_number,
        episode_number=episode_number,
        episode_tag=episode_tag,
        is_file=is_file,
        no_muxer=no_muxer,
        cnt=cnt,
    )

    if not keyword:
        raise HTTPException(status_code=400, detail="请提供影片名称或搜索关键词")

    return SubtitleSearchResponse(
        status=True,
        keyword=keyword,
        total=len(results),
        results=results,
        sources=sources,
    )


# ── 源状态 ──

class SourceStatus(BaseModel):
    id: str
    name: str
    configured: bool
    requires_config: str = ""


@router.get("/sources", response_model=List[SourceStatus])
async def list_sources():
    """返回各字幕源的可用状态，供前端提示缺失配置"""
    return [
        SourceStatus(
            id="assrt",
            name="射手网(伪)",
            configured=service.get_assrt_client() is not None,
            requires_config="assrt_token",
        ),
        SourceStatus(
            id="subhd",
            name="SubHD",
            configured=service.get_subhd_client() is not None,
        ),
        SourceStatus(
            id="subdl",
            name="SubDL",
            configured=service.get_subdl_client() is not None,
            requires_config="subdl_api_key",
        ),
    ]


# ── 详情（assrt 专有）──

@router.get("/detail", response_model=SubtitleDetailResponse)
async def get_subtitle_detail(subtitle_id: int):
    """获取 assrt 字幕详情（含下载链接和压缩包内文件列表）"""
    client = service.get_assrt_client()
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 assrt_token")

    detail = client.detail(subtitle_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="字幕不存在或服务暂时不可用")

    return SubtitleDetailResponse(status=True, detail=detail)


# ── 下载 ──

class DownloadResponse(BaseModel):
    status: bool = True
    saved_files: List[str] = []
    message: str = ""


@router.post("/download", response_model=DownloadResponse)
async def download_subtitle(req: SubtitleDownloadRequest):
    """下载字幕到视频同目录，文件名与视频一致"""
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=400, detail=f"视频文件不存在: {req.video_path}")

    saved_files, error = service.download_subtitle(
        source=req.source or "assrt",
        subtitle_id=req.subtitle_id,
        video_path=req.video_path,
        file_url=req.file_url or "",
        language_suffix=req.language_suffix,
        slug=req.slug,
    )

    if error:
        return DownloadResponse(status=False, message=error)
    if not saved_files:
        return DownloadResponse(status=False, message="下载失败，请重试")

    return DownloadResponse(
        status=True,
        saved_files=saved_files,
        message=f"已保存 {len(saved_files)} 个字幕文件",
    )
