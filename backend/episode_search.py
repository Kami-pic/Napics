"""剧集搜索策略：整季包优先 → 逐集搜索回退 → 同源匹配。

核心流程：
1. 搜索 "标题 SXX" 整季包
2. Bencode 解析 .torrent 验证集数完整性（兼容单文件/多文件种子）
3. 无完整整季包 → 逐集搜索 S01E01..S01ENN
4. 同源匹配：计算发布组覆盖率，优先推荐完整覆盖的发布组

关键设计：
- 复用 tmdb_client.parse_filename 提取集数
- 复用 quality_parser.parse_quality 提取发布组
- 磁力链接标记 is_magnet=True，不尝试 HTTP 请求
- Bencode 兼容单文件种子（info.name）和多文件种子（info.files[].path）
"""

import os
import time
from typing import List, Dict, Optional, Set
from collections import defaultdict

import requests
from pydantic import BaseModel

from searcher import ProwlarrClient, SearchResult, EnhancedSearchResponse, enhanced_search
from alias_resolver import AliasSet
from global_filter import GlobalFilter
from quality_parser import parse_quality
from tmdb_client import parse_filename
from indexer_priority_manager import IndexerPriorityManager


# 视频文件扩展名
VIDEO_EXTS: Set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm",
    ".flv", ".ts", ".m4v", ".webm", ".mpg", ".mpeg",
}


# ── 数据模型 ──

class PackVerification(BaseModel):
    """整季包验证结果"""
    verified: bool = False       # 是否成功解析了种子文件
    is_magnet: bool = False      # 是否为磁力链接（无法预先验证）
    episode_count: int = 0       # 解析出的视频文件集数
    episodes_found: List[int] = []  # 解析出的具体集号列表
    is_complete: bool = False    # 集数 >= 目标总集数


class SeasonPackInfo(BaseModel):
    """整季包信息"""
    result: SearchResult
    verification: PackVerification = PackVerification()


class EpisodeResult(BaseModel):
    """单集搜索结果"""
    episode: int
    status: str = "not_found"    # "found" | "not_found"
    recommended: Optional[SearchResult] = None
    alternatives: List[SearchResult] = []


class SameSourcePlan(BaseModel):
    """同源匹配方案"""
    primary_group: str = ""      # 主推荐发布组
    coverage: float = 0.0        # 覆盖率 0.0-1.0
    episodes: Dict[int, SearchResult] = {}  # 集号 → 选中资源
    missing_episodes: List[int] = []        # 缺失集数


class SeasonSearchResult(BaseModel):
    """季级搜索完整结果"""
    season_packs: List[SeasonPackInfo] = []
    episode_results: Dict[int, EpisodeResult] = {}
    recommended_plan: str = "season_pack"  # "season_pack" | "per_episode"
    same_source_plan: Optional[SameSourcePlan] = None
    total_size_pack_gb: float = 0.0        # 整季包方案总大小
    total_size_episode_gb: float = 0.0     # 逐集方案总大小


# ── Bencode 解析工具 ──

def _parse_torrent_episodes(torrent_bytes: bytes) -> List[int]:
    """从 .torrent 文件的二进制内容中解析视频文件集数。

    兼容两种种子结构：
    - 多文件种子：info.files[].path（list of bytes，需 join）
    - 单文件种子：info.name（bytes）

    返回去重的集号列表。
    """
    try:
        import bencodepy
        torrent = bencodepy.decode(torrent_bytes)
    except Exception:
        # bencodepy 不可用时尝试手动解析或返回空
        return []

    info = torrent.get(b"info", {})
    if not info:
        return []

    filenames: List[str] = []

    if b"files" in info:
        # 多文件种子
        for f in info[b"files"]:
            path_parts = f.get(b"path", [])
            if path_parts:
                # path 是 list of bytes，取最后一个作为文件名
                fname = path_parts[-1]
                if isinstance(fname, bytes):
                    fname = fname.decode("utf-8", errors="replace")
                filenames.append(fname)
    else:
        # 单文件种子
        name = info.get(b"name", b"")
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="replace")
        if name:
            filenames.append(name)

    # 过滤视频文件，用 parse_filename 提取集数
    episodes: Set[int] = set()
    for fname in filenames:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in VIDEO_EXTS:
            continue
        parsed = parse_filename(fname)
        ep = parsed.get("episode")
        if ep is not None:
            episodes.add(ep)

    return sorted(episodes)


# ── 核心策略类 ──

