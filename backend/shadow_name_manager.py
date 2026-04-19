"""
影子名管理器：管理媒体项的隐藏标准化名称（Shadow Name）
影子名存储在 media_library.json 中，不修改实际文件名，
所有搜索/刮削/匹配优先使用影子名。
"""
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional


@dataclass
class ShadowNameEntry:
    """影子名条目"""
    shadow_name: str
    source: str  # "manual" | "tmdb" | "nfo" | "douban" | "bangumi" | "parsed"
    tmdb_id: Optional[int] = None


class ShadowNameManager:
    def __init__(self, library_path: str = "media_library.json"):
        self.library_path = library_path

    # ── 内部读写 ──

    def _load_library(self) -> list:
        if os.path.exists(self.library_path):
            with open(self.library_path, "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        return []

    def _save_library(self, data: list) -> None:
        with open(self.library_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _find_item(self, library: list, file_path: str) -> Optional[dict]:
        for item in library:
            if item.get("file_path") == file_path:
                return item
        return None

    # ── 公开 API ──

    def get(self, file_path: str) -> Optional[ShadowNameEntry]:
        """获取指定媒体项的影子名"""
        library = self._load_library()
        item = self._find_item(library, file_path)
        if not item or not item.get("shadow_name"):
            return None
        return ShadowNameEntry(
            shadow_name=item["shadow_name"],
            source=item.get("shadow_name_source", ""),
            tmdb_id=item.get("shadow_tmdb_id"),
        )

    def set(self, file_path: str, shadow_name: str,
            source: str = "manual",
            tmdb_id: Optional[int] = None) -> None:
        """设置影子名（任何来源均可写入，包括覆盖已有值）"""
        library = self._load_library()
        item = self._find_item(library, file_path)
        if item is None:
            return
        item["shadow_name"] = shadow_name
        item["shadow_name_source"] = source
        item["shadow_tmdb_id"] = tmdb_id
        self._save_library(library)

    def auto_fill(self, file_path: str, shadow_name: str,
                  source: str, tmdb_id: Optional[int] = None,
                  organize_status: str = "ok") -> bool:
        """自动填充影子名（分层优先级保护：高优先级不被低优先级覆盖）
        优先级：manual(4) > nfo(3) > tmdb(3) > douban/bangumi(2) > scrape(2) > parsed(1)
        返回 True 表示填充成功，False 表示已有更高优先级被跳过
        organize_status: "ok" | "scrape_failed" """
        # 优先级表（和 shared.py 的 NAME_SOURCE_PRIORITY 保持一致）
        _PRIORITY = {"manual": 4, "nfo": 3, "tmdb": 3, "douban": 2, "bangumi": 2, "scrape": 2, "parsed": 1, "": 0}
        library = self._load_library()
        item = self._find_item(library, file_path)
        if item is None:
            return False
        existing_source = item.get("shadow_name_source", "")
        if _PRIORITY.get(existing_source, 0) > _PRIORITY.get(source, 0):
            return False
        item["shadow_name"] = shadow_name
        item["shadow_name_source"] = source
        item["shadow_tmdb_id"] = tmdb_id
        item["organize_status"] = organize_status
        self._save_library(library)
        return True

    def clear(self, file_path: str) -> None:
        """清除影子名，移除所有影子名相关字段"""
        library = self._load_library()
        item = self._find_item(library, file_path)
        if item is None:
            return
        item.pop("shadow_name", None)
        item.pop("shadow_name_source", None)
        item.pop("shadow_tmdb_id", None)
        self._save_library(library)

    def get_search_name(self, file_path: str) -> str:
        """获取用于搜索的名称：优先影子名，fallback 到原始文件名"""
        library = self._load_library()
        item = self._find_item(library, file_path)
        if item is None:
            return ""
        if item.get("shadow_name"):
            return item["shadow_name"]
        return item.get("file_name", "")

    def batch_generate(self, tmdb_client=None) -> dict:
        """批量生成影子名
        1. 从 NFO 提取 originaltitle
        2. NFO 没有时，用文件名搜 TMDB 获取英文名
        3. originaltitle 不是英文时，额外请求 TMDB en-US 获取英文名
        返回 {"generated": int, "skipped": int, "failed": int}"""
        library = self._load_library()
        stats = {"generated": 0, "skipped": 0, "failed": 0}

        for item in library:
            # 已有手动影子名 → 跳过
            if item.get("shadow_name_source") == "manual":
                stats["skipped"] += 1
                continue

            file_path = item.get("file_path", "")
            if not file_path:
                stats["failed"] += 1
                continue

            shadow_name = None
            source = None
            tmdb_id = None

            # 方式1：从 NFO 提取
            try:
                nfo_info = self._read_nfo_originaltitle(file_path)
                if nfo_info:
                    original_title = nfo_info.get("original_title", "")
                    year = nfo_info.get("year", "")
                    nfo_tmdb_id = nfo_info.get("tmdb_id")
                    
                    # 如果 originaltitle 不是英文且有 tmdb_id，尝试获取英文名
                    if original_title and nfo_tmdb_id and tmdb_client:
                        if not self._is_latin(original_title):
                            try:
                                en = tmdb_client._get_english_title("movie", nfo_tmdb_id, original_title)
                                if not en:
                                    en = tmdb_client._get_english_title("tv", nfo_tmdb_id, original_title)
                                if en:
                                    original_title = en
                            except Exception:
                                pass
                    
                    if original_title:
                        shadow_name = f"{original_title} ({year})" if year else original_title
                        source = "nfo"
                        tmdb_id = nfo_tmdb_id
            except Exception:
                pass

            # 方式2：没有 NFO，用文件名搜 TMDB
            if not shadow_name and tmdb_client:
                try:
                    file_name = item.get("file_name", "")
                    if file_name:
                        result = tmdb_client.scrape_by_filename(file_name)
                        if result.tmdb_id and result.original_title:
                            orig = result.original_title
                            # 确保是英文
                            if not self._is_latin(orig):
                                try:
                                    mt = "tv" if result.media_type in ("tv", "tvshow", "episode") else "movie"
                                    en = tmdb_client._get_english_title(mt, result.tmdb_id, orig)
                                    if en:
                                        orig = en
                                except Exception:
                                    pass
                            year = result.year or ""
                            shadow_name = f"{orig} ({year})" if year else orig
                            source = "tmdb"
                            tmdb_id = result.tmdb_id
                except Exception:
                    pass

            if shadow_name:
                item["shadow_name"] = shadow_name
                item["shadow_name_source"] = source
                item["shadow_tmdb_id"] = tmdb_id
                stats["generated"] += 1
            else:
                stats["failed"] += 1

        self._save_library(library)
        return stats

    @staticmethod
    def _is_latin(text: str) -> bool:
        if not text:
            return False
        latin_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
        total = sum(1 for ch in text if ch.isalpha())
        return total > 0 and latin_count / total > 0.5

    # ── NFO 读取辅助 ──

    def _read_nfo_originaltitle(self, file_path: str) -> Optional[dict]:
        """从视频文件对应的 NFO 中提取 originaltitle、year、tmdb_id"""
        # 1. 同名 NFO（{filename}.nfo）
        base = os.path.splitext(file_path)[0]
        nfo_path = base + ".nfo"
        result = self._parse_nfo_file(nfo_path)
        if result:
            return result

        # 2. 所在文件夹的标准 NFO（movie.nfo / tvshow.nfo）
        folder = os.path.dirname(file_path)
        for name in ("movie.nfo", "tvshow.nfo", "season.nfo"):
            p = os.path.join(folder, name)
            result = self._parse_nfo_file(p)
            if result:
                return result

        return None

    def _parse_nfo_file(self, nfo_path: str) -> Optional[dict]:
        """解析单个 NFO 文件，提取 originaltitle / year / tmdb_id"""
        if not os.path.exists(nfo_path):
            return None
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            original_title = ""
            el = root.find("originaltitle")
            if el is not None and el.text:
                original_title = el.text.strip()
            if not original_title:
                return None
            year = ""
            el_year = root.find("year")
            if el_year is not None and el_year.text:
                year = el_year.text.strip()
            tmdb_id = None
            for uid in root.findall("uniqueid"):
                if uid.get("type") == "tmdb" and uid.text:
                    try:
                        tmdb_id = int(uid.text)
                    except ValueError:
                        pass
            return {
                "original_title": original_title,
                "year": year,
                "tmdb_id": tmdb_id,
            }
        except Exception:
            return None
