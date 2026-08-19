"""字幕搜索数据模型。"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SubtitleLang(BaseModel):
    """字幕语言信息"""
    desc: str = ""
    langlist: dict = Field(default_factory=dict)


class SubtitleSearchItem(BaseModel):
    """搜索结果条目（列表级）"""
    id: int
    native_name: str = ""
    videoname: str = ""
    subtype: str = ""  # "Subrip(srt)" / "ASS" / "VobSub" 等
    upload_time: str = ""
    vote_score: int = 0
    release_site: str = ""  # 字幕组
    lang: SubtitleLang = Field(default_factory=SubtitleLang)
    revision: int = 0


class SubtitleFileItem(BaseModel):
    """压缩包内的单个字幕文件"""
    f: str = ""       # 文件名
    s: str = ""       # 文件大小（如 "52KB"）
    url: str = ""     # 单文件下载地址


class SubtitleDetail(BaseModel):
    """字幕详情（含下载链接）"""
    id: int
    native_name: str = ""
    filename: str = ""
    title: str = ""
    url: str = ""             # 压缩包下载地址
    size: int = 0             # 字节
    subtype: str = ""
    upload_time: str = ""
    vote_score: int = 0
    release_site: str = ""
    lang: SubtitleLang = Field(default_factory=SubtitleLang)
    filelist: List[SubtitleFileItem] = Field(default_factory=list)
    down_count: int = 0
    view_count: int = 0


# ── 前端请求/响应 DTO ──

class SubtitleSearchRequest(BaseModel):
    """前端搜索请求参数"""
    query: str
    is_file: bool = False     # 是否按文件名搜索
    no_muxer: bool = False    # 是否忽略压制组信息


class SubtitleDownloadRequest(BaseModel):
    """前端下载请求参数"""
    subtitle_id: int                  # assrt 字幕 ID
    video_path: str                   # 视频文件完整路径（用于命名和定位目录）
    file_url: Optional[str] = None    # 如果指定了 filelist 中的单文件 URL
    language_suffix: str = ""         # 语言后缀，如 "chs"、"cht"、"eng"


class SubtitleSearchResponse(BaseModel):
    """搜索响应"""
    status: bool = True
    keyword: str = ""
    total: int = 0
    results: List[SubtitleSearchItem] = Field(default_factory=list)


class SubtitleDetailResponse(BaseModel):
    """详情响应"""
    status: bool = True
    detail: Optional[SubtitleDetail] = None
