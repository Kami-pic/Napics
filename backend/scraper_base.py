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
    """所有爬虫的基类。子类必须实现 search() 方法。

    use_curl_cffi=True 时使用 curl_cffi 模拟浏览器 TLS 指纹，
    能有效绕过 Cloudflare 的中低级保护（频率触发型 JS Challenge）。
    """

    # 指数退避间隔（秒）
    BACKOFF_DELAYS = [2, 4, 8]
    # 需要重试的 HTTP 状态码
    RETRY_STATUS_CODES = {429, 503}

    def __init__(self, proxy: Optional[str] = None, cache_ttl: int = 600,
                 use_curl_cffi: bool = False, impersonate: str = "chrome131"):
        self.proxy = proxy
        self.cache_ttl = cache_ttl          # 缓存 TTL（秒），默认 10 分钟
        self.max_retries = 3
        self.use_curl_cffi = use_curl_cffi
        self._impersonate = impersonate
        self._cache: Dict[str, tuple] = {}  # {cache_key: (timestamp, results)}
        self._cf_session = None             # curl_cffi session（懒加载）
        self.session = requests.Session()
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

    def _get_cf_session(self):
        """懒加载 curl_cffi session。"""
        if self._cf_session is not None:
            return self._cf_session
        try:
            from curl_cffi import requests as cf_requests
            self._cf_session = cf_requests.Session(impersonate=self._impersonate)
            return self._cf_session
        except ImportError:
            logger.warning("[%s] curl_cffi 未安装，降级到 requests", self.__class__.__name__)
            self.use_curl_cffi = False
            return None

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
        use_curl_cffi=True 时优先用 curl_cffi（浏览器 TLS 指纹），失败降级到 requests。
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                self._rotate_ua()
                if attempt > 0:
                    self.random_delay(2.0, 4.0)

                # 优先用 curl_cffi
                if self.use_curl_cffi:
                    resp = self._curl_cffi_request(url, method, timeout, **kwargs)
                    if resp is not None:
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

                # 降级到 requests
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
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    backoff = self.BACKOFF_DELAYS[min(attempt, len(self.BACKOFF_DELAYS) - 1)]
                    logger.warning(
                        "[%s] %s 异常: %s，%ds 后重试 (%d/%d)",
                        self.__class__.__name__, url, str(e),
                        backoff, attempt + 1, self.max_retries,
                    )
                    time.sleep(backoff)
                    continue

        raise last_exc or requests.RequestException(f"请求失败: {url}")

    def _curl_cffi_request(self, url: str, method: str, timeout: float, **kwargs):
        """用 curl_cffi 发请求，返回 requests.Response 兼容对象。"""
        cf = self._get_cf_session()
        if cf is None:
            return None
        try:
            proxy = self.proxy if self.proxy else None
            # curl_cffi 的参数名和 requests 略有不同
            cf_kwargs = {}
            if "params" in kwargs:
                cf_kwargs["params"] = kwargs["params"]
            if "data" in kwargs:
                cf_kwargs["data"] = kwargs["data"]
            if "json" in kwargs:
                cf_kwargs["json"] = kwargs["json"]
            if "headers" in kwargs:
                cf_kwargs["headers"] = kwargs["headers"]

            resp = cf.request(method, url, timeout=timeout, proxy=proxy, **cf_kwargs)
            return resp
        except Exception as e:
            logger.debug("[%s] curl_cffi 请求失败: %s，降级到 requests", self.__class__.__name__, str(e))
            return None

    # ──────────────────────────────────────────
    # Cloudflare 拦截检测
    # ──────────────────────────────────────────

    @staticmethod
    def is_cf_blocked(response) -> bool:
        """检测响应是否被 Cloudflare 拦截。

        检测 JS Challenge / Managed Challenge / Turnstile 等。
        返回 True 表示被拦截，调用方应跳过解析直接返回空结果。
        """
        if response.status_code == 403:
            text = response.text[:3000].lower() if hasattr(response, "text") else ""
            if any(k in text for k in ["just a moment", "challenge-platform", "cf-chl", "turnstile", "cloudflare"]):
                return True
        return False

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
