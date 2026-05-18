"""订阅路由：CRUD + 手动搜索 + RSS 源管理。"""

import os
import logging
from fastapi import APIRouter
from typing import Optional

from shared import config_m, media_matcher, _tmdb_client, _get_sub_manager
from subscriber import SubscriptionManager
from alias_resolver import AliasResolver
from rss_engine import RSSSourceManager, SubscriptionScheduler
from rss_provider_factory import get_rss_source_factories

logger = logging.getLogger(__name__)

router = APIRouter()

# 懒加载单例（SubscriptionManager 从 shared.py 获取）
_source_manager: Optional[RSSSourceManager] = None
_scheduler: Optional[SubscriptionScheduler] = None


def _get_source_manager() -> RSSSourceManager:
    global _source_manager
    if _source_manager is None:
        _source_manager = RSSSourceManager()
        for name, factory in get_rss_source_factories().items():
            try:
                _source_manager.register(factory())
            except Exception as e:
                logger.error(f"[Subscribe] RSS 源 {name} 注册失败: {e}")
    return _source_manager


def _get_scheduler() -> SubscriptionScheduler:
    global _scheduler
    if _scheduler is None:
        from shared import _get_download_manager, config_m

        _scheduler = SubscriptionScheduler(
            sub_manager=_get_sub_manager(),
            source_manager=_get_source_manager(),
            download_manager=_get_download_manager(),
            base_interval_hours=getattr(config_m.config, "subscribe_interval_hours", 4.0),
        )
        _scheduler.start()
    return _scheduler


def _get_alias_resolver() -> AliasResolver:
    return AliasResolver()


@router.get("/subscribe/check")
def check_subscribed(tmdb_id: Optional[int] = None,
                     title: Optional[str] = None,
                     year: Optional[str] = None,
                     season: Optional[int] = None):
    """检查是否已订阅（前端用于显示订阅状态）"""
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("subscribe"):
        return {"subscribed": False}
    mgr = _get_sub_manager()
    return {"subscribed": mgr.is_subscribed(
        tmdb_id=tmdb_id, title=title or "", year=year or "", season=season
    )}


@router.get("/subscribe/sources")
def list_sources():
    """查询所有 RSS 源及状态。未安装 feature-subscribe 插件时返回空。"""
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("subscribe"):
        return []
    sm = _get_source_manager()
    return sm.get_all_sources()


@router.put("/subscribe/sources/{name}")
def toggle_source(name: str, req: dict):
    """启用/禁用某个 RSS 源"""
    sm = _get_source_manager()
    enabled = req.get("enabled", True)
    if sm.set_enabled(name, enabled):
        return {"status": "ok"}
    return {"status": "not_found"}


@router.get("/subscribe/calendar")
def get_calendar():
    """订阅日历：返回剧集订阅的播出时间线"""
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("subscribe"):
        return {"calendar": []}
    mgr = _get_sub_manager()
    tmdb = _tmdb_client()
    if not tmdb:
        return []

    active_tv = [s for s in mgr.get_all() if s.type == "tv" and s.state in ("active", "paused") and s.purpose != "upgrade"]
    calendar = []
    for sub in active_tv:
        found_episodes = False
        # 优先 TMDB
        if sub.tmdb_id:
            try:
                season_num = sub.season or 1
                raw = tmdb.get_raw(f"/tv/{sub.tmdb_id}/season/{season_num}")
                episodes = raw.get("episodes", [])
                downloaded = set(sub.downloaded_episodes.keys())
                for ep in episodes:
                    ep_num = ep.get("episode_number", 0)
                    air_date = ep.get("air_date", "")
                    if not air_date or not ep_num:
                        continue
                    found_episodes = True
                    calendar.append({
                        "subscription_id": sub.id,
                        "title": sub.title,
                        "season": season_num,
                        "episode": ep_num,
                        "episode_title": ep.get("name", ""),
                        "air_date": air_date,
                        "downloaded": str(ep_num) in downloaded,
                        "poster": sub.poster,
                    })
            except Exception as e:
                logger.error(f"[Calendar] TMDB {sub.title} 获取失败: {e}")

        # TMDB 没有放送日期时 fallback 到 Bangumi（日漫常见）
        if not found_episodes:
            try:
                import bangumi_client as _bgm
                # 尝试用标题搜索 Bangumi 获取 bgm_id
                bgm_episodes = []
                bgm_results = _bgm.search(sub.title, media_type="动画")
                if bgm_results:
                    bgm_id = bgm_results[0].get("bgm_id", 0)
                    if bgm_id:
                        bgm_episodes = _bgm.get_episodes(bgm_id)
                if bgm_episodes:
                    downloaded = set(sub.downloaded_episodes.keys())
                    for ep in bgm_episodes:
                        ep_num = ep.get("episode", 0)
                        air_date = ep.get("air_date", "")
                        if not ep_num:
                            continue
                        calendar.append({
                            "subscription_id": sub.id,
                            "title": sub.title,
                            "season": sub.season or 1,
                            "episode": ep_num,
                            "episode_title": ep.get("name_cn", "") or ep.get("name", ""),
                            "air_date": air_date,
                            "downloaded": str(ep_num) in downloaded,
                            "poster": sub.poster,
                        })
                        found_episodes = True
            except Exception as e:
                logger.error(f"[Calendar] Bangumi fallback {sub.title} 失败: {e}")

    calendar.sort(key=lambda x: x.get("air_date", ""))
    return calendar


