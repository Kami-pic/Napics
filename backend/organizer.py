"""
媒体库整理引擎：分类判定核心
重命名功能已拆分到 renamer.py，结构整理已拆分到 structure_organizer.py
"""
import os
import re
import json
from typing import List, Dict, Optional, Tuple
from tmdb_client import parse_filename, ScrapeResult
import scraper
from core.constants import VIDEO_EXTS

# ── 从拆分模块 re-export，保持对外兼容 ──
from renamer import (
    generate_standard_name, _is_mostly_latin, _extract_english_from_filename,
    rename_videos_in_folder, generate_shadow_name_from_nfo, generate_folder_shadow_name,
    NAMING_RULES,
)
from structure_organizer import (
    reorganize_seasons, reorganize_seasons_by_nfo,
    wrap_loose_videos_in_category, organize_folder,
    merge_scattered_seasons, smart_archive_plan,
    smart_archive_recursive, execute_archive_plan,
)

# ── 判断算法 ──

_IGNORE_SUBDIRS = {
    # 字幕
    'subs', 'subtitles', 'sub', 'subtitle', 'fonts', 'font',
    # 花絮/附属（Plex/Emby 保留字）
    'extras', 'extra', 'bonus', 'featurettes', 'featurette',
    'behind the scenes', 'deleted scenes', 'interviews', 'scenes',
    'shorts', 'trailers', 'trailer', 'other',
    # 资源包/扫图/CD
    'scans', 'scan', 'cd', 'cds', 'ost', 'soundtrack', 'booklet', 'artbook', 'covers', 'cover',
    # 系统目录
    'sample', 'samples',
    '@eadir', '#recycle', '.ds_store',
}

_SUBTITLE_KEYWORDS = {'字幕', '外挂字幕', '外挂', 'subtitle', 'sub'}

def _is_ignorable_subdir(dirname: str) -> bool:
    """判断子目录是否应该被忽略（字幕、特典、系统目录等）"""
    dl = dirname.lower().strip()
    if dl in _IGNORE_SUBDIRS:
        return True
    # 包含字幕关键词
    for kw in _SUBTITLE_KEYWORDS:
        if kw in dl:
            return True
    return False


