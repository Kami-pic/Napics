"""
媒体库分析引擎 — 独立诊断层
输入文件夹路径，输出完整诊断报告（纯读取，不修改文件）
支持单文件夹分析 + 批量全库分析
"""
import os
import re
from typing import List, Dict, Optional

from organizer import (
    classify_folder, _is_ignorable_subdir, _is_season_dir,
    _extract_season_number, _count_episode_files
)
import scraper
from core.constants import MEDIA_EXTS, SUBTITLE_EXTS, VIDEO_EXTS

# ── 常量 ──

# 广告检测模式
AD_PATTERNS = [
    re.compile(r'(?:www\.|https?://)\S+', re.I),                    # URL
    re.compile(r'@\S{2,}'),                                          # @推广
    re.compile(r'(加群|招人|更多资源|关注|公众号|频道|电报)', re.I),    # 中文广告词
    re.compile(r'\b(join|follow|subscribe|channel|telegram)\b', re.I), # 英文广告词
]

# 乱码检测模式
GARBLED_PATTERNS = [
    re.compile(r'锟斤拷'),
    re.compile(r'烫烫烫'),
    re.compile(r'屯屯屯'),
    re.compile(r'ÃÂ'),
    re.compile(r'Ã©|Ã¨|Ã¤|Ã¶|Ã¼'),
    re.compile(r'â€[™""]'),
]

# 综艺日期模式
VARIETY_DATE_PATTERN = re.compile(r'20\d{2}[.\-]?\d{2}[.\-]?\d{2}')

# 杂项关键词
MISC_KEYWORDS = {'mv', 'cg', '短片', '教程', 'vlog', 'pv', 'cm', 'mad', 'amv', 'trailer', '预告'}
VARIETY_KEYWORDS = {'综艺', '真人秀', 'variety', '脱口秀', '晚会', '春晚', '跨年'}


# ── 单文件分析 ──

def _analyze_filename(filename: str) -> Dict:
    """分析单个文件名，检测广告/乱码/垃圾标签/中英混杂异常"""
    issues = []
    name = os.path.splitext(filename)[0]

    # 广告检测
    for pat in AD_PATTERNS:
        m = pat.search(name)
        if m:
            issues.append({"type": "ad_tag", "detail": m.group(0), "auto_fixable": True})

    # 乱码检测
    for pat in GARBLED_PATTERNS:
        if pat.search(name):
            issues.append({"type": "garbled", "detail": pat.pattern, "auto_fixable": False})
            break

    # 不可识别字符比例
    non_normal = re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9\s\[\]\(\)（）【】._\-+&!]', '', name)
    if len(non_normal) > len(name) * 0.15 and len(non_normal) >= 3:
        issues.append({"type": "junk_chars", "detail": non_normal[:20], "auto_fixable": False})

    # 过多方括号标签
    brackets = re.findall(r'\[.*?\]', name)
    if len(brackets) > 3:
        issues.append({"type": "excessive_tags", "detail": f"{len(brackets)} 个标签", "auto_fixable": True})

    # 中英混杂异常检测（审查规避：中文里夹杂单个拉丁字母/拼音）
    # 提取去掉方括号标签后的核心名
    core = re.sub(r'\[.*?\]', '', name)
    core = re.sub(r'\(.*?\)', '', core)
    core = re.sub(r'(?i)(2160p|1080p|720p|480p|BluRay|BD|HD|WEB-?DL|x264|x265|HEVC)', '', core)
    core = core.strip(' ._-')
    if core:
        # 统计中文字符和单个拉丁字母的交替模式
        # 如 "tou香。大z探皮k丘" → 中文和单字母频繁交替
        cjk_chars = re.findall(r'[\u4e00-\u9fff]', core)
        # 单个拉丁字母夹在中文之间（前后至少一边是中文）
        lone_latin = re.findall(r'(?<=[\u4e00-\u9fff])[a-zA-Z](?=[\u4e00-\u9fff])|(?<=[\u4e00-\u9fff])[a-zA-Z]$|^[a-zA-Z](?=[\u4e00-\u9fff])', core)
        # 短拼音片段夹在中文之间（2-3个字母，不是标准英文单词）
        short_latin = re.findall(r'(?<=[\u4e00-\u9fff])[a-zA-Z]{2,3}(?=[\u4e00-\u9fff])', core)
        mixed_count = len(lone_latin) + len(short_latin)
        if mixed_count >= 2 and len(cjk_chars) >= 2:
            issues.append({
                "type": "censorship_evasion",
                "detail": f"中英混杂异常（{mixed_count}处），疑似审查规避",
                "auto_fixable": False,
                "needs_ai": True,
            })

    return {"filename_issues": issues}


def _analyze_subtitles(folder_path: str, video_files: List[str]) -> Dict:
    """分析字幕情况"""
    all_files = []
    try:
        all_files = os.listdir(folder_path)
    except OSError:
        return {"has_embedded": False, "has_external": False, "external_languages": [], "missing_chinese": True}

    ext_subs = [f for f in all_files if os.path.splitext(f)[1].lower() in SUBTITLE_EXTS]
    has_external = len(ext_subs) > 0

    # 检测外挂字幕语种
    languages = set()
    lang_patterns = {
        "chs": re.compile(r'[.\-_](chs|sc|zh|chi|chinese|简体|中文|简中)', re.I),
        "cht": re.compile(r'[.\-_](cht|tc|繁体|繁中)', re.I),
        "eng": re.compile(r'[.\-_](eng|en|english)', re.I),
        "jpn": re.compile(r'[.\-_](jpn|jp|ja|japanese|日语|日文)', re.I),
        "kor": re.compile(r'[.\-_](kor|ko|korean|韩语|韩文)', re.I),
    }
    for sf in ext_subs:
        matched = False
        for lang, pat in lang_patterns.items():
            if pat.search(sf):
                languages.add(lang)
                matched = True
        if not matched:
            languages.add("unknown")

    missing_chinese = "chs" not in languages and "cht" not in languages

    return {
        "has_embedded": False,  # 需要 mediainfo 才能判断，暂时不做
        "has_external": has_external,
        "external_languages": sorted(languages),
        "missing_chinese": missing_chinese if has_external else True,
    }


