"""RSS 订阅引擎：源管理 + 定时调度 + 匹配 + 下载触发。

核心职责：
- RSSSourceManager：管理所有 RSS 源（注册/启用/禁用）
- SubscriptionScheduler：定时遍历活跃订阅，调用源拉取 + 匹配 + 处理结果
- 频率衰减：新订阅高频搜索，长期无果自动降频/暂停
"""

import random
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from rss_source_base import RSSSourceBase, RSSItem
from rss_matcher import match_items
from subscriber import Subscription, SubscriptionManager


# ── 源管理器 ──

class RSSSourceManager:
    """管理所有 RSS 源。新增源只需调用 register()。"""

    def __init__(self):
        self._sources: Dict[str, RSSSourceBase] = {}

    def register(self, source: RSSSourceBase):
        """注册一个 RSS 源"""
        self._sources[source.name] = source
        print(f"[RSSEngine] 注册源: {source.name} ({source.display_name})")

    def get_enabled_sources(self) -> List[RSSSourceBase]:
        """获取所有启用的源"""
        return [s for s in self._sources.values() if s.enabled]

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """获取所有源的状态信息（供 API 返回）"""
        return [
            {"name": s.name, "display_name": s.display_name, "enabled": s.enabled}
            for s in self._sources.values()
        ]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """启用/禁用某个源"""
        if name in self._sources:
            self._sources[name].enabled = enabled
            return True
        return False


# ── 频率衰减 ──

