"""订阅管理器：CRUD + JSON 持久化 + 别名预拉取 + 媒体库查重。

核心设计：
- 数据持久化到 subscriptions.json，读写加锁
- 订阅创建时预拉取别名（alias_resolver），缓存到订阅数据中
- 订阅创建时检查媒体库是否已有（local_media_matcher）
- 状态机：active ↔ paused，全部下载完成 → completed
- downloaded_episodes 用对象结构存储指纹信息，防止重复下载
"""

import os
import json
import uuid
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


SUBSCRIPTIONS_FILE = "subscriptions.json"


# ── 数据模型 ──

class EpisodeInfo(BaseModel):
    """单集下载指纹"""
    info_hash: str = ""
    title: str = ""
    quality_tag: str = ""
    source: str = ""          # "prowlarr" / "pan"
    channel: str = ""         # "qb" / "alist"
    task_id: str = ""         # 关联 DownloadManager 的 task_id
    timestamp: str = ""


class Subscription(BaseModel):
    """订阅数据结构"""
    id: str = ""
    title: str = ""
    year: str = ""
    type: str = ""                # "movie" / "tv"
    tmdb_id: Optional[int] = None
    douban_id: Optional[str] = None
    poster: str = ""
    season: Optional[int] = None  # 剧集才有
    total_episode: int = 0
    downloaded_episodes: Dict[str, EpisodeInfo] = Field(default_factory=dict)
    quality: str = "1080p"        # 质量偏好（最低要求）
    include: str = ""             # 包含关键词
    exclude: str = ""             # 排除关键词
    save_path: str = ""
    search_keyword: str = ""      # 自定义搜索词（空则用 title）
    aliases: Dict[str, List[str]] = Field(default_factory=lambda: {"cn": [], "en": [], "jp": []})
    sources: List[str] = Field(default_factory=list)  # 指定搜索源（空=用全局设置）
    state: str = "active"         # active / paused / completed
    mode: str = "notify"          # notify / auto
    found_resources: List[Dict[str, Any]] = Field(default_factory=list)
    best_version: bool = False
    search_count: int = 0         # 累计无效搜索次数（找到资源后重置）
    first_search: str = ""
    last_search: str = ""
    last_found: str = ""
    created_at: str = ""
    note: str = ""


# ── 核心管理器 ──

