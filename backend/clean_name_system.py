"""
清洗名系统 — 从脏文件名/刮削数据中提取结构化的多语言名称

唯一入口，所有清洗逻辑集中在此。
依赖 L1 text_processing 的 normalize/split_by_language/detect_language。
对应技能文档：.kiro/skills/clean-name-system.md
"""
import os
import re
from typing import Optional, Dict
from dataclasses import dataclass, field, asdict

from text_processing import (
    normalize, split_by_language, detect_language, _trad_to_simp,
    _KANA_RE, _CJK_RE, _YEAR_RE
)


# ════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════

@dataclass
class CleanNameResult:
    """结构化清洗名"""
    cn: str = ""              # 中文名（简体）
    en: str = ""              # 英文名
    original: str = ""        # 原始语言名（日文/韩文等）
    display: str = ""         # UI 展示用的组合名
    suffix: str = ""          # 附加尾缀：S01E03 / 第2季 / 剧场版
    year: str = ""            # 年份
    source: str = ""          # 来源：manual/nfo/tmdb/scrape/parsed
    confidence: str = "low"   # 置信度：high/medium/low

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CleanNameResult":
        return CleanNameResult(**{k: v for k, v in d.items() if k in CleanNameResult.__dataclass_fields__})


# ════════════════════════════════════════
# 优先级保护
# ════════════════════════════════════════

NAME_SOURCE_PRIORITY = {
    "manual": 4,
    "nfo": 3,
    "tmdb": 3,
    "douban": 2,
    "bangumi": 2,
    "scrape": 2,
    "parsed": 1,
    "": 0,
}


def safe_update_clean_name(item: dict, new: CleanNameResult) -> bool:
    """安全更新 clean_name 结构化字段，低优先级不覆盖高优先级。
    返回 True 表示有字段被更新。"""
    existing_source = item.get("clean_name_source", "")
    existing_priority = NAME_SOURCE_PRIORITY.get(existing_source, 0)
    new_priority = NAME_SOURCE_PRIORITY.get(new.source, 0)

    if existing_priority > new_priority:
        return False

    changed = False
    # display 字段（向后兼容的 clean_name）
    if new.display:
        item["clean_name"] = new.display
        item["clean_name_source"] = new.source
        changed = True
    # 结构化字段
    if new.cn:
        item["clean_name_cn"] = new.cn
        changed = True
    if new.en:
        item["clean_name_en"] = new.en
        changed = True
    if new.original:
        item["clean_name_original"] = new.original
        changed = True
    return changed


# ════════════════════════════════════════
# Level 0：去噪（strip_noise）
# ════════════════════════════════════════

# 已知媒体扩展名
_MEDIA_EXTS = {
    ".mp4", ".mkv", ".avi", ".ts", ".rmvb", ".rm", ".flv", ".wmv", ".mov", ".m4v",
    ".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt", ".nfo", ".jpg", ".png", ".tmp",
}

# CD/Disc 分片标记
_CD_PATTERN = re.compile(r'[.\s_\-]?(?:CD|Disc|DISC|disk)\s*(\d{1,2})', re.I)

# 已知发布组
_KNOWN_GROUPS = (
    r'(?:FGT|SPARKS|DHD|CMCT|WIKI|FRDS|USURY|RARBG|YIFY|NTb|AMZN|FLUX|NOGRP|'
    r'TEPES|EDITH|EMBER|AMIABLE|GECKOS|ROVERS|DEMAND|EVOLVE|PLAYNOW|SHORTBREHD)'
)

# 尾部 "-发布组" 形态（白名单外的发布组靠形态识别）
_TRAILING_GROUP_RE = re.compile(r'\s*-\s*([A-Za-z0-9][A-Za-z0-9._]{1,14})\s*$')

# 质量/编码标签。用于判断 "-XXX" 到底是发布组还是作品名的一部分：
# 发布命名里发布组是最后一段（x264-GROUP），后面不会再出现质量标签；
# 而 "Ultimate Factories-BMW.HDTV.720p" 的 BMW 后面还跟着质量标签，说明它是节目主题。
_QUALITY_TOKEN_RE = re.compile(
    r'(?i)\b(?:2160p|1080[pi]?|720[pi]?|480p|BluRay|WEB-?DL|WEB-?HR|WEBRip|HDTV\w*|'
    r'BDRip|DVDRip|Remux|UHD|x264|x265|H\.?26[45]|HEVC|AVC|XviD|DivX)\b'
)