@router.get("/subscribe/save-paths")
def get_save_paths():
    """返回分类标签→路径映射，供前端根据 mediaType 自动填入保存路径。"""
    conf = config_m.config
    category_tags = conf.category_tags or {}
    # 反转：标签→路径列表
    tag_to_paths: dict = {}
    for path, tag in category_tags.items():
        tag_to_paths.setdefault(tag, []).append(path)
    # 兜底：nas_paths 的第一个路径
    default_path = conf.nas_paths[0] if conf.nas_paths else ""
    return {"paths": tag_to_paths, "default": default_path}


@router.get("/subscribe/notifications/unread")
def get_unread():
    """获取所有订阅的未读通知总数"""
    from notification_service import get_unread_count
    mgr = _get_sub_manager()
    return {"unread": get_unread_count(mgr)}


# ── CRUD 路由（参数路由放最后，避免和固定路径冲突）──

@router.post("/subscribe")
def add_subscription(req: dict):
    """新增订阅"""
    mgr = _get_sub_manager()
    tmdb = _tmdb_client()
    return mgr.add(
        data=req,
        alias_resolver=_get_alias_resolver(),
        media_matcher=media_matcher,
        tmdb=tmdb,
    )


@router.get("/subscribe")
def list_subscriptions(state: Optional[str] = None):
    """查询所有订阅。未安装 feature-subscribe 插件时返回空列表。"""
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("subscribe"):
        return []
    mgr = _get_sub_manager()
    subs = mgr.get_all(state=state)
    return [s.model_dump() for s in subs]


@router.get("/subscribe/{sub_id}")
def get_subscription(sub_id: str):
    """查询单个订阅"""
    mgr = _get_sub_manager()
    sub = mgr.get(sub_id)
    if not sub:
        return {"status": "not_found"}
    return sub.model_dump()


@router.put("/subscribe/{sub_id}")
def update_subscription(sub_id: str, req: dict):
    """更新订阅"""
    mgr = _get_sub_manager()
    return mgr.update(sub_id, req)


@router.delete("/subscribe/{sub_id}")
def delete_subscription(sub_id: str):
    """删除订阅"""
    mgr = _get_sub_manager()
    return mgr.delete(sub_id)


@router.post("/subscribe/{sub_id}/search")
def trigger_search(sub_id: str):
    """手动触发单个订阅搜索"""
    mgr = _get_sub_manager()
    sub = mgr.get(sub_id)
    if not sub:
        return {"status": "not_found"}
    scheduler = _get_scheduler()
    matched = scheduler.search_one(sub)
    # 通知模式：存入 found_resources
    if matched and sub.mode == "notify":
        resources = [item.model_dump() for item in matched]
        existing = sub.found_resources or []
        existing_hashes = {r.get("info_hash", "") for r in existing}
        new_res = [r for r in resources if r.get("info_hash", "") not in existing_hashes]
        if new_res:
            mgr.update(sub_id, {"found_resources": existing + new_res})
    return {
        "status": "ok",
        "matched": len(matched),
        "items": [item.model_dump() for item in matched[:20]],
    }


@router.get("/subscribe/{sub_id}/logs")
def get_search_logs(sub_id: str):
    """获取订阅的搜索日志"""
    mgr = _get_sub_manager()
    sub = mgr.get(sub_id)
    if not sub:
        return {"status": "not_found"}
    return [l.model_dump() for l in sub.search_logs]


@router.get("/subscribe/{sub_id}/notifications")
def get_notifications(sub_id: str):
    """获取订阅的通知列表"""
    mgr = _get_sub_manager()
    sub = mgr.get(sub_id)
    if not sub:
        return {"status": "not_found"}
    return [n.model_dump() for n in sub.notifications]


@router.post("/subscribe/{sub_id}/notifications/read")
def mark_read(sub_id: str):
    """标记订阅的所有通知为已读"""
    from notification_service import mark_notifications_read
    mgr = _get_sub_manager()
    mark_notifications_read(mgr, sub_id)
    return {"status": "ok"}
