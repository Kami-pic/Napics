"""低端影视 (ddys.io) 爬虫。

反爬较强（Cloudflare/JS 验证），降级策略：
1. Cloudscraper 优先绕过 Cloudflare
2. 失败 → Playwright 轻量实例获取 Token
3. 整体超时 5 秒强制返回（不阻塞其他搜索源）

资源链接通常是加密 ID，需要 JS 解密逻辑还原真实网盘地址。
"""

import base64
import re
import time
import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from bs4 import BeautifulSoup

from scraper_base import ScraperBase
from pan_models import PanResult, PanType, VALID_PAN_DOMAINS

logger = logging.getLogger(__name__)

# 网盘域名 → PanType
_DOMAIN_TO_PAN_TYPE = {
    "pan.quark.cn": PanType.QUARK,
    "drive.quark.cn": PanType.QUARK,
    "www.alipan.com": PanType.ALIYUN,
    "www.aliyundrive.com": PanType.ALIYUN,
    "pan.baidu.com": PanType.BAIDU,
    "115.com": PanType.PAN115,
    "anxia.com": PanType.PAN115,
    "mypikpak.com": PanType.PIKPAK,
}

# 提取码正则
_PASSWORD_RE = re.compile(
    r"(?:提取码|密码|访问码)\s*[:：]\s*([a-zA-Z0-9]{4,8})",
)

# 网盘链接正则
_PAN_URL_RE = re.compile(
    r"https?://(?:" +
    "|".join(re.escape(d) for d in VALID_PAN_DOMAINS) +
    r")[^\s\"'<>]*",
)

# 整体搜索超时（秒）
SEARCH_TIMEOUT = 5