def _group_token_is_topic(raw_base: str, token: str) -> bool:
    """判断尾部 "-token" 是作品名的一部分（而非发布组）。
    依据：token 在原始文件名里后面还跟着质量标签，说明它不是发布命名的末段。
    raw_base 用未清洗的原始名，因为清洗会把质量标签删掉、位置信息就丢了。
    """
    idx = raw_base.lower().rfind("-" + token.lower())
    if idx < 0:
        return False  # 原名里找不到，保守按发布组处理（维持既有行为）
    return bool(_QUALITY_TOKEN_RE.search(raw_base[idx + 1 + len(token):]))


def strip_noise(filename: str) -> str:
    """Level 0：从脏文件名中去除所有非作品名内容。
    保留年份和季集号，不做语言分离。
    """
    # 去扩展名
    base, ext = os.path.splitext(filename)
    name = base if ext.lower() in _MEDIA_EXTS else filename

    # 0. + 替换为空格
    name = re.sub(r'\+', ' ', name)

    # 0a. 去除季范围尾缀（用户手动标注的"已下载哪几季"，不是作品名）
    # 匹配：S1-S3、S0-S2、1-8季、1-6季 等
    name = re.sub(r'\s*S\d+\s*-\s*S\d+\s*$', '', name, flags=re.I)
    name = re.sub(r'\s*\d+-\d+季\s*$', '', name)
    # 去除尾部独立季号标记（如 "守望尘世S1"、"猎魔人S"、"XX 16季"）
    # 注意：不去除作品名中的数字（如 "白2023"、"1984"）
    name = re.sub(r'(?<=[\u4e00-\u9fff])\s*S\d*\s*$', '', name, flags=re.I)
    name = re.sub(r'(?<=[\u4e00-\u9fff])\s*\d{1,2}季\s*$', '', name)

    # 0b. 点号分隔符转空格（保护小数点如 5.1、版本号如 v2.0）
    # 先处理分隔符，再去广告，避免 "电影天堂www.dytt.com.盗梦空间" 这种粘连
    name = re.sub(r'(?<!\d)\.(?!\d)', ' ', name)

    # 1. 去方括号内容
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'【.*?】', '', name)
    name = re.sub(r'「.*?」', '', name)

    # 2. 去圆括号内的广告/URL
    name = re.sub(r'\([^)]*(?:www\.|bbs\.|\.com|\.net|\.org|\.cc|\.co)[^)]*\)', '', name, flags=re.I)
    # 去圆括号内的编码/技术信息
    name = re.sub(r'\([^)]*(?:x264|x265|HEVC|AVC|AAC|DTS|FLAC|10bit|ASSx?\d?)[^)]*\)', '', name, flags=re.I)
    # 去圆括号内的 hash
    name = re.sub(r'\([A-Fa-f0-9]{6,}\)', '', name)

    # 3. 去广告站名（含紧跟的 URL）
    name = re.sub(r'(?:红旅首发|电影天堂|影视帝国|66影视|六六影视|更多[^\s]*请去)\S*', '', name, flags=re.I)

    # 4. 去裸 URL
    name = re.sub(r'(?:www\.|bbs\.|https?://)\S+', '', name, flags=re.I)

    # 5. 去质量标签
    name = re.sub(r'(?i)\.?(2160p|1080[pi]?|720[pi]?|480p|BluRay|WEB-?DL|WEB-?HR|WEBRip|HDTVrip|HDTV|BDRip|BDrip|DVDRip|Remux|UHD)(?=[^a-zA-Z]|$)', '', name)
    name = re.sub(r'(?i)(?<![a-zA-Z])(BD|HD|DVD|SD)(?=[^a-zA-Z]|$)', '', name)
    name = re.sub(r'(?i)\.?(x264|x265|H\.?264|H\.?265|HEVC|AVC|XviD|DivX|MiniSD|AAC|DTS|DTS-HD|FLAC|TrueHD|Atmos|10bit|Main10|AC3|DD\+?\d?)\b', '', name)
    # 去 web 作为独立词（来自 WEB-DL 拆分后的残留）
    name = re.sub(r'(?i)\bweb\b', '', name)
    name = re.sub(r'(?i)(中英双字|中英字幕|双语双字|中文字幕|中字|英字|无水印|修复版|加长版|初版|dvd-?rmvb|UNCUT|KORSUB)', '', name)
    name = re.sub(r'(?i)(国粤双语|国英双语|国日双语|粤语|国语|日语|韩语|英语|法语|泰语|简繁字幕|简繁外挂|简体|繁体)', '', name)
    name = re.sub(r'(?i)(1280高清|1024高清|高清|未删减版|超清|双语字幕[^\s]*)', '', name)

    # 6. 去字幕组/发布组名
    name = re.sub(r'(?i)(?:YYeTs人人影视|人人影视|ZhuixinFan|Chi[_ ]Jap|Jap[_ ]Chi|AMZN|NTb|chs[_ ]eng|eng[_ ]chs)', '', name)
    name = re.sub(r'(?i)(?:FIX字幕侠|深影字幕组|弯弯字幕组|卜卜酱|AGE动漫)', '', name)
    name = re.sub(r'(?i)(?:在线观看|动漫下载)', '', name)
    # 去音频声道标签（5.1、7.1，以及 AAC5.1 格式）
    name = re.sub(r'(?i)\bAAC\d?\.\d\b', '', name)
    name = re.sub(r'(?<!\d)\d\s*\.\s*1(?!\d)', '', name)

    # 6b. 去独立的语言/音轨标签（RUS/JAP/ENG/FRE/GER/ITA/SPA/KOR/CHI 等 ISO 语言缩写）
    name = re.sub(r'(?i)\b(?:RUS|JAP|JPN|ENG|FRE|FRA|GER|DEU|ITA|SPA|KOR|CHI|CHS|CHT|ARA|POR|THA|VIE|IND|TUR|POL|NLD|DUT|SWE|NOR|DAN|FIN|CZE|HUN|RUM|ROM|HEB|GRE|UKR|BUL|HRV|SRP|SLK|SLV|EST|LAT|LIT)\b', '', name)
    # 去独立的发布者/字幕组名（常见的非作品名英文标识，通常在尾部）
    name = re.sub(r'(?i)\b(?:Deadmauvlad|LostFilm|NovaFilm|BaibaKo|Kuraj|Bambey|AlexFilm|NewStudio|RG\s*Paravozik|DVO|AVO|MVO|VO)\b', '', name)

    # 7. 去媒体形式标签（TV版/电视剧版/OVA/OAD等，包括紧跟中文名的情况）
    name = re.sub(r'(?:TV版|电视剧版|OAD|番外篇|总集篇|完结篇)(?=[\s._\-]|$)', '', name)
    name = re.sub(r'(?<=[\u4e00-\u9fff])TV版', '', name)
    # 去独立的 OVA/OAD/ONA/SP 标签（不在作品名中间的）
    name = re.sub(r'(?<![a-zA-Z])(?:OVA|OAD|ONA)(?![a-zA-Z])', '', name)

    # 8. 去分辨率数字（1920x1080 等）
    name = re.sub(r'\d{3,4}[xX×]\d{3,4}', '', name)
    name = re.sub(r'\d{3,4}[xX×](?=\s|$)', '', name)

    # 9. 去 CD 标记
    name = _CD_PATTERN.sub('', name)

    # 10. 去尾部发布组标签
    name = re.sub(r'\s*-\s*' + _KNOWN_GROUPS + r'$', '', name, flags=re.I)

    # 10b. 去尾部未知发布组（如 x264-BARC0DE 里的 BARC0DE）。
    # _KNOWN_GROUPS 是白名单，覆盖不到的发布组会残留，
    # 还会被后续语言分离切成 "BARC 0 DE" 这种垃圾尾缀，同时污染清洗名和标准名。
    # 只在 "-" 之前已是多词标题时才剥，避免误伤 X-MEN / Spider-Man 这类片名本身；
    # 后面还跟着质量标签的不剥，那是节目主题（Ultimate Factories-BMW.HDTV.720p）。
    group_match = _TRAILING_GROUP_RE.search(name)
    if group_match:
        head = name[:group_match.start()].strip()
        if " " in head and len(head) >= 4 and not _group_token_is_topic(base, group_match.group(1)):
            name = head

    # 11. 清理分隔符
    name = re.sub(r'(?<!\d)[._]+', ' ', name)
    name = re.sub(r'[._]+(?!\d)', ' ', name)
    name = re.sub(r'_', ' ', name)
    name = re.sub(r'\s*-\s*', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()

    # 12. 去空括号和尾部中文标点
    name = re.sub(r'\(\s*\)', '', name).strip()
    name = re.sub(r'[：；，。！？、&]+$', '', name).strip()

    # 13. 去尾部纯数字集号（如 "进击的巨人 01" → "进击的巨人"）
    # 但保留 S01E03 这种标准格式
    name = re.sub(r'\s+\d{1,3}$', '', name).strip()

    # 14. 去 SxxExx 后面的集标题（如 "S02E01 Chapter One MADMAX" → "S02E01"）
    name = re.sub(r'(S\d+E\d+)\s+[A-Z][a-zA-Z].*$', r'\1', name)

    if not name:
        # 全部被清洗掉了，尝试从方括号中提取
        name = _extract_core_from_brackets(base)

    return name


def _extract_core_from_brackets(raw_name: str) -> str:
    """从全是方括号的文件名中提取有意义的部分"""
    brackets = re.findall(r'\[([^\]]+)\]', raw_name)
    if not brackets:
        return raw_name

    skip_pat = re.compile(
        r'^(?:720[pP]?|1080[pP]?|2160[pP]?|480[pP]?|'
        r'GB|BIG5|CHS|CHT|JP|EN|SC|TC|'
        r'X264|X265|HEVC|AVC|AAC|DTS|FLAC|MP4|MKV|AVI|'
        r'GB_CN|GB_MP4|BDrip|BDRIP|HDRip|WEBRip|'
        r'AVC-8bit|简繁外挂|v\d+|'
        r'X264[_ ]AAC|DTS[_ ]HD|'
        r'\d{3,4}[xX]\d{3,4})$', re.I)
    ad_pat = re.compile(r'(?:www\.|http|bbs\.|\.com|\.net|\.org|\.cc|红旅|电影天堂|影视帝国|66影视)', re.I)
    tech_pat = re.compile(r'(?:x264|x265|HEVC|AVC|AAC|DTS|FLAC|BDRIP|BDRip|WEBRip|HDRip|\d{3,4}[xX×]\d{3,4})', re.I)

    candidates = []
    for i, b in enumerate(brackets):
        b = b.strip()
        if not b or len(b) < 2:
            continue
        if skip_pat.match(b):
            continue
        if ad_pat.search(b):
            continue
        if tech_pat.search(b):
            continue
        if re.match(r'^\d{1,3}(v\d)?$', b):
            continue
        # 第一个方括号如果是纯英文短名，大概率是字幕组名
        if i == 0 and re.match(r'^[A-Za-z][\w\-]{1,14}$', b):
            continue
        candidates.append(b)

    if candidates:
        cn_cands = [c for c in candidates if re.search(r'[\u4e00-\u9fff]', c)]
        if cn_cands:
            result = max(cn_cands, key=len)
        else:
            result = max(candidates, key=len)
        result = result.replace('_', ' ').strip()
        result = re.sub(r'\s+', ' ', result)
        return result
    return raw_name


# ════════════════════════════════════════
# Level 1：语言分离（split_names）
# ════════════════════════════════════════

# 年份正则（带括号和不带括号）
_YEAR_PAREN_RE = re.compile(r'\s*[\(\[（]((?:19|20)\d{2})[\)\]）]\s*')
_YEAR_BARE_RE = re.compile(r'(?<![.\d])\b((?:19|20)\d{2})\b(?!\d)')


def split_names(text: str) -> Dict[str, str]:
    """Level 1：从清洗后的文本中分离 cn/en/original/year。

    返回 {"cn": ..., "en": ..., "original": ..., "year": ...}
    """
    if not text:
        return {"cn": "", "en": "", "original": "", "year": ""}

    # 1. 提取年份
    year = ""
    m = _YEAR_PAREN_RE.search(text)
    if m:
        year = m.group(1)
        text = text[:m.start()] + text[m.end():]
    else:
        m = _YEAR_BARE_RE.search(text)
        if m:
            year = m.group(1)
            text = text[:m.start()] + text[m.end():]
    text = re.sub(r'\s+', ' ', text).strip()

    # 2. 检测日文假名 → original
    original = ""
    has_kana = bool(_KANA_RE.search(text))
    if has_kana:
        # 提取包含假名的连续段落作为 original
        # 策略：找到包含假名的最长连续 CJK+假名 段
        jp_segments = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\u3400-\u4dbfー・]+', text)
        jp_with_kana = [s for s in jp_segments if _KANA_RE.search(s)]
        if jp_with_kana:
            original = max(jp_with_kana, key=len)
            # 从 text 中移除 original 部分，剩余做中英分离
            text = text.replace(original, '').strip()
            text = re.sub(r'\s+', ' ', text).strip()

    # 3. 检测韩文 → original
    _HANGUL_RE = re.compile(r'[\uac00-\ud7af]')
    if not original and _HANGUL_RE.search(text):
        ko_segments = re.findall(r'[\uac00-\ud7af\u3130-\u318f]+', text)
        if ko_segments:
            original = max(ko_segments, key=len)
            text = text.replace(original, '').strip()
            text = re.sub(r'\s+', ' ', text).strip()

    # 4. 中英文分离（调用 L1）
    parts = split_by_language(text)
    cn = parts.get("cn", "")
    en = parts.get("en", "")

    # 5. 繁体转简体
    if cn:
        cn_simp = _trad_to_simp(cn)
        if cn_simp != cn:
            # 原始繁体归入 original（如果 original 还空的话）
            if not original:
                original = cn
            cn = cn_simp

    # 6. 从 en 中去除尾部季集号（S01E01、S01、E03 等不是英文名的一部分）
    if en:
        en = re.sub(r'\s+[sS]\d+[eE]\d+\s*$', '', en).strip()
        en = re.sub(r'\s+[sS]\d+\s*$', '', en).strip()
        en = re.sub(r'\s+[eE]\d+\s*$', '', en).strip()

    return {"cn": cn, "en": en, "original": original, "year": year}


