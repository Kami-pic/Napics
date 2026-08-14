"""RSS 订阅引擎：源管理 + 定时调度 + 匹配 + 下载触发。

核心职责：
- RSSSourceManager：管理所有 RSS 源（注册/启用/禁用）
- SubscriptionScheduler：定时遍历活跃订阅，调用源拉取 + 匹配 + 处理结果
- 频率衰减：新订阅高频搜索，长期无果自动降频/暂停
"""

import json
import random
import threading
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from rss_source_base import RSSSourceBase, RSSItem
from rss_matcher import match_items
from subscriber import Subscription, SubscriptionManager

logger = logging.getLogger(__name__)


# ── 搜索结果缓存 ──

class SearchResultCache:
    """搜索结果缓存：同一源+同一关键词在 TTL 内不重复请求。"""

    def __init__(self, ttl_seconds: int = 1800):
        self._cache: Dict[str, Tuple[float, List[RSSItem]]] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, source_name: str, keyword: str) -> Optional[List[RSSItem]]:
        """获取缓存结果，过期返回 None。"""
        key = f"{source_name}:{keyword}"
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() - entry[0] < self._ttl:
                return list(entry[1])
            if entry:
                del self._cache[key]
        return None

    def set(self, source_name: str, keyword: str, items: List[RSSItem]):
        """写入缓存（只缓存有结果的）。"""
        if not items:
            return
        key = f"{source_name}:{keyword}"
        with self._lock:
            self._cache[key] = (time.time(), list(items))
            # LRU 清理：超过 500 条时删最旧的
            if len(self._cache) > 500:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]

    def clear(self):
        with self._lock:
            self._cache.clear()


# ── 全局速率限制 ──

