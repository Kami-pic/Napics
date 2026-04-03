"""人人电影网 (rrdynb.com) 爬虫。

搜索接口被 Cloudflare 保护，使用 cloudscraper 绕过。
搜索路径：/plus/search.php?q=关键词
搜索流程：cloudscraper 预热首页 → GET 搜索 → 解析结果页 → 逐条访问详情页 → 提取网盘链接+提取码。
"""

import re
import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper_base import ScraperBase
from pan_models import PanResult, PanType, VALID_PAN_DOMAINS

logger = logging.getLogger(__name__)

# 网盘域名 → PanType 映射
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
    r"(?:提取码|密码|访问码|提取密码)\s*[:：]\s*([a-zA-Z0-9]{4,8})",
)

# 网盘链接正则
_PAN_URL_RE = re.compile(
    r"https?://(?:" +
    "|".join(re.escape(d) for d in VALID_PAN_DOMAINS) +
    r")[^\s\"'<>]*",
)

_YEAR_RE = re.compile(r"((?:19|20)\d{2})")


class RrdynbScraper(ScraperBase):
    """人人电影网爬虫 — 使用 cloudscraper 绕过 Cloudflare。"""

    BASE_URL = "https://www.rrdynb.com"
    SEARCH_PATH = "/plus/search.php"
    SOURCE_NAME = "rrdynb"
    MAX_DETAIL_PAGES = 5

    def __init__(self, proxy: Optional[str] = None):
        super().__init__(proxy=proxy)
        self._cs = None
        self._warmed_up = False

    def _get_cs(self):
        """懒加载 cloudscraper 实例。"""
        if self._cs is not None:
            return self._cs
        try:
            import cloudscraper
            self._cs = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows"}
            )
            if self.proxy:
                self._cs.proxies = {"http": self.proxy, "https": self.proxy}
            return self._cs
        except ImportError:
            logger.warning("[rrdynb] cloudscraper 未安装")
            return None

    def warm_up(self) -> None:
        """预热：访问首页获取 Cloudflare cookie。"""
        if self._warmed_up:
            return
        cs = self._get_cs()
        if cs:
            try:
                resp = cs.get(self.BASE_URL, timeout=15)
                if resp.status_code == 200:
                    self._warmed_up = True
                    logger.info("[rrdynb] cloudscraper 预热成功")
            except Exception as e:
                logger.warning("[rrdynb] 预热失败: %s", str(e))

    def _request(self, url: str, **kwargs):
        """优先用 cloudscraper，降级用 session。"""
        cs = self._get_cs()
        if cs:
            try:
                return cs.get(url, timeout=kwargs.get("timeout", 15))
            except Exception as e:
                logger.warning("[rrdynb] cloudscraper 请求失败: %s", str(e))
        # 降级
        return self.request_with_backoff(url, timeout=kwargs.get("timeout", 15))

    def search(self, keyword: str) -> List[PanResult]:
        """搜索并返回 PanResult 列表。"""
        cached = self.get_cached(keyword)
        if cached is not None:
            return cached

        if not self._warmed_up:
            self.warm_up()

        try:
            search_items = self._do_search(keyword)
            if not search_items:
                logger.info("[rrdynb] 搜索 '%s' 无结果", keyword)
                return []

            all_results: List[PanResult] = []
            for item in search_items[:self.MAX_DETAIL_PAGES]:
                self.random_delay()
                detail_results = self._parse_detail_page(
                    item["url"], item["title"]
                )
                all_results.extend(detail_results)

            self.set_cached(keyword, all_results)
            logger.info("[rrdynb] 搜索 '%s' 获取 %d 条结果", keyword, len(all_results))
            return all_results

        except Exception as e:
            logger.error("[rrdynb] 搜索异常: %s", str(e))
            return []

    def _do_search(self, keyword: str) -> List[dict]:
        """GET /plus/search.php?q=关键词"""
        url = f"{self.BASE_URL}{self.SEARCH_PATH}"
        try:
            cs = self._get_cs()
            if cs:
                resp = cs.get(url, params={"q": keyword, "pagesize": 10}, timeout=15)
            else:
                resp = self.request_with_backoff(
                    url, params={"q": keyword, "pagesize": 10}, timeout=15
                )

            if resp.status_code != 200:
                logger.warning("[rrdynb] 搜索返回 %d", resp.status_code)
                return []

            return self._parse_search_page(resp.text)

        except Exception as e:
            logger.error("[rrdynb] 搜索请求失败: %s", str(e))
            return []

    def _parse_search_page(self, html: str) -> List[dict]:
        """解析搜索结果页。"""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        # 尝试多种选择器适配不同模板
        for selector in [
            ".stui-vodlist__box a",       # stui 模板
            ".module-item a",             # module 模板
            ".search-list a",             # 搜索列表
            "li .title a",               # 通用列表
            ".vodlist_item a",            # vodlist 模板
        ]:
            links = soup.select(selector)
            if links:
                for a in links:
                    href = a.get("href", "")
                    title = a.get("title", "") or a.get_text(strip=True)
                    if title and href and href != "#" and len(title) > 1:
                        full_url = urljoin(self.BASE_URL, href)
                        year_match = _YEAR_RE.search(title)
                        items.append({
                            "title": title,
                            "url": full_url,
                            "year": year_match.group(1) if year_match else "",
                        })
                break  # 找到匹配的选择器就停

        # 如果上面都没匹配到，用宽泛选择器
        if not items:
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                if not any(p in href for p in ["/vod/", "/movie/", "/tv/", "/detail/", ".html"]):
                    continue
                if href in ("#", "/", self.BASE_URL, self.BASE_URL + "/"):
                    continue
                full_url = urljoin(self.BASE_URL, href)
                year_match = _YEAR_RE.search(title)
                items.append({
                    "title": title,
                    "url": full_url,
                    "year": year_match.group(1) if year_match else "",
                })

        # 去重
        seen = set()
        deduped = []
        for item in items:
            if item["url"] not in seen:
                seen.add(item["url"])
                deduped.append(item)
        return deduped

    def _parse_detail_page(self, url: str, page_title: str) -> List[PanResult]:
        """解析详情页，提取网盘链接+提取码。"""
        try:
            resp = self._request(url, timeout=15)
            if resp.status_code != 200:
                return []
            return self._extract_pan_links(resp.text, page_title)
        except Exception as e:
            logger.warning("[rrdynb] 详情页解析失败 %s: %s", url, str(e))
            return []

    def _extract_pan_links(self, html: str, page_title: str) -> List[PanResult]:
        """从详情页提取所有网盘链接和提取码。"""
        results: List[PanResult] = []
        seen_urls = set()

        pan_urls = _PAN_URL_RE.findall(html)
        for raw_url in pan_urls:
            url = raw_url.rstrip(".,;:!?\"')")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            pan_type = self._detect_pan_type(url)
            if pan_type is None:
                continue

            password = self._find_nearby_password(html, raw_url)

            try:
                results.append(PanResult(
                    title=page_title,
                    pan_type=pan_type,
                    share_url=url,
                    password=password,
                    source=self.SOURCE_NAME,
                ))
            except ValueError as e:
                logger.debug("[rrdynb] PanResult 校验失败: %s", str(e))
                continue

        return results

    def _detect_pan_type(self, url: str) -> Optional[PanType]:
        """根据 URL 域名检测网盘类型。"""
        domain = urlparse(url).netloc.lower()
        for d, pt in _DOMAIN_TO_PAN_TYPE.items():
            if d in domain:
                return pt
        return None

    def _find_nearby_password(self, html: str, url: str, window: int = 200) -> str:
        """在 URL 附近文本中搜索提取码。"""
        idx = html.find(url)
        if idx < 0:
            return ""
        start = max(0, idx - window)
        end = min(len(html), idx + len(url) + window)
        context = html[start:end]
        match = _PASSWORD_RE.search(context)
        return match.group(1) if match else ""