# ════════════════════════════════════════
# Level 2：附加信息提取（extract_suffix）
# ════════════════════════════════════════

# 特殊标记
_SPECIAL_MARKS = {
    "剧场版": "剧场版", "劇場版": "剧场版",
    "OVA": "OVA", "OAD": "OAD", "SP": "SP", "特别篇": "SP",
}
_SPECIAL_RE = re.compile(
    r'(?<![a-zA-Z])(?:剧场版|劇場版|OVA|OAD|SP|特别篇)(?![a-zA-Z])',
    re.I
)


def extract_suffix(filename: str, folder_name: str = "",
                   season_override: Optional[int] = None,
                   episode_override: Optional[int] = None) -> Dict[str, str]:
    """Level 2：从文件名/文件夹名中提取季集号和特殊标记。

    返回 {"suffix": ..., "suffix_cn": ..., "season": int|None, "episode": int|None, "special": str}
    - suffix: 英文格式 "S01E03"（用于搜索）
    - suffix_cn: 中文格式 "第1季第3集"（用于中文展示）
    - special: "剧场版"/"OVA"/"SP" 等
    """
    from tmdb_client import parse_filename

    parsed = parse_filename(filename)
    season = season_override if season_override is not None else parsed.get("season")
    episode = episode_override if episode_override is not None else parsed.get("episode")
    abs_ep = parsed.get("absolute_episode")

    # 特殊标记检测（从文件名和文件夹名中）
    special = ""
    for text in [filename, folder_name]:
        m = _SPECIAL_RE.search(text)
        if m:
            matched = m.group(0)
            for k, v in _SPECIAL_MARKS.items():
                if matched.lower() == k.lower():
                    special = v
                    break
            if special:
                break

    # 构造 suffix
    suffix = ""
    suffix_cn = ""
    if season is not None and episode is not None:
        suffix = f"S{season:02d}E{episode:02d}"
        suffix_cn = f"第{season}季第{episode}集"
    elif abs_ep is not None:
        suffix = f"E{abs_ep}"
        suffix_cn = f"第{abs_ep}集"
    elif episode is not None:
        suffix = f"E{episode:02d}"
        suffix_cn = f"第{episode}集"
    elif season is not None:
        suffix = f"S{season:02d}"
        suffix_cn = f"第{season}季"
    elif special:
        suffix = special
        suffix_cn = special

    return {
        "suffix": suffix,
        "suffix_cn": suffix_cn,
        "season": season,
        "episode": episode,
        "special": special,
    }


