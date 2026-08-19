"""assrt.net API 客户端。

封装搜索和详情两个接口，支持代理和速率限制。
API 文档：https://assrt.net/api/doc
"""

import logging
import time
import zipfile
import io
import os
import shutil
import tempfile
from typing import List, Optional, Tuple

import requests

from subtitle_models import (
    SubtitleDetail,
    SubtitleFileItem,
    SubtitleLang,
    SubtitleSearchItem,
)

logger = logging.getLogger(__name__)

# assrt API 基础地址
_BASE_URL = "https://api.assrt.net"
_ALT_BASE_URL = "https://api.makedie.me"  # 备用域名

# 速率限制：最少间隔（秒）
_MIN_INTERVAL_SEC = 1.0


class AssrtClient:
    """assrt.net API 客户端"""

    def __init__(self, token: str, proxy: str = ""):
        self._token = token
        self._proxy = proxy
        self._last_request_time: float = 0
        self._base_url = _BASE_URL

    def _get_proxies(self) -> dict:
        if self._proxy:
            return {"http": self._proxy, "https": self._proxy}
        return {}

    def _rate_limit(self):
        """简单速率限制：确保两次请求间隔 >= _MIN_INTERVAL_SEC"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        self._last_request_time = time.time()

    def _request(self, endpoint: str, params: dict) -> dict:
        """发起 API 请求"""
        self._rate_limit()
        params["token"] = self._token
        url = f"{self._base_url}{endpoint}"

        try:
            resp = requests.get(
                url,
                params=params,
                proxies=self._get_proxies(),
                timeout=15,
                headers={"User-Agent": "napics/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != 0:
                err_msg = data.get("sub", {}).get("result", "") or data.get("message", "未知错误")
                logger.warning(f"[assrt] API 错误: status={data.get('status')}, msg={err_msg}")
                return {}
            return data
        except requests.exceptions.RequestException as e:
            # 主域名失败时尝试备用域名
            if self._base_url == _BASE_URL:
                logger.warning(f"[assrt] 主域名请求失败: {e}，尝试备用域名")
                self._base_url = _ALT_BASE_URL
                return self._request(endpoint, params)
            logger.error(f"[assrt] 请求失败: {e}")
            return {}

    def search(
        self,
        query: str,
        *,
        is_file: bool = False,
        no_muxer: bool = False,
        pos: int = 0,
        cnt: int = 15,
    ) -> Tuple[List[SubtitleSearchItem], str]:
        """搜索字幕。

        返回：(结果列表, 搜索关键词)
        """
        params: dict = {"q": query, "pos": pos, "cnt": cnt}
        if is_file:
            params["is_file"] = 1
        if no_muxer:
            params["no_muxer"] = 1

        data = self._request("/v1/sub/search", params)
        if not data:
            return [], query

        sub_data = data.get("sub", {})
        keyword = sub_data.get("keyword", query)
        raw_subs = sub_data.get("subs", [])

        results: List[SubtitleSearchItem] = []
        for item in raw_subs:
            lang_raw = item.get("lang", {})
            lang = SubtitleLang(
                desc=lang_raw.get("desc", ""),
                langlist=lang_raw.get("langlist", {}),
            )
            results.append(SubtitleSearchItem(
                id=item.get("id", 0),
                native_name=item.get("native_name", ""),
                videoname=item.get("videoname", ""),
                subtype=item.get("subtype", ""),
                upload_time=item.get("upload_time", ""),
                vote_score=item.get("vote_score", 0),
                release_site=item.get("release_site", ""),
                lang=lang,
                revision=item.get("revision", 0),
            ))

        return results, keyword

    def detail(self, subtitle_id: int) -> Optional[SubtitleDetail]:
        """获取字幕详情（含下载链接）"""
        data = self._request("/v1/sub/detail", {"id": subtitle_id})
        if not data:
            return None

        sub_data = data.get("sub", {})
        subs = sub_data.get("subs", [])
        if not subs:
            return None

        item = subs[0]
        lang_raw = item.get("lang", {})
        lang = SubtitleLang(
            desc=lang_raw.get("desc", ""),
            langlist=lang_raw.get("langlist", {}),
        )

        filelist = []
        for f in item.get("filelist", []):
            filelist.append(SubtitleFileItem(
                f=f.get("f", ""),
                s=f.get("s", ""),
                url=f.get("url", ""),
            ))

        return SubtitleDetail(
            id=item.get("id", 0),
            native_name=item.get("native_name", ""),
            filename=item.get("filename", ""),
            title=item.get("title", ""),
            url=item.get("url", ""),
            size=item.get("size", 0),
            subtype=item.get("subtype", ""),
            upload_time=item.get("upload_time", ""),
            vote_score=item.get("vote_score", 0),
            release_site=item.get("release_site", ""),
            lang=lang,
            filelist=filelist,
            down_count=item.get("down_count", 0),
            view_count=item.get("view_count", 0),
        )

    def download_subtitle(
        self,
        download_url: str,
        video_path: str,
        language_suffix: str = "",
    ) -> List[str]:
        """下载字幕文件到视频同目录。

        参数：
        - download_url: 字幕下载地址（可能是 zip 或单文件）
        - video_path: 视频文件完整路径
        - language_suffix: 语言后缀（如 "chs"），为空则不加

        返回：保存的文件路径列表
        """
        video_dir = os.path.dirname(video_path)
        video_stem = os.path.splitext(os.path.basename(video_path))[0]

        try:
            resp = requests.get(
                download_url,
                proxies=self._get_proxies(),
                timeout=30,
                headers={"User-Agent": "napics/1.0"},
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[assrt] 下载字幕失败: {e}")
            return []

        content_type = resp.headers.get("Content-Type", "")
        saved_files: List[str] = []

        # 判断是否为 zip 文件
        if "zip" in content_type or download_url.endswith(".zip") or _is_zip_content(resp.content):
            saved_files = self._extract_zip(resp.content, video_dir, video_stem, language_suffix)
        else:
            # 单个字幕文件
            ext = _guess_extension(download_url, resp.content)
            suffix = f".{language_suffix}" if language_suffix else ""
            filename = f"{video_stem}{suffix}{ext}"
            save_path = os.path.join(video_dir, filename)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            saved_files.append(save_path)
            logger.info(f"[assrt] 字幕已保存: {save_path}")

        return saved_files

    def _extract_zip(
        self,
        content: bytes,
        video_dir: str,
        video_stem: str,
        language_suffix: str,
    ) -> List[str]:
        """解压 zip 包，提取字幕文件并重命名"""
        # 字幕文件扩展名
        sub_exts = {".srt", ".ass", ".ssa", ".sub", ".sup", ".idx", ".vtt"}
        saved: List[str] = []

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                sub_files = [
                    name for name in zf.namelist()
                    if os.path.splitext(name)[1].lower() in sub_exts
                ]

                if not sub_files:
                    logger.warning("[assrt] zip 包中未找到字幕文件")
                    return []

                for i, sub_name in enumerate(sub_files):
                    ext = os.path.splitext(sub_name)[1].lower()
                    suffix = f".{language_suffix}" if language_suffix else ""
                    # 多个字幕文件时加序号
                    index_suffix = f".{i+1}" if len(sub_files) > 1 else ""
                    filename = f"{video_stem}{suffix}{index_suffix}{ext}"
                    save_path = os.path.join(video_dir, filename)

                    with zf.open(sub_name) as src, open(save_path, "wb") as dst:
                        dst.write(src.read())
                    saved.append(save_path)
                    logger.info(f"[assrt] 字幕已保存: {save_path}")

        except zipfile.BadZipFile:
            logger.error("[assrt] zip 文件损坏")
        except Exception as e:
            logger.error(f"[assrt] 解压字幕失败: {e}")

        return saved


def _is_zip_content(content: bytes) -> bool:
    """通过 magic bytes 判断是否为 zip"""
    return content[:4] == b"PK\x03\x04"


def _guess_extension(url: str, content: bytes) -> str:
    """猜测字幕文件扩展名"""
    # 从 URL 猜
    for ext in (".srt", ".ass", ".ssa", ".sub", ".sup", ".vtt"):
        if ext in url.lower():
            return ext
    # 从内容猜（文本类字幕）
    try:
        text = content[:200].decode("utf-8", errors="ignore")
        if "[Script Info]" in text:
            return ".ass"
        if text.strip().startswith("1\n") or text.strip().startswith("1\r\n"):
            return ".srt"
    except Exception:
        pass
    return ".srt"  # 默认 srt
