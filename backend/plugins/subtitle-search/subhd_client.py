"""SubHD 客户端 —— 中文字幕补充源（无官方 API，走页面解析）。

站点：https://subhd.tv

已核实的站点行为（2026-08）：
- 搜索页：GET /search/{关键词}
- 结果卡片：div.col-lg-10，标题在 div.f16.fw-bold，发布名在 div.view-text
- 字幕详情链接：/a/{slug}，slug 是字母数字（非数字 ID）
- 下载：POST /api/sub/prepare-download，JSON body {"sid": slug}
  → {"success": true, "url": "/down/{slug}"}，再 GET 该 url 取文件
  注意：form 编码会被拒（415），必须发 JSON
"""

import logging
import re
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from subtitle_downloader import save_subtitle_from_url
from subtitle_models import SubtitleLang, SubtitleSearchItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://subhd.tv"
_PREPARE_DOWNLOAD = f"{_BASE_URL}/api/sub/prepare-download"

# 详情页链接：/a/{slug}，slug 为字母数字
_SLUG_PATTERN = re.compile(r"^/a/([A-Za-z0-9]+)")

# 卡片文本里的元信息：格式 / 大小 / 语言
_FORMAT_PATTERN = re.compile(r"\b(SRT|ASS|SSA|SUP|SUB|IDX|VTT)\b", re.IGNORECASE)
_SIZE_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?[kKmM])\b")


class SubhdClient:
    """SubHD 字幕搜索客户端"""

    source_id = "subhd"

    def __init__(self, proxy: str = ""):
        self._proxy = proxy
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def _get_proxies(self) -> dict:
        if self._proxy:
            return {"http": self._proxy, "https": self._proxy}
        return {}

    def search(self, query: str, limit: int = 15) -> Tuple[List[SubtitleSearchItem], str]:
        """搜索字幕，返回 (结果列表, 搜索词)。"""
        query = (query or "").strip()
        if not query:
            return [], query

        try:
            resp = self._session.get(
                f"{_BASE_URL}/search/{requests.utils.quote(query)}",
                proxies=self._get_proxies(),
                timeout=15,
            )
            resp.raise_for_status()
            # 站点未在响应头声明字符集时 requests 会猜成 GBK，必须显式指定
            resp.encoding = "utf-8"
        except requests.exceptions.RequestException as e:
            logger.warning(f"[subhd] 搜索请求失败: {e}")
            return [], query

        try:
            return self._parse_search_page(resp.text, query, limit), query
        except Exception as e:
            logger.warning(f"[subhd] 页面解析失败: {e}")
            return [], query

    def _parse_search_page(self, html: str, query: str, limit: int) -> List[SubtitleSearchItem]:
        """解析搜索结果页。

        只取结果卡片内的 /a/{slug} 链接，避开侧栏"最新/热门字幕"等推荐位
        （那些是 /d/{数字} 链接，混进来会变成一堆无关影片）。
        """
        soup = BeautifulSoup(html, "html.parser")
        results: List[SubtitleSearchItem] = []
        seen_slugs = set()

        for card in soup.select("div.col-lg-10"):
            anchor = None
            slug = ""
            for a in card.find_all("a", href=True):
                match = _SLUG_PATTERN.match(a["href"])
                if match:
                    anchor = a
                    slug = match.group(1)
                    break
            if not anchor or not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            title_el = card.select_one("div.f16.fw-bold")
            release_el = card.select_one("div.view-text")
            title = title_el.get_text(strip=True) if title_el else anchor.get_text(strip=True)
            release_name = release_el.get_text(strip=True) if release_el else ""
            if not title:
                continue

            card_text = card.get_text(" ", strip=True)
            size_match = _SIZE_PATTERN.search(card_text)

            results.append(SubtitleSearchItem(
                # 前端列表 key 需要数字 ID，slug 才是下载用的真实标识
                id=abs(hash(slug)) & 0x7FFFFFFF,
                slug=slug,
                native_name=title,
                videoname=release_name,
                subtype=_detect_format(card_text),
                upload_time=_detect_date(card_text),
                vote_score=0,
                release_site=_detect_publisher(card_text) or "SubHD",
                lang=SubtitleLang(desc=_detect_lang(card_text), langlist={}),
                revision=0,
                source=self.source_id,
                download_url="",  # 下载时换取一次性链接
                hit_keyword=query,
                file_size=size_match.group(1) if size_match else "",
            ))
            if len(results) >= limit:
                break
        return results

    def resolve_download_url(self, slug: str) -> Optional[str]:
        """换取一次性下载链接。失败返回 None。"""
        if not slug:
            return None

        # 先访问详情页建立会话（站点按会话签发下载链接，跳过这步会 403）
        try:
            self._session.get(
                f"{_BASE_URL}/a/{slug}",
                proxies=self._get_proxies(),
                timeout=20,
            )
        except requests.exceptions.RequestException as e:
            logger.debug(f"[subhd] 详情页预访问失败 slug={slug}: {e}")

        try:
            resp = self._session.post(
                _PREPARE_DOWNLOAD,
                json={"sid": slug},  # 必须 JSON，form 编码会被拒（415）
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{_BASE_URL}/a/{slug}",
                },
                proxies=self._get_proxies(),
                timeout=25,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[subhd] 获取下载链接失败 slug={slug}: {e}")
            return None

        if not data.get("success"):
            logger.warning(f"[subhd] 站点拒绝下载 slug={slug}: {data.get('error', '')}")
            return None

        url = data.get("url") or ""
        if not url:
            return None
        return url if url.startswith("http") else f"{_BASE_URL}{url}"

    def download_subtitle(
        self,
        slug: str,
        video_path: str,
        language_suffix: str = "",
    ) -> List[str]:
        """换取链接后下载字幕。"""
        url = self.resolve_download_url(slug)
        if not url:
            return []
        # 复用本客户端 session：一次性链接只认换取它的那个会话
        return save_subtitle_from_url(
            url,
            video_path,
            language_suffix=language_suffix,
            proxy=self._proxy,
            referer=f"{_BASE_URL}/a/{slug}",
            session=self._session,
        )


def _detect_lang(text: str) -> str:
    """从卡片文本推断语言（卡片会列出"简体/繁体/双语/英语"等标签）"""
    has_simplified = "简体" in text
    has_traditional = "繁体" in text
    if "双语" in text or (has_simplified and "英语" in text):
        return "双语"
    if has_simplified:
        return "简中"
    if has_traditional:
        return "繁中"
    if "日语" in text or "日文" in text:
        return "日语"
    if "韩语" in text or "韩文" in text:
        return "韩语"
    if "粤语" in text:
        return "粤语"
    if "英语" in text or "英文" in text:
        return "英文"
    return ""


def _detect_format(text: str) -> str:
    """从卡片文本推断格式（卡片会标注 SRT / ASS / SUP 等）"""
    match = _FORMAT_PATTERN.search(text)
    if not match:
        return ""
    fmt = match.group(1).upper()
    if fmt == "SRT":
        return "Subrip(srt)"
    if fmt in ("SUB", "IDX"):
        return "VobSub"
    return fmt


def _detect_publisher(text: str) -> str:
    """提取"发布人 XXX"中的发布者"""
    match = re.search(r"发布人\s*([^\s]+)", text)
    return match.group(1) if match else ""


def _detect_date(text: str) -> str:
    """提取卡片上的日期（可能是 2025-04-27 或 07-17 13:37）"""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2}-\d{2})\s+\d{2}:\d{2}\b", text)
    return match.group(1) if match else ""