class SubscriptionManager:
    """订阅管理器：CRUD + 持久化 + 别名预拉取。"""

    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self._file_path = os.path.join(base_path, SUBSCRIPTIONS_FILE)
        self._lock = threading.Lock()
        self.subscriptions: List[Subscription] = []
        self._load()

    # ── CRUD ──

    def add(self, data: dict, alias_resolver=None, media_matcher=None, tmdb=None) -> dict:
        """新增订阅。

        参数:
            data: 订阅基础信息（title/year/type/tmdb_id/douban_id 等）
            alias_resolver: AliasResolver 实例，用于预拉取别名
            media_matcher: LocalMediaMatcher 实例，用于检查媒体库是否已有
            tmdb: TMDBClient 实例，用于获取剧集总集数

        返回:
            {"status": "ok", "subscription": {...}} 或 {"status": "error", "message": "..."}
        """
        title = data.get("title", "").strip()
        if not title:
            return {"status": "error", "message": "标题不能为空"}

        # 检查是否已订阅（同 tmdb_id 或同 title+year+season）
        year = str(data.get("year", "")).strip()
        tmdb_id = data.get("tmdb_id")
        season = data.get("season")

        # 自动补全 tmdb_id（用 TMDB 搜索）
        if not tmdb_id and tmdb and title:
            try:
                media_type = data.get("type", "movie")
                if media_type == "tv":
                    results = tmdb.search_tv(title)
                else:
                    results = tmdb.search_movie(title)
                if results:
                    best = results[0]
                    # 年份校验（避免匹配到同名不同年份的作品）
                    candidate_id = best.get("id")
                    candidate_date = best.get("first_air_date") or best.get("release_date") or ""
                    if candidate_id:
                        if not year or not candidate_date or candidate_date.startswith(year):
                            tmdb_id = candidate_id
                            data["tmdb_id"] = tmdb_id
                            print(f"[Subscriber] TMDB 自动补全: {title} → tmdb_id={tmdb_id}")
                        else:
                            print(f"[Subscriber] TMDB 年份不匹配: {title} 期望{year} 实际{candidate_date[:4]}")
            except Exception as e:
                print(f"[Subscriber] TMDB 补全失败: {e}")
        for sub in self.subscriptions:
            if tmdb_id and sub.tmdb_id == tmdb_id and sub.season == season:
                return {"status": "error", "message": f"已订阅: {sub.title}"}
            if sub.title == title and sub.year == year and sub.season == season:
                return {"status": "error", "message": f"已订阅: {sub.title}"}

        # 检查媒体库是否已有
        local_warning = ""
        if media_matcher:
            try:
                status, folder = media_matcher.match({
                    "title": title,
                    "year": year,
                    "tmdb_id": tmdb_id,
                    "douban_id": data.get("douban_id"),
                })
                if status.startswith("owned"):
                    local_warning = f"媒体库已有该资源（{folder}），仍然创建订阅"
            except Exception as e:
                print(f"[Subscriber] 媒体库检查失败: {e}")

        # 预拉取别名
        aliases = {"cn": [], "en": [], "jp": []}
        if alias_resolver:
            try:
                alias_set = alias_resolver.resolve(title, year=year)
                aliases = {
                    "cn": alias_set.cn_names or [],
                    "en": alias_set.en_names or [],
                    "jp": alias_set.jp_names or [],
                }
            except Exception as e:
                print(f"[Subscriber] 别名拉取失败: {e}")

        # 获取剧集总集数
        total_episode = data.get("total_episode", 0)
        if data.get("type") == "tv" and tmdb_id and not total_episode and tmdb:
            total_episode = self._fetch_total_episodes(tmdb, tmdb_id, season)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sub = Subscription(
            id=str(uuid.uuid4())[:8],
            title=title,
            year=year,
            type=data.get("type", "movie"),
            tmdb_id=tmdb_id,
            douban_id=data.get("douban_id"),
            poster=data.get("poster", ""),
            season=season,
            total_episode=total_episode,
            quality=data.get("quality", "1080p"),
            include=data.get("include", ""),
            exclude=data.get("exclude", ""),
            save_path=data.get("save_path", ""),
            search_keyword=data.get("search_keyword", ""),
            aliases=aliases,
            mode=data.get("mode", "notify"),
            created_at=now,
        )

        # 媒体库联动：剧集订阅自动填充已有集数
        if data.get("type") == "tv" and local_warning and media_matcher:
            try:
                local_episodes = self._scan_local_episodes(title, year, season, media_matcher)
                if local_episodes:
                    for ep_num in local_episodes:
                        sub.downloaded_episodes[str(ep_num)] = EpisodeInfo(
                            source="local", timestamp=now, title=f"本地已有 E{ep_num:02d}",
                        )
                    print(f"[Subscriber] 媒体库联动: {title} 已有 {len(local_episodes)} 集")
            except Exception as e:
                print(f"[Subscriber] 媒体库联动失败: {e}")

        with self._lock:
            self.subscriptions.append(sub)
            self._save()

        result = {"status": "ok", "subscription": sub.model_dump()}
        if local_warning:
            result["warning"] = local_warning
        return result

    def get(self, sub_id: str) -> Optional[Subscription]:
        """查询单个订阅"""
        for sub in self.subscriptions:
            if sub.id == sub_id:
                return sub
        return None

    def get_all(self, state: Optional[str] = None) -> List[Subscription]:
        """查询所有订阅，可按状态过滤"""
        if state:
            return [s for s in self.subscriptions if s.state == state]
        return list(self.subscriptions)

    def update(self, sub_id: str, data: dict) -> dict:
        """更新订阅字段"""
        sub = self.get(sub_id)
        if not sub:
            return {"status": "not_found"}

        # 允许更新的字段白名单
        updatable = {
            "quality", "include", "exclude", "save_path", "search_keyword",
            "state", "mode", "best_version", "note", "total_episode",
            "found_resources", "downloaded_episodes", "search_count",
            "first_search", "last_search", "last_found", "poster",
        }
        with self._lock:
            for key, val in data.items():
                if key in updatable:
                    setattr(sub, key, val)
            self._save()
        return {"status": "ok", "subscription": sub.model_dump()}

    def delete(self, sub_id: str) -> dict:
        """删除订阅"""
        with self._lock:
            before = len(self.subscriptions)
            self.subscriptions = [s for s in self.subscriptions if s.id != sub_id]
            if len(self.subscriptions) == before:
                return {"status": "not_found"}
            self._save()
        return {"status": "ok"}

    # ── 辅助方法 ──

    def _fetch_total_episodes(self, tmdb, tmdb_id: int, season: Optional[int]) -> int:
        """从 TMDB 获取剧集总集数"""
        try:
            if season:
                result = tmdb.get_season_detail(tmdb_id, season)
                if result and result.data:
                    episodes = result.data.get("episodes", [])
                    return len(episodes)
            else:
                result = tmdb.get_tv_detail(tmdb_id)
                if result and result.data:
                    return result.data.get("number_of_episodes", 0)
        except Exception as e:
            print(f"[Subscriber] TMDB 获取集数失败: {e}")
        return 0

    def _scan_local_episodes(self, title: str, year: str, season: Optional[int],
                              media_matcher) -> list:
        """扫描媒体库中该剧已有的集号列表"""
        import re
        try:
            # 从 media_matcher 的索引中找到匹配的文件夹
            status, folder = media_matcher.match({"title": title, "year": year})
            if not status.startswith("owned") or not folder:
                return []

            # 读取媒体库，找到该文件夹下的所有视频
            from config_manager import ConfigManager
            cm = ConfigManager()
            library = cm.load_library()
            episodes = set()
            for v in library:
                fp = v.get("file_path", "")
                fn = v.get("folder_name", "")
                # 匹配文件夹路径
                if folder not in fn and folder not in fp:
                    continue
                # 从文件名提取集号
                fname = v.get("file_name", "")
                ep = self._extract_episode_from_filename(fname)
                if ep is not None:
                    episodes.add(ep)
            return sorted(episodes)
        except Exception as e:
            print(f"[Subscriber] 扫描本地集数失败: {e}")
            return []

    @staticmethod
    def _extract_episode_from_filename(filename: str) -> Optional[int]:
        """从文件名提取集号"""
        import re
        patterns = [
            re.compile(r"S\d{1,2}E(\d{1,4})", re.IGNORECASE),
            re.compile(r"[\[\s]E(\d{1,4})[\]\s\.\-]", re.IGNORECASE),
            re.compile(r"第(\d{1,4})[集话話]"),
            re.compile(r"EP\.?(\d{1,4})", re.IGNORECASE),
            re.compile(r"\s-\s(\d{1,4})\s"),
        ]
        for pat in patterns:
            m = pat.search(filename)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    def is_subscribed(self, tmdb_id: Optional[int] = None,
                      title: str = "", year: str = "",
                      season: Optional[int] = None) -> bool:
        """检查是否已订阅"""
        for sub in self.subscriptions:
            if sub.state == "completed":
                continue
            if tmdb_id and sub.tmdb_id == tmdb_id and sub.season == season:
                return True
            if title and sub.title == title and sub.year == year and sub.season == season:
                return True
        return False

    def on_download_complete(self, subscription_id: str, episode: Optional[int],
                             info_hash: str = "", title: str = "",
                             quality_tag: str = "", source: str = "",
                             channel: str = "", task_id: str = ""):
        """下载完成回调：更新 downloaded_episodes 指纹"""
        sub = self.get(subscription_id)
        if not sub:
            return

        ep_key = str(episode) if episode is not None else "0"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ep_info = EpisodeInfo(
            info_hash=info_hash,
            title=title,
            quality_tag=quality_tag,
            source=source,
            channel=channel,
            task_id=task_id,
            timestamp=now,
        )

        with self._lock:
            sub.downloaded_episodes[ep_key] = ep_info
            sub.last_found = now

            # 检查是否全部完成
            if sub.type == "movie":
                sub.state = "completed"
            elif sub.total_episode > 0:
                if len(sub.downloaded_episodes) >= sub.total_episode:
                    sub.state = "completed"

            self._save()

        print(f"[Subscriber] 下载完成回调: {sub.title} E{ep_key}, state={sub.state}")

    # ── 持久化 ──

    def _load(self):
        """从 JSON 文件加载订阅数据"""
        if not os.path.exists(self._file_path):
            self.subscriptions = []
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.subscriptions = []
            for item in raw:
                # downloaded_episodes 兼容：旧格式 list → 新格式 dict
                dl_eps = item.get("downloaded_episodes", {})
                if isinstance(dl_eps, list):
                    item["downloaded_episodes"] = {
                        str(ep): {"timestamp": ""} for ep in dl_eps
                    }
                self.subscriptions.append(Subscription(**item))
            print(f"[Subscriber] 加载 {len(self.subscriptions)} 条订阅")
        except Exception as e:
            print(f"[Subscriber] 加载失败: {e}")
            self.subscriptions = []

    def _save(self):
        """保存订阅数据到 JSON 文件（调用方需持有 _lock）"""
        try:
            data = [s.model_dump() for s in self.subscriptions]
            tmp = self._file_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._file_path)
        except Exception as e:
            print(f"[Subscriber] 保存失败: {e}")
