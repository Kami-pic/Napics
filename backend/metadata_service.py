"""Core MetadataService — 元数据统一入口。

本模块是 scraper/completeness/discover 等 Core 模块访问元数据的唯一入口。
内部委托给具体的元数据客户端（当前为 TMDBClient），对外暴露稳定的方法签名。

设计目标：
- Core 模块不再直接 import TMDBClient
- 保持 ScrapeResult 返回类型不变
- 为未来多源 fallback 留口子（TMDB 失败→豆瓣兜底）
"""

import logging
from typing import Dict, List, Optional

from tmdb_client import ScrapeResult

logger = logging.getLogger(__name__)


class MetadataService:
    """Core 元数据服务。

    当前实现：薄包装 TMDBClient，方法签名完全兼容。
    后续演进：内部可切换为通过 ProviderRegistry 获取 MetadataProvider。
    """

    def __init__(self, tmdb_client):
        """初始化。

        Args:
            tmdb_client: TMDBClient 实例（或任何实现相同方法签名的对象）
        """
        self._tmdb = tmdb_client

    @property
    def proxy(self) -> str:
        """获取代理配置（海报下载等场景需要）。"""
        return getattr(self._tmdb, "proxy", "") or ""

    # ── 搜索 ──

    def scrape_by_filename(self, filename: str) -> ScrapeResult:
        """文件名智能刮削：解析→搜索→匹配→返回最佳结果。"""
        return self._tmdb.scrape_by_filename(filename)

    def search_movie(self, query: str) -> List[dict]:
        """搜索电影候选列表。"""
        return self._tmdb.search_movie(query)

    def search_tv(self, query: str) -> List[dict]:
        """搜索剧集候选列表。"""
        return self._tmdb.search_tv(query)

    # ── 详情 ──

    def get_movie_detail(self, tmdb_id: int) -> ScrapeResult:
        """获取电影详情。"""
        return self._tmdb.get_movie_detail(tmdb_id)

    def get_tv_detail(self, tmdb_id: int) -> ScrapeResult:
        """获取剧集详情（含 seasons_info）。"""
        return self._tmdb.get_tv_detail(tmdb_id)

    def get_season_detail(self, tv_id: int, season_num: int) -> ScrapeResult:
        """获取季详情。"""
        return self._tmdb.get_season_detail(tv_id, season_num)

    def get_episode_detail(self, tv_id: int, season_num: int, ep_num: int) -> ScrapeResult:
        """获取集详情。"""
        return self._tmdb.get_episode_detail(tv_id, season_num, ep_num)

    # ── 原始 API 访问（completeness 等模块需要） ──

    def get_raw(self, path: str, params: dict = None) -> dict:
        """直接调用 TMDB API 获取原始 JSON。

        替代 TMDBClient._get()，避免 Core 模块调用私有方法。
        """
        return self._tmdb._get(path, params or {})

    # ── 缓存操作（scraper_tv 季信息更新需要） ──

    def get_cache_path(self, prefix: str, id: int) -> str:
        """获取缓存文件路径。"""
        return self._tmdb._cache_path(prefix, id)

    def save_cache(self, path: str, data: dict):
        """保存数据到缓存文件。"""
        self._tmdb._save_cache(path, data)

    # ── 英文名获取 ──

    def get_english_title(self, media_type: str, tmdb_id: int, original_title: str = "") -> str:
        """获取英文标题（带缓存）。"""
        return self._tmdb._get_english_title(media_type, tmdb_id, original_title)

    # ── 发现推荐（discover/trending） ──

    def trending(self, page: int = 1) -> List[dict]:
        """TMDB 流行趋势（周榜）。"""
        return self._tmdb.trending(page=page)

    def discover(self, **kwargs) -> List[dict]:
        """TMDB Discover 探索筛选。"""
        return self._tmdb.discover(**kwargs)

    # ── 兼容属性（让 scraper 代码无需改动即可使用） ──

    @property
    def query_builder(self):
        """搜索词构造器（如果有的话）。"""
        return getattr(self._tmdb, "query_builder", None)
