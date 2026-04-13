"""订阅路由：CRUD + 手动搜索触发。"""

from fastapi import APIRouter
from typing import Optional

from shared import config_m, media_matcher, _tmdb_client
from subscriber import SubscriptionManager
from alias_resolver import AliasResolver

router = APIRouter()

# 懒加载订阅管理器单例
_sub_manager: Optional[SubscriptionManager] = None


def _get_sub_manager() -> SubscriptionManager:
    global _sub_manager
    if _sub_manager is None:
        import os
        base = os.path.dirname(os.path.abspath(__file__))
        # routes/ 的上级就是 backend/
        _sub_manager = SubscriptionManager(
            base_path=os.path.dirname(base)
        )
    return _sub_manager


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


# ── 路由 ──

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
    """手动触发单个订阅搜索（子阶段 B 实现搜索逻辑，当前返回占位）"""
    mgr = _get_sub_manager()
    sub = mgr.get(sub_id)
    if not sub:
        return {"status": "not_found"}
    # TODO: 子阶段 B 实现 subscribe_searcher.search_one(sub)
    return {"status": "ok", "message": "搜索功能将在子阶段 B 实现"}
