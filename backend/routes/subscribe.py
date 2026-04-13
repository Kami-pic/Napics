"""订阅路由：CRUD + 手动搜索 + RSS 源管理。"""

from fastapi import APIRouter
from typing import Optional

from shared import config_m, media_matcher, _tmdb_client
from subscriber import SubscriptionManager
from alias_resolver import AliasResolver
from rss_engine import RSSSourceManager, SubscriptionScheduler
from rss_source_prowlarr import ProwlarrRSSSource

router = APIRouter()

# 懒加载单例
_sub_manager: Optional[SubscriptionManager] = None
_source_manager: Optional[RSSSourceManager] = None
_scheduler: Optional[SubscriptionScheduler] = None


def _get_sub_manager() -> SubscriptionManager:
    global _sub_manager
    if _sub_manager is None:
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        _sub_manager = SubscriptionManager(base_path=os.path.dirname(base))
    return _sub_manager


def _get_source_manager() -> RSSSourceManager:
    global _source_manager
    if _source_manager is None:
        _source_manager = RSSSourceManager()
        # 注册 Prowlarr 源
        prowlarr_source = ProwlarrRSSSource()
        conf = config_m.config
        if conf.prowlarr_url and conf.prowlarr_api_key:
            from searcher import ProwlarrClient
            prowlarr_source.set_client(ProwlarrClient(conf.prowlarr_url, conf.prowlarr_api_key))
        _source_manager.register(prowlarr_source)
    return _source_manager


def _get_scheduler() -> SubscriptionScheduler:
    global _scheduler
    if _scheduler is None:
        from shared import _get_download_manager
        _scheduler = SubscriptionScheduler(
            sub_manager=_get_sub_manager(),
            source_manager=_get_source_manager(),
            download_manager=_get_download_manager(),
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
    mgr = _get_sub_manager()
    return {"subscribed": mgr.is_subscribed(
        tmdb_id=tmdb_id, title=title or "", year=year or "", season=season
    )}


@router.get("/subscribe/sources")
def list_sources():
    """查询所有 RSS 源及状态"""
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
    """查询所有订阅"""
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
