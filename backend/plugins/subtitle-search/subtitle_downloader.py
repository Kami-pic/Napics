"""字幕文件下载与落盘 —— 三个源共用。

职责：拉取字幕（单文件或 zip 包）→ 解压 → 按视频文件名重命名 → 写入视频同目录。
不关心字幕来自哪个源，只处理 URL。
"""

import io
import logging
import os
import zipfile
from typing import List, Optional

import requests  # noqa: F401  (Session 类型与默认请求器都来自这里)

logger = logging.getLogger(__name__)

# 字幕文件扩展名（zip 内提取时用）
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".sup", ".idx", ".vtt"}


def save_subtitle_from_url(
    download_url: str,
    video_path: str,
    *,
    language_suffix: str = "",
    proxy: str = "",
    referer: str = "",
    session: Optional[requests.Session] = None,
) -> List[str]:
    """下载字幕并保存到视频同目录，返回保存的文件路径列表。

    命名规则：视频名[.语言后缀][.序号].扩展名

    session: 需要携带站点会话 cookie 时传入（SubHD 的一次性下载链接
    只认换取该链接的那个会话，用新连接会 403）。
    """
    video_dir = os.path.dirname(video_path)
    video_stem = os.path.splitext(os.path.basename(video_path))[0]

    proxies = {"http": proxy, "https": proxy} if proxy else {}
    headers = {}
    if session is None:
        headers["User-Agent"] = "napics/1.0"
    if referer:
        headers["Referer"] = referer

    requester = session or requests
    try:
        resp = requester.get(download_url, proxies=proxies, timeout=30, headers=headers)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[subtitle] 下载失败: {e}")
        return []

    content = resp.content
    content_type = resp.headers.get("Content-Type", "")

    if "zip" in content_type or download_url.lower().endswith(".zip") or _is_zip(content):
        return _extract_zip(content, video_dir, video_stem, language_suffix)

    # 单个字幕文件
    ext = _guess_extension(download_url, content)
    suffix = f".{language_suffix}" if language_suffix else ""
    save_path = os.path.join(video_dir, f"{video_stem}{suffix}{ext}")
    try:
        with open(save_path, "wb") as f:
            f.write(content)
    except OSError as e:
        logger.error(f"[subtitle] 写入失败 {save_path}: {e}")
        return []
    logger.info(f"[subtitle] 已保存: {save_path}")
    return [save_path]


def _extract_zip(
    content: bytes,
    video_dir: str,
    video_stem: str,
    language_suffix: str,
) -> List[str]:
    """解压 zip 包，提取字幕文件并按视频名重命名"""
    saved: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            sub_files = [
                name for name in zf.namelist()
                if os.path.splitext(name)[1].lower() in SUBTITLE_EXTS
            ]
            if not sub_files:
                logger.warning("[subtitle] zip 包中未找到字幕文件")
                return []

            for index, sub_name in enumerate(sub_files):
                ext = os.path.splitext(sub_name)[1].lower()
                suffix = f".{language_suffix}" if language_suffix else ""
                order = f".{index + 1}" if len(sub_files) > 1 else ""
                save_path = os.path.join(video_dir, f"{video_stem}{suffix}{order}{ext}")
                with zf.open(sub_name) as src, open(save_path, "wb") as dst:
                    dst.write(src.read())
                saved.append(save_path)
                logger.info(f"[subtitle] 已保存: {save_path}")
    except zipfile.BadZipFile:
        logger.error("[subtitle] zip 文件损坏")
    except Exception as e:
        logger.error(f"[subtitle] 解压失败: {e}")
    return saved


def _is_zip(content: bytes) -> bool:
    """通过 magic bytes 判断是否为 zip"""
    return content[:4] == b"PK\x03\x04"


def _guess_extension(url: str, content: bytes) -> str:
    """猜测字幕文件扩展名"""
    lower_url = url.lower()
    for ext in (".srt", ".ass", ".ssa", ".sup", ".sub", ".vtt"):
        if ext in lower_url:
            return ext
    try:
        head = content[:200].decode("utf-8", errors="ignore")
        if "[Script Info]" in head:
            return ".ass"
        if "WEBVTT" in head:
            return ".vtt"
    except Exception:
        pass
    return ".srt"
