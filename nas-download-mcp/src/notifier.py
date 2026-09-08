"""推送（todo §9）。可插拔，渠道由 NOTIFY_CHANNEL 决定。

第一版渠道待用户定；先实现 noop（默认）+ bark + telegram 骨架，
凭据走 env（不在此硬编码）。成功/失败/需要用户输入 三类事件。
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("nas_download_mcp.notify")


class Notifier:
    def __init__(self, channel: str = ""):
        self.channel = (channel or "").strip().lower()

    def notify(self, title: str, body: str, event: str = "info") -> None:
        """event: success | failure | waiting_user | info。失败只记日志，不影响主流程。"""
        try:
            if self.channel == "bark":
                self._bark(title, body)
            elif self.channel == "telegram":
                self._telegram(title, body)
            else:
                logger.info("[notify:%s] %s — %s", event, title, body)
        except Exception as e:
            logger.warning("[notify] 推送失败（不影响任务）: %s", e)

    def _bark(self, title: str, body: str) -> None:
        # BARK_URL 形如 https://api.day.app/<key>
        base = os.getenv("BARK_URL", "").rstrip("/")
        if not base:
            logger.info("[notify] 未配 BARK_URL，跳过")
            return
        httpx.get(f"{base}/{title}/{body}", timeout=5)

    def _telegram(self, title: str, body: str) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            logger.info("[notify] 未配 Telegram，跳过")
            return
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"{title}\n{body}"},
            timeout=5,
        )