# ════════════════════════════════════════
# Level 3：组装展示名（compose_display）
# ════════════════════════════════════════

def compose_display(cn: str, en: str = "", suffix: str = "",
                    year: str = "", include_en: bool = False) -> str:
    """Level 3：组装 UI 展示用的 display 字符串。

    规则：
    - cn 为空时用 en 替代
    - cn 和 en 相同时只显示一个
    - include_en=True 时拼接英文名（用于文件夹级展示）
    - suffix 非空时追加
    """
    base = cn or en or ""
    if not base:
        return ""

    # 拼接英文名
    if include_en and en and en != cn and cn:
        base = f"{cn} {en}"

    # 拼接尾缀
    if suffix:
        return f"{base} {suffix}"
    return base


# ════════════════════════════════════════
# 统一入口
# ════════════════════════════════════════

def clean_from_filename(filename: str, folder_name: str = "",
                        parent_cn: str = "", parent_en: str = "",
                        parent_original: str = "") -> CleanNameResult:
    """从文件名解析清洗名（source=parsed）。

    parent_cn/en/original：父文件夹已知的名称，优先使用。
    """
    # Level 0：去噪
    cleaned = strip_noise(filename)

    # Level 1：语言分离
    names = split_names(cleaned)

    # 优先用父文件夹的名称
    cn = parent_cn or names["cn"]
    en = parent_en or names["en"]
    original = parent_original or names["original"]
    year = names["year"]

    # 纯数字不算有效英文名（如文件名 "02.mkv" 清洗后 en="02"）
    if en and not parent_en and re.match(r'^\d+$', en):
        en = ""

    # Level 2：提取季集号
    suffix_info = extract_suffix(filename, folder_name)
    suffix = suffix_info["suffix"]

    # Level 3：组装展示名
    display = compose_display(cn, en, suffix)

    # 置信度
    confidence = "low"
    if cn and en:
        confidence = "medium"
    elif cn:
        confidence = "medium"

    return CleanNameResult(
        cn=cn, en=en, original=original,
        display=display, suffix=suffix, year=year,
        source="parsed", confidence=confidence,
    )


