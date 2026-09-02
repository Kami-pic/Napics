"""
搜索词映射器：为每个搜索源选择最佳语言的搜索词 + 回退链。

职责：
- 维护源→语言优先级映射表
- 根据可用名称为指定源生成搜索词列表（首选 + 回退）
- 季号拼接（中文源"第N季"，英文源"S0N"）
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MultiLangKeywords:
    """多语言搜索词集合"""
    cn: str = ""           # 中文名
    en: str = ""           # 英文名
    original: str = ""     # 原始语言名（日/韩/法等非中非英）
    query: str = ""        # 用户输入的原始 query（兜底用）
    season_number: int = 0 # 季号（0 = 不拼接）
    # 目标年份。**不参与搜索词拼接**（把年份拼进搜索词会让 BT 站命中率骤降），
    # 只往下传给 enrich_result 做匹配加分 —— 重名不同年的片子非常多。
    year: str = ""


# 源→语言优先级映射（回退顺序）
# 每个源的列表表示：第一个是默认搜索词语言，后续是回退顺序
SOURCE_LANG_PRIORITY: Dict[str, List[str]] = {
    # BT/磁力源
    "prowlarr":     ["en", "cn", "query"],
    "bitsearch":    ["en", "cn"],
    "yts":          ["en", "cn"],
    "limetorrents": ["en", "cn"],
    "cilixiong":    ["cn", "en"],
    "xl720":        ["cn", "en"],
    "nyaa":         ["original", "en", "cn"],
    "mikan":        ["cn", "original", "en"],
    "acgrip":       ["cn", "original", "en"],
    "bangumi_moe":  ["cn", "original", "en"],
    "eztv":         ["en", "cn"],             # EZTV 欧美剧集，英文优先
    "dmhy":         ["cn", "original", "en"], # 动漫花园，中文优先
    "1337x":        ["en", "cn"],             # 1337x 综合站，英文优先
    # 网盘源（中文优先）
    "pansearch":    ["cn", "en"],
    "rrdynb":       ["cn", "en"],
    "ddys":         ["cn", "en"],
    "pansou":       ["cn", "en"],
    "sites":        ["cn", "en"],
    "slowread":     ["cn", "en"],
    "wnsearch":     ["cn", "en"],
    "gogopanso":    ["cn", "en"],
    "github":       ["cn", "en"],
}

# 中文源集合（季号拼"第N季"）
CN_SEASON_SOURCES = {"cilixiong", "xl720", "mikan", "acgrip", "bangumi_moe", "dmhy",
                     "pansearch", "rrdynb", "ddys", "pansou", "sites",
                     "slowread", "wnsearch", "gogopanso", "github"}

# 英文源集合（季号拼"S0N"）
EN_SEASON_SOURCES = {"prowlarr", "bitsearch", "yts", "limetorrents", "nyaa", "eztv", "1337x"}


def _get_keyword_by_lang(keywords: MultiLangKeywords, lang: str) -> str:
    """根据语言标识获取对应的搜索词"""
    if lang == "cn":
        return keywords.cn
    elif lang == "en":
        return keywords.en
    elif lang == "original":
        return keywords.original
    elif lang == "query":
        return keywords.query
    return ""


def _append_season(keyword: str, season_number: int, source_name: str) -> str:
    """为搜索词拼接季号"""
    if not keyword or season_number <= 0:
        return keyword
    if source_name in CN_SEASON_SOURCES:
        return f"{keyword} 第{season_number}季"
    elif source_name in EN_SEASON_SOURCES:
        return f"{keyword} S{str(season_number).zfill(2)}"
    return keyword


def get_search_keywords_for_source(
    source_name: str,
    keywords: MultiLangKeywords,
) -> List[str]:
    """为指定源生成搜索词列表（首选 + 回退词），去重去空。

    返回值：
    - 列表第一个是默认搜索词，后续是回退词
    - 最多 3 个词（默认 + 2 次回退）
    - 相同的词会被去重跳过
    """
    lang_priority = SOURCE_LANG_PRIORITY.get(source_name, ["en", "cn", "query"])
    seen = set()
    result = []

    for lang in lang_priority:
        kw = _get_keyword_by_lang(keywords, lang).strip()
        if not kw:
            continue
        # 拼接季号
        kw_with_season = _append_season(kw, keywords.season_number, source_name)
        # 去重（忽略大小写）
        kw_lower = kw_with_season.lower()
        if kw_lower in seen:
            continue
        seen.add(kw_lower)
        result.append(kw_with_season)
        if len(result) >= 3:
            break

    # 兜底：如果所有名称都为空，用 query
    if not result and keywords.query:
        fallback = _append_season(keywords.query, keywords.season_number, source_name)
        result.append(fallback)

    return result


def get_default_keyword_for_source(
    source_name: str,
    keywords: MultiLangKeywords,
) -> str:
    """获取指定源的默认搜索词（不含回退）。用于前端 Tab 切换时填入搜索框。"""
    kw_list = get_search_keywords_for_source(source_name, keywords)
    return kw_list[0] if kw_list else keywords.query or ""