class EpisodeSearchStrategy:
    """剧集搜索策略：整季包优先 → 逐集回退 → 同源匹配。"""

    # 整季包 .torrent 下载超时（秒）
    TORRENT_FETCH_TIMEOUT = 5
    # 逐集搜索间隔（秒），避免 Prowlarr 限流
    EPISODE_SEARCH_DELAY = 1.5

    def search_season(
        self,
        client: ProwlarrClient,
        title: str,
        season_number: int,
        total_episodes: int,
        aliases: Optional[AliasSet] = None,
        year: str = "",
        global_filter: Optional[GlobalFilter] = None,
        indexer_manager: Optional[IndexerPriorityManager] = None,
        shadow_name: str = "",
        clean_name: str = "",
    ) -> SeasonSearchResult:
        """执行季级搜索的完整流程。

        1. 搜索整季包（"标题 SXX"）
        2. 验证整季包完整性（Bencode 解析）
        3. 无完整整季包 → 逐集搜索
        4. 同源匹配
        """
        result = SeasonSearchResult()
        season_tag = f"S{season_number:02d}"

        # ── 第一步：搜索整季包 ──
        pack_results = self._search_season_pack(
            client=client,
            title=title,
            season_tag=season_tag,
            aliases=aliases,
            year=year,
            global_filter=global_filter,
            indexer_manager=indexer_manager,
            shadow_name=shadow_name,
            clean_name=clean_name,
        )

        # 验证每个整季包候选
        for sr in pack_results:
            verification = self._verify_season_pack(sr, total_episodes)
            pack_info = SeasonPackInfo(result=sr, verification=verification)
            result.season_packs.append(pack_info)

        # 检查是否有完整的整季包
        complete_packs = [p for p in result.season_packs if p.verification.is_complete]
        if complete_packs:
            result.recommended_plan = "season_pack"
            # 取做种数最高的完整包计算大小
            best_pack = max(complete_packs, key=lambda p: p.result.seeders)
            result.total_size_pack_gb = best_pack.result.size_gb

        # ── 第二步：逐集搜索（无论是否有整季包，都搜一遍供用户选择）──
        episode_results, same_source = self._episode_search_all(
            client=client,
            title=title,
            season_number=season_number,
            total_episodes=total_episodes,
            aliases=aliases,
            year=year,
            global_filter=global_filter,
            indexer_manager=indexer_manager,
            shadow_name=shadow_name,
            clean_name=clean_name,
        )
        result.episode_results = episode_results
        result.same_source_plan = same_source

        # 计算逐集方案总大小
        total_ep_size = 0.0
        for ep_num, ep_result in episode_results.items():
            if ep_result.recommended:
                total_ep_size += ep_result.recommended.size_gb
        result.total_size_episode_gb = round(total_ep_size, 2)

        # 如果没有完整整季包，推荐逐集方案
        if not complete_packs:
            result.recommended_plan = "per_episode"

        return result

    def _search_season_pack(
        self,
        client: ProwlarrClient,
        title: str,
        season_tag: str,
        aliases: Optional[AliasSet],
        year: str,
        global_filter: Optional[GlobalFilter],
        indexer_manager: Optional[IndexerPriorityManager],
        shadow_name: str,
        clean_name: str,
    ) -> List[SearchResult]:
        """搜索整季包：使用 "标题 SXX" 格式。

        复用 enhanced_search 的回退链+二次匹配+全局过滤。
        """
        # 构建整季包搜索词：在各关键词后追加 SXX
        pack_shadow = f"{shadow_name} {season_tag}" if shadow_name else ""
        pack_clean = f"{clean_name} {season_tag}" if clean_name else ""

        resp = enhanced_search(
            client=client,
            title=f"{title} {season_tag}",
            aliases=aliases or AliasSet(),
            year=year,
            media_type="tv",
            indexer_manager=indexer_manager,
            shadow_name=pack_shadow,
            clean_name=pack_clean,
            global_filter=global_filter,
        )
        return resp.results

    def _verify_season_pack(
        self, result: SearchResult, total_episodes: int
    ) -> PackVerification:
        """验证整季包完整性 — Bencode 解析。

        流程：
        1. 磁力链接 → 直接标记 is_magnet=True, verified=False
        2. HTTP GET 拉取 .torrent 文件流
        3. Bencode 解析，兼容单文件/多文件种子
        4. 过滤视频文件，用 parse_filename 提取集数
        5. 统计集数，与 total_episodes 比对
        """
        url = result.download_url

        # 磁力链接无法预先解析
        if not url or url.startswith("magnet:"):
            return PackVerification(is_magnet=True)

        try:
            resp = requests.get(url, timeout=self.TORRENT_FETCH_TIMEOUT)
            if resp.status_code != 200:
                return PackVerification()

            # 检查是否真的是 torrent 文件（Bencode 以 d 开头）
            if not resp.content or resp.content[0:1] != b"d":
                return PackVerification()

            episodes = _parse_torrent_episodes(resp.content)
            return PackVerification(
                verified=True,
                episode_count=len(episodes),
                episodes_found=episodes,
                is_complete=len(episodes) >= total_episodes,
            )
        except Exception:
            return PackVerification()

    def _episode_search_all(
        self,
        client: ProwlarrClient,
        title: str,
        season_number: int,
        total_episodes: int,
        aliases: Optional[AliasSet],
        year: str,
        global_filter: Optional[GlobalFilter],
        indexer_manager: Optional[IndexerPriorityManager],
        shadow_name: str,
        clean_name: str,
    ) -> tuple:
        """逐集搜索 S01E01..S01ENN，返回 (episode_results, same_source_plan)。"""
        episode_results: Dict[int, EpisodeResult] = {}
        # 收集每集的所有候选（供同源匹配使用）
        all_candidates: Dict[int, List[SearchResult]] = defaultdict(list)

        for ep_num in range(1, total_episodes + 1):
            ep_tag = f"S{season_number:02d}E{ep_num:02d}"

            # 构建逐集搜索词
            ep_shadow = f"{shadow_name} {ep_tag}" if shadow_name else ""
            ep_clean = f"{clean_name} {ep_tag}" if clean_name else ""

            try:
                resp = enhanced_search(
                    client=client,
                    title=f"{title} {ep_tag}",
                    aliases=aliases or AliasSet(),
                    year=year,
                    media_type="tv",
                    indexer_manager=indexer_manager,
                    shadow_name=ep_shadow,
                    clean_name=ep_clean,
                    global_filter=global_filter,
                )
                results = resp.results
            except Exception:
                results = []

            if results:
                # 取评分最高的（enhanced_search 已排序）作为推荐
                recommended = results[0]
                alternatives = results[1:10]  # 最多保留 9 个备选
                episode_results[ep_num] = EpisodeResult(
                    episode=ep_num,
                    status="found",
                    recommended=recommended,
                    alternatives=alternatives,
                )
                all_candidates[ep_num] = results
            else:
                episode_results[ep_num] = EpisodeResult(
                    episode=ep_num,
                    status="not_found",
                )

            # 间隔避免限流（最后一集不等待）
            if ep_num < total_episodes:
                time.sleep(self.EPISODE_SEARCH_DELAY)

        # 同源匹配
        same_source = self._same_source_match(all_candidates, total_episodes)

        return episode_results, same_source

    def _same_source_match(
        self,
        all_candidates: Dict[int, List[SearchResult]],
        total_episodes: int,
    ) -> Optional[SameSourcePlan]:
        """同源匹配：选择覆盖率最高的发布组，缺失集从其他发布组补充。

        算法：
        1. 遍历所有集的候选结果，统计每个发布组覆盖了哪些集
        2. 按覆盖率降序排列
        3. 选覆盖率最高的作为主基调
        4. 缺失集从覆盖率第二高的发布组中借
        5. 仍然缺失的标记为 missing
        """
        if not all_candidates:
            return None

        # 统计每个发布组覆盖的集数和对应资源
        # group_name → {ep_num: best_result}
        group_coverage: Dict[str, Dict[int, SearchResult]] = defaultdict(dict)

        for ep_num, candidates in all_candidates.items():
            for result in candidates:
                quality = result.quality or parse_quality(result.title)
                group = quality.release_group or "_unknown_"
                # 每个发布组每集只保留第一个（已按评分排序）
                if ep_num not in group_coverage[group]:
                    group_coverage[group][ep_num] = result

        if not group_coverage:
            return None

        # 按覆盖集数降序排列
        sorted_groups = sorted(
            group_coverage.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        # 主发布组
        primary_group_name, primary_episodes = sorted_groups[0]
        coverage = len(primary_episodes) / total_episodes if total_episodes > 0 else 0.0

        # 构建最终方案：主发布组 + 补充
        plan_episodes: Dict[int, SearchResult] = dict(primary_episodes)
        missing: List[int] = []

        # 检查缺失集，从其他发布组补充
        for ep_num in range(1, total_episodes + 1):
            if ep_num in plan_episodes:
                continue
            # 从其他发布组借
            borrowed = False
            for group_name, group_eps in sorted_groups[1:]:
                if ep_num in group_eps:
                    plan_episodes[ep_num] = group_eps[ep_num]
                    borrowed = True
                    break
            if not borrowed:
                missing.append(ep_num)

        return SameSourcePlan(
            primary_group=primary_group_name if primary_group_name != "_unknown_" else "",
            coverage=round(coverage, 2),
            episodes=plan_episodes,
            missing_episodes=missing,
        )