def clean_from_scrape(title: str, original_title: str = "",
                      english_title: str = "", year: str = "",
                      filename: str = "", folder_name: str = "",
                      source: str = "scrape") -> CleanNameResult:
    """从刮削结果构建清洗名（source=tmdb/nfo/scrape）。

    刮削数据已经是干净的，不需要 strip_noise。
    季集号从 filename 提取。
    """
    cn = ""
    en = ""
    original = ""

    # 判断 title 的语言
    lang = detect_language(title)
    if lang in ("cn", "mixed"):
        # title 含中文 → 作为 cn
        parts = split_by_language(title)
        cn = parts.get("cn", "") or title
    elif lang == "jp":
        original = title
    elif lang == "ko":
        original = title
    else:
        # 纯英文 title
        en = title

    # english_title 直接作为 en
    if english_title and english_title != title:
        en = english_title

    # original_title 处理
    if original_title and original_title != title and original_title != english_title:
        orig_lang = detect_language(original_title)
        if orig_lang == "jp":
            if not original:
                original = original_title
        elif orig_lang == "ko":
            if not original:
                original = original_title
        elif orig_lang == "en":
            if not en:
                en = original_title
        elif orig_lang in ("cn", "mixed"):
            if not cn:
                cn = original_title

    # 季集号
    suffix_info = extract_suffix(filename, folder_name) if filename else {"suffix": "", "suffix_cn": ""}
    suffix = suffix_info.get("suffix", "")

    # 组装展示名
    display = compose_display(cn, en, suffix, year)

    # 置信度
    confidence = "high" if (cn or en) else "low"
    if source in ("tmdb", "nfo") and (cn and en):
        confidence = "high"
    elif source == "scrape" and cn:
        confidence = "medium"

    return CleanNameResult(
        cn=cn, en=en, original=original,
        display=display, suffix=suffix, year=year,
        source=source, confidence=confidence,
    )