class RateLimiter:
    """全局速率限制器：每个源每分钟最多 N 次请求。"""

    def __init__(self, max_per_minute: int = 4):
        self._max = max_per_minute
        self._timestamps: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def acquire(self, source_name: str) -> bool:
        """尝试获取请求许可。返回 True 表示可以请求，False 表示需要等待。"""
        now = time.time()
        with self._lock:
            # 清理 1 分钟前的记录
            self._timestamps[source_name] = [
                t for t in self._timestamps[source_name] if now - t < 60
            ]
            if len(self._timestamps[source_name]) >= self._max:
                return False
            self._timestamps[source_name].append(now)
            return True

    def wait_and_acquire(self, source_name: str, timeout: float = 120) -> bool:
        """等待直到获取许可或超时。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire(source_name):
                return True
            time.sleep(2)
        return False


# 全局实例
_search_cache = SearchResultCache(ttl_seconds=1800)  # 30 分钟
_rate_limiter = RateLimiter(max_per_minute=4)  # 每源每分钟最多 4 次


def clear_rss_search_cache() -> None:
    """插件实现热更新后清空旧 RSS 结果。"""
    _search_cache.clear()


# ── 源管理器 ──

class RSSSourceManager:
    """线程安全地管理 RSS 源，并支持插件热刷新。"""

    def __init__(self):
        self._sources: Dict[str, RSSSourceBase] = {}
        self._lock = threading.RLock()

    def register(self, source: RSSSourceBase):
        """注册一个 RSS 源。"""
        with self._lock:
            self._sources[source.name] = source
        logger.info(f"[RSSEngine] 注册源: {source.name} ({source.display_name})")

    def replace_sources(self, sources: List[RSSSourceBase]) -> None:
        """原子替换全部源，并保留同名源的启用状态。"""
        with self._lock:
            enabled_by_name = {
                name: source.enabled for name, source in self._sources.items()
            }
            replacement = {}
            for source in sources:
                if source.name in enabled_by_name:
                    source.enabled = enabled_by_name[source.name]
                replacement[source.name] = source
            self._sources = replacement
        logger.info(f"[RSSEngine] RSS 源已刷新: {list(replacement)}")

    def get_enabled_sources(self) -> List[RSSSourceBase]:
        """获取所有启用源的稳定快照。"""
        with self._lock:
            return [source for source in self._sources.values() if source.enabled]

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """获取所有源的状态快照（供 API 返回）。"""
        with self._lock:
            return [
                {
                    "name": source.name,
                    "display_name": source.display_name,
                    "enabled": source.enabled,
                }
                for source in self._sources.values()
            ]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """启用或禁用指定源。"""
        with self._lock:
            source = self._sources.get(name)
            if source is None:
                return False
            source.enabled = enabled
            return True


# ── 频率衰减 ──

def should_search_now(sub: Subscription, base_interval_hours: float = 4.0) -> bool:
    """判断订阅当前是否应该搜索。

    优先级：
    1. sub.search_interval_hours > 0 时使用自定义间隔
    2. 否则使用衰减策略：前72h→base / 3-14天→12h / 14-30天→24h / 30天→暂停
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

    since_last = (now - last).total_seconds() / 3600  # 小时

    # 自定义搜索间隔优先
    custom_interval = getattr(sub, "search_interval_hours", 0) or 0
    if custom_interval > 0:
        return since_last >= custom_interval

    # 默认衰减策略
    created = now
    if sub.created_at:
        try:
            created = datetime.strptime(sub.created_at, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pass

    age_days = (now - created).total_seconds() / 86400

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
        check_interval_seconds: float = 300,  # 每 5 分钟检查一轮（RSS 通道）
        search_interval_seconds: float = 14400,  # 直搜通道间隔（默认 4 小时）
        max_source_workers: int = 4,
        source_timeout_seconds: float = 30,
    ):
        self.sub_manager = sub_manager
        self.source_manager = source_manager
        self.download_manager = download_manager
        self.base_interval = base_interval_hours
        self.check_interval = check_interval_seconds
        self.search_interval = search_interval_seconds
        self.max_source_workers = max(1, max_source_workers)
        self.source_timeout = max(0.05, source_timeout_seconds)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._search_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._source_locks: Dict[str, threading.Lock] = {}
        self._source_locks_guard = threading.Lock()

    def start(self):
        """启动互不阻塞的 RSS 与直搜调度线程。"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="rss-scheduler")
        self._search_thread = threading.Thread(
            target=self._search_loop,
            daemon=True,
            name="subscription-search-scheduler",
        )
        self._thread.start()
        self._search_thread.start()
        logger.info(
            f"[RSSEngine] 调度器启动，RSS 检查间隔 {self.check_interval}s，"
            f"直搜间隔 {self.search_interval}s"
        )

    def stop(self):
        """停止两个调度线程。"""
        self._running = False
        self._stop_event.set()
        for thread in (self._thread, self._search_thread):
            if thread:
                thread.join(timeout=5)
        logger.info("[RSSEngine] 调度器已停止")

    def search_one(self, sub: Subscription) -> List[RSSItem]:
        """手动触发单个订阅搜索（不受频率衰减限制）"""
        return self._do_search(sub)

    def _loop(self):
        """RSS 调度循环；慢 RSS 源不会阻塞直搜通道。"""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[RSSEngine] RSS 调度异常: {e}")
            self._stop_event.wait(self.check_interval)

    def _search_loop(self):
        """直搜调度循环，与 RSS 调度独立运行。"""
        while self._running:
            try:
                self._tick_search()
            except Exception as e:
                logger.error(f"[RSSEngine] 直搜调度异常: {e}")
            self._stop_event.wait(self.search_interval)

    def _tick(self):
        """单次调度：遍历活跃订阅，判断是否该搜索 + 检测下载失败重试"""
        active_subs = self.sub_manager.get_all(state="active")
        if not active_subs:
            return

        # 检测下载失败，自动换候选重试
        self._retry_failed_downloads(active_subs)

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

    @staticmethod
    def _subscription_cache_key(sub: Subscription) -> str:
        """构造只包含源查询条件的稳定缓存键。"""
        payload = {
            "title": sub.title,
            "year": sub.year,
            "type": sub.type,
            "season": sub.season,
            "search_keyword": sub.search_keyword,
            "aliases": sub.aliases,
            "imdb_id": sub.imdb_id,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _get_source_lock(self, source_name: str) -> threading.Lock:
        """每个源只允许一个在途请求，避免手动搜索与调度器击穿缓存。"""
        with self._source_locks_guard:
            return self._source_locks.setdefault(source_name, threading.Lock())

    def _fetch_source(self, source: RSSSourceBase, sub: Subscription, cache_key: str):
        """拉取单个源，接入缓存、限流和同源请求合并。"""
        cached = _search_cache.get(source.name, cache_key)
        if cached is not None:
            return cached, ""

        source_lock = self._get_source_lock(source.name)
        if not source_lock.acquire(blocking=False):
            return [], "已有请求正在执行"
        try:
            cached = _search_cache.get(source.name, cache_key)
            if cached is not None:
                return cached, ""
            if not _rate_limiter.wait_and_acquire(source.name, timeout=5):
                return [], "速率限制超时"
            items = source.fetch(sub)
            _search_cache.set(source.name, cache_key, items)
            return items, ""
        finally:
            source_lock.release()

    def _do_search(self, sub: Subscription) -> List[RSSItem]:
        """执行搜索：遍历所有启用的源，合并结果后匹配"""
        sources = self.source_manager.get_enabled_sources()
        if not sources:
            return []

        # 订阅级别源过滤：sub.sources 非空时只用指定源
        if hasattr(sub, "sources") and sub.sources:
            sources = [s for s in sources if s.name in sub.sources]
            if not sources:
                logger.info(f"[RSSEngine] {sub.title}: 指定的源都未启用")
                return []

        all_items: List[RSSItem] = []
        source_errors: Dict[str, str] = {}
        source_items: Dict[str, List[RSSItem]] = {}
        cache_key = self._subscription_cache_key(sub)
        executor = ThreadPoolExecutor(
            max_workers=min(self.max_source_workers, len(sources)),
            thread_name_prefix="rss-source",
        )
        future_sources = {
            executor.submit(self._fetch_source, source, sub, cache_key): source
            for source in sources
        }
        done, pending = wait(future_sources, timeout=self.source_timeout)
        for future in done:
            source = future_sources[future]
            try:
                items, error = future.result()
                source_items[source.name] = items
                if error:
                    source_errors[source.name] = error
            except Exception as e:
                source_errors[source.name] = str(e)
                logger.error(f"[RSSEngine] 源 {source.name} 搜索失败: {e}")
        for future in pending:
            source = future_sources[future]
            source_errors[source.name] = f"超过 {self.source_timeout:g}s 总预算"
            future.cancel()
            logger.warning(
                f"[RSSEngine] 源 {source.name} 超过 {self.source_timeout:g}s 总预算，跳过本轮"
            )
        executor.shutdown(wait=False, cancel_futures=True)

        # 并发完成后仍按配置顺序合并，保证排序和测试结果稳定。
        for source in sources:
            all_items.extend(source_items.get(source.name, []))

        # 更新搜索时间和计数
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_data: Dict[str, Any] = {"last_search": now}
        if not sub.first_search:
            update_data["first_search"] = now

        # 匹配过滤
        matched = match_items(all_items, sub)

        # 构建搜索结果摘要
        summary = self._build_results_summary(all_items, matched, source_errors)
        update_data["last_results_summary"] = summary

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
                        logger.info(f"[RSSEngine] {sub.title} 自动暂停（30天无果）")
                except (ValueError, TypeError):
                    pass

        self.sub_manager.update(sub.id, update_data)

        # 写入搜索日志
        try:
            from notification_service import add_search_log, add_notification
            sources_ok = [s.name for s in sources if s.name not in source_errors]
            sources_fail = list(source_errors.keys())
            best_q = ""
            for item in matched:
                if item.quality_tag and item.quality_tag != "Unknown":
                    best_q = item.quality_tag
                    break
            add_search_log(
                self.sub_manager, sub.id,
                channel="rss", total=len(all_items), matched=len(matched),
                best_quality=best_q, sources_ok=sources_ok, sources_fail=sources_fail,
                summary=summary,
            )
            # 自动暂停时发通知
            if update_data.get("state") == "paused":
                add_notification(self.sub_manager, sub.id, "auto_paused", "长期未找到资源，已自动暂停")
        except Exception as e:
            logger.warning(f"[RSSEngine] 搜索日志写入失败: {e}")

        logger.info(f"[RSSEngine] {sub.title}: 搜索完成，原始 {len(all_items)} 条，匹配 {len(matched)} 条")
        return matched

    def _handle_results(self, sub: Subscription, matched: List[RSSItem]):
        """处理匹配结果：通知模式存储，自动模式下载，洗版模式比较质量"""
        if not matched:
            return

        if sub.mode == "notify":
            # 存入 found_resources
            resources = [item.model_dump() for item in matched]
            added_count = self.sub_manager.merge_found_resources(sub.id, resources)
            if added_count:
                logger.info(f"[RSSEngine] {sub.title}: 通知模式，新增 {added_count} 条待选资源")
                # 发现资源通知
                try:
                    from notification_service import add_notification
                    add_notification(
                        self.sub_manager, sub.id, "found_resource",
                        f"发现 {added_count} 条新资源，请手动选择下载",
                    )
                except Exception:
                    pass

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
                logger.info(f"[RSSEngine] 洗版: {sub.title} 发现更高质量 ({best_score} > {current_score})")
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
            ep_label = f" E{item.episode:02d}" if item.episode else ""
            task = DownloadTask(
                media_name=f"{sub.title}{ep_label}",
                download_url=item.download_url,
                save_path=sub.save_path,
                channel="qb",
                category_hint="tv" if sub.type == "tv" else "movie",
                subscription_id=sub.id,
                subscription_episode=item.episode,
            )
            self.download_manager.submit(task)
            logger.info(f"[RSSEngine] 自动下载: {task.media_name} (来源: {item.source_name})")
            # 下载提交通知
            try:
                from notification_service import add_notification
                quality_info = f" ({item.quality_tag})" if item.quality_tag and item.quality_tag != "Unknown" else ""
                add_notification(
                    self.sub_manager, sub.id, "download_complete",
                    f"已自动下载{ep_label}{quality_info}，来源: {item.source_name}",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[RSSEngine] 下载提交失败: {e}")

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
            raw = tmdb.get_raw(f"/tv/{sub.tmdb_id}/season/{season_num}")
            episodes = raw.get("episodes", [])
            today = datetime.now().strftime("%Y-%m-%d")
            downloaded = set(sub.downloaded_episodes.keys())
            for ep in episodes:
                air_date = ep.get("air_date", "")
                ep_num = ep.get("episode_number", 0)
                if air_date == today and str(ep_num) not in downloaded:
                    logger.info(f"[RSSEngine] 日历触发: {sub.title} E{ep_num} 今天播出")
                    return True
        except Exception:
            pass
        return False

    def _build_results_summary(
        self, all_items: List[RSSItem], matched: List[RSSItem], errors: Dict[str, str]
    ) -> str:
        """构建搜索结果摘要字符串，供前端展示。"""
        parts = []
        if matched:
            # 找最高质量
            best_quality = ""
            for item in matched:
                if item.quality_tag and item.quality_tag != "Unknown":
                    best_quality = item.quality_tag
                    break
            if best_quality:
                parts.append(f"搜到 {len(matched)} 条，最高 {best_quality}")
            else:
                parts.append(f"搜到 {len(matched)} 条")
        elif all_items:
            parts.append(f"搜到 {len(all_items)} 条，匹配 0 条")
        else:
            parts.append("未搜到资源")
        if errors:
            parts.append(f"{len(errors)} 源失败")
        return " · ".join(parts)

    def _retry_failed_downloads(self, active_subs: List[Subscription]):
        """检测下载失败的订阅任务，从 found_resources 中选下一个候选重试。"""
        if not self.download_manager:
            return
        for sub in active_subs:
            if not sub.found_resources:
                continue
            # 检查该订阅是否有失败的下载任务
            failed_tasks = [
                t for t in self.download_manager.tasks
                if t.subscription_id == sub.id and t.status in ("failed", "lost")
            ]
            if not failed_tasks:
                continue
            # 已尝试过的 URL 集合
            tried_urls = {t.download_url for t in self.download_manager.tasks if t.subscription_id == sub.id}
            # 从 found_resources 中找未尝试过的候选
            for res in sub.found_resources:
                url = res.get("download_url", "")
                if not url or url in tried_urls:
                    continue
                # 找到候选，提交下载
                try:
                    from download_manager import DownloadTask
                    ep = res.get("episode")
                    ep_label = f" E{ep:02d}" if ep else ""
                    task = DownloadTask(
                        media_name=f"{sub.title}{ep_label} (重试)",
                        download_url=url,
                        save_path=sub.save_path,
                        channel="qb",
                        category_hint="tv" if sub.type == "tv" else "movie",
                        subscription_id=sub.id,
                        subscription_episode=ep,
                    )
                    self.download_manager.submit(task)
                    logger.info(f"[RSSEngine] 下载失败重试: {task.media_name}")
                    break  # 每次只重试一个候选
                except Exception as e:
                    logger.error(f"[RSSEngine] 重试提交失败: {e}")

    def _tick_search(self):
        """直搜通道：用 search_service 搜索无 RSS 的源，补充覆盖。

        只搜无 RSS 的源（磁力熊/XL720/Bitsearch）+ 可选全源兜底。
        频率比 RSS 通道低（默认 4 小时一次）。
        """
        active_subs = self.sub_manager.get_all(state="active")
        if not active_subs:
            return

        # 无 RSS 的直搜源列表
        search_only_sources = ["cilixiong", "xl720", "bitsearch"]

        for sub in active_subs:
            if not self._running:
                break

            # 直搜通道也受频率衰减控制（用更长的基准间隔）
            if not should_search_now(sub, base_interval_hours=max(self.search_interval / 3600, 4.0)):
                continue

            # 随机延迟防限频
            delay = random.randint(10, 60)
            time.sleep(delay)
            if not self._running:
                break

            try:
                from search_service import build_keywords, search_all_sources
                from shared import get_clients, config_m

                # 构造搜索词
                aliases = sub.aliases or {}
                cn = (aliases.get("cn") or [""])[0] if aliases.get("cn") else sub.title
                en = (aliases.get("en") or [""])[0] if aliases.get("en") else ""
                original = (aliases.get("original") or aliases.get("jp") or [""])[0] if (aliases.get("original") or aliases.get("jp")) else ""

                keywords = build_keywords(
                    query=sub.search_keyword or sub.title,
                    cn_name=cn, en_name=en, original_name=original,
                    season_number=sub.season or 0,
                )

                # 订阅级别源过滤
                sources = search_only_sources
                if sub.sources:
                    # 只搜用户指定的源中属于直搜的
                    sources = [s for s in sub.sources if s in search_only_sources]
                    if not sources:
                        continue

                clients = get_clients()
                bt_overrides = config_m.config.bt_search_sources or {}

                results = search_all_sources(
                    keywords=keywords,
                    query=sub.search_keyword or sub.title,
                    sources=sources,
                    bt_overrides=bt_overrides,
                    search_client=clients.get("search"),
                    timeout=30,
                )

                if results:
                    # 转换为 RSSItem 格式以复用 match_items
                    from rss_source_base import RSSItem as _RSSItem, extract_episode, extract_season
                    rss_items = []
                    for r in results:
                        rss_items.append(_RSSItem(
                            title=r.get("title", ""),
                            download_url=r.get("download_url", ""),
                            size_gb=r.get("size_gb", 0),
                            seeders=r.get("seeders", 0),
                            info_hash=r.get("info_hash", ""),
                            quality_tag=r.get("quality_tag", ""),
                            resolution=r.get("resolution", ""),
                            episode=extract_episode(r.get("title", "")),
                            season=extract_season(r.get("title", "")),
                            source_name=r.get("source", r.get("indexer", "")),
                        ))

                    matched = match_items(rss_items, sub)
                    if matched:
                        logger.info(f"[RSSEngine/直搜] {sub.title}: 搜到 {len(results)} 条，匹配 {len(matched)} 条")
                        self._handle_results(sub, matched)

                    # 直搜通道搜索日志
                    try:
                        from notification_service import add_search_log
                        best_q = ""
                        for item in matched:
                            if item.quality_tag and item.quality_tag != "Unknown":
                                best_q = item.quality_tag
                                break
                        add_search_log(
                            self.sub_manager, sub.id,
                            channel="search", total=len(results), matched=len(matched),
                            best_quality=best_q, sources_ok=sources,
                            summary=f"直搜 {len(results)} 条，匹配 {len(matched)} 条",
                        )
                    except Exception:
                        pass
                else:
                    # 无结果也记录日志
                    try:
                        from notification_service import add_search_log
                        add_search_log(
                            self.sub_manager, sub.id,
                            channel="search", total=0, matched=0,
                            sources_ok=sources, summary="直搜未找到资源",
                        )
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"[RSSEngine/直搜] {sub.title} 搜索失败: {e}")


# ── RSSItem → SearchResult 桥接 ──

def rss_item_to_search_result(item: RSSItem) -> dict:
    """将 RSSItem 转换为 SearchResult 格式（dict），供下载和前端展示统一使用。"""
    from quality_parser import parse_quality, compute_quality_score
    quality = parse_quality(item.title)
    return {
        "title": item.title,
        "download_url": item.download_url,
        "info_url": item.info_url,
        "size_gb": item.size_gb,
        "seeders": item.seeders,
        "indexer": item.indexer or item.source_name,
        "source": item.source_name,
        "info_hash": item.info_hash,
        "quality": quality.model_dump() if hasattr(quality, "model_dump") else {},
        "quality_score": compute_quality_score(quality),
        "quality_tag": item.quality_tag,
        "resolution": item.resolution,
        "episode": item.episode,
        "season": item.season,
        "pub_date": item.pub_date,
    }