def should_search_now(sub: Subscription, base_interval_hours: float = 4.0) -> bool:
    """判断订阅当前是否应该搜索。

    衰减策略：
    - 前 72h：每 base_interval_hours 搜一次
    - 3-14 天未命中：每 12h
    - 14-30 天未命中：每 24h
    - 30 天未命中：返回 False（调用方负责暂停）
    """
    if sub.state != "active":
        return False

    now = datetime.now()

    # 从未搜索过 → 立即搜
    if not sub.last_search:
        return True

    try:
        last = datetime.strptime(sub.last_search, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return True

    created = now
    if sub.created_at:
        try:
            created = datetime.strptime(sub.created_at, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pass

    age_days = (now - created).total_seconds() / 86400
    since_last = (now - last).total_seconds() / 3600  # 小时

    # 确定当前间隔
    if age_days <= 3 or sub.search_count <= 18:  # 前 72h（约 18 次 × 4h）
        interval = base_interval_hours
    elif age_days <= 14:
        interval = 12.0
    elif age_days <= 30:
        interval = 24.0
    else:
        return False  # 超过 30 天，调用方负责暂停

    return since_last >= interval


# ── 调度器 ──

class SubscriptionScheduler:
    """订阅定时调度器：后台线程遍历活跃订阅，执行搜索+匹配+处理。"""

    def __init__(
        self,
        sub_manager: SubscriptionManager,
        source_manager: RSSSourceManager,
        download_manager=None,
        base_interval_hours: float = 4.0,
        check_interval_seconds: float = 300,  # 每 5 分钟检查一轮
    ):
        self.sub_manager = sub_manager
        self.source_manager = source_manager
        self.download_manager = download_manager
        self.base_interval = base_interval_hours
        self.check_interval = check_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="rss-scheduler")
        self._thread.start()
        print(f"[RSSEngine] 调度器启动，检查间隔 {self.check_interval}s")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[RSSEngine] 调度器已停止")

    def search_one(self, sub: Subscription) -> List[RSSItem]:
        """手动触发单个订阅搜索（不受频率衰减限制）"""
        return self._do_search(sub)

    def _loop(self):
        """调度主循环"""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"[RSSEngine] 调度异常: {e}")
            time.sleep(self.check_interval)

    def _tick(self):
        """单次调度：遍历活跃订阅，判断是否该搜索"""
        active_subs = self.sub_manager.get_all(state="active")
        if not active_subs:
            return

        for sub in active_subs:
            if not self._running:
                break

            # 日历触发：剧集今天有新集播出时强制搜索
            calendar_trigger = self._check_calendar_trigger(sub)

            if not calendar_trigger and not should_search_now(sub, self.base_interval):
                continue

            # 随机延迟 30-120 秒防限频
            delay = random.randint(30, 120)
            time.sleep(delay)

            if not self._running:
                break

            matched = self._do_search(sub)
            self._handle_results(sub, matched)

    def _do_search(self, sub: Subscription) -> List[RSSItem]:
        """执行搜索：遍历所有启用的源，合并结果后匹配"""
        sources = self.source_manager.get_enabled_sources()
        if not sources:
            return []

        # 订阅级别源过滤：sub.sources 非空时只用指定源
        if hasattr(sub, "sources") and sub.sources:
            sources = [s for s in sources if s.name in sub.sources]
            if not sources:
                print(f"[RSSEngine] {sub.title}: 指定的源都未启用")
                return []

        all_items: List[RSSItem] = []
        for source in sources:
            try:
                items = source.fetch(sub)
                all_items.extend(items)
            except Exception as e:
                print(f"[RSSEngine] 源 {source.name} 搜索失败: {e}")

        # 更新搜索时间和计数
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_data: Dict[str, Any] = {"last_search": now}
        if not sub.first_search:
            update_data["first_search"] = now

        # 匹配过滤
        matched = match_items(all_items, sub)

        if matched:
            update_data["search_count"] = 0  # 找到资源，重置计数
            update_data["last_found"] = now
        else:
            update_data["search_count"] = sub.search_count + 1
            # 超过 30 天无果，自动暂停
            if sub.created_at:
                try:
                    created = datetime.strptime(sub.created_at, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - created).days > 30 and sub.search_count > 20:
                        update_data["state"] = "paused"
                        update_data["note"] = "长期未找到资源，已自动暂停"
                        print(f"[RSSEngine] {sub.title} 自动暂停（30天无果）")
                except (ValueError, TypeError):
                    pass

        self.sub_manager.update(sub.id, update_data)

        print(f"[RSSEngine] {sub.title}: 搜索完成，原始 {len(all_items)} 条，匹配 {len(matched)} 条")
        return matched

    def _handle_results(self, sub: Subscription, matched: List[RSSItem]):
        """处理匹配结果：通知模式存储，自动模式下载，洗版模式比较质量"""
        if not matched:
            return

        if sub.mode == "notify":
            # 存入 found_resources
            resources = [item.model_dump() for item in matched]
            # 合并已有的，去重
            existing = sub.found_resources or []
            existing_hashes = {r.get("info_hash", "") for r in existing}
            new_resources = [r for r in resources if r.get("info_hash", "") not in existing_hashes]
            if new_resources:
                self.sub_manager.update(sub.id, {
                    "found_resources": existing + new_resources,
                })
                print(f"[RSSEngine] {sub.title}: 通知模式，新增 {len(new_resources)} 条待选资源")

        elif sub.mode == "auto" and self.download_manager:
            if sub.best_version:
                to_download = self._select_best_version(matched, sub)
            else:
                to_download = self._select_best(matched, sub)
            for item in to_download:
                self._submit_download(sub, item)

    def _select_best(self, items: List[RSSItem], sub: Subscription) -> List[RSSItem]:
        """选择最佳下载条目：电影取最高质量，剧集每集取最高质量"""
        if sub.type != "tv":
            # 电影：按 seeders 降序取第一条
            sorted_items = sorted(items, key=lambda x: x.seeders, reverse=True)
            return sorted_items[:1]

        # 剧集：按集号分组，每集取 seeders 最高的
        by_episode: Dict[int, List[RSSItem]] = {}
        for item in items:
            ep = item.episode
            if ep is None:
                continue
            by_episode.setdefault(ep, []).append(item)

        best = []
        for ep, ep_items in by_episode.items():
            ep_items.sort(key=lambda x: x.seeders, reverse=True)
            best.append(ep_items[0])
        return best

    def _select_best_version(self, items: List[RSSItem], sub: Subscription) -> List[RSSItem]:
        """洗版模式：只选择质量分数高于已有版本的条目"""
        from quality_parser import parse_quality, compute_quality_score, compare_quality_score

        downloaded = sub.downloaded_episodes or {}
        to_download = []

        if sub.type != "tv":
            # 电影洗版：比较 "0" 的已有质量
            current_tag = downloaded.get("0", {})
            current_qt = current_tag.quality_tag if hasattr(current_tag, "quality_tag") else (current_tag.get("quality_tag", "") if isinstance(current_tag, dict) else "")
            current_score = compute_quality_score(parse_quality(current_qt)) if current_qt else 0

            best_item = None
            best_score = current_score
            for item in items:
                new_score = compute_quality_score(parse_quality(item.title))
                if compare_quality_score(best_score, new_score):
                    best_score = new_score
                    best_item = item
            if best_item:
                to_download.append(best_item)
                print(f"[RSSEngine] 洗版: {sub.title} 发现更高质量 ({best_score} > {current_score})")
        else:
            # 剧集洗版：按集独立比较
            by_episode: Dict[int, List[RSSItem]] = {}
            for item in items:
                if item.episode is not None:
                    by_episode.setdefault(item.episode, []).append(item)

            for ep, ep_items in by_episode.items():
                ep_key = str(ep)
                current_tag = downloaded.get(ep_key, {})
                current_qt = current_tag.quality_tag if hasattr(current_tag, "quality_tag") else (current_tag.get("quality_tag", "") if isinstance(current_tag, dict) else "")
                current_score = compute_quality_score(parse_quality(current_qt)) if current_qt else 0

                best_item = None
                best_score = current_score
                for item in ep_items:
                    new_score = compute_quality_score(parse_quality(item.title))
                    if compare_quality_score(best_score, new_score):
                        best_score = new_score
                        best_item = item
                if best_item:
                    to_download.append(best_item)

        return to_download

    def _submit_download(self, sub: Subscription, item: RSSItem):
        """提交下载任务到 DownloadManager"""
        if not self.download_manager or not item.download_url:
            return

        try:
            from download_manager import DownloadTask
            task = DownloadTask(
                media_name=f"{sub.title} E{item.episode or 0}",
                download_url=item.download_url,
                save_path=sub.save_path,
                channel="qb",
                category_hint="tv" if sub.type == "tv" else "movie",
                subscription_id=sub.id,
                subscription_episode=item.episode,
            )
            self.download_manager.submit(task)
            print(f"[RSSEngine] 自动下载: {task.media_name}")
        except Exception as e:
            print(f"[RSSEngine] 下载提交失败: {e}")

    def _check_calendar_trigger(self, sub: Subscription) -> bool:
        """检查剧集订阅是否有今天播出的新集（日历触发）"""
        if sub.type != "tv" or not sub.tmdb_id:
            return False
        try:
            from shared import _tmdb_client
            tmdb = _tmdb_client()
            if not tmdb:
                return False
            season_num = sub.season or 1
            raw = tmdb._get(f"/tv/{sub.tmdb_id}/season/{season_num}")
            episodes = raw.get("episodes", [])
            today = datetime.now().strftime("%Y-%m-%d")
            downloaded = set(sub.downloaded_episodes.keys())
            for ep in episodes:
                air_date = ep.get("air_date", "")
                ep_num = ep.get("episode_number", 0)
                if air_date == today and str(ep_num) not in downloaded:
                    print(f"[RSSEngine] 日历触发: {sub.title} E{ep_num} 今天播出")
                    return True
        except Exception:
            pass
        return False