def _load_folder_type_override(folder_path: str) -> Optional[str]:
    """读取手动设置的文件夹类型"""
    ft_path = os.path.join(os.path.dirname(__file__), "folder_types.json")
    if os.path.exists(ft_path):
        try:
            with open(ft_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(folder_path)
        except Exception:
            pass
    return None


def classify_folder(folder_path: str, library_data: List[Dict] = None, category_hint: str = "") -> Dict:
    """判断文件夹类型。
    category_hint: 一级分类目录名（如"电影""电视剧""动画番""综艺""其他"），由上层传入。
    有 category_hint 时走简化路径（一级分类直接决定基础类型）；
    无 category_hint 时走旧的文件结构推断逻辑（兼容测试脚本/API直接调用）。
    返回: {"type": "movie"|"tv"|"collection"|"series"|"season"|"mixed", ...}
    """
    if not os.path.isdir(folder_path):
        return {"type": "unknown"}
    
    # 检查手动设置的类型（优先级最高）
    _ft_override = _load_folder_type_override(folder_path)
    if _ft_override:
        return {"type": _ft_override, "folder_name": os.path.basename(folder_path), "source": "manual"}
    
    folder_name = os.path.basename(folder_path)
    
    # ── 有 category_hint 时走简化路径 ──
    if category_hint:
        return _classify_by_category(folder_path, folder_name, category_hint, library_data)
    
    # ── 无 category_hint：旧的文件结构推断逻辑（兼容） ──
    return _classify_by_structure(folder_path, folder_name, library_data)


# ── 一级分类名 → 标签映射 ──
# 标签 6 种：movie / tv / anime_tv / anime_movie / variety / other
# 底层文件结构类型只有 2 种：movie / tv
# 自动推断用关键词匹配，用户可在 UI 上覆盖（持久化到 config.category_tags）
_CATEGORY_KEYWORD_MAP = {
    # movie
    "电影": "movie", "movie": "movie", "movies": "movie", "film": "movie", "films": "movie",
    # anime_movie
    "动画电影": "anime_movie",
    # tv
    "电视剧": "tv", "tv": "tv", "tvshow": "tv", "tvshows": "tv", "tv show": "tv", "tv shows": "tv",
    "剧集": "tv", "连续剧": "tv", "drama": "tv", "series": "tv",
    "纪录片": "tv", "documentary": "tv",
    # anime_tv
    "动画番": "anime_tv", "动画": "anime_tv", "番剧": "anime_tv", "anime": "anime_tv", "animation": "anime_tv",
    # variety
    "综艺": "variety", "variety": "variety", "variety show": "variety", "综艺节目": "variety",
    # other
    "其他": "other", "其他视频": "other", "other": "other", "mv": "other", "cg": "other",
}

# 标签 → 底层文件结构类型
CATEGORY_TAG_TO_STRUCTURE = {
    "movie": "movie",
    "anime_movie": "movie",
    "other": "movie",
    "tv": "tv",
    "anime_tv": "tv",
    "variety": "tv",
}


def category_tag_to_structure_type(tag: str) -> str:
    """标签 → 底层文件结构类型（movie/tv）"""
    return CATEGORY_TAG_TO_STRUCTURE.get(tag, "movie")


def infer_category_tag(dir_name: str) -> str:
    """根据目录名关键词自动推断标签，推断不了返回 'movie'
    默认 movie：movie 的处理逻辑更宽松，不会强行改变目录结构"""
    name_lower = dir_name.strip().lower()
    # 精确匹配
    if name_lower in _CATEGORY_KEYWORD_MAP:
        return _CATEGORY_KEYWORD_MAP[name_lower]
    # 包含匹配（优先长关键词）
    for kw in sorted(_CATEGORY_KEYWORD_MAP.keys(), key=len, reverse=True):
        if kw in name_lower:
            return _CATEGORY_KEYWORD_MAP[kw]
    return "movie"


def get_category_tag(category_name: str) -> str:
    """一级分类目录名 → 标签（movie/tv），识别不了的归 movie。
    兼容旧调用方式，内部走 infer_category_tag。"""
    return infer_category_tag(category_name)


def _classify_by_category(folder_path: str, folder_name: str, category_hint: str, library_data: List[Dict] = None) -> Dict:
    """根据一级分类标签 + 文件结构做简化判断。
    category_hint 是标签（movie/tv/anime_tv/anime_movie/variety/other）。"""
    subdirs, videos = _collect_children(folder_path)
    # 映射到底层结构类型
    structure_type = category_tag_to_structure_type(category_hint)
    
    # TV 类：需要区分 tv / mixed
    if structure_type == "tv":
        return _classify_tv_category(folder_path, folder_name, subdirs, videos, library_data)
    
    # 电影类：需要区分 movie / collection / series / mixed
    if structure_type == "movie":
        return _classify_movie_category(folder_path, folder_name, subdirs, videos, library_data)
    
    # 未知标签 fallback 到结构推断
    return _classify_by_structure(folder_path, folder_name, library_data)


def _classify_tv_category(folder_path: str, folder_name: str, subdirs: List[str], videos: List[str], library_data: List[Dict] = None) -> Dict:
    """tv 标签下的判定：tv / mixed
    - 无子目录有视频 → tv（扁平结构，整理时会强制季化）
    - 子目录是季目录（直接包含视频） → tv
    - 子目录各自还有子目录（三层结构，多部不同剧聚合） → mixed
    """
    # 无子目录
    if not subdirs:
        if videos:
            return {"type": "tv", "folder_name": folder_name, "videos": videos, "episode_count": len(videos)}
        return {"type": "empty", "folder_name": folder_name}
    
    # 只有1个子目录 → 不可能是聚合
    if len(subdirs) == 1:
        return {"type": "tv", "folder_name": folder_name,
                "videos": videos, "seasons": subdirs,
                "episode_count": len(videos)}
    
    # 多个子目录：检查结构深度
    # tv 是两层（季目录下直接是视频），mixed 是三层（子目录各自还有子目录）
    _SPECIAL_PATTERNS = re.compile(r'(?:Season\s*0+|Specials?|SP|OVA|OAD|特别篇|剧[場场]版)', re.I)
    children_with_subdirs = 0
    for d in subdirs:
        if _SPECIAL_PATTERNS.search(d):
            continue  # 特别篇豁免
        dp = os.path.join(folder_path, d)
        try:
            sub_items = os.listdir(dp)
            has_subdir = any(os.path.isdir(os.path.join(dp, s)) and not s.startswith('.')
                           and not _is_ignorable_subdir(s) for s in sub_items)
            if has_subdir:
                children_with_subdirs += 1
        except OSError:
            pass
    
    # 多个子目录各自有子目录 → mixed（多部不同 tv 聚合）
    if children_with_subdirs >= 2:
        return {"type": "mixed", "folder_name": folder_name, "subdirs": subdirs, "loose_videos": videos}
    
    # 默认当作 tv（子目录当作季处理）
    return {"type": "tv", "folder_name": folder_name,
            "videos": videos, "seasons": subdirs,
            "episode_count": len(videos)}


def _classify_movie_category(folder_path: str, folder_name: str, subdirs: List[str], videos: List[str], library_data: List[Dict] = None) -> Dict:
    """电影分类下的子文件夹判断：movie / collection / series / mixed
    处理三种情况：
    1. 纯末端（无子目录）：单视频=movie，多视频=collection/series
    2. 有散落视频（不管有没有子目录）：单视频=movie，多视频=collection/series
       子目录可能是正在下载的种子文件夹，不影响分类
    3. 纯封装（有子目录无散落视频）：看深度和系列关系
    """
    # 有散落视频时，以视频数量为准判定类型（忽略子目录）
    if videos:
        if len(videos) == 1:
            return {"type": "movie", "folder_name": folder_name, "videos": videos}
        if _is_series_collection(videos, folder_name):
            return {"type": "series", "folder_name": folder_name, "videos": videos}
        return {"type": "collection", "folder_name": folder_name, "videos": videos}
    
    # 无视频无子目录
    if not subdirs:
        return {"type": "empty", "folder_name": folder_name}
    
    # 纯封装（有子目录无散落视频）：计算深度决定展示方式
    depth = _calc_depth(folder_path)
    if depth >= 3:
        return {"type": "mixed", "folder_name": folder_name, "subdirs": subdirs, "loose_videos": []}
    
    # 2层结构：每个子目录是一部电影 → collection 或 series
    if _is_series_collection(subdirs, folder_name):
        return {"type": "series", "folder_name": folder_name, "subdirs": subdirs}
    return {"type": "collection", "folder_name": folder_name, "subdirs": subdirs}


def _collect_children(folder_path: str) -> Tuple[List[str], List[str]]:
    """收集子目录和视频文件（忽略字幕/特典等）"""
    subdirs = []
    videos = []
    for item in os.listdir(folder_path):
        full = os.path.join(folder_path, item)
        if os.path.isdir(full) and not item.startswith('.'):
            if not _is_ignorable_subdir(item):
                subdirs.append(item)
        elif os.path.isfile(full) and os.path.splitext(item)[1].lower() in VIDEO_EXTS:
            videos.append(item)
    return subdirs, videos


def _calc_depth(folder_path: str) -> int:
    """计算文件夹的最大子目录深度（当前层=1）"""
    max_d = 1
    try:
        for item in os.listdir(folder_path):
            full = os.path.join(folder_path, item)
            if os.path.isdir(full) and not item.startswith('.') and not _is_ignorable_subdir(item):
                max_d = max(max_d, 1 + _calc_depth(full))
    except OSError:
        pass
    return max_d


def _classify_by_structure(folder_path: str, folder_name: str, library_data: List[Dict] = None) -> Dict:
    """旧的文件结构推断逻辑（无 category_hint 时使用）"""
    subdirs, videos = _collect_children(folder_path)
    
    # 构建 shadow_name 映射
    lib_map = {}
    if library_data:
        for v in library_data:
            lib_map[v.get("file_path", "")] = v
    
    def _display_name(filename):
        full = os.path.join(folder_path, filename)
        info = lib_map.get(full, {})
        return info.get("shadow_name") or filename
    
    # 读旧 NFO
    nfo_data = scraper.read_nfo(folder_path)
    nfo_media_type = nfo_data.get("media_type", "") if nfo_data and nfo_data.get("title") else ""
    
    # ── 末端文件夹 ──
    if not subdirs:
        if not videos:
            return {"type": "empty", "folder_name": folder_name}
        if len(videos) == 1:
            if nfo_media_type in ("tvshow", "tv"):
                return {"type": "tv", "folder_name": folder_name, "videos": videos, "episode_count": 1}
            return {"type": "movie", "folder_name": folder_name, "videos": videos}
        
        display_names = [_display_name(v) for v in videos]
        ep_count = max(_count_episode_files(display_names), _count_episode_files(videos))
        
        individual_nfo_count = sum(
            1 for v in videos
            if os.path.exists(os.path.join(folder_path, os.path.splitext(v)[0] + ".nfo"))
        )
        if individual_nfo_count >= len(videos) * 0.5 and len(videos) >= 2:
            if _is_series_collection(display_names, folder_name):
                return {"type": "series", "folder_name": folder_name, "videos": videos}
            return {"type": "collection", "folder_name": folder_name, "videos": videos}
        
        if ep_count < len(videos) * 0.3 and len(videos) >= 3:
            if not _is_series_collection(display_names, folder_name):
                return {"type": "collection", "folder_name": folder_name, "videos": videos}
        
        if ep_count >= len(videos) * 0.5:
            return {"type": "tv", "folder_name": folder_name, "videos": videos, "episode_count": len(videos)}
        
        durations = _get_durations(folder_path, videos, library_data)
        avg_duration = sum(durations) / len(durations) if durations else 0
        if avg_duration > 0 and avg_duration < 45:
            return {"type": "tv", "folder_name": folder_name, "videos": videos, "episode_count": len(videos)}
        elif avg_duration > 60:
            if _is_series_collection(display_names, folder_name):
                return {"type": "series", "folder_name": folder_name, "videos": videos}
            return {"type": "collection", "folder_name": folder_name, "videos": videos}
        
        if nfo_media_type in ("tvshow", "tv") and ep_count > 0:
            return {"type": "tv", "folder_name": folder_name, "videos": videos, "episode_count": len(videos)}
        
        if _is_series_collection(display_names, folder_name):
            return {"type": "series", "folder_name": folder_name, "videos": videos}
        return {"type": "collection", "folder_name": folder_name, "videos": videos}
    
    # ── 有子目录 ──
    season_dirs = [d for d in subdirs if _is_season_dir(d)]
    non_season_dirs = [d for d in subdirs if not _is_season_dir(d)]
    
    if season_dirs and not non_season_dirs and not videos:
        return {"type": "tv", "folder_name": folder_name, "seasons": season_dirs}
    
    if season_dirs and (non_season_dirs or videos):
        actual_season_dirs = list(season_dirs)
        remaining_non_season = []
        for d in non_season_dirs:
            dp = os.path.join(folder_path, d)
            try:
                sub_videos = [f for f in os.listdir(dp) if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
                ep_count = _count_episode_files(sub_videos)
                if ep_count >= len(sub_videos) * 0.3 and len(sub_videos) >= 2:
                    actual_season_dirs.append(d)
                else:
                    remaining_non_season.append(d)
            except OSError:
                remaining_non_season.append(d)
        
        if not remaining_non_season and not videos:
            return {"type": "tv", "folder_name": folder_name, "seasons": actual_season_dirs}
        if len(actual_season_dirs) >= len(subdirs) * 0.5:
            return {"type": "tv", "folder_name": folder_name, "seasons": actual_season_dirs + remaining_non_season}
        return {"type": "mixed", "folder_name": folder_name, "seasons": actual_season_dirs, "others": remaining_non_season, "loose_videos": videos}
    
    # 无季目录
    child_types = []
    for d in subdirs:
        ct = classify_folder(os.path.join(folder_path, d), library_data)
        child_types.append(ct["type"])
    
    subdir_ep_count = _count_episode_files(subdirs)
    if subdir_ep_count >= len(subdirs) * 0.5 and len(subdirs) >= 3:
        return {"type": "tv", "folder_name": folder_name, "seasons": subdirs}
    
    if all(t == "tv" for t in child_types):
        return {"type": "tv", "folder_name": folder_name, "seasons": subdirs}
    
    tv_count = sum(1 for t in child_types if t == "tv")
    if tv_count >= len(child_types) * 0.5 and len(child_types) >= 2:
        return {"type": "tv", "folder_name": folder_name, "seasons": subdirs}
    
    if all(t in ("movie", "collection") for t in child_types):
        if _is_series_collection(subdirs, folder_name):
            return {"type": "series", "folder_name": folder_name, "subdirs": subdirs}
        return {"type": "collection", "folder_name": folder_name, "subdirs": subdirs}
    
    if nfo_media_type in ("tvshow", "tv") and subdirs:
        return {"type": "tv", "folder_name": folder_name, "seasons": subdirs}
    
    return {"type": "mixed", "folder_name": folder_name, "subdirs": subdirs, "loose_videos": videos}


def _count_episode_files(filenames: List[str]) -> int:
    """统计有集号特征的文件数，使用 parse_filename 做准确判断"""
    count = 0
    for f in filenames:
        parsed = parse_filename(f)
        if parsed.get("episode") is not None:
            count += 1
    return count

def _is_series_collection(videos: List[str], folder_name: str) -> bool:
    """判断多视频文件夹是否是同系列电影集合（如壳中少女三部曲、EVA新剧场版）
    通过文件名共同前缀或文件夹名关联度判断"""
    if len(videos) < 2:
        return False
    # 提取每个文件名的核心部分（去掉标签、年份、质量等）
    cores = []
    for f in videos:
        name = os.path.splitext(f)[0]
        name = re.sub(r'[\[\(【（].*?[\]\)】）]', ' ', name)
        name = re.sub(r'(?i)(2160p|1080p|720p|480p|BluRay|WEB-?DL|x264|x265|HEVC|AAC|DTS)', '', name)
        name = re.sub(r'\(\d{4}\)', '', name)  # 去年份
        name = re.sub(r'[._\-]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        # 取前几个字（中文取前4字，英文取前2词）
        cn = re.findall(r'[\u4e00-\u9fff]+', name)
        core = cn[0][:4] if cn else name.split()[0] if name.split() else ""
        cores.append(core)
    
    if not cores or not cores[0]:
        return False
    
    # 检查共同前缀
    prefix = cores[0]
    match_count = sum(1 for c in cores[1:] if c.startswith(prefix[:3]) or prefix[:3].startswith(c[:3]))
    if match_count >= len(cores) - 1:
        return True
    
    # 检查文件夹名是否包含系列关键词
    series_keywords = ['三部曲', '四部', '系列', '全集', '合集', 'trilogy', 'collection', 'saga']
    fn_lower = folder_name.lower()
    if any(kw in fn_lower for kw in series_keywords):
        return True
    
    # 检查文件夹名和文件名的关联度
    folder_core = re.sub(r'[\[\(【（].*?[\]\)】）]', '', folder_name)
    folder_core = re.sub(r'[^\u4e00-\u9fff\w\s]', '', folder_core).strip()[:6]
    if folder_core and len(folder_core) >= 2:
        folder_match = sum(1 for c in cores if folder_core[:3] in c or c[:3] in folder_core)
        if folder_match >= len(cores) * 0.5:
            return True
    
    return False


def _is_season_dir(dirname: str) -> bool:
    """判断目录名是否是季级别目录（含特别篇/SP/OVA/OAD/剧场版等，用于结构识别）"""
    return bool(re.search(
        r'(?:S\d+|第\d+季|第[一二三四五六七八九十]+季|Season\s*\d+|特别篇|SP|OVA|OAD|剧場版|剧场版|Specials?)',
        dirname, re.I
    ))


def _get_season_number(dirname: str) -> Optional[int]:
    """从目录名提取季号。无法确定季号时返回 None（不强行映射到 0）。
    物理层面的季号由 NFO 元数据决定，这里只做能确定的提取。"""
    # 标准季号
    m = re.search(r'(?:S(\d+)|第(\d+)季|Season\s*(\d+))', dirname, re.I)
    if m:
        return int(m.group(1) or m.group(2) or m.group(3))
    # 中文数字
    cn_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    m2 = re.search(r'第([一二三四五六七八九十]+)季', dirname)
    if m2:
        cn = m2.group(1)
        if cn in cn_map:
            return cn_map[cn]
        if cn.startswith('十') and len(cn) == 2 and cn[1] in cn_map:
            return 10 + cn_map[cn[1]]
        if cn == '十':
            return 10
    # SP/OVA/特别篇/剧场版 → 不强行分配季号，交给 NFO
    return None


def _extract_season_number(dirname: str) -> Optional[int]:
    """从目录名提取季号，支持多种格式"""
    # S01, Season 1, 第1季
    m = re.search(r'(?:S(\d+)|第(\d+)季|Season\s*(\d+))', dirname, re.I)
    if m:
        return int(m.group(1) or m.group(2) or m.group(3))
    # 中文数字：第一季, 第二季...
    cn_num_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    cn_m = re.search(r'第([一二三四五六七八九十]+)季', dirname)
    if cn_m:
        cn_str = cn_m.group(1)
        if cn_str in cn_num_map:
            return cn_num_map[cn_str]
        # 十一 ~ 十九
        if len(cn_str) == 2 and cn_str[0] == '十' and cn_str[1] in cn_num_map:
            return 10 + cn_num_map[cn_str[1]]
    # 圆圈数字 ①②③...
    circle_map = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5, '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10}
    for ch, num in circle_map.items():
        if ch in dirname:
            return num
    # 罗马数字 II, III, IV（在末尾或空格后）
    roman = re.search(r'(?:^|\s)(IV|III|II|I)(?:\s|$|\[)', dirname)
    if roman:
        roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
        return roman_map.get(roman.group(1))
    return None

def _get_durations(folder_path: str, filenames: List[str], library_data: List[Dict] = None) -> List[float]:
    """从媒体库数据中获取视频时长（分钟）"""
    if not library_data:
        return []
    durations = []
    for f in filenames:
        full = os.path.join(folder_path, f)
        for v in library_data:
            if v.get("file_path") == full:
                dur = v.get("duration_min", 0) or v.get("duration", 0)
                if dur > 0:
                    durations.append(dur)
                break
    return durations


# ── 刮削补充 ──

def scrape_supplement(folder_path: str, tmdb_client) -> Dict:
    """补充缺少的刮削字段，不覆盖已有数据"""
    existing = scraper.read_nfo(folder_path)
    
    if not existing:
        # 完全没有 NFO，执行完整刮削
        return scraper.scrape_folder(folder_path, tmdb_client, force=False)
    
    # 有 NFO 但可能缺字段
    folder_name = os.path.basename(folder_path)
    result = tmdb_client.scrape_by_filename(folder_name)
    if not result.tmdb_id:
        return {"status": "not_found", "data": existing}
    
    # 补充缺少的字段
    updated = False
    new_data = result.dict()
    for key in ["overview", "rating", "genres", "poster_url", "backdrop_url", "director", "cast", "runtime", "status", "total_seasons"]:
        existing_val = existing.get(key)
        new_val = new_data.get(key)
        if (not existing_val or existing_val in (0, 0.0, [], "")) and new_val:
            existing[key] = new_val
            updated = True
    
    if updated:
        # 重写 NFO
        scrape_result = ScrapeResult(**{**new_data, **{k: v for k, v in existing.items() if k in ScrapeResult.__fields__}})
        if existing.get("media_type") == "movie":
            scraper.write_movie_nfo(folder_path, scrape_result)
        else:
            scraper.write_tvshow_nfo(folder_path, scrape_result)
        
        # 补充海报
        if not _has_poster(folder_path) and result.poster_url:
            scraper.download_poster(folder_path, result.poster_url)
    
    return {"status": "supplemented" if updated else "complete", "data": existing}

def _has_poster(folder_path: str) -> bool:
    for name in ["poster.jpg", "poster.png", "folder.jpg"]:
        if os.path.exists(os.path.join(folder_path, name)):
            return True
    return False
