"""
别名解析器：从多个数据源收集影片的所有已知名称变体
数据源：豆瓣搜索建议、Bangumi 搜索、NFO 文件
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

import douban_client
import bangumi_client
import scraper


@dataclass
class AliasSet:
    """影片别名集合"""
    cn_names: List[str] = field(default_factory=list)   # 中文名变体
    en_names: List[str] = field(default_factory=list)   # 英文名变体
    jp_names: List[str] = field(default_factory=list)   # 日文名变体
    original_title: str = ""                             # 原始标题
    year: str = ""
    source: str = ""  # 别名来源标记


def _is_cjk(text: str) -> bool:
    """判断字符串是否主要包含中日韩字符"""
    if not text:
        return False
    cjk_count = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff'
                    or '\u3040' <= ch <= '\u309f'
                    or '\u30a0' <= ch <= '\u30ff')
    return cjk_count > len(text) * 0.3


def _is_japanese(text: str) -> bool:
    """判断字符串是否包含日文假名"""
    if not text:
        return False
    return any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff'
               for ch in text)


def _is_chinese(text: str) -> bool:
    """判断字符串是否主要包含中文汉字（不含日文假名）"""
    if not text:
        return False
    has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in text)
    has_kana = any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff'
                   for ch in text)
    return has_cjk and not has_kana


def _is_english(text: str) -> bool:
    """判断字符串是否主要包含英文字母"""
    if not text:
        return False
    alpha_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return alpha_count > len(text.replace(" ", "")) * 0.5


def _classify_name(name: str) -> str:
    """分类名称语言：cn / en / jp"""
    if _is_japanese(name):
        return "jp"
    if _is_english(name):
        return "en"
    return "cn"


def _merge_alias_set(target: AliasSet, source: AliasSet) -> None:
    """将 source 中的别名合并到 target，去重"""
    for name in source.cn_names:
        if name and name not in target.cn_names:
            target.cn_names.append(name)
    for name in source.en_names:
        if name and name not in target.en_names:
            target.en_names.append(name)
    for name in source.jp_names:
        if name and name not in target.jp_names:
            target.jp_names.append(name)
    if source.original_title and not target.original_title:
        target.original_title = source.original_title
    if source.year and not target.year:
        target.year = source.year


class AliasResolver:
    def __init__(self, douban=None, bangumi=None):
        self.douban = douban or douban_client
        self.bangumi = bangumi or bangumi_client
        self._cache: dict[str, AliasSet] = {}

    def resolve(self, title: str, year: str = "",
                media_type: str = "") -> AliasSet:
        """解析影片别名，合并多源结果

        前置条件: title 非空
        后置条件:
          - 返回的 AliasSet 至少包含原始 title 在 cn_names 中
          - 所有名称已去重
          - 结果已缓存，相同 title 的重复调用不会发起新请求
        """
        if not title:
            return AliasSet()

        cache_key = title
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = AliasSet(year=year, original_title=title)

        # 始终将原始标题加入 cn_names
        result.cn_names.append(title)

        # 从豆瓣获取别名
        try:
            douban_aliases = self._from_douban(title)
            _merge_alias_set(result, douban_aliases)
        except Exception as e:
            print(f"[AliasResolver] douban failed, skipping: {e}")

        # 从 Bangumi 获取别名
        try:
            bangumi_aliases = self._from_bangumi(title)
            _merge_alias_set(result, bangumi_aliases)
        except Exception as e:
            print(f"[AliasResolver] bangumi failed, skipping: {e}")

        self._cache[cache_key] = result
        return result

    def _from_douban(self, title: str) -> AliasSet:
        """从豆瓣搜索建议提取 subtitle/别名

        豆瓣 search() 返回:
        [{"douban_id", "title", "year", "poster_url", "subtitle", "type", "episode"}, ...]
        subtitle 字段包含外文名/别名
        """
        aliases = AliasSet(source="douban")
        results = self.douban.search(title)
        if not results:
            return aliases

        for item in results:
            item_title = item.get("title", "")
            subtitle = item.get("subtitle", "")
            item_year = item.get("year", "")

            # 将豆瓣标题加入对应语言列表
            if item_title and item_title != title:
                lang = _classify_name(item_title)
                if lang == "jp":
                    if item_title not in aliases.jp_names:
                        aliases.jp_names.append(item_title)
                elif lang == "en":
                    if item_title not in aliases.en_names:
                        aliases.en_names.append(item_title)
                else:
                    if item_title not in aliases.cn_names:
                        aliases.cn_names.append(item_title)

            # subtitle 通常是外文名/别名，可能包含多个用 / 分隔
            if subtitle:
                parts = [p.strip() for p in subtitle.split("/")]
                for part in parts:
                    if not part:
                        continue
                    lang = _classify_name(part)
                    if lang == "jp":
                        if part not in aliases.jp_names:
                            aliases.jp_names.append(part)
                    elif lang == "en":
                        if part not in aliases.en_names:
                            aliases.en_names.append(part)
                    else:
                        if part not in aliases.cn_names:
                            aliases.cn_names.append(part)

            if item_year and not aliases.year:
                aliases.year = item_year

        return aliases

    def _from_bangumi(self, title: str) -> AliasSet:
        """从 Bangumi 搜索提取 original_title（日文原名）

        bangumi search() 返回:
        [{"bgm_id", "title", "original_title", "year", ...}, ...]
        original_title 通常是日文原名
        """
        aliases = AliasSet(source="bangumi")
        results = self.bangumi.search(title)
        if not results:
            return aliases

        for item in results:
            original = item.get("original_title", "")
            item_title = item.get("title", "")
            item_year = item.get("year", "")

            if original:
                lang = _classify_name(original)
                if lang == "jp":
                    if original not in aliases.jp_names:
                        aliases.jp_names.append(original)
                elif lang == "en":
                    if original not in aliases.en_names:
                        aliases.en_names.append(original)
                else:
                    if original not in aliases.cn_names:
                        aliases.cn_names.append(original)

                if not aliases.original_title:
                    aliases.original_title = original

            if item_title and item_title != title:
                lang = _classify_name(item_title)
                if lang == "jp":
                    if item_title not in aliases.jp_names:
                        aliases.jp_names.append(item_title)
                elif lang == "en":
                    if item_title not in aliases.en_names:
                        aliases.en_names.append(item_title)
                else:
                    if item_title not in aliases.cn_names:
                        aliases.cn_names.append(item_title)

            if item_year and not aliases.year:
                aliases.year = item_year

        return aliases

    def _from_nfo(self, folder_path: str) -> AliasSet:
        """从已有 NFO 文件提取别名

        scraper.read_nfo() 返回:
        {"title", "original_title", "year", "media_type", ...}
        """
        aliases = AliasSet(source="nfo")
        if not folder_path:
            return aliases

        try:
            nfo_data = scraper.read_nfo(folder_path)
        except Exception as e:
            print(f"[AliasResolver] NFO read failed: {e}")
            return aliases

        if not nfo_data:
            return aliases

        original = nfo_data.get("original_title", "")
        nfo_title = nfo_data.get("title", "")
        nfo_year = nfo_data.get("year", "")

        if original:
            aliases.original_title = original
            lang = _classify_name(original)
            if lang == "jp":
                aliases.jp_names.append(original)
            elif lang == "en":
                aliases.en_names.append(original)
            else:
                aliases.cn_names.append(original)

        if nfo_title:
            lang = _classify_name(nfo_title)
            if lang == "jp":
                if nfo_title not in aliases.jp_names:
                    aliases.jp_names.append(nfo_title)
            elif lang == "en":
                if nfo_title not in aliases.en_names:
                    aliases.en_names.append(nfo_title)
            else:
                if nfo_title not in aliases.cn_names:
                    aliases.cn_names.append(nfo_title)

        if nfo_year:
            aliases.year = nfo_year

        return aliases
