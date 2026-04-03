"""爬虫基类 — 所有网盘/磁力爬虫必须继承此类。

强制使用内置的：
- requests.Session 会话持久化（自动维护 Cookie/Token）
- random_delay（请求间 1-2s 随机延迟）
- UA 轮换池（10+ 常见浏览器 UA）
- request_with_backoff（指数退避重试 2s/4s/8s）
- 结果缓存（5 分钟 TTL）
- 可选代理池
- 标题清洗 + 分辨率提取 + 整季判定
- fast_check_url 链接存活预检
"""

import random
import time
import hashlib
import logging
from typing import Any, Dict, List, Optional

import requests

from pan_models import (
    PanResult, clean_title, parse_resolution,
    is_cam_quality, is_fragment_episode,
)

logger = logging.getLogger(__name__)

# 10+ 常见浏览器 User-Agent
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


class ScraperBase:
    """所有爬虫的基类。子类必须实现 search() 方法。"""

    # 指数退避间隔（秒）
    BACKOFF_DELAYS = [2, 4, 8]
    # 需要重试的 HTTP 状态码
    RETRY_STATUS_CODES = {429, 503}

    def __init__(self, proxy: Optional[str] = None, cache_ttl: int = 300):
        self.proxy = proxy
        self.cache_ttl = cache_ttl          # 缓存 TTL（秒），默认 5 分钟
        self.max_retries = 3
        self.session = requests.Session()
        self._cache: Dict[str, tuple] = {}  # {cache_key: (timestamp, results)}
        self._init_session()

    def _init_session(self) -> None:
        """初始化持久化会话：设置默认 headers、代理。
        子类可覆写此方法添加站点特定的初始化逻辑。"""
        self.session.headers.update({
            "User-Agent": random.choice(_UA_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

    def warm_up(self) -> None:
        """会话预热：请求目标站点首页获取必要的 Cookie/Token。
        默认空实现，ddys 等需要预热的站点覆写此方法。"""
        pass

    # ──────────────────────────────────────────
    # 请求控制
    # ──────────────────────────────────────────

    def random_delay(self, min_s: float = 1.0, max_s: float = 2.0) -> None:
        """请求间随机延迟，避免触发频率限制。"""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def _rotate_ua(self) -> None:
        """轮换 User-Agent。"""
        self.session.headers["User-Agent"] = random.choice(_UA_POOL)

    def request_with_backoff(
        self,
        url: str,
        method: str = "GET",
        timeout: float = 10.0,
        **kwargs,
    ) -> requests.Response:
        """带指数退避的 HTTP 请求。

        429/503/超时自动重试，最多 3 次，退避 2s/4s/8s。
        每次重试前轮换 UA。
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                self._rotate_ua()
                if attempt > 0:
                    self.random_delay()

                resp = self.session.request(
                    method, url, timeout=timeout, **kwargs
                )

                if resp.status_code in self.RETRY_STATUS_CODES and attempt < self.max_retries:
                    backoff = self.BACKOFF_DELAYS[min(attempt, len(self.BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "[%s] %s 返回 %d，%ds 后重试 (%d/%d)",
                        self.__class__.__name__, url, resp.status_code,
                        backoff, attempt + 1, self.max_retries,
                    )
                    time.sleep(backoff)
                    continue

                return resp

            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    backoff = self.BACKOFF_DELAYS[min(attempt, len(self.BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "[%s] %s 请求异常: %s，%ds 后重试 (%d/%d)",
                        self.__class__.__name__, url, str(e),
                        backoff, attempt + 1, self.max_retries,
                    )
                    time.sleep(backoff)
                    continue

        raise last_exc or requests.RequestException(f"请求失败: {url}")

    # ──────────────────────────────────────────
    # 缓存
    # ──────────────────────────────────────────

    def _cache_key(self, keyword: str) -> str:
        """生成缓存键（类名+关键词的 hash）。"""
        raw = f"{self.__class__.__name__}:{keyword}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get_cached(self, keyword: str) -> Optional[List]:
        """获取缓存结果（TTL 内有效）。"""
        key = self._cache_key(keyword)
        if key in self._cache:
            ts, results = self._cache[key]
            if time.time() - ts < self.cache_ttl:
                logger.debug("[%s] 缓存命中: %s", self.__class__.__name__, keyword)
                return results
            # 过期，删除
            del self._cache[key]
        return None

    def set_cached(self, keyword: str, results: List) -> None:
        """设置缓存（仅缓存有结果的，空结果不缓存）。"""
        if not results:
            return
        key = self._cache_key(keyword)
        self._cache[key] = (time.time(), results)

    # ──────────────────────────────────────────
    # 标题清洗与质量检测（复用 pan_models 逻辑）
    # ──────────────────────────────────────────

    @staticmethod
    def clean_title(raw_title: str) -> str:
        """标题清洗：去站点水印、乱码后缀。"""
        return clean_title(raw_title)

    @staticmethod
    def parse_resolution(title: str) -> str:
        """从标题提取分辨率。"""
        return parse_resolution(title)

    @staticmethod
    def is_cam_quality(title: str) -> bool:
        """检测枪版。"""
        return is_cam_quality(title)

    @staticmethod
    def is_fragment_episode(title: str) -> bool:
        """检测碎片集。"""
        return is_fragment_episode(title)

    # ──────────────────────────────────────────
    # 链接存活预检
    # ──────────────────────────────────────────

    def fast_check_url(self, url: str, timeout: float = 3.0) -> bool:
        """对 share_url 执行 HEAD 请求快速预检。

        失效链接（404/403/超时）返回 False。
        注意：仅对最终聚合结果执行，不对中间结果逐条检查。
        """
        try:
            resp = self.session.head(url, timeout=timeout, allow_redirects=True)
            # 200/301/302 视为存活
            return resp.status_code < 400
        except Exception:
            return False

    # ──────────────────────────────────────────
    # 子类必须实现
    # ──────────────────────────────────────────

    def search(self, keyword: str) -> List:
        """搜索方法 — 子类必须实现。

        返回 List[PanResult] 或 List[SearchResult]。
        """
        raise NotImplementedError(f"{self.__class__.__name__} 必须实现 search()")