def clean_for_folder(folder_name: str, shadow_name: str = "",
                     parent_cn: str = "", parent_en: str = "",
                     folder_type: str = "", season_num: Optional[int] = None) -> CleanNameResult:
    """文件夹级清洗名。

    folder_type: movie/tv/season/collection 等
    season_num: 季号（season 类型时传入）
    """
    # 有 shadow_name 时优先用
    if shadow_name:
        names = split_names(shadow_name)
        cn = names["cn"]
        en = names["en"]
        original = names["original"]
        year = names["year"]
        source = "scrape"
    else:
        # 从文件夹名清洗
        cleaned = strip_noise(folder_name + ".tmp")  # 加 .tmp 触发扩展名剥离
        names = split_names(cleaned)
        cn = names["cn"]
        en = names["en"]
        original = names["original"]
        year = names["year"]
        source = "parsed"

    # 季文件夹：用父级剧名 + 第X季
    suffix = ""
    if folder_type == "season" and season_num is not None:
        cn = parent_cn or cn
        en = parent_en or en
        suffix = f"第{season_num}季"
    elif folder_type == "season":
        cn = parent_cn or cn
        en = parent_en or en

    display = compose_display(cn, en, suffix)

    confidence = "medium" if cn else "low"
    if shadow_name:
        confidence = "high" if (cn and en) else "medium"

    return CleanNameResult(
        cn=cn, en=en, original=original,
        display=display, suffix=suffix, year=year,
        source=source, confidence=confidence,
    )


