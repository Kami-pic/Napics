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
    # 来源标识："assrt" | "subhd" | "subdl"
    source: str = "assrt"
    # 直链下载地址（SubDL 直接给出；assrt 需二次请求详情，此处为空）
    download_url: str = ""
    # 非数字 ID 的源用它承载真实标识（SubHD 是 /a/{slug} 形式的字母数字 slug）
    slug: str = ""
    # 命中该结果的搜索词（用于前端回显）
    hit_keyword: str = ""
    # 文件大小展示串（如 "223k"）
    file_size: str = ""
    # 相关性匹配分（0-100，复用 L2 匹配链）
    match_score: int = 0
    # 智能过滤标记
    is_junk: bool = False
    junk_reasons: List[str] = Field(default_factory=list)


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

class SubtitleDownloadRequest(BaseModel):
    """前端下载请求参数"""
    subtitle_id: int = 0              # 字幕 ID（assrt 为真实 ID，其他源为哈希 ID）
    video_path: str = ""              # 视频文件完整路径（用于命名和定位目录）
    file_url: Optional[str] = None    # 直链（SubDL/详情文件列表给出时直接用）
    language_suffix: str = ""         # 语言后缀，如 "chs"、"cht"、"eng"
    source: str = "assrt"             # 来源标识，决定用哪条下载路径
    slug: str = ""                    # SubHD 的字母数字标识


class SubtitleSourceStat(BaseModel):
    """单个源的搜索情况（供前端回显搜了哪些词）"""
    source: str
    searched_keywords: List[str] = Field(default_factory=list)
    hit_keyword: str = ""
    count: int = 0
    error: str = ""


class SubtitleSearchResponse(BaseModel):
    """搜索响应"""
    status: bool = True
    keyword: str = ""
    total: int = 0
    results: List[SubtitleSearchItem] = Field(default_factory=list)
    sources: List[SubtitleSourceStat] = Field(default_factory=list)


class SubtitleDetailResponse(BaseModel):
    """详情响应"""
    status: bool = True
    detail: Optional[SubtitleDetail] = None
