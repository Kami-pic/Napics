"""assrt.net（射手网伪）API 客户端 —— 中文字幕主力源。

API 文档：https://assrt.net/api/doc
字幕服务由 assrt.net 提供。
"""

import logging
import time
from typing import List, Optional, Tuple

import requests

from subtitle_downloader import save_subtitle_from_url
from subtitle_models import (
    SubtitleDetail,
    SubtitleFileItem,
    SubtitleLang,
    SubtitleSearchItem,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.assrt.net"
_ALT_BASE_URL = "https://api.makedie.me"  # 备用域名（文档给出）

# 两次请求最小间隔（秒），避免触发配额限制
_MIN_INTERVAL_SEC = 1.0

# 浏览器 TLS 指纹（与 scraper_base 默认值保持一致）
_IMPERSONATE = "chrome131"


class AssrtClient:
    """assrt.net API 客户端"""

    source_id = "assrt"

    def __init__(self, token: str, proxy: str = ""):
        self._token = token
        self._proxy = proxy
        self._last_request_time: float = 0
        self._base_url = _BASE_URL
        self._cf_session = None

    def _get_proxies(self) -> dict:
        if self._proxy:
            return {"http": self._proxy, "https": self._proxy}
        return {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        self._last_request_time = time.time()

    def _get_cf_session(self):
        """懒加载 curl_cffi session。

        assrt.net 对普通 requests 的 TLS 握手会直接断开（SSL EOF），
        必须用浏览器 TLS 指纹才能连上。
        """
        if self._cf_session is not None:
            return self._cf_session
        try:
            from curl_cffi import requests as cf_requests
            self._cf_session = cf_requests.Session(impersonate=_IMPERSONATE)
        except ImportError:
            logger.warning("[assrt] curl_cffi 未安装，降级到 requests（可能连不上）")
            return None
        return self._cf_session

    def _http_get(self, url: str, params: dict):
        """优先 curl_cffi，失败降级 requests。返回 response 或 None。"""
        proxies = self._get_proxies()

        cf = self._get_cf_session()
        if cf is not None:
            try:
                return cf.get(
                    url,
                    params=params,
                    timeout=15,
                    proxies=proxies or None,
                )
            except Exception as e:
                logger.debug(f"[assrt] curl_cffi 请求失败({e})，降级 requests")

        return requests.get(
            url,
            params=params,
            proxies=proxies,
            timeout=15,
            headers={"User-Agent": "napics/1.0"},
        )

    def _request(self, endpoint: str, params: dict, _retried: bool = False) -> dict:
        """发起 API 请求。失败返回空 dict。"""
        self._rate_limit()
        params = dict(params)
        params["token"] = self._token

        try:
            resp = self._http_get(f"{self._base_url}{endpoint}", params)
            if resp is None:
                return {}
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status != 0:
                # 30900 = 配额超限，20001 = token 无效
                msg = (data.get("sub") or {}).get("result", "") or data.get("message", "")
                logger.warning(f"[assrt] API 错误 status={status} {msg}")
                return {}
            return data
        except Exception as e:
            if not _retried and self._base_url == _BASE_URL:
                logger.warning(f"[assrt] 主域名失败({e})，切备用域名重试")
                self._base_url = _ALT_BASE_URL
                return self._request(endpoint, params, _retried=True)
            logger.error(f"[assrt] 请求失败: {e}")
            return {}

    def search(
        self,
        query: str,
        *,
        is_file: bool = False,
        no_muxer: bool = True,
        pos: int = 0,
        cnt: int = 15,
    ) -> Tuple[List[SubtitleSearchItem], str]:
        """搜索字幕，返回 (结果列表, 实际搜索词)。"""
        params: dict = {"q": query, "pos": pos, "cnt": min(cnt, 15)}
        if is_file:
            params["is_file"] = 1
        if no_muxer:
            params["no_muxer"] = 1

        data = self._request("/v1/sub/search", params)
        if not data:
            return [], query

        sub_data = data.get("sub") or {}
        keyword = sub_data.get("keyword", query)
        raw_subs = sub_data.get("subs") or []

        results: List[SubtitleSearchItem] = []
        for item in raw_subs:
            lang_raw = item.get("lang") or {}
            results.append(SubtitleSearchItem(
                id=item.get("id", 0),
                native_name=item.get("native_name", ""),
                videoname=item.get("videoname", ""),
                subtype=item.get("subtype", ""),
                upload_time=item.get("upload_time", ""),
                vote_score=item.get("vote_score", 0) or 0,
                release_site=item.get("release_site", ""),
                lang=SubtitleLang(
                    desc=lang_raw.get("desc", ""),
                    langlist=lang_raw.get("langlist") or {},
                ),
                revision=item.get("revision", 0) or 0,
                source=self.source_id,
                hit_keyword=query,
            ))
        return results, keyword

    def detail(self, subtitle_id: int) -> Optional[SubtitleDetail]:
        """获取字幕详情（含下载链接与压缩包内文件列表）。"""
        data = self._request("/v1/sub/detail", {"id": subtitle_id})
        if not data:
            return None

        subs = (data.get("sub") or {}).get("subs") or []
        if not subs:
            return None

        item = subs[0]
        lang_raw = item.get("lang") or {}
        filelist = [
            SubtitleFileItem(
                f=f.get("f", ""),
                s=f.get("s", ""),
                url=f.get("url", ""),
            )
            for f in (item.get("filelist") or [])
        ]

        return SubtitleDetail(
            id=item.get("id", 0),
            native_name=item.get("native_name", ""),
            filename=item.get("filename", ""),
            title=item.get("title", ""),
            url=item.get("url", ""),
            size=item.get("size", 0) or 0,
            subtype=item.get("subtype", ""),
            upload_time=item.get("upload_time", ""),
            vote_score=item.get("vote_score", 0) or 0,
            release_site=item.get("release_site", ""),
            lang=SubtitleLang(
                desc=lang_raw.get("desc", ""),
                langlist=lang_raw.get("langlist") or {},
            ),
            filelist=filelist,
            down_count=item.get("down_count", 0) or 0,
            view_count=item.get("view_count", 0) or 0,
        )

    def download_subtitle(
        self,
        download_url: str,
        video_path: str,
        language_suffix: str = "",
    ) -> List[str]:
        """下载字幕到视频同目录（复用公共下载器）。"""
        return save_subtitle_from_url(
            download_url,
            video_path,
            language_suffix=language_suffix,
            proxy=self._proxy,
        )
