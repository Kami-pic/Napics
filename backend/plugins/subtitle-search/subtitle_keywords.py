"""字幕搜索词构造 —— 与「搜索升级」保持同一套规则。

规则对齐 frontend/components/search/useSearchState.ts 的 searchTags：
按 folder_type 分支生成 中文 / 中文+英文 / 英文 三类变体，季集号按语言拼接。

各源语言偏好不同（assrt/SubHD 中文站、SubDL 英文站），
因此在同一份词表上按源重排优先级，而不是各写一套词。
"""

from dataclasses import dataclass
from typing import List, Optional

# 语言标识
LANG_CN = "cn"
LANG_EN = "en"
LANG_CN_EN = "cn_en"
LANG_ORIGINAL = "original"
LANG_QUERY = "query"

# 各源语言优先级（越靠前越先搜）
SOURCE_LANG_PRIORITY = {
    "assrt": [LANG_CN, LANG_CN_EN, LANG_EN, LANG_ORIGINAL, LANG_QUERY],
    "subhd": [LANG_CN, LANG_CN_EN, LANG_EN, LANG_QUERY],
    "subdl": [LANG_EN, LANG_ORIGINAL, LANG_CN, LANG_CN_EN, LANG_QUERY],
}

# 每个源最多尝试的搜索词数量（控制请求数与配额）
SOURCE_MAX_KEYWORDS = {
    "assrt": 4,
    "subhd": 3,
    "subdl": 3,
}


@dataclass
class KeywordTag:
    """一个候选搜索词及其语言归属"""
    keyword: str
    lang: str
    has_season: bool = False


def build_keyword_tags(
    *,
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    query: str = "",
    folder_type: str = "",
    season_number: Optional[int] = None,
    episode_tag: str = "",
) -> List[KeywordTag]:
    """构造候选搜索词（与搜索升级的 searchTags 同规则）。

    分支：
    - season / tv / series 且有季号：中文第N季 → 英文 SNN → 中文+英文 → 中文 → 英文
    - 有 episode_tag（SxxExx）：中文 SxxExx → 英文 SxxExx → 中文+英文 → 中文 → 英文
    - 其他（电影）：中文 → 中文+英文 → 英文
    """
    cn = (cn_name or "").strip()
    en = (en_name or "").strip()
    original = (original_name or "").strip()
    q = (query or "").strip()

    s_num = season_number or 0
    s_tag = f"S{str(s_num).zfill(2)}" if s_num else ""
    # cn 与 en 实质相同时不重复出词（忽略大小写）
    is_same = bool(cn) and cn.lower() == en.lower()

    tags: List[KeywordTag] = []

    def _push(keyword: str, lang: str, has_season: bool = False):
        tags.append(KeywordTag(keyword=keyword, lang=lang, has_season=has_season))

    if folder_type == "season" and s_num:
        if cn:
            _push(f"{cn} 第{s_num}季", LANG_CN, True)
        if en and s_tag and not is_same:
            _push(f"{en} {s_tag}", LANG_EN, True)
        if cn and en and not is_same:
            _push(f"{cn} {en}", LANG_CN_EN)
        if cn:
            _push(cn, LANG_CN)
        if en and not is_same:
            _push(en, LANG_EN)
    elif folder_type in ("tv", "series") and s_num:
        if cn:
            _push(f"{cn} 第{s_num}季", LANG_CN, True)
        if en and s_tag and not is_same:
            _push(f"{en} {s_tag}", LANG_EN, True)
        if cn:
            _push(cn, LANG_CN)
        if en and not is_same:
            _push(en, LANG_EN)
    elif episode_tag:
        if cn:
            _push(f"{cn} {episode_tag}", LANG_CN, True)
        if en and not is_same:
            _push(f"{en} {episode_tag}", LANG_EN, True)
        if cn and en and not is_same:
            _push(f"{cn} {en}", LANG_CN_EN)
        if cn:
            _push(cn, LANG_CN)
        if en and not is_same:
            _push(en, LANG_EN)
    else:
        if cn:
            _push(cn, LANG_CN)
        if cn and en and not is_same:
            _push(f"{cn} {en}", LANG_CN_EN)
        if en and not is_same:
            _push(en, LANG_EN)

    # 原始语言名（日/韩等）作为补充
    if original and original.lower() not in (cn.lower(), en.lower()):
        _push(original, LANG_ORIGINAL)

    # query 兜底（前端手动输入或无清洗名时）
    if q:
        _push(q, LANG_QUERY)

    # 去重（保持先后顺序）
    seen = set()
    deduped: List[KeywordTag] = []
    for tag in tags:
        key = tag.keyword.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return deduped


def keywords_for_source(source: str, tags: List[KeywordTag]) -> List[str]:
    """按源的语言偏好重排搜索词，返回该源的回退链。

    同一份词表在中文源上 cn 优先，在 SubDL 上 en 优先。
    """
    priority = SOURCE_LANG_PRIORITY.get(source, [LANG_CN, LANG_CN_EN, LANG_EN, LANG_QUERY])
    limit = SOURCE_MAX_KEYWORDS.get(source, 3)

    def _rank(tag: KeywordTag) -> int:
        try:
            return priority.index(tag.lang)
        except ValueError:
            return len(priority)

    # 只保留该源支持的语言，稳定排序后截断
    allowed = [tag for tag in tags if tag.lang in priority]
    allowed.sort(key=_rank)

    result: List[str] = []
    seen = set()
    for tag in allowed:
        key = tag.keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag.keyword)
        if len(result) >= limit:
            break
    return result


def base_names_for_source(source: str, tags: List[KeywordTag]) -> List[str]:
    """返回不含季集号的基础名回退链。

    SubDL 的季集号走独立请求参数（season_number / episode_number），
    搜索词里不应再拼 "S03E05"，否则匹配不到。
    """
    priority = SOURCE_LANG_PRIORITY.get(source, [LANG_EN, LANG_CN, LANG_QUERY])
    limit = SOURCE_MAX_KEYWORDS.get(source, 3)

    def _rank(tag: KeywordTag) -> int:
        try:
            return priority.index(tag.lang)
        except ValueError:
            return len(priority)

    allowed = [tag for tag in tags if tag.lang in priority and not tag.has_season]
    allowed.sort(key=_rank)

    result: List[str] = []
    seen = set()
    for tag in allowed:
        key = tag.keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag.keyword)
        if len(result) >= limit:
            break
    return result
