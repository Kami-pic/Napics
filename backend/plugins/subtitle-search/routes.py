"""字幕搜索与下载路由。

提供：
- GET  /subtitle/search  — 搜索字幕
- GET  /subtitle/detail  — 获取字幕详情（含下载链接和文件列表）
- POST /subtitle/download — 下载字幕到视频同目录
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from assrt_client import AssrtClient
from subtitle_models import (
    SubtitleDetailResponse,
    SubtitleDownloadRequest,
    SubtitleSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subtitle", tags=["subtitle"])

# 客户端单例（由 __init__.py 初始化后注入）
_client: Optional[AssrtClient] = None


def set_client(client: AssrtClient):
    """由插件注册时调用，注入 assrt 客户端实例"""
    global _client
    _client = client


def _get_client() -> AssrtClient:
    if _client is None:
        raise HTTPException(status_code=503, detail="字幕搜索服务未初始化，请检查 assrt_token 配置")
    return _client


# ── 搜索 ──

@router.get("/search", response_model=SubtitleSearchResponse)
async def search_subtitles(
    query: str,
    is_file: bool = False,
    no_muxer: bool = False,
    pos: int = 0,
    cnt: int = 15,
):
    """搜索字幕。

    参数：
    - query: 搜索关键词（影片名称或文件名）
    - is_file: 是否按文件名模式搜索（忽略分辨率等技术参数）
    - no_muxer: 是否忽略压制组信息
    - pos: 分页起始位置
    - cnt: 返回数量（最大 15）
    """
    if len(query) < 3:
        raise HTTPException(status_code=400, detail="搜索关键词至少 3 个字符")

    client = _get_client()
    results, keyword = client.search(
        query, is_file=is_file, no_muxer=no_muxer, pos=pos, cnt=cnt
    )

    return SubtitleSearchResponse(
        status=True,
        keyword=keyword,
        total=len(results),
        results=results,
    )


# ── 详情 ──

@router.get("/detail", response_model=SubtitleDetailResponse)
async def get_subtitle_detail(subtitle_id: int):
    """获取字幕详情（含下载链接和文件列表）。

    参数：
    - subtitle_id: assrt 字幕 ID
    """
    client = _get_client()
    detail = client.detail(subtitle_id)
    if not detail:
        raise HTTPException(status_code=404, detail="字幕不存在或服务暂时不可用")

    return SubtitleDetailResponse(status=True, detail=detail)


# ── 下载 ──

class DownloadResponse(BaseModel):
    status: bool = True
    saved_files: list = []
    message: str = ""


@router.post("/download", response_model=DownloadResponse)
async def download_subtitle(req: SubtitleDownloadRequest):
    """下载字幕到视频同目录。

    流程：
    1. 如果提供了 file_url，直接下载该单文件
    2. 否则通过 subtitle_id 获取详情，取 url（压缩包）或 filelist 中第一个文件
    3. 下载后自动重命名为 "视频名.语言后缀.扩展名" 格式
    """
    client = _get_client()

    # 验证视频路径存在
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=400, detail=f"视频文件不存在: {req.video_path}")

    # 确定下载地址
    download_url = req.file_url
    if not download_url:
        detail = client.detail(req.subtitle_id)
        if not detail:
            raise HTTPException(status_code=404, detail="无法获取字幕详情")

        # 优先用 filelist 中的单文件（避免下载整个 zip）
        if detail.filelist:
            download_url = detail.filelist[0].url
        elif detail.url:
            download_url = detail.url
        else:
            raise HTTPException(status_code=404, detail="字幕无下载链接")

    # 执行下载
    saved_files = client.download_subtitle(
        download_url=download_url,
        video_path=req.video_path,
        language_suffix=req.language_suffix,
    )

    if not saved_files:
        return DownloadResponse(status=False, message="下载失败，请重试")

    return DownloadResponse(
        status=True,
        saved_files=saved_files,
        message=f"已保存 {len(saved_files)} 个字幕文件",
    )