# ── 单文件夹分析 ──

def analyze_folder(folder_path: str, library_data: List[Dict] = None, tmdb_client=None, category_hint: str = "") -> Dict:
    """分析单个文件夹，返回完整诊断报告（纯读取）
    tmdb_client: 可选，传入则用 TMDB 增强改名预览（获取英文名/年份）
    category_hint: 一级分类目录名，传给 classify_folder
    """
    if not os.path.isdir(folder_path):
        return {"path": folder_path, "folder_type": "unknown", "error": "not a directory"}

    folder_name = os.path.basename(folder_path)
    info = classify_folder(folder_path, library_data, category_hint=category_hint)
    folder_type = info.get("type", "unknown")

    # 收集文件
    all_items = []
    try:
        all_items = os.listdir(folder_path)
    except OSError:
        return {"path": folder_path, "folder_type": folder_type, "error": "cannot read directory"}

    video_files = [f for f in all_items if os.path.isfile(os.path.join(folder_path, f))
                   and os.path.splitext(f)[1].lower() in VIDEO_EXTS]
    subdirs = [d for d in all_items if os.path.isdir(os.path.join(folder_path, d))
               and not d.startswith('.') and not _is_ignorable_subdir(d)]

    # ── 构建 library 映射 ──
    lib_map = {}
    if library_data:
        for v in library_data:
            lib_map[v.get("file_path", "")] = v

    # ── 类型细化已移除（新体系只有 movie/collection/series/tv/season/mixed）──

    # ── 结构诊断 ──
    structure_ops = _diagnose_structure(folder_path, folder_name, folder_type, video_files, subdirs)

    # ── 刮削诊断 ──
    scrape_issues = _diagnose_scrape(folder_path, folder_type, video_files)

    # ── 影子名诊断 ──
    shadow_name_issues = _diagnose_shadow_names(folder_path, video_files, lib_map)

    # ── 质量诊断 ──
    quality_issues = _diagnose_quality(folder_path, video_files, lib_map)

    # ── 文件名诊断 ──
    filename_issues = []
    for vf in video_files:
        fi = _analyze_filename(vf)
        if fi["filename_issues"]:
            for issue in fi["filename_issues"]:
                issue["file"] = vf
                filename_issues.append(issue)

    # ── 命名诊断 ──
    rename_ops = _diagnose_rename(folder_path, folder_type, video_files, lib_map, tmdb_client)

    # ── 字幕诊断 ──
    subtitle_info = _analyze_subtitles(folder_path, video_files)

    # ── 视频清单 ──
    videos_detail = []
    for vf in video_files:
        full = os.path.join(folder_path, vf)
        v_info = lib_map.get(full, {})
        videos_detail.append({
            "file_name": vf,
            "resolution": v_info.get("resolution", ""),
            "codec": v_info.get("video_codec", ""),
            "audio": v_info.get("audio_codec", ""),
            "size_gb": v_info.get("size_gb", 0),
            "duration": v_info.get("duration", 0) or v_info.get("duration_min", 0),
            "hdr_type": v_info.get("hdr_type", ""),
        })

    return {
        "path": folder_path,
        "folder_name": folder_name,
        "folder_type": folder_type,
        "structure_ops": structure_ops,
        "rename_ops": rename_ops,
        "scrape_issues": scrape_issues,
        "shadow_name_issues": shadow_name_issues,
        "quality_issues": quality_issues,
        "filename_issues": filename_issues,
        "subtitle_info": subtitle_info,
        "videos": videos_detail,
    }


# ── 类型细化 ──

def _refine_type(folder_name: str, video_files: List[str], current_type: str) -> str:
    """细化 movie_collection/mixed 为 variety/misc"""
    fn_lower = folder_name.lower()

    # 综艺关键词
    for kw in VARIETY_KEYWORDS:
        if kw in fn_lower:
            return "variety"

    # 文件名带日期模式 → 综艺
    if video_files:
        date_count = sum(1 for f in video_files if VARIETY_DATE_PATTERN.search(f))
        if date_count >= len(video_files) * 0.4:
            return "variety"

    # 杂项关键词
    for kw in MISC_KEYWORDS:
        if kw in fn_lower:
            return "misc"

    return current_type


# ── CD 分片检测 ──

# 匹配 CD/Disc 分片标记：CD1, cd2, Disc1, .cd1, CD 1 等
_CD_PATTERN = re.compile(r'[.\s_\-]?(?:CD|Disc|DISC|disk)\s*(\d{1,2})', re.I)

