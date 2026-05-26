"""RSS 源基类：定义标准化接口，所有源实现此接口即可接入订阅框架。

新增源只需：
1. 继承 RSSSourceBase，实现 fetch()
2. 在 rss_engine.py 的 RSSSourceManager 中注册
"""

import re
from typing import List, Optional
from pydantic import BaseModel


class RSSItem(BaseModel):
    """RSS 条目标准化结构（所有源输出统一格式）"""
    title: str = ""
    download_url: str = ""       # 种子/磁力链接（可直接下载）
    info_url: str = ""           # 详情页链接
    pub_date: str = ""           # 发布时间
    size_gb: float = 0.0
    info_hash: str = ""          # 种子哈希（去重用）
    quality_tag: str = ""        # 质量标签（如 "WEB-DL-1080p-x265"）
    resolution: str = ""         # 分辨率（"720p"/"1080p"/"2160p"）
    episode: Optional[int] = None  # 集号（剧集用，电影为 None）
    season: Optional[int] = None   # 季号
    source_name: str = ""        # 来源名称（如 "prowlarr"）
    seeders: int = 0
    indexer: str = ""


class RSSSourceBase:
    """RSS 源基类。所有源必须实现 fetch() 方法。"""

    name: str = ""          # 源名称标识
    display_name: str = ""  # 显示名称
    enabled: bool = True

    def fetch(self, subscription) -> List[RSSItem]:
        """根据订阅信息拉取匹配条目。

        参数:
            subscription: Subscription 对象（含 title/year/type/season/aliases/search_keyword 等）

        返回:
            标准化的 RSSItem 列表
        """
        raise NotImplementedError

    def can_download(self, item: RSSItem) -> bool:
        """该源的条目是否支持直接下载"""
        return bool(item.download_url)

    def get_download_url(self, item: RSSItem) -> str:
        """获取下载链接"""
        return item.download_url


# ── 集号提取工具 ──

_EP_PATTERNS = [
    re.compile(r"S\d{1,2}E(\d{1,4})", re.IGNORECASE),          # S01E05
    re.compile(r"[\[\s]E(\d{1,4})[\]\s\.\-]", re.IGNORECASE),  # [E05] E05.
    re.compile(r"[\[\s](\d{1,4})[\]\s]"),                        # [05]
    re.compile(r"第(\d{1,4})[集话話]"),                           # 第5集/第5话
    re.compile(r"EP\.?(\d{1,4})", re.IGNORECASE),                # EP05 EP.05
    re.compile(r"\s-\s(\d{1,4})\s"),                             # - 05 (常见于字幕组)
]

_SEASON_PATTERNS = [
    re.compile(r"S(\d{1,2})", re.IGNORECASE),                   # S01
    re.compile(r"Season\s*(\d{1,2})", re.IGNORECASE),           # Season 1
    re.compile(r"第(\d{1,2})季"),                                 # 第1季
]


def extract_episode(title: str) -> Optional[int]:
    """从标题提取集号"""
    for pat in _EP_PATTERNS:
        m = pat.search(title)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def extract_season(title: str) -> Optional[int]:
    """从标题提取季号"""
    for pat in _SEASON_PATTERNS:
        m = pat.search(title)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                continue
    return None
