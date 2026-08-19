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
    query: str = "",
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
    is_file: bool = False,
    no_muxer: bool = True,
    pos: int = 0,
    cnt: int = 15,
):
    """搜索字幕（智能回退链）。

    优先用 cn_name 搜索，无结果回退 en_name，再回退 original_name，最后用 query。
    季集号会自动拼接到搜索词中。

    参数：
    - query: 原始搜索词（兜底）
    - cn_name: 中文名
    - en_name: 英文名
    - original_name: 原始语言名
    - season_number: 季号
    - episode_number: 集号
    - is_file: 是否按文件名模式搜索
    - no_muxer: 是否忽略压制组信息（默认 True）
    """
    client = _get_client()

    # 构建回退搜索词链
    candidates = _build_search_keywords(
        cn_name=cn_name, en_name=en_name, original_name=original_name,
        query=query, season_number=season_number, episode_number=episode_number,
    )

    if not candidates:
        raise HTTPException(status_code=400, detail="搜索关键词至少 3 个字符")

    # 逐词回退搜索，找到结果就停
    results = []
    used_keyword = ""
    for kw in candidates:
        if len(kw) < 3:
            continue
        search_results, keyword = client.search(
            kw, is_file=is_file, no_muxer=no_muxer, pos=pos, cnt=cnt
        )
        if search_results:
            results = search_results
            used_keyword = keyword
            break
        used_keyword = keyword

    return SubtitleSearchResponse(
        status=True,
        keyword=used_keyword,
        total=len(results),
        results=results,
    )


def _build_search_keywords(
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    query: str = "",
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
) -> list:
    """构建字幕搜索词回退链。

    策略：
    1. 中文名（拼季集号）
    2. 中文名（不带集号，只带季号）
    3. 英文名（拼 SxxExx）
    4. 英文名（只带 Sxx）
    5. 原始名
    6. 原始 query 兜底
    """
    candidates = []
    seen = set()

    def _add(kw: str):
        kw = kw.strip()
        if kw and len(kw) >= 3 and kw.lower() not in seen:
            seen.add(kw.lower())
            candidates.append(kw)

    # 季集号构造
    se_cn = ""
    se_en = ""
    s_cn = ""
    s_en = ""
    if season_number and season_number > 0:
        s_cn = f"第{season_number}季"
        s_en = f"S{str(season_number).zfill(2)}"
        if episode_number and episode_number > 0:
            se_cn = f"第{season_number}季第{episode_number}集"
            se_en = f"S{str(season_number).zfill(2)}E{str(episode_number).zfill(2)}"

    # 中文名优先
    if cn_name:
        if se_cn:
            _add(f"{cn_name} {se_cn}")
        if s_cn:
            _add(f"{cn_name} {s_cn}")
        _add(cn_name)

    # 英文名
    if en_name:
        if se_en:
            _add(f"{en_name} {se_en}")
        if s_en:
            _add(f"{en_name} {s_en}")
        _add(en_name)

    # 原始名
    if original_name:
        _add(original_name)

    # 兜底
    if query:
        _add(query)

    return candidates


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
