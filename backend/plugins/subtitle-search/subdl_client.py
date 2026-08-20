"""SubDL API 客户端 —— 英文/小语种回退源。

API: https://api.subdl.com/api/v1/subtitles
需要 api_key（subdl.com 注册后在账户设置获取）。
季集号走独立请求参数，不拼进搜索词。
"""

import logging
import time
from typing import List, Tuple

import requests

from subtitle_downloader import save_subtitle_from_url
from subtitle_models import SubtitleLang, SubtitleSearchItem

logger = logging.getLogger(__name__)

_API_URL = "https://api.subdl.com/api/v1/subtitles"
_DOWNLOAD_HOST = "https://dl.subdl.com"

_MIN_INTERVAL_SEC = 1.0


class SubdlClient:
    """SubDL 字幕搜索客户端"""

    source_id = "subdl"

    def __init__(self, api_key: str, proxy: str = ""):
        self._api_key = (api_key or "").strip()
        self._proxy = proxy
        self._last_request_time: float = 0

    @property
    def configured(self) -> bool:
        """SubDL 强制要求 api_key，未配置时该源不可用"""
        return bool(self._api_key)

    def _get_proxies(self) -> dict:
        if self._proxy:
            return {"http": self._proxy, "https": self._proxy}
        return {}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        self._last_request_time = time.time()

    def search(
        self,
        film_name: str,
        *,
        media_type: str = "",
        season_number: int = 0,
        episode_number: int = 0,
        languages: str = "ZH,EN",
        tmdb_id: int = 0,
        limit: int = 30,
    ) -> Tuple[List[SubtitleSearchItem], str]:
        """搜索字幕，返回 (结果列表, 实际搜索词)。

        季集号通过 season_number / episode_number 参数传递，
        搜索词只用基础片名。
        """
        if not self.configured:
            return [], film_name

        params = {
            "api_key": self._api_key,
            "subs_per_page": str(min(limit, 30)),
            "client": "custom_integration",
        }
        if tmdb_id:
            params["tmdb_id"] = str(tmdb_id)
        elif film_name:
            params["film_name"] = film_name
        else:
            return [], film_name

        if media_type in ("movie", "tv"):
            params["type"] = media_type
        if season_number > 0:
            params["season_number"] = str(season_number)
        if episode_number > 0:
            params["episode_number"] = str(episode_number)
        if languages:
            params["languages"] = languages

        self._rate_limit()
        try:
            resp = requests.get(
                _API_URL,
                params=params,
                proxies=self._get_proxies(),
                timeout=15,
                headers={"User-Agent": "napics/1.0", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"[subdl] 请求失败: {e}")
            return [], film_name
        except ValueError as e:
            logger.error(f"[subdl] 响应解析失败: {e}")
            return [], film_name

        if not data.get("status"):
            logger.warning(f"[subdl] API 返回失败: {data.get('error', '')}")
            return [], film_name

        results: List[SubtitleSearchItem] = []
        for item in data.get("subtitles") or []:
            url = item.get("url", "") or ""
            download_url = item.get("download_link") or (
                f"{_DOWNLOAD_HOST}{url}" if url.startswith("/") else url
            )
            if not download_url:
                continue

            display = item.get("release_name") or item.get("name") or ""
            lang_str = item.get("lang", "") or ""
            season = item.get("season") or 0
            episode = item.get("episode") or 0
            se_note = ""
            if season:
                se_note = f"S{str(season).zfill(2)}"
                if episode:
                    se_note += f"E{str(episode).zfill(2)}"

            results.append(SubtitleSearchItem(
                # SubDL 无稳定数字 ID，用下载路径哈希保证同一结果 ID 稳定
                id=abs(hash(download_url)) & 0x7FFFFFFF,
                native_name=display,
                videoname=item.get("release_name", "") or "",
                subtype=_guess_format(item.get("name", "") or display),
                upload_time="",
                vote_score=0,
                release_site=item.get("author") or "SubDL",
                lang=SubtitleLang(desc=_normalize_lang(lang_str), langlist={}),
                revision=0,
                source=self.source_id,
                download_url=download_url,
                hit_keyword=f"{film_name} {se_note}".strip() if se_note else film_name,
            ))
        return results, film_name

    def download_subtitle(
        self,
        download_url: str,
        video_path: str,
        language_suffix: str = "",
    ) -> List[str]:
        return save_subtitle_from_url(
            download_url,
            video_path,
            language_suffix=language_suffix,
            proxy=self._proxy,
            referer="https://subdl.com/",
        )


def _normalize_lang(lang: str) -> str:
    """SubDL 返回的是语言全名（english/chinese_simplified 等），转成中文短标签"""
    lower = (lang or "").lower()
    if "simplified" in lower or lower in ("chinese", "zh", "chi"):
        return "简中"
    if "traditional" in lower:
        return "繁中"
    if "english" in lower or lower == "en":
        return "英文"
    if "japanese" in lower:
        return "日语"
    if "korean" in lower:
        return "韩语"
    if "cantonese" in lower:
        return "粤语"
    return lang or ""


def _guess_format(filename: str) -> str:
    """从文件名猜字幕格式"""
    lower = (filename or "").lower()
    if ".ass" in lower:
        return "ASS"
    if ".ssa" in lower:
        return "SSA"
    if ".sup" in lower:
        return "SUP"
    if ".sub" in lower or "vobsub" in lower:
        return "VobSub"
    if ".srt" in lower:
        return "Subrip(srt)"
    return "Subrip(srt)"
