"""通知服务：统一管理订阅系统的通知推送。

当前实现：
- 内存通知队列（前端轮询获取）
- 写入订阅的 notifications 字段（持久化）

预留接口（后续可接入）：
- Bark（iOS 推送）
- Server 酱（微信推送）
- Webhook（自定义 HTTP 回调）
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 最大通知条数（每个订阅）
MAX_NOTIFICATIONS_PER_SUB = 100
# 最大搜索日志条数（每个订阅）
MAX_SEARCH_LOGS_PER_SUB = 50


def add_notification(
    sub_manager,
    subscription_id: str,
    notify_type: str,
    message: str,
):
    """向订阅添加一条通知。

    notify_type: "download_complete" / "upgrade_complete" / "found_resource" / "auto_paused"
    """
    sub = sub_manager.get(subscription_id)
    if not sub:
        return

    from subscriber import NotificationEntry
    entry = NotificationEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        type=notify_type,
        message=message,
        read=False,
    )

    notifications = list(sub.notifications)
    notifications.append(entry)
    # 保留最近 N 条
    if len(notifications) > MAX_NOTIFICATIONS_PER_SUB:
        notifications = notifications[-MAX_NOTIFICATIONS_PER_SUB:]

    sub_manager.update(subscription_id, {"notifications": [n.model_dump() for n in notifications]})
    logger.info(f"[Notification] {sub.title}: {notify_type} - {message}")

    # 预留：外部推送
    _push_external(sub, notify_type, message)


def add_search_log(
    sub_manager,
    subscription_id: str,
    channel: str,
    total: int,
    matched: int,
    downloaded: int = 0,
    best_quality: str = "",
    sources_ok: Optional[list] = None,
    sources_fail: Optional[list] = None,
    summary: str = "",
):
    """向订阅添加一条搜索日志。"""
    sub = sub_manager.get(subscription_id)
    if not sub:
        return

    from subscriber import SearchLogEntry
    entry = SearchLogEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        channel=channel,
        total=total,
        matched=matched,
        downloaded=downloaded,
        best_quality=best_quality,
        sources_ok=sources_ok or [],
        sources_fail=sources_fail or [],
        summary=summary,
    )

    logs = list(sub.search_logs)
    logs.append(entry)
    if len(logs) > MAX_SEARCH_LOGS_PER_SUB:
        logs = logs[-MAX_SEARCH_LOGS_PER_SUB:]

    sub_manager.update(subscription_id, {"search_logs": [l.model_dump() for l in logs]})


def mark_notifications_read(sub_manager, subscription_id: str):
    """标记订阅的所有通知为已读。"""
    sub = sub_manager.get(subscription_id)
    if not sub:
        return

    notifications = [n.model_dump() for n in sub.notifications]
    for n in notifications:
        n["read"] = True
    sub_manager.update(subscription_id, {"notifications": notifications})


def get_unread_count(sub_manager) -> int:
    """获取所有订阅的未读通知总数。"""
    total = 0
    for sub in sub_manager.get_all():
        total += sum(1 for n in sub.notifications if not n.read)
    return total


def _push_external(sub, notify_type: str, message: str):
    """预留：外部推送接口。后续可接入 Bark/Server酱/Webhook。"""
    # TODO: 从 config.json 读取推送配置
    # if config.bark_url:
    #     _push_bark(config.bark_url, sub.title, message)
    # if config.serverchan_key:
    #     _push_serverchan(config.serverchan_key, sub.title, message)
    pass