def clean_for_season_search(cn: str, en: str = "", season: int = 1) -> Dict[str, str]:
    """季搜索词构造：中文源加中文季号，英文源加英文季号。

    返回 {"cn_query": "进击的巨人 第3季", "en_query": "Attack on Titan S03"}
    """
    cn_query = f"{cn} 第{season}季" if cn else ""
    en_query = f"{en} S{season:02d}" if en else ""
    return {"cn_query": cn_query, "en_query": en_query}


def clean_for_episode_search(cn: str, en: str = "",
                             season: int = 1, episode: int = 1) -> Dict[str, str]:
    """单集搜索词构造。

    返回 {"cn_query": "进击的巨人 S01E03", "en_query": "Attack on Titan S01E03"}
    """
    ep_tag = f"S{season:02d}E{episode:02d}"
    cn_query = f"{cn} {ep_tag}" if cn else ""
    en_query = f"{en} {ep_tag}" if en else ""
    return {"cn_query": cn_query, "en_query": en_query}


# ════════════════════════════════════════
# 从旧数据反向解析（向后兼容）
# ════════════════════════════════════════

def parse_legacy_clean_name(item: dict) -> CleanNameResult:
    """从旧格式的 media_library.json 条目中解析出结构化清洗名。

    旧格式只有 clean_name（字符串）和 clean_name_source。
    新格式有 clean_name_cn/en/original。
    """
    # 优先用新字段
    cn = item.get("clean_name_cn", "")
    en = item.get("clean_name_en", "")
    original = item.get("clean_name_original", "")
    source = item.get("clean_name_source", "")
    display = item.get("clean_name", "")

    if cn or en or original:
        # 已有结构化字段
        return CleanNameResult(
            cn=cn, en=en, original=original,
            display=display, source=source,
            confidence="high" if source in ("manual", "nfo", "tmdb") else "medium",
        )

    # 旧格式：从 clean_name 字符串反向解析
    if not display:
        return CleanNameResult(source=source)

    # 提取尾部的季集号
    suffix = ""
    text = display
    ep_match = re.search(r'\s+(S\d+E\d+|E\d+)$', text)
    if ep_match:
        suffix = ep_match.group(1)
        text = text[:ep_match.start()]

    # 语言分离
    names = split_names(text)
    return CleanNameResult(
        cn=names["cn"], en=names["en"], original=names["original"],
        display=display, suffix=suffix, year=names["year"],
        source=source,
        confidence="medium" if names["cn"] else "low",
    )


# ════════════════════════════════════════
# 重新生成（用户显式触发）
# ════════════════════════════════════════

