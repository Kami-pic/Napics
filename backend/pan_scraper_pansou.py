"""PanSou API 客户端 — 网盘搜索兜底源。

对接 PanSou 的 /api/search 接口，按目标网盘类型过滤结果。
未配置 API 地址时跳过搜索返回空结果。
"""

import logging
from typing import List, Optional
from urllib.parse import urlparse

from scraper_base import ScraperBase
from pan_models import PanResult, PanType, VALID_PAN_DOMAINS

logger = logging.getLogger(__name__)

# PanSou 返回的网盘类型标识 → PanType 映射
_PANSOU_TYPE_MAP = {
    "quark": PanType.QUARK,
    "夸克": PanType.QUARK,
    "aliyun": PanType.ALIYUN,
    "aliyundrive": PanType.ALIYUN,
    "阿里": PanType.ALIYUN,
    "baidu": PanType.BAIDU,
    "百度": PanType.BAIDU,
    "115": PanType.PAN115,
    "pikpak": PanType.PIKPAK,
}

# 目标网盘类型（只保留这些类型的结果）
_TARGET_PAN_TYPES = {
    PanType.QUARK, PanType.ALIYUN, PanType.BAIDU,
    PanType.PAN115, PanType.PIKPAK,
}


class PanSouClient(ScraperBase):
    """PanSou API 客户端 — 继承 ScraperBase。"""

    SOURCE_NAME = "pansou"

    def __init__(self, api_url: str = "", proxy: Optional[str] = None):
        super().__init__(proxy=proxy)
        self.api_url = api_url.rstrip("/") if api_url else ""

    def search(self, keyword: str) -> List[PanResult]:
        """搜索并返回 PanResult 列表。未配置 API 地址时返回空。"""
        if not self.api_url:
            logger.debug("[pansou] API 地址未配置，跳过")
            return []

        cached = self.get_cached(keyword)
        if cached is not None:
            return cached

        try:
            url = f"{self.api_url}/api/search"
            resp = self.request_with_backoff(
                url, method="GET",
                params={"keyword": keyword, "page": 1, "size": 20},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("[pansou] API 返回 %d", resp.status_code)
                return []

            data = resp.json()
            items = data.get("data", data.get("list", data.get("results", [])))
            if not isinstance(items, list):
                return []

            results = self._parse_results(items, keyword)
            self.set_cached(keyword, results)
            logger.info("[pansou] 搜索 '%s' 获取 %d 条结果", keyword, len(results))
            return results

        except Exception as e:
            logger.error("[pansou] 搜索异常: %s", str(e))
            return []

    def _parse_results(self, items: list, keyword: str) -> List[PanResult]:
        """解析 PanSou API 返回的结果列表。"""
        results = []
        seen_urls = set()

        for item in items:
            title = item.get("title", item.get("name", ""))
            share_url = item.get("url", item.get("share_url", item.get("link", "")))
            pan_type_str = item.get("type", item.get("pan_type", item.get("source", "")))
            password = item.get("password", item.get("pwd", ""))

            if not title or not share_url:
                continue
            if share_url in seen_urls:
                continue
            seen_urls.add(share_url)

            # 解析网盘类型
            pan_type = self._resolve_pan_type(pan_type_str, share_url)
            if pan_type not in _TARGET_PAN_TYPES:
                continue

            try:
                results.append(PanResult(
                    title=title,
                    pan_type=pan_type,
                    share_url=share_url,
                    password=str(password) if password else "",
                    source=self.SOURCE_NAME,
                ))
            except ValueError as e:
                logger.debug("[pansou] PanResult 校验失败: %s", str(e))
                continue

        return results

    def _resolve_pan_type(self, type_str: str, url: str) -> PanType:
        """解析网盘类型：先从 type 字段匹配，再从 URL 域名推断。"""
        # 从 type 字段匹配
        type_lower = type_str.lower().strip()
        for key, pt in _PANSOU_TYPE_MAP.items():
            if key in type_lower:
                return pt

        # 从 URL 域名推断
        domain = urlparse(url).netloc.lower()
        if "quark" in domain:
            return PanType.QUARK
        if "alipan" in domain or "aliyun" in domain:
            return PanType.ALIYUN
        if "baidu" in domain:
            return PanType.BAIDU
        if "115" in domain or "anxia" in domain:
            return PanType.PAN115
        if "pikpak" in domain:
            return PanType.PIKPAK

        return PanType.UNKNOWN