# 广告/垃圾前缀清洗（用于提取核心文件名）
_AD_SITE_PATTERNS = [
    re.compile(r'\[?(?:红旅首发|电影天堂|影视帝国|66影视|六六影视)\S*\]?', re.I),
    re.compile(r'\[[\w\s]*(?:www\.|bbs\.|http)\S*?\]', re.I),  # [xxx www.xxx.com]
    re.compile(r'\[\S*?\.(?:com|net|org|cc|co|tv)\S*?\]', re.I),  # [xxx.com] 域名
    re.compile(r'(?:www\.|bbs\.|http)\S+', re.I),  # 裸 URL
]


def _extract_cd_group_key(filename: str) -> Optional[str]:
    """提取 CD 分片的分组 key（去掉 CD 编号后的核心名）。非分片返回 None"""
    name = os.path.splitext(filename)[0]
    m = _CD_PATTERN.search(name)
    if not m:
        return None
    # 去掉 CD 标记得到核心名
    core = name[:m.start()] + name[m.end():]
    core = core.strip(' ._-')
    return core if core else None


def _clean_filename_for_folder(filename: str) -> str:
    """清洗文件名用于生成文件夹名：去广告、去质量标签、去 CD 标记"""
    # 只去掉已知的媒体扩展名，避免误删 .Zero .Reign 等
    base, ext = os.path.splitext(filename)
    name = base if ext.lower() in MEDIA_EXTS else filename

    # 0. + 替换为空格（字幕组常用 + 代替空格）
    name = re.sub(r'\+', ' ', name)
    # 1. 去方括号内容（广告标签、字幕组等）— 包括中文方括号和日文引号
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'【.*?】', '', name)
    name = re.sub(r'「.*?」', '', name)
    # 2. 去圆括号内含域名的广告
    name = re.sub(r'\([^)]*(?:www\.|bbs\.|\.com|\.net|\.org|\.cc|\.co)[^)]*\)', '', name, flags=re.I)
    # 2b. 去圆括号内的编码/技术信息（如 (BD 720P x264 10bit AAC)、(1920x x 264 FLACx2)）
    name = re.sub(r'\([^)]*(?:x264|x265|HEVC|AVC|AAC|DTS|FLAC|10bit|ASSx?\d?)[^)]*\)', '', name, flags=re.I)
    # 2c. 去圆括号内的十六进制 hash（如 (C46B0638)）
    name = re.sub(r'\([A-Fa-f0-9]{6,}\)', '', name)
    # 3. 去已知广告站名
    name = re.sub(r'(?:红旅首发|电影天堂|影视帝国|66影视|六六影视|更多[^\s]*请去)[\s._\-]*', '', name, flags=re.I)
    # 4. 去裸 URL
    name = re.sub(r'(?:www\.|bbs\.|https?://)\S+', '', name, flags=re.I)
    # 5. 去质量标签
    name = re.sub(r'(?i)\.?(2160p|1080[pi]?|720[pi]?|480p|BluRay|WEB-?DL|WEB-?HR|WEBRip|HDTVrip|HDTV|BDRip|BDrip|DVDRip|Remux|UHD)(?=[^a-zA-Z]|$)', '', name)
    name = re.sub(r'(?i)(?<![a-zA-Z])(BD|HD|DVD|SD)(?=[^a-zA-Z]|$)', '', name)
    name = re.sub(r'(?i)\.?(x264|x265|H\.?264|H\.?265|HEVC|AVC|AAC|DTS|DTS-HD|FLAC|TrueHD|Atmos|10bit|Main10|AC3|DD\+?\d?)\b', '', name)
    name = re.sub(r'(?i)(中英双字|中英字幕|双语双字|中文字幕|中字|英字|无水印|修复版|加长版|初版|dvd-?rmvb|UNCUT|KORSUB)', '', name)
    name = re.sub(r'(?i)(国粤双语|国英双语|国日双语|粤语|国语|日语|韩语|英语|法语|泰语|简繁字幕|简繁外挂|简体|繁体)', '', name)
    name = re.sub(r'(?i)(1280高清|1024高清|高清|未删减版|超清)', '', name)
    # 5a2. 去字幕组/发布组名（常见的）
    name = re.sub(r'(?i)(?:YYeTs人人影视|人人影视|ZhuixinFan|Chi[_ ]Jap|Jap[_ ]Chi|AMZN|NTb|chs[_ ]eng|eng[_ ]chs)', '', name)
    # 5a3. 去音频声道标签（如 5.1、7.1）
    name = re.sub(r'(?<!\d)\d\s*\.\s*1(?!\d)', '', name)
    # 5b. 去媒体形式标签（对 TMDB 搜索是干扰）— 仅在非核心位置时去除
    # "剧场版" 如果紧跟在中文名后面（如"福音战士新剧场版"），不去除，因为它是名字的一部分
    # 只去独立出现的（前后有空格/分隔符/开头结尾）
    name = re.sub(r'(?<=[\s._\-])(?:劇場版|剧场版|TV版|电视剧版|OVA|OAD|SP|特别篇|番外篇|总集篇|完结篇)(?=[\s._\-]|$)', '', name)
    name = re.sub(r'^(?:劇場版|剧场版|TV版|电视剧版|OVA|OAD|SP|特别篇|番外篇|总集篇|完结篇)(?=[\s._\-]|$)', '', name)
    # 5c. 去季号标记（第1季/第一季/S01/s1-s3/1-8季 等）
    name = re.sub(r'第[一二三四五六七八九十\d]+[季部]', '', name)
    name = re.sub(r'\d+-\d+季', '', name)  # 1-8季
    name = re.sub(r'\d+季', '', name)  # 单独的 X季
    # 去尾部数字范围（如 "剧场版1-3"、"三部曲1-3"）
    name = re.sub(r'[\s]*\d+\s*-\s*\d+$', '', name)
    name = re.sub(r'[\s._-]*[sS]\d+\s*[-~&+]\s*[sS]?\d+$', '', name)  # s1-s3, s1+s2, s1&s2
    name = re.sub(r'[\s._-]*[sS]\d+\s+[sS]\d+$', '', name)  # S1 S2
    name = re.sub(r'[\s._-]*[sS]\d+$', '', name)  # 尾部 S01
    # 去 & 连接的季号（如 "第1季&第2季"、"s1&s2"）
    name = re.sub(r'[\s._-]*[sS]\d+\s*&\s*[sS]?\d+', '', name)
    name = re.sub(r'[\s._-]*&[\s._-]*$', '', name)  # 清理残留的 &
    # 5b2. 去分辨率数字（如 1024X576、1280X720、1920x1080）
    name = re.sub(r'\d{3,4}[xX×]\d{3,4}', '', name)
    # 也去掉单独的分辨率数字后跟 X（如 "1280X" 残留）
    name = re.sub(r'\d{3,4}[xX×](?=\s|$)', '', name)
    # 5c. 去掉集号标记后的子标题（如 ".01.霸王之卵" → ".01"，保留集号但去子标题）
    name = re.sub(r'(?<=\d{2})[.\s]+[\u4e00-\u9fff][\u4e00-\u9fff\w]*$', '', name)
    # 5d. 去掉中日双语混合名中的重复部分（英文名.中文名 → 只保留英文名）
    m = re.match(r'^([A-Za-z][\w\s\':!,&.-]+\d*)\s*[.。]\s*([\u4e00-\u9fff].+)', name)
    if m:
        en_part = m.group(1).strip()
        if len(en_part.split()) >= 2:
            name = en_part
    # 6. 去 CD 标记
    name = _CD_PATTERN.sub('', name)
    # 7. 去尾部的发布组标签（只匹配已知的常见发布组）
    known_groups = r'(?:FGT|SPARKS|DHD|CMCT|WIKI|FRDS|USURY|RARBG|YIFY|NTb|AMZN|FLUX|NOGRP|TEPES|EDITH|EMBER|AMIABLE|GECKOS|ROVERS|DEMAND|EVOLVE|PLAYNOW|SHORTBREHD)'
    name = re.sub(r'\s*-\s*' + known_groups + r'$', '', name, flags=re.I)
    # 8. 清理分隔符和多余空格
    # 保护小数点（如 8.0、5.1）不被当分隔符
    name = re.sub(r'(?<!\d)[._]+', ' ', name)  # 前面不是数字的 . 和 _ 转空格
    name = re.sub(r'[._]+(?!\d)', ' ', name)   # 后面不是数字的 . 和 _ 转空格
    name = re.sub(r'_', ' ', name)  # 确保下划线也转空格
    name = re.sub(r'\s*-\s*', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # 9. 去掉尾部残留的圆括号（空括号去掉）
    name = re.sub(r'\(\s*\)', '', name).strip()
    # 10. 去掉尾部残留的中文标点
    name = re.sub(r'[：；，。！？、&]+$', '', name).strip()
    # 11. 去掉集号标记（Ep01、E01、S01E01 及其后面的内容）
    name = re.sub(r'\s+[Ee][Pp]?\d{1,3}(?:\s.*)?$', '', name).strip()
    name = re.sub(r'\s+S\d+E\d+(?:\s.*)?$', '', name, flags=re.I).strip()
    # 12. 去掉尾部的纯数字集号（如 "Devilman Crybaby 01" → "Devilman Crybaby"）
    name = re.sub(r'\s+\d{1,3}$', '', name).strip()
    # 12b. 去掉尾部的数字范围（如 "剧场版1-3" → "剧场版"）
    name = re.sub(r'\s*\d+-\d+$', '', name).strip()
    # 13. 去年份（独立的4位年份，如 2001、(2019)）
    name = re.sub(r'\(\s*(19|20)\d{2}\s*\)', '', name)  # 去 (2019)
    name = re.sub(r'(?<![.\d])\b(19|20)\d{2}\b(?!\d)', '', name)  # 去独立年份 2001
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else _extract_core_from_brackets(os.path.splitext(filename)[0])


def _extract_core_from_brackets(raw_name: str) -> str:
    """从全是方括号的文件名中提取有意义的部分（非字幕组、非分辨率、非编码）"""
    import re as _re
    brackets = _re.findall(r'\[([^\]]+)\]', raw_name)
    if not brackets:
        return raw_name
    
    # 过滤掉字幕组、分辨率、编码、语言等无意义的方括号
    skip_patterns = _re.compile(
        r'^(?:720[pP]?|1080[pP]?|2160[pP]?|480[pP]?|'
        r'GB|BIG5|CHS|CHT|JP|EN|SC|TC|'
        r'X264|X265|HEVC|AVC|AAC|DTS|FLAC|MP4|MKV|AVI|'
        r'GB_CN|GB_MP4|BDrip|BDRIP|HDRip|WEBRip|'
        r'AVC-8bit|简繁外挂|v\d+|'
        r'X264[_ ]AAC|DTS[_ ]HD|'  # 组合编码标签
        r'\d{3,4}[xX]\d{3,4})$', _re.I)  # 分辨率如 1280X720
    
    # 广告/URL 模式
    ad_pattern = _re.compile(r'(?:www\.|http|bbs\.|\.com|\.net|\.org|\.cc|红旅|电影天堂|影视帝国|66影视)', _re.I)
    
    # 编码/技术信息模式（方括号内含这些关键词的都跳过）
    tech_pattern = _re.compile(r'(?:x264|x265|HEVC|AVC|AAC|DTS|FLAC|BDRIP|BDRip|WEBRip|HDRip|\d{3,4}[xX×]\d{3,4})', _re.I)
    
    # 字幕组通常是第一个方括号且全英文短名
    candidates = []
    for i, b in enumerate(brackets):
        b = b.strip()
        if not b or len(b) < 2:
            continue
        if skip_patterns.match(b):
            continue
        if ad_pattern.search(b):
            continue
        if tech_pattern.search(b):
            continue
        # 纯数字（集号）跳过
        if _re.match(r'^\d{1,3}(v\d)?$', b):
            continue
        # 第一个方括号如果是纯英文短名（<15字符），大概率是字幕组名，跳过
        if i == 0 and _re.match(r'^[A-Za-z][\w\-]{1,14}$', b):
            continue
        candidates.append(b)
    
    if candidates:
        # 优先选含中文的（最可能是作品名），否则取最长的
        cn_candidates = [c for c in candidates if _re.search(r'[\u4e00-\u9fff]', c)]
        if cn_candidates:
            result = max(cn_candidates, key=len)
        else:
            result = max(candidates, key=len)
        # 下划线转空格，清理多余空格
        result = result.replace('_', ' ').strip()
        result = _re.sub(r'\s+', ' ', result)
        return result
    return raw_name


def clean_season_name(season_folder_name: str, parent_show_name: str = "") -> str:
    """季文件夹的 clean_name：中文剧名 + 第X季。
    剧名优先从父文件夹获取，没有父级时从季文件夹名自身清洗提取。
    只取中文部分。季号用中文"第X季"。
    """
    import re as _re
    from organizer import _extract_season_number

    season_num = _extract_season_number(season_folder_name)

    # 剧名：优先用父文件夹的剧名（只取中文部分）
    show_name = _extract_chinese_name(parent_show_name) if parent_show_name else ""

    if not show_name:
        cleaned = _clean_filename_for_folder(season_folder_name + ".tmp")
        show_name = _extract_chinese_name(cleaned) if cleaned else ""
        if not show_name or len(show_name) < 2 or _re.match(r'^(Season|第\d+季?|S\d+)$', show_name, _re.I):
            return season_folder_name

    if season_num is not None:
        return f"{show_name} 第{season_num}季"
    else:
        return show_name


def clean_episode_name(video_filename: str, parent_show_name: str = "",
                       episode_title: str = "") -> str:
    """集视频的 clean_name：中文剧名 + SxxExx [+ 集标题]。
    剧名优先从父文件夹获取，没有父级时从视频文件名清洗提取。只取中文部分。
    """
    import re as _re
    from tmdb_client import parse_filename

    parsed = parse_filename(video_filename)
    season = parsed.get("season")
    episode = parsed.get("episode")
    abs_ep = parsed.get("absolute_episode")

    # 剧名：优先用父文件夹的中文名
    show_name = _extract_chinese_name(parent_show_name) if parent_show_name else ""

    if not show_name:
        raw_clean = parsed.get("clean_name", "")
        cleaned = _re.sub(r'\s*-\s*\d+\s*$', '', raw_clean).strip()
        cleaned = _re.sub(r'\s+EP?\d+.*$', '', cleaned, flags=_re.I).strip()
        cleaned = _re.sub(r'\s+(中[英法日韩]|双语|字幕|弯弯).*$', '', cleaned).strip()
        cleaned = cleaned.strip(' -·')
        show_name = _extract_chinese_name(cleaned) if cleaned else ""

    if not show_name:
        return os.path.splitext(video_filename)[0]

    if season is not None and episode is not None:
        result = f"{show_name} S{season:02d}E{episode:02d}"
    elif abs_ep is not None:
        result = f"{show_name} E{abs_ep}"
    elif episode is not None:
        result = f"{show_name} E{episode:02d}"
    else:
        result = show_name

    if episode_title and episode_title != show_name:
        result = f"{result} {episode_title}"

    return result


def _extract_chinese_name(name: str) -> str:
    """从混合中英文名中提取中文部分。
    '西部世界 Westworld' → '西部世界'
    '钢之炼金术师 FA' → '钢之炼金术师 FA'
    '切尔诺贝利 Chernobyl' → '切尔诺贝利'
    '鋼の錬金術師' → '鋼の錬金術師'
    纯英文名 → 返回原始名（fallback）
    """
    import re as _re
    if not name:
        return ""
    # 匹配开头的中文字符，可选跟一个全大写缩写（2-4字母，如 FA、TV、OVA）
    # 缩写后面不再继续匹配（避免 "钢之炼金术师 FA 鋼の錬金術師" 全部被匹配）
    m = _re.match(r'^([\u4e00-\u9fff]+(?:\s+[A-Z]{2,4})?)', name)
    if not m:
        # 没有缩写的纯中文
        m = _re.match(r'^([\u4e00-\u9fff]+)', name)
    if m:
        result = m.group(1).strip()
        if len(result) >= 2:
            return result
    return name


# ── 结构诊断 ──

def _diagnose_structure(folder_path: str, folder_name: str, folder_type: str,
                        video_files: List[str], subdirs: List[str]) -> List[Dict]:
    """诊断文件夹结构问题，生成整理计划"""
    ops = []

    # 聚合文件夹内散装视频 → 需要包文件夹（CD 分片合并到同一文件夹）
    if folder_type in ("collection", "series") and video_files:
        # 先按 CD 分片分组
        cd_groups = {}  # group_key → [files]
        standalone = []  # 非分片文件
        for vf in video_files:
            gk = _extract_cd_group_key(vf)
            if gk:
                cd_groups.setdefault(gk, []).append(vf)
            else:
                standalone.append(vf)

        # CD 分片组：合并到同一个文件夹
        for group_key, files in cd_groups.items():
            # 用第一个文件清洗后的名字作为文件夹名
            folder_target = _clean_filename_for_folder(files[0])
            for vf in files:
                ops.append({
                    "action": "wrap_in_folder",
                    "file": vf,
                    "target_folder": folder_target,
                    "severity": "high",
                    "auto_fixable": True,
                    "desc": f"CD分片 {vf} → 合并到 {folder_target}/",
                })

        # 非分片文件：各自包文件夹
        for vf in standalone:
            folder_target = _clean_filename_for_folder(vf)
            ops.append({
                "action": "wrap_in_folder",
                "file": vf,
                "target_folder": folder_target,
                "severity": "high",
                "auto_fixable": True,
                "desc": f"散装视频 {vf} → 包进文件夹 {folder_target}/",
            })

    # 有散落视频 + 子目录共存
    elif video_files and subdirs:
        ep_count = _count_episode_files(video_files)
        # 如果散落视频大多不是剧集编号，说明是独立作品散落在分类目录里 → 各自包文件夹
        if ep_count < len(video_files) * 0.3 and folder_type not in ("tv",):
            for vf in video_files:
                folder_target = _clean_filename_for_folder(vf)
                ops.append({
                    "action": "wrap_in_folder",
                    "file": vf,
                    "target_folder": folder_target,
                    "severity": "high",
                    "auto_fixable": True,
                    "desc": f"散装视频 {vf} → 包进文件夹 {folder_target}/",
                })
        elif folder_type == "tv":
            # TV 类型：散落视频和子目录共存
            # 检查是否多季混合 — 只有多季时才移到季目录
            from tmdb_client import parse_filename as _pf
            season_groups = {}
            for vf in video_files:
                s = _pf(vf).get("season") or 1
                season_groups.setdefault(s, []).append(vf)
            if len(season_groups) > 1:
                # 多季散落 → 按季归入子目录
                clean_name = re.sub(r'\s*[-–]\s*(TV|SP|OVA|OAD|特别篇|剧场版).*$', '', folder_name, flags=re.I).strip() or folder_name
                for s_num, files in sorted(season_groups.items()):
                    target = f"{clean_name} 第{s_num}季"
                    for vf in files:
                        ops.append({
                            "action": "move_to_subdir",
                            "file": vf,
                            "target_folder": target,
                            "severity": "high",
                            "auto_fixable": True,
                            "desc": f"{vf} → {target}/",
                        })
            # 单季散落 → 不动（TV 剧集可以直接散落在文件夹里）

    # 只有一个子目录 → 提升内容（但 tv 类型的单季目录是正常结构，不提升）
    elif len(subdirs) == 1 and not video_files and folder_type not in ("tv",):
        ops.append({
            "action": "flatten_single_subdir",
            "subdir": subdirs[0],
            "severity": "medium",
            "auto_fixable": True,
            "desc": f"只有一个子目录 {subdirs[0]}，内容可提升到 {folder_name}/",
        })

    # tv 类型末端文件夹混着不同季 — V3: 不再生成 split_seasons 操作
    # 季拆分交给 Step 4 的 reorganize_seasons_by_nfo 根据 NFO 做
    # elif folder_type == "tv" and not subdirs and video_files:
    #     （已移除，由 NFO 驱动的 reorganize_seasons_by_nfo 替代）

    return ops


# ── 刮削诊断 ──

def _diagnose_scrape(folder_path: str, folder_type: str, video_files: List[str]) -> List[Dict]:
    """诊断刮削问题"""
    issues = []

    # 聚合文件夹不检查文件夹级 NFO
    if folder_type in ("collection", "series", "mixed"):
        # 检查每个视频是否有同名 NFO
        for vf in video_files:
            base = os.path.splitext(vf)[0]
            nfo_path = os.path.join(folder_path, base + ".nfo")
            if not os.path.exists(nfo_path):
                issues.append({"type": "missing_nfo", "file": vf, "severity": "medium", "auto_fixable": True})
            # 检查同名 poster
            has_poster = any(
                os.path.exists(os.path.join(folder_path, base + suffix))
                for suffix in ["-poster.jpg", "-poster.png"]
            )
            if not has_poster:
                issues.append({"type": "missing_poster", "file": vf, "severity": "low", "auto_fixable": True})
    else:
        # 非聚合：检查文件夹级 NFO
        has_nfo = any(
            os.path.exists(os.path.join(folder_path, n))
            for n in ("movie.nfo", "tvshow.nfo", "season.nfo")
        )
        if not has_nfo:
            issues.append({"type": "missing_nfo", "file": None, "severity": "medium", "auto_fixable": True})

        # 检查文件夹级 poster
        has_poster = any(
            os.path.exists(os.path.join(folder_path, n))
            for n in ("poster.jpg", "poster.png")
        )
        if not has_poster:
            issues.append({"type": "missing_poster", "file": None, "severity": "low", "auto_fixable": True})

    return issues


# ── 影子名诊断 ──

def _diagnose_shadow_names(folder_path: str, video_files: List[str], lib_map: Dict) -> List[Dict]:
    """诊断影子名问题"""
    issues = []
    for vf in video_files:
        full = os.path.join(folder_path, vf)
        v_info = lib_map.get(full, {})
        shadow = v_info.get("shadow_name", "")
        source = v_info.get("shadow_name_source", "")
        tmdb_id = v_info.get("shadow_tmdb_id")

        if not shadow:
            issues.append({"type": "no_shadow_name", "file": vf, "severity": "medium", "auto_fixable": True})
            continue

        # 无英文名
        has_latin = bool(re.search(r'[a-zA-Z]{2,}', shadow))
        if not has_latin:
            issues.append({"type": "no_english", "file": vf, "shadow": shadow, "severity": "low", "auto_fixable": True})

        # 来源是 parsed 但有 tmdb 数据 → 应该升级
        if source == "parsed" and tmdb_id:
            issues.append({"type": "source_upgradable", "file": vf, "source": source, "severity": "low", "auto_fixable": True})

        # NFO 存在时检查 tmdb_id 一致性
        nfo_data = None
        base = os.path.splitext(vf)[0]
        nfo_path = os.path.join(folder_path, base + ".nfo")
        if os.path.exists(nfo_path):
            nfo_data = scraper.read_video_nfo(full)
        if not nfo_data:
            nfo_data = scraper.read_nfo(folder_path)
        if nfo_data and tmdb_id and nfo_data.get("tmdb_id") and tmdb_id != nfo_data.get("tmdb_id"):
            issues.append({"type": "tmdb_id_mismatch", "file": vf, "shadow_tmdb_id": tmdb_id,
                           "nfo_tmdb_id": nfo_data.get("tmdb_id"), "severity": "high", "auto_fixable": False})

    return issues


# ── 质量诊断 ──

def _diagnose_quality(folder_path: str, video_files: List[str], lib_map: Dict) -> List[Dict]:
    """诊断视频质量问题"""
    issues = []
    for vf in video_files:
        full = os.path.join(folder_path, vf)
        v_info = lib_map.get(full, {})
        if not v_info:
            continue

        resolution = v_info.get("resolution", "")
        width = v_info.get("width", 0)
        codec = v_info.get("video_codec", "")
        size_gb = v_info.get("size_gb", 0)
        duration = v_info.get("duration", 0) or v_info.get("duration_min", 0)

        # 低清
        if width and width < 1280:
            issues.append({"type": "low_resolution", "file": vf, "resolution": resolution,
                           "width": width, "severity": "medium", "auto_fixable": False})

        # 码率不足（粗略：size_gb / duration_hours < 2GB/h 对 1080p 来说偏低）
        if duration and duration > 0 and width and width >= 1280:
            duration_hours = duration / 60.0
            if duration_hours > 0:
                bitrate_approx = size_gb / duration_hours
                if bitrate_approx < 1.5:
                    issues.append({"type": "low_bitrate", "file": vf, "approx_gb_per_hour": round(bitrate_approx, 2),
                                   "severity": "low", "auto_fixable": False})

        # 旧编码
        if codec and codec.lower() in ("h264", "x264", "avc"):
            issues.append({"type": "old_codec", "file": vf, "codec": codec,
                           "severity": "low", "auto_fixable": False})

        # 文件名有广告/乱码 → 标记低质量来源
        fi = _analyze_filename(vf)
        if any(i["type"] in ("ad_tag", "garbled") for i in fi["filename_issues"]):
            issues.append({"type": "likely_low_quality_source", "file": vf,
                           "severity": "low", "auto_fixable": False})

    return issues


# ── 命名诊断 ──

def _diagnose_rename(folder_path: str, folder_type: str, video_files: List[str], lib_map: Dict,
                     tmdb_client=None) -> List[Dict]:
    """诊断命名问题，生成重命名计划
    分析层职责：清洗出最纯净的名字
    - 有 NFO：用 NFO 的 title + english_title + year
    - 有 tmdb_client：用 TMDB 查询增强
    - 都没有：用 _clean_filename_for_folder 清洗
    """
    ops = []
    is_collection = folder_type in ("collection", "series", "mixed")

    # 读取文件夹级刮削数据
    folder_scrape = scraper.read_nfo(folder_path)

    for vf in video_files:
        full = os.path.join(folder_path, vf)
        ext = os.path.splitext(vf)[1]

        # 1. 尝试读取视频级 NFO
        scrape_data = scraper.read_video_nfo(full)
        # 非聚合文件夹可以 fallback 到文件夹级 NFO
        if not scrape_data and not is_collection and folder_scrape:
            scrape_data = folder_scrape

        # 2. 有 tmdb_client 且没有 NFO → 用清洗名查 TMDB
        if not scrape_data and tmdb_client:
            clean = _clean_filename_for_folder(vf)
            if clean:
                try:
                    result = tmdb_client.scrape_by_filename(clean)
                    if result.tmdb_id:
                        scrape_data = result.dict()
                except Exception:
                    pass

        # 3. 生成新名字
        if scrape_data and scrape_data.get("title"):
            title = scrape_data.get("title", "")
            en = scrape_data.get("english_title", "")
            orig = scrape_data.get("original_title", "")
            year = scrape_data.get("year", "")
            # 英文名优先级：english_title > original_title（如果是拉丁文）
            if not en and orig and orig != title and bool(re.search(r'[a-zA-Z]{2,}', orig)):
                en = orig
            # 构建标准名
            clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
            if en and en != title:
                clean_en = re.sub(r'[<>:"/\\|?*]', '', en).strip()
                new_base = f"{clean_title} {clean_en}"
            else:
                new_base = clean_title
            if year:
                new_base = f"{new_base} ({year})"
            new_name = new_base + ext
        else:
            # 没有刮削数据 → 用清洗后的纯净名字
            clean = _clean_filename_for_folder(vf)
            new_name = clean + ext

        if new_name != vf:
            ops.append({
                "old_name": vf,
                "new_name": new_name,
                "severity": "low",
                "auto_fixable": True,
                "desc": f"{vf} → {new_name}",
            })

    return ops


# ── 全库批量分析 ──

def analyze_library(base_path: str, library_data: List[Dict] = None, tmdb_client=None) -> Dict:
    """分析整个媒体库，包含跨文件夹的诊断（如同剧多季散落）"""
    results = []
    cross_folder_issues = []

    if not os.path.isdir(base_path):
        return {"results": [], "cross_folder_issues": [], "error": "base path not found"}

    # 收集所有一级子文件夹的分析结果
    for item in sorted(os.listdir(base_path)):
        full = os.path.join(base_path, item)
        if os.path.isdir(full) and not item.startswith('.') and not _is_ignorable_subdir(item):
            report = analyze_folder(full, library_data, tmdb_client)
            results.append(report)

    # ── 跨文件夹诊断：同剧多季散落 ──
    cross_folder_issues.extend(_diagnose_scattered_seasons(results))

    # 统计
    total_structure = sum(len(r.get("structure_ops", [])) for r in results)
    total_rename = sum(len(r.get("rename_ops", [])) for r in results)
    total_scrape = sum(len(r.get("scrape_issues", [])) for r in results)
    total_quality = sum(len(r.get("quality_issues", [])) for r in results)
    total_filename = sum(len(r.get("filename_issues", [])) for r in results)
    total_shadow = sum(len(r.get("shadow_name_issues", [])) for r in results)

    return {
        "results": results,
        "cross_folder_issues": cross_folder_issues,
        "summary": {
            "total_folders": len(results),
            "structure_issues": total_structure,
            "rename_issues": total_rename,
            "scrape_issues": total_scrape,
            "quality_issues": total_quality,
            "filename_issues": total_filename,
            "shadow_name_issues": total_shadow,
            "cross_folder_issues": len(cross_folder_issues),
        }
    }


def _diagnose_scattered_seasons(folder_reports: List[Dict]) -> List[Dict]:
    """检测同剧多季散落在同级目录的情况
    两轮匹配：1. 文本匹配（核心名）2. TMDB ID 匹配（刮削数据）
    """
    issues = []
    already_matched_paths = set()

    # ── 第一轮：文本匹配 ──
    tv_folders = []
    for r in folder_reports:
        if r.get("folder_type") == "tv":
            name = r.get("folder_name", "")
            core = re.sub(r'\s*(?:S\d+|第\d+季|Season\s*\d+|第[一二三四五六七八九十]+季).*$', '', name, flags=re.I).strip()
            core = re.sub(r'\s*\(\d{4}\)\s*$', '', core).strip()
            core = re.sub(r'\s*\d{4}\s*$', '', core).strip()
            if core:
                tv_folders.append({"core_name": core, "folder_name": name, "path": r.get("path", "")})

    groups = {}
    for tf in tv_folders:
        key = tf["core_name"].lower()
        groups.setdefault(key, []).append(tf)

    for key, folders in groups.items():
        if len(folders) > 1:
            paths = [f["path"] for f in folders]
            already_matched_paths.update(paths)
            issues.append({
                "type": "scattered_seasons",
                "match_method": "text",
                "core_name": folders[0]["core_name"],
                "folders": [{"name": f["folder_name"], "path": f["path"]} for f in folders],
                "severity": "high",
                "auto_fixable": True,
                "desc": f"同剧多季散落：{folders[0]['core_name']}（{len(folders)} 个文件夹）",
            })

    # ── 第二轮：TMDB ID 匹配（捕获不同译名的同剧）──
    tmdb_groups = {}  # tmdb_id → [folder_info]
    for r in folder_reports:
        if r.get("folder_type") != "tv":
            continue
        path = r.get("path", "")
        if path in already_matched_paths:
            continue  # 已经被文本匹配捕获了
        # 读取 NFO 获取 tmdb_id
        nfo = scraper.read_nfo(path)
        if nfo and nfo.get("tmdb_id"):
            tid = nfo["tmdb_id"]
            tmdb_groups.setdefault(tid, []).append({
                "folder_name": r.get("folder_name", ""),
                "path": path,
                "tmdb_id": tid,
                "title": nfo.get("title", ""),
            })

    for tid, folders in tmdb_groups.items():
        if len(folders) > 1:
            title = folders[0]["title"] or folders[0]["folder_name"]
            issues.append({
                "type": "scattered_seasons",
                "match_method": "tmdb_id",
                "tmdb_id": tid,
                "core_name": title,
                "folders": [{"name": f["folder_name"], "path": f["path"]} for f in folders],
                "severity": "high",
                "auto_fixable": True,
                "desc": f"同剧多季散落（TMDB匹配）：{title}（{len(folders)} 个文件夹，ID={tid}）",
            })

    return issues