def build_search_index_name(file_path: str, file_name: str = "") -> Optional[CleanNameResult]:
    """为搜索构造最容易命中的索引名（中文 + 英文）。

    取名优先级（越靠前信息越干净）：
    1. NFO —— 刮削结果里 title / english_title 是最准的中英文对
    2. 文件夹名 —— 已整理过的目录通常是 `中文 English (年份)`，中英文齐全
    3. 文件名 —— 最脏，常缺英文名、且带发布组等尾缀

    只看文件名是不够的：`爱情与灵药 (2010).mp4` 拿不到英文名，
    但它所在目录 `爱情与灵药 Love & Other Drugs (2010)` 里有。
    """
    file_name = file_name or os.path.basename(file_path)
    folder = os.path.dirname(file_path)
    folder_name = os.path.basename(folder)

    # 1. NFO
    work_folder_name = folder_name
    try:
        from nfo_handler import read_nfo, read_show_names, read_video_nfo, work_folder_of

        nfo = read_video_nfo(file_path) or read_nfo(folder)
        work_folder_name = os.path.basename(work_folder_of(file_path))
    except Exception:
        nfo = None

    if nfo and nfo.get("title"):
        title = nfo.get("title", "")
        original_title = nfo.get("original_title", "") or ""
        english_title = nfo.get("english_title", "") or ""
        # 分集 NFO 的 <title> 是分集标题（「炎兔」「第 1 集」），不是作品名。
        # 整季每集都会算出不同的检索名，搜索时一条都对不上。
        if nfo.get("media_type") == "episodedetails" or nfo.get("showtitle"):
            show = read_show_names(file_path, nfo)
            if show:
                title = show["title"]
                original_title = show["original_title"]
                english_title = show["english_title"]
            else:
                title = ""   # 拿不到作品名就走下面的目录名/文件名，不用分集标题

        if title:
            result = clean_from_scrape(
                title=title,
                original_title=original_title,
                english_title=english_title,
                year=str(nfo.get("year", "") or ""),
                filename=file_name,
                folder_name=folder_name,
                source="nfo",
            )
            # NFO 常年只有中文名（实测军火女王的 tvshow.nfo 英文名是空的），
            # 而作品级目录名里就写着 `军火女王 Jormungand`。只在缺失的一侧补，
            # 且要求两边指向同一部作品，避免拿 `动画番` 这种分类目录名当片名。
            if result.cn and not result.en and work_folder_name:
                folder_guess = clean_for_folder(work_folder_name)
                if folder_guess.en and _points_to_same_work(result, folder_guess):
                    result.en = folder_guess.en
                    result.display = compose_display(
                        result.cn, result.en, result.suffix, result.year)
            if result.cn or result.en:
                return result

    # 2. 文件名，缺失的一侧用文件夹名补
    file_result = clean_from_filename(file_name, folder_name=folder_name)
    folder_result = clean_for_folder(folder_name) if folder_name else None

    # 只有确认文件夹指向同一部作品才敢用它的名字：
    # 视频若直接放在 `media`、`电影` 这类通用目录下，拿目录名当片名会污染结果
    if folder_result and _points_to_same_work(file_result, folder_result):
        cn = file_result.cn or folder_result.cn
        en = file_result.en or folder_result.en
        original = file_result.original or folder_result.original
        if cn != file_result.cn or en != file_result.en or original != file_result.original:
            return CleanNameResult(
                cn=cn, en=en, original=original,
                display=compose_display(cn, en, file_result.suffix),
                suffix=file_result.suffix,
                year=file_result.year or folder_result.year,
                source="parsed",
                confidence="medium",
            )

    return file_result


def _points_to_same_work(a: CleanNameResult, b: CleanNameResult) -> bool:
    """两个清洗结果是否指向同一部作品（任一语言侧对得上即可）"""
    for left, right in ((a.cn, b.cn), (a.en, b.en)):
        left_norm = normalize(left) if left else ""
        right_norm = normalize(right) if right else ""
        if not left_norm or not right_norm:
            continue
        if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
            return True
    return False


def regenerate_clean_names(library: list, file_path: str, is_folder: bool = False) -> Dict:
    """重新生成搜索索引名（清洗名），返回 {updated, cn, en, display}。

    与 safe_update_clean_name 的区别：这里是用户点按钮显式要求重算，
    所以强制覆写，不受 NAME_SOURCE_PRIORITY 保护（否则已有 manual/nfo 名字时按钮点了没反应）。
    """
    if not file_path:
        return {"updated": 0, "matched": 0, "reason": "no_path", "cn": "", "en": "", "display": ""}

    targets = []
    if is_folder:
        folder_norm = file_path.replace("\\", "/").rstrip("/") + "/"
        for item in library:
            item_path = item.get("file_path", "").replace("\\", "/")
            if item_path.startswith(folder_norm):
                targets.append(item)
    else:
        targets = [item for item in library if item.get("file_path") == file_path]

    if not targets:
        return {
            "updated": 0, "matched": 0, "reason": "not_in_library",
            "cn": "", "en": "", "display": "",
        }

    updated = 0
    first: Optional[CleanNameResult] = None

    for item in targets:
        item_path = item.get("file_path", "")
        file_name = item.get("file_name", "") or os.path.basename(item_path)
        if not file_name:
            continue

        result = build_search_index_name(item_path, file_name)
        if result is None or not (result.cn or result.en):
            continue

        item["clean_name"] = result.display
        item["clean_name_cn"] = result.cn
        item["clean_name_en"] = result.en
        if result.original:
            item["clean_name_original"] = result.original
        item["clean_name_source"] = result.source
        updated += 1
        if first is None:
            first = result

    if first is None:
        # 区分两种失败：库里根本没这条记录 vs 记录在但名字解析不出来。
        # 之前都返回 not_found，排查时无法判断到底是路径对不上还是解析失败。
        return {
            "updated": 0,
            "matched": len(targets),
            "reason": "unparsable" if targets else "not_in_library",
            "cn": "", "en": "", "display": "",
        }

    return {
        "updated": updated,
        "matched": len(targets),
        "reason": "",
        "cn": first.cn,
        "en": first.en,
        "display": first.display,
    }