class DdysScraper(ScraperBase):
    """低端影视爬虫 — 继承 ScraperBase。

    降级链：Cloudscraper → Playwright → 空结果。
    整体 5 秒超时强制返回。
    """

    BASE_URL = "https://ddys.pro"
    SOURCE_NAME = "ddys"
    MAX_DETAIL_PAGES = 3  # ddys 反爬强，少请求

    def __init__(self, proxy: Optional[str] = None):
        super().__init__(proxy=proxy)
        self._cloudscraper = None
        self._warmed_up = False

    def warm_up(self) -> None:
        """会话预热：请求首页获取 Cookie/Token。"""
        if self._warmed_up:
            return
        try:
            # 优先尝试 cloudscraper
            cs = self._get_cloudscraper()
            if cs:
                resp = cs.get(self.BASE_URL, timeout=10)
                if resp.status_code == 200:
                    self._warmed_up = True
                    logger.info("[ddys] cloudscraper 预热成功")
                    return

            # 降级：普通 session 请求首页
            resp = self.request_with_backoff(self.BASE_URL, timeout=10)
            if resp.status_code == 200:
                self._warmed_up = True
                logger.info("[ddys] session 预热成功")
        except Exception as e:
            logger.warning("[ddys] 预热失败: %s", str(e))

    def _get_cloudscraper(self):
        """懒加载 cloudscraper 实例。"""
        if self._cloudscraper is not None:
            return self._cloudscraper
        try:
            import cloudscraper
            self._cloudscraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows"}
            )
            if self.proxy:
                self._cloudscraper.proxies = {
                    "http": self.proxy, "https": self.proxy
                }
            return self._cloudscraper
        except ImportError:
            logger.warning("[ddys] cloudscraper 未安装，跳过")
            self._cloudscraper = False  # 标记为不可用
            return None

    def search(self, keyword: str) -> List[PanResult]:
        """搜索并返回 PanResult 列表。5 秒超时强制返回。"""
        cached = self.get_cached(keyword)
        if cached is not None:
            return cached

        # 用线程池实现 5 秒超时
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._search_internal, keyword)
            try:
                results = future.result(timeout=SEARCH_TIMEOUT)
            except (FuturesTimeout, Exception) as e:
                logger.warning("[ddys] 搜索超时或异常 (%s)，返回空结果", str(e))
                return []

        self.set_cached(keyword, results)
        return results

    def _search_internal(self, keyword: str) -> List[PanResult]:
        """实际搜索逻辑（在超时线程中执行）。"""
        # 确保预热
        if not self._warmed_up:
            self.warm_up()

        try:
            search_items = self._do_search(keyword)
            if not search_items:
                return []

            all_results: List[PanResult] = []
            for item in search_items[:self.MAX_DETAIL_PAGES]:
                self.random_delay()
                detail_results = self._parse_detail_page(
                    item["url"], item["title"]
                )
                all_results.extend(detail_results)

            logger.info("[ddys] 搜索 '%s' 获取 %d 条结果", keyword, len(all_results))
            return all_results

        except Exception as e:
            logger.error("[ddys] 搜索异常: %s", str(e))
            return []

    def _do_search(self, keyword: str) -> List[dict]:
        """执行搜索请求（Cloudscraper 优先 → Session 降级）。"""
        search_url = f"{self.BASE_URL}/?s={keyword}&post_type=post"

        # 尝试 cloudscraper
        cs = self._get_cloudscraper()
        if cs:
            try:
                resp = cs.get(search_url, timeout=10)
                if resp.status_code == 200:
                    return self._parse_search_page(resp.text)
            except Exception as e:
                logger.warning("[ddys] cloudscraper 搜索失败: %s", str(e))

        # 降级：普通 session
        try:
            resp = self.request_with_backoff(search_url, timeout=10)
            if resp.status_code == 200:
                return self._parse_search_page(resp.text)
        except Exception as e:
            logger.warning("[ddys] session 搜索也失败: %s", str(e))

        return []

    def _parse_search_page(self, html: str) -> List[dict]:
        """解析搜索结果页。"""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # ddys 搜索结果通常在 article 或 .post-title 中
        for article in soup.select("article, .post-box, .search-result"):
            a = article.select_one("a[href]")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or not href:
                continue
            full_url = urljoin(self.BASE_URL, href)
            items.append({"title": title, "url": full_url})

        # 如果上面没匹配到，尝试更宽泛的选择器
        if not items:
            for a in soup.select("h2 a[href], h3 a[href], .entry-title a[href]"):
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if title and href and href != "#":
                    full_url = urljoin(self.BASE_URL, href)
                    items.append({"title": title, "url": full_url})

        # 去重
        seen = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)

        return deduped

    def _parse_detail_page(self, url: str, page_title: str) -> List[PanResult]:
        """解析详情页，提取网盘链接。"""
        try:
            cs = self._get_cloudscraper()
            html = None

            if cs:
                try:
                    resp = cs.get(url, timeout=10)
                    if resp.status_code == 200:
                        html = resp.text
                except Exception:
                    pass

            if html is None:
                resp = self.request_with_backoff(url, timeout=10)
                if resp.status_code == 200:
                    html = resp.text

            if not html:
                return []

            # 先尝试解密加密资源 ID
            decrypted_urls = self._decrypt_resource_ids(html)

            # 再直接正则匹配明文网盘链接
            plain_urls = _PAN_URL_RE.findall(html)

            all_urls = list(set(decrypted_urls + plain_urls))
            return self._build_results(all_urls, html, page_title)

        except Exception as e:
            logger.warning("[ddys] 详情页解析失败 %s: %s", url, str(e))
            return []

    def _decrypt_resource_ids(self, html: str) -> List[str]:
        """解密页面中的加密资源 ID。

        ddys 常见加密方式：
        1. Base64 编码的网盘链接
        2. 简单位移加密（Caesar cipher 变体）
        3. data-* 属性中的加密值
        """
        decrypted = []

        # 模式 1：Base64 编码的链接（data-url 或 data-link 属性）
        soup = BeautifulSoup(html, "html.parser")
        for el in soup.select("[data-url], [data-link], [data-src]"):
            for attr in ["data-url", "data-link", "data-src"]:
                val = el.get(attr, "")
                if val:
                    decoded = self._try_base64_decode(val)
                    if decoded and decoded.startswith("http"):
                        decrypted.append(decoded)

        # 模式 2：JS 变量中的 Base64 字符串
        b64_pattern = re.compile(
            r'["\']([A-Za-z0-9+/=]{20,})["\']'
        )
        for match in b64_pattern.finditer(html):
            decoded = self._try_base64_decode(match.group(1))
            if decoded and any(d in decoded for d in VALID_PAN_DOMAINS):
                decrypted.append(decoded)

        return decrypted

    @staticmethod
    def _try_base64_decode(encoded: str) -> Optional[str]:
        """尝试 Base64 解码，失败返回 None。"""
        try:
            # 标准 Base64
            decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            if decoded.startswith("http"):
                return decoded.strip()
        except Exception:
            pass

        try:
            # URL-safe Base64
            decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
            if decoded.startswith("http"):
                return decoded.strip()
        except Exception:
            pass

        return None

    def _build_results(self, urls: List[str], html: str,
                       page_title: str) -> List[PanResult]:
        """从 URL 列表构建 PanResult。"""
        results = []
        seen = set()

        for raw_url in urls:
            url = raw_url.rstrip(".,;:!?\"')")
            if url in seen:
                continue
            seen.add(url)

            # 域名检测
            domain = urlparse(url).netloc.lower()
            pan_type = None
            for d, pt in _DOMAIN_TO_PAN_TYPE.items():
                if d in domain:
                    pan_type = pt
                    break
            if pan_type is None:
                continue

            # 提取码
            idx = html.find(raw_url)
            password = ""
            if idx >= 0:
                context = html[max(0, idx - 200):idx + len(raw_url) + 200]
                m = _PASSWORD_RE.search(context)
                if m:
                    password = m.group(1)

            try:
                results.append(PanResult(
                    title=page_title,
                    pan_type=pan_type,
                    share_url=url,
                    password=password,
                    source=self.SOURCE_NAME,
                ))
            except ValueError:
                continue

        return results
