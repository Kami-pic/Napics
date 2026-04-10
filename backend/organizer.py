"""
媒体库整理引擎：判断算法 + 统一命名 + 刮削补充 + 多季规整 + 归类整理
"""
import os
import re
import shutil
import json
from typing import List, Dict, Optional, Tuple
from tmdb_client import parse_filename, ScrapeResult
import scraper

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
# 标签只有 2 种：movie / tv
# 自动推断用关键词匹配，用户可在 UI 上覆盖（持久化到 config.category_tags）
_CATEGORY_KEYWORD_MAP = {
    # movie
    "电影": "movie", "movie": "movie", "movies": "movie", "film": "movie", "films": "movie",
    "动画电影": "movie",
    # tv（所有非电影的都归 tv）
    "电视剧": "tv", "tv": "tv", "tvshow": "tv", "tvshows": "tv", "tv show": "tv", "tv shows": "tv",
    "剧集": "tv", "连续剧": "tv", "drama": "tv", "series": "tv",
    "动画番": "tv", "动画": "tv", "番剧": "tv", "anime": "tv", "animation": "tv",
    "综艺": "tv", "variety": "tv", "variety show": "tv", "综艺节目": "tv",
    "其他": "tv", "其他视频": "tv", "other": "tv", "mv": "tv", "cg": "tv",
    "纪录片": "tv", "documentary": "tv",
}


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
    category_hint 是标签（movie/tv）。"""
    subdirs, videos = _collect_children(folder_path)
    tag = category_hint
    
    # TV 类：需要区分 tv / mixed
    if tag == "tv":
        return _classify_tv_category(folder_path, folder_name, subdirs, videos, library_data)
    
    # 电影类：需要区分 movie / collection / series / mixed
    if tag == "movie":
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
    2. 纯封装（有子目录无散落视频）：看深度和系列关系
    3. 混合（有子目录也有散落视频）：封装+散装共存 → collection
    """
    # 末端文件夹（无子目录）
    if not subdirs:
        if not videos:
            return {"type": "empty", "folder_name": folder_name}
        if len(videos) == 1:
            return {"type": "movie", "folder_name": folder_name, "videos": videos}
        # 多视频：判断是 collection 还是 series
        if _is_series_collection(videos, folder_name):
            return {"type": "series", "folder_name": folder_name, "videos": videos}
        return {"type": "collection", "folder_name": folder_name, "videos": videos}
    
    # 有子目录也有散落视频 → 封装+散装共存
    if videos:
        return {"type": "collection", "folder_name": folder_name,
                "subdirs": subdirs, "loose_videos": videos}
    
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
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    for item in os.listdir(folder_path):
        full = os.path.join(folder_path, item)
        if os.path.isdir(full) and not item.startswith('.'):
            if not _is_ignorable_subdir(item):
                subdirs.append(item)
        elif os.path.isfile(full) and os.path.splitext(item)[1].lower() in video_exts:
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
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
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
                sub_videos = [f for f in os.listdir(dp) if os.path.splitext(f)[1].lower() in video_exts]
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

# ── 命名规则 ──

NAMING_RULES = {
    "movie": "{title} ({year})",
    "episode": "{title} S{season:02d}E{episode:02d}",
    "episode_with_name": "{title} S{season:02d}E{episode:02d} {ep_title}",
}

def generate_standard_name(filename: str, scrape_data: Optional[Dict] = None, video_info: Optional[Dict] = None, folder_title: str = "", is_collection: bool = False) -> str:
    """根据刮削数据生成标准文件名
    命名优先级：中文名 + 英文原名（确保英文名存在）
    is_collection=True 时不按剧集格式命名（电影聚合/剧场版聚合）
    """
    ext = os.path.splitext(filename)[1]
    parsed = parse_filename(filename)
    
    cn_title = ""
    en_title = ""
    year = ""
    season = parsed.get("season")
    episode = parsed.get("episode")
    
    if scrape_data:
        cn_title = scrape_data.get("title", "")
        # 分集模式：用剧名而非分集标题作为主名
        ep_title = scrape_data.get("episode_title", "")
        if ep_title and episode is not None and folder_title:
            cn_title = folder_title  # 用剧名
        
        # 优先用 english_title（专门获取的英文名）
        en = scrape_data.get("english_title", "")
        orig = scrape_data.get("original_title", "")
        
        if en and en != cn_title:
            en_title = en
        elif orig and orig != cn_title and _is_mostly_latin(orig):
            en_title = orig
        
        year = scrape_data.get("year", "")
    
    if not cn_title:
        # 优先用 _clean_filename_for_folder 深度清洗
        from analyzer import _clean_filename_for_folder
        cleaned = _clean_filename_for_folder(filename)
        if cleaned and len(cleaned) >= 2:
            cn_title = cleaned
        else:
            clean_name = parsed["clean_name"]
            if len(clean_name) <= 2 or re.match(r'^[\d~]+$', clean_name):
                cn_title = folder_title or clean_name
            else:
                cn_title = clean_name
    
    # 如果 cn_title 只是集号（S01E02 等），用 folder_title 替代
    if cn_title and re.match(r'^S\d+E\d+$', cn_title, re.I) and folder_title:
        cn_title = folder_title
    if not year:
        year = parsed.get("year", "")
    
    def clean(s):
        return re.sub(r'[<>:"/\\|?*]', '', s).strip()
    
    # 构建名字：中文名 + 英文名
    base = clean(cn_title)
    if en_title and en_title != cn_title:
        base += " " + clean(en_title)
    
    # 电影聚合/剧场版聚合：尊重原始名称，不按剧集格式
    if is_collection:
        if year:
            name = f"{base} ({year})"
        else:
            name = base
    elif episode is not None:
        s = season or 1
        name = f"{base} S{s:02d}E{episode:02d}"
    elif year:
        name = f"{base} ({year})"
    else:
        name = base
    
    # 附加质量信息
    if video_info:
        h = video_info.get("height", 0)
        if h >= 2160: name += " 2160p"
        elif h >= 1080: name += " 1080p"
        elif h >= 720: name += " 720p"
    
    # 最终清洗：去掉影子名中不应该出现的内容
    name = re.sub(r'\([A-Fa-f0-9]{6,}\)', '', name)       # 去 hash (C46B0638)
    name = re.sub(r'\[.*?\]', '', name)                     # 去方括号 [Heaven's Feel]
    name = re.sub(r'「.*?」', '', name)                     # 去日文引号
    name = re.sub(r'(?:www\.|http)\S*', '', name, flags=re.I)  # 去 URL
    name = re.sub(r'(?:电影天堂|影视帝国|红旅首发|66影视)\S*', '', name)  # 去广告站名
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name + ext


def _is_mostly_latin(text: str) -> bool:
    """判断字符串是否主要由拉丁字母组成"""
    if not text:
        return False
    latin_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = sum(1 for ch in text if ch.isalpha())
    return total > 0 and latin_count / total > 0.5


def _extract_english_from_filename(raw_name: str) -> str:
    """从文件名中提取英文部分（连续的拉丁字母+空格序列）"""
    if not raw_name:
        return ""
    # 找到最长的连续英文片段
    parts = re.findall(r'[A-Za-z][A-Za-z\s\'\-\.]{3,}', raw_name)
    if not parts:
        return ""
    # 取最长的那个，清理一下
    best = max(parts, key=len)
    best = re.sub(r'\s+', ' ', best).strip(' .-')
    # 过滤掉纯质量标签
    quality_words = {'BluRay', 'WEB', 'HDTV', 'DVDRip', 'BDRip', 'Remux', 'HEVC', 'AAC', 'DTS', 'FLAC'}
    if best in quality_words or len(best) < 3:
        return ""
    return best

# ── 统一命名 ──

def rename_videos_in_folder(folder_path: str, tmdb_client=None, dry_run: bool = True,
                            library_data: List[Dict] = None, folder_type: str = None,
                            category_hint: str = "", whitelist: List[str] = None) -> List[Dict]:
    """统一重命名：文件夹 + 内部视频文件
    folder_type: 由流水线传入，不传则保底调 classify_folder
    category_hint: 一级分类目录名，传给 classify_folder
    dry_run=True 时只返回预览，不实际执行
    whitelist: 如果提供，则只对名单内的文件生成重命名计划
    """
    results = []
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    folder_name = os.path.basename(folder_path)
    
    # 构建 file_path → video_info 的映射
    lib_map = {}
    if library_data:
        for v in library_data:
            lib_map[v.get("file_path", "")] = v
    
    # 保底：没传 folder_type 就自己判断
    if folder_type is None:
        ft_result = classify_folder(folder_path, library_data, category_hint=category_hint)
        folder_type = ft_result.get("type", "unknown")
    
    is_collection = folder_type in ("collection", "series", "mixed")
    is_wrapped_movie = folder_type == "movie"  # 封装电影：文件夹名和视频文件名同步
    
    # 1. 先尝试重命名文件夹本身（基于刮削数据）
    # 聚合文件夹（多部不同电影）不重命名文件夹本身
    folder_scrape = None
    if is_collection:
        # 聚合文件夹：不刮削文件夹，不改文件夹名，每个视频单独处理
        pass
    else:
        nfo = scraper.read_nfo(folder_path)
        if nfo and nfo.get("tmdb_id"):
            folder_scrape = nfo
            if not nfo.get("english_title") and tmdb_client:
                try:
                    mt = nfo.get("media_type", "movie")
                    if mt in ("tvshow", "tv", "episode"):
                        mt = "tv"
                    en = tmdb_client._get_english_title(mt, nfo["tmdb_id"], nfo.get("original_title", ""))
                    if en:
                        folder_scrape = dict(folder_scrape)
                        folder_scrape["english_title"] = en
                except Exception:
                    pass
        elif tmdb_client:
            r = tmdb_client.scrape_by_filename(folder_name)
            if r.tmdb_id:
                folder_scrape = r.dict()
    
    if folder_scrape:
        title = folder_scrape.get("title", "")
        orig = folder_scrape.get("original_title", "")
        year = folder_scrape.get("year", "")
        media_type = folder_scrape.get("media_type", "")
        
        if title:
            clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
            # 加英文名（优先 english_title，fallback 到 original_title）
            en = folder_scrape.get("english_title", "")
            if not en and orig and orig != title and _is_mostly_latin(orig):
                en = orig
            if en and en != title:
                clean_en = re.sub(r'[<>:"/\\|?*]', '', en).strip()
                clean_title = clean_title + " " + clean_en
            
            if media_type == "movie" and year:
                new_folder_name = f"{clean_title} ({year})"
            elif media_type in ("tv", "tvshow"):
                new_folder_name = clean_title
            else:
                new_folder_name = f"{clean_title} ({year})" if year else clean_title
            
            # 生成文件夹的影子名（中文名 + 英文名 (年份)）
            folder_shadow = title
            en = folder_scrape.get("english_title", "")
            if not en and orig and orig != title and _is_mostly_latin(orig):
                en = orig
            if en and en != title:
                folder_shadow = f"{title} {en}"
            if year and folder_shadow:
                folder_shadow = f"{folder_shadow} ({year})"
            
            if new_folder_name != folder_name:
                results.append({
                    "old_name": folder_name,
                    "new_name": new_folder_name,
                    "old_path": folder_path,
                    "new_path": os.path.join(os.path.dirname(folder_path), new_folder_name),
                    "is_folder": True,
                    "shadow_name": folder_shadow,
                })
            else:
                # 名字没变也要返回影子名信息
                results.append({
                    "old_name": folder_name,
                    "new_name": folder_name,
                    "old_path": folder_path,
                    "new_path": folder_path,
                    "is_folder": True,
                    "unchanged": True,
                    "shadow_name": folder_shadow,
                })
    
    # 2. 重命名内部视频文件
    # 规范化白名单路径方便对比
    w_set = {os.path.normpath(p).lower() for p in whitelist} if whitelist else None

    for item in sorted(os.listdir(folder_path)):
        full = os.path.normpath(os.path.abspath(os.path.join(folder_path, item)))
        if not os.path.isfile(full) or os.path.splitext(item)[1].lower() not in video_exts:
            continue
        
        # 白名单过滤：如果提供了白名单且当前文件不在名单内，跳过（它是老兵）
        if w_set is not None and full.lower() not in w_set:
            continue
        
        ext = os.path.splitext(item)[1]
        
        # ── 封装电影：视频文件名 = 文件夹名 + 扩展名（无条件绑定）──
        if is_wrapped_movie:
            # 从文件夹改名结果中取标准名（如果文件夹要改名，用新名；否则用当前文件夹名）
            folder_rename = next((r for r in results if r.get("is_folder")), None)
            target_folder_name = folder_rename["new_name"] if folder_rename else folder_name
            new_name = target_folder_name + ext
            
            shadow = target_folder_name
            shadow = re.sub(r'\s+(2160p|1080p|720p)$', '', shadow)
            
            if new_name != item:
                results.append({
                    "old_name": item, "new_name": new_name,
                    "old_path": full, "new_path": os.path.join(folder_path, new_name),
                    "shadow_name": shadow,
                })
            else:
                results.append({
                    "old_name": item, "new_name": item,
                    "old_path": full, "new_path": full,
                    "unchanged": True, "shadow_name": shadow,
                })
            
            if new_name != item and not dry_run:
                new_path = os.path.join(folder_path, new_name)
                if not os.path.exists(new_path):
                    os.rename(full, new_path)
                    # 同步重命名同名前缀的关联文件（旧格式兼容）
                    old_base = os.path.splitext(full)[0]
                    new_base = os.path.splitext(new_path)[0]
                    for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                        old_f = old_base + suffix
                        new_f = new_base + suffix
                        if os.path.exists(old_f):
                            try: os.rename(old_f, new_f)
                            except: pass
            continue
        
        # ── 非封装电影：走原有逻辑 ──
        scrape_data = None
        file_nfo = scraper.read_video_nfo(full)
        if file_nfo and file_nfo.get("tmdb_id"):
            scrape_data = file_nfo
            # 补充 english_title
            if not file_nfo.get("english_title") and tmdb_client:
                try:
                    mt = file_nfo.get("media_type", "movie")
                    if mt in ("tvshow", "tv", "episode"):
                        mt = "tv"
                    en = tmdb_client._get_english_title(mt, file_nfo["tmdb_id"], file_nfo.get("original_title", ""))
                    if en:
                        scrape_data = dict(scrape_data)
                        scrape_data["english_title"] = en
                except Exception:
                    pass
        elif folder_scrape:
            scrape_data = folder_scrape
        elif tmdb_client:
            r = tmdb_client.scrape_by_filename(item)
            if r.tmdb_id:
                scrape_data = r.dict()
        
        # 对于电影聚合中的每个文件，尝试单独刮削获取各自的标题
        file_scrape = scrape_data
        if is_collection and not file_nfo:
            # 电影聚合中每个文件可能是不同的电影，尝试单独匹配
            if tmdb_client:
                r = tmdb_client.scrape_by_filename(item)
                if r.tmdb_id:
                    file_scrape = r.dict()
        
        video_info = lib_map.get(full)
        ft = ""
        if folder_scrape:
            ft = folder_scrape.get("title", "") or folder_scrape.get("original_title", "")
            # 补充英文名：分集 NFO 可能没有英文剧名，从文件夹级 NFO 获取
            if file_scrape and not file_scrape.get("english_title") and folder_scrape.get("english_title"):
                file_scrape = dict(file_scrape)
                file_scrape["english_title"] = folder_scrape["english_title"]
        if not ft:
            ft = re.sub(r'[\[\(【（].*?[\]\)】）]', '', folder_name).strip()
        new_name = generate_standard_name(item, file_scrape, video_info, ft, is_collection=is_collection)
        
        # 生成影子名（不含扩展名和质量标签）
        shadow = os.path.splitext(new_name)[0]
        shadow = re.sub(r'\s+(2160p|1080p|720p)$', '', shadow)
        
        if new_name != item:
            results.append({
                "old_name": item,
                "new_name": new_name,
                "old_path": full,
                "new_path": os.path.join(folder_path, new_name),
                "shadow_name": shadow,
            })
        else:
            # 名字没变也返回，带影子名
            results.append({
                "old_name": item,
                "new_name": item,
                "old_path": full,
                "new_path": full,
                "unchanged": True,
                "shadow_name": shadow,
            })
        
        if new_name != item and not dry_run:
            new_path = os.path.join(folder_path, new_name)
            if not os.path.exists(new_path):
                os.rename(full, new_path)
                old_base = os.path.splitext(full)[0]
                new_base = os.path.splitext(new_path)[0]
                for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
                    old_f = old_base + suffix
                    new_f = new_base + suffix
                    if os.path.exists(old_f):
                        try:
                            os.rename(old_f, new_f)
                        except Exception:
                            pass
    
    # 3. 递归处理子文件夹（季目录重命名 + 非季子文件夹也递归）
    try:
        for item in sorted(os.listdir(folder_path)):
            sub_path = os.path.join(folder_path, item)
            if not os.path.isdir(sub_path) or item.startswith('.') or _is_ignorable_subdir(item):
                continue
            
            # 尝试识别季号（支持多种格式）
            season_num = _extract_season_number(item)
            is_special = bool(re.search(r'(特别篇|SP|OVA|OAD|剧场版)', item, re.I))
            
            if season_num is not None or is_special:
                # 构造标准季目录名
                show_name = ""
                if folder_scrape:
                    cn = folder_scrape.get("title", "")
                    en = folder_scrape.get("original_title", "")
                    if cn:
                        show_name = re.sub(r'[<>:"/\\|?*]', '', cn).strip()
                        if en and en != cn and _is_mostly_latin(en):
                            show_name += " " + re.sub(r'[<>:"/\\|?*]', '', en).strip()
                
                if season_num is not None:
                    if not show_name:
                        show_name = re.sub(r'[\s._-]*(?:S\d+|第\d+季|Season\s*\d+|[①②③④⑤⑥⑦⑧⑨⑩]).*$', '', item, flags=re.I).strip()
                        if not show_name:
                            show_name = folder_name
                    new_sub_name = f"{show_name} Season {season_num:02d}"
                else:
                    # OVA/SP/剧场版
                    sp_type = re.search(r'(特别篇|SP|OVA|OAD|剧场版)', item, re.I)
                    sp_label = sp_type.group(1) if sp_type else item
                    if not show_name:
                        show_name = folder_name
                    new_sub_name = f"{show_name} {sp_label}" if show_name not in item else item
                
                if new_sub_name != item:
                    results.append({
                        "old_name": item, "new_name": new_sub_name,
                        "old_path": sub_path, "new_path": os.path.join(folder_path, new_sub_name),
                        "is_folder": True, "is_subfolder": True, "shadow_name": new_sub_name,
                    })
                else:
                    results.append({
                        "old_name": item, "new_name": item,
                        "old_path": sub_path, "new_path": sub_path,
                        "is_folder": True, "is_subfolder": True, "unchanged": True,
                        "shadow_name": new_sub_name,
                    })
            
            # 递归处理子文件夹内的视频文件
            sub_results = rename_videos_in_folder(sub_path, tmdb_client, dry_run, library_data,
                                                    category_hint=category_hint)
            # 用父目录的剧名+英文名修正子文件夹视频的标准名
            if folder_scrape:
                parent_cn = folder_scrape.get("title", "")
                parent_en = folder_scrape.get("english_title", "") or folder_scrape.get("original_title", "")
                if parent_en and _is_mostly_latin(parent_en):
                    pass
                else:
                    parent_en = ""
                if parent_cn:
                    for sr in sub_results:
                        if sr.get("is_folder") or not sr.get("shadow_name"):
                            continue
                        shadow = sr["shadow_name"]
                        # 构建正确的标准名：剧名 + 英文名 + 集号
                        import re as _re_ep
                        ep_match = _re_ep.search(r'S\d+E\d+', shadow)
                        if ep_match:
                            new_shadow = parent_cn
                            if parent_en and parent_en != parent_cn:
                                new_shadow += " " + parent_en
                            new_shadow += " " + ep_match.group(0)
                            quality = _re_ep.search(r'(2160p|1080p|720p)$', shadow)
                            if quality:
                                new_shadow += " " + quality.group(0)
                            sr["shadow_name"] = new_shadow
                        elif not shadow.startswith(parent_cn):
                            # 没有集号格式，从原始文件名重新提取集号
                            from tmdb_client import parse_filename as _pf
                            old_name = sr.get("old_name", "")
                            _parsed = _pf(old_name)
                            new_shadow = parent_cn
                            if parent_en and parent_en != parent_cn:
                                new_shadow += " " + parent_en
                            if _parsed.get("episode") is not None:
                                s = _parsed.get("season") or 1
                                new_shadow += f" S{s:02d}E{_parsed['episode']:02d}"
                            sr["shadow_name"] = new_shadow
            for sr in sub_results:
                if not sr.get("is_folder"):
                    results.append(sr)
    except OSError:
        pass
    
    # 4. 执行文件夹重命名（最后执行，因为路径会变）
    # 先执行子文件夹重命名，再执行父文件夹重命名
    if not dry_run:
        for r in results:
            if r.get("is_subfolder") and not r.get("unchanged") and os.path.exists(r["old_path"]) and not os.path.exists(r["new_path"]):
                os.rename(r["old_path"], r["new_path"])
        for r in results:
            if r.get("is_folder") and not r.get("is_subfolder") and not r.get("unchanged") and os.path.exists(r["old_path"]) and not os.path.exists(r["new_path"]):
                os.rename(r["old_path"], r["new_path"])
    
    return results

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


# ── V3 影子名生成（严格读 NFO） ──

def generate_shadow_name_from_nfo(video_path: str, folder_path: str, folder_type: str) -> str:
    """V3：严格从 NFO 生成影子名。没有 NFO 则返回 None，不回退到文件名清洗。"""
    import scraper as _scraper

    if folder_type == "movie":
        nfo = _scraper.read_video_nfo(video_path) or _scraper.read_nfo(folder_path)
        if not nfo or not nfo.get("title"):
            return None
        title = nfo["title"]
        en = nfo.get("english_title") or ""
        orig = nfo.get("original_title") or ""
        if not en and orig and _is_mostly_latin(orig):
            en = orig
        year = nfo.get("year", "")
        shadow = title
        if en and en != title:
            shadow += f" {en}"
        if year:
            shadow += f" ({year})"
        return shadow

    elif folder_type in ("tv", "season"):
        nfo = _scraper.read_video_nfo(video_path)
        if not nfo:
            return None
        # 剧名优先从 showtitle 获取，其次从 tvshow.nfo
        show_title = nfo.get("showtitle") or ""
        show_en = ""
        if not show_title:
            tv_nfo = _scraper.read_nfo(folder_path, no_fallback=True)
            if tv_nfo:
                show_title = tv_nfo.get("title", "")
                show_en = tv_nfo.get("english_title") or ""
                show_orig = tv_nfo.get("original_title") or ""
                if not show_en and show_orig and _is_mostly_latin(show_orig):
                    show_en = show_orig
        if not show_title:
            show_title = nfo.get("title", "")

        season = nfo.get("season_number", 0)
        episode = nfo.get("episode_number", 0)
        if not show_title:
            return None

        shadow = show_title
        if show_en and show_en != show_title:
            shadow += f" {show_en}"
        if season and episode:
            shadow += f" S{season:02d}E{episode:02d}"
        return shadow

    elif folder_type in ("collection", "series", "mixed"):
        # 聚合容器内的子视频：各自独立，按 movie 逻辑
        return generate_shadow_name_from_nfo(video_path, os.path.dirname(video_path), "movie")

    return None


def generate_folder_shadow_name(folder_path: str, folder_type: str) -> str:
    """V3：文件夹级影子名。聚合容器返回 None。"""
    import scraper as _scraper

    if folder_type in ("tv", "movie"):
        nfo = _scraper.read_nfo(folder_path, no_fallback=(folder_type == "tv"))
        if not nfo or not nfo.get("title"):
            return None
        title = nfo["title"]
        en = nfo.get("english_title") or ""
        orig = nfo.get("original_title") or ""
        if not en and orig and _is_mostly_latin(orig):
            en = orig
        year = nfo.get("year", "")
        shadow = title
        if en and en != title:
            shadow += f" {en}"
        if year:
            shadow += f" ({year})"
        return shadow

    return None  # 聚合容器不生成文件夹级影子名


# ── 多季规整 ──

def reorganize_seasons(folder_path: str, tmdb_client=None, dry_run: bool = True, category_hint: str = "") -> Dict:
    """检测同作品不同季，建立标准文件夹结构
    目标结构: 作品名/Season XX/作品名 - S01E01.ext
    仅对能确定季号的目录做标准化，SP/OVA/剧场版等保持原名不动
    """
    info = classify_folder(folder_path, category_hint=category_hint)
    ops = []
    
    if info["type"] == "tv":
        # 如果自己已经是季文件夹就不动
        if _is_season_dir(os.path.basename(folder_path)):
            return {"status": "already_organized", "ops": []}
        
        # 检查是否已有季子目录
        try:
            existing_subdirs = [d for d in os.listdir(folder_path)
                               if os.path.isdir(os.path.join(folder_path, d))
                               and not d.startswith('.') and not _is_ignorable_subdir(d)]
        except OSError:
            existing_subdirs = []
        
        videos_in_root = info.get("videos", [])
        
        # 扁平 tv 目录（无子目录，有视频）→ 强制创建 Season 01 并移入
        if not existing_subdirs and videos_in_root:
            season_dir_name = "Season 01"
            season_dir = os.path.join(folder_path, season_dir_name)
            for f in videos_in_root:
                old_path = os.path.join(folder_path, f)
                new_path = os.path.join(season_dir, f)
                ops.append({"action": "move", "old": old_path, "new": new_path, "mkdir": season_dir})
        elif videos_in_root:
            # 有子目录也有散落视频 → 按季号归入对应季目录
            season_groups = {}
            for v in videos_in_root:
                parsed = parse_filename(v)
                s = parsed.get("season") or 1
                if s not in season_groups:
                    season_groups[s] = []
                season_groups[s].append(v)
            
            for season_num, files in sorted(season_groups.items()):
                # 找已有的季目录
                target_dir = None
                for sd in existing_subdirs:
                    sd_num = _get_season_number(sd)
                    if sd_num is not None and sd_num == season_num:
                        target_dir = os.path.join(folder_path, sd)
                        break
                if not target_dir:
                    season_dir_name = f"Season {season_num:02d}"
                    target_dir = os.path.join(folder_path, season_dir_name)
                
                for f in files:
                    old_path = os.path.join(folder_path, f)
                    new_path = os.path.join(target_dir, f)
                    ops.append({"action": "move", "old": old_path, "new": new_path, "mkdir": target_dir})
    
    elif info["type"] == "mixed":
        # 有季目录也有散落文件，把散落文件归入对应季
        loose = info.get("loose_videos", [])
        if loose:
            for v in loose:
                parsed = parse_filename(v)
                s = parsed.get("season") or 1
                # 找到对应的季目录
                target_dir = None
                for sd in info.get("seasons", []):
                    sd_num = _get_season_number(sd)
                    if sd_num is not None and sd_num == s:
                        target_dir = os.path.join(folder_path, sd)
                        break
                if not target_dir:
                    season_dir_name = f"Season {s:02d}"
                    target_dir = os.path.join(folder_path, season_dir_name)
                
                old_path = os.path.join(folder_path, v)
                new_path = os.path.join(target_dir, v)
                ops.append({"action": "move", "old": old_path, "new": new_path, "mkdir": target_dir})
    
    # 标准化已有的季目录名（仅对能确定季号的目录：如 "第1季" → "Season 01"）
    # SP/OVA/特别篇/剧场版等不强行重命名，它们的物理名由 NFO 元数据决定
    try:
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if not os.path.isdir(item_path) or item.startswith('.'):
                continue
            if _is_season_dir(item):
                sn = _get_season_number(item)
                if sn is not None:  # 只有能确定季号的才标准化
                    standard_name = f"Season {sn:02d}"
                    if item != standard_name:
                        new_path = os.path.join(folder_path, standard_name)
                        if not os.path.exists(new_path):
                            ops.append({"action": "rename_dir", "old": item_path, "new": new_path,
                                         "desc": f"季目录标准化: {item} → {standard_name}"})
    except OSError:
        pass
    
    if not dry_run:
        for op in ops:
            try:
                if op["action"] == "move":
                    if op.get("mkdir"):
                        os.makedirs(op["mkdir"], exist_ok=True)
                    if os.path.exists(op["old"]):
                        shutil.move(op["old"], op["new"])
                elif op["action"] == "rename_dir":
                    if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                        os.rename(op["old"], op["new"])
            except Exception as e:
                print(f"Reorganize error: {e}")
    
    return {"status": "ok", "ops": ops, "count": len(ops)}


def reorganize_seasons_by_nfo(folder_path: str, dry_run: bool = True) -> Dict:
    """V3：读取 episode.nfo 确定季号，按季号建目录并移入。
    核心规则：没有 NFO 的文件完全不动（Leave it alone）。
    """
    import scraper as _scraper

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    subtitle_exts = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}
    ops = []

    # 遍历文件夹下所有视频（含子目录）
    for root_dir, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() not in video_exts:
                continue
            video_path = os.path.join(root_dir, f)
            nfo = _scraper.read_video_nfo(video_path)
            if not nfo or not nfo.get("season_number"):
                continue  # 没有 NFO 或没有季号 → 不动

            season_num = nfo["season_number"]
            target_dir = os.path.join(folder_path, f"Season {season_num:02d}")

            # 如果视频已经在正确的季目录里，跳过
            current_dir = os.path.dirname(video_path)
            if os.path.normpath(current_dir) == os.path.normpath(target_dir):
                continue

            # 移动视频
            ops.append({
                "action": "move", "old": video_path,
                "new": os.path.join(target_dir, f),
                "mkdir": target_dir,
                "desc": f"{f} → Season {season_num:02d}/ (NFO season={season_num})",
            })
            # 移动关联文件（.nfo, poster, 字幕等）
            base = os.path.splitext(video_path)[0]
            assoc_suffixes = [".nfo", "-poster.jpg", "-poster.png", "-thumb.jpg",
                              "-fanart.jpg", "-clearlogo.png"]
            for suffix in assoc_suffixes:
                assoc = base + suffix
                if os.path.exists(assoc):
                    ops.append({
                        "action": "move", "old": assoc,
                        "new": os.path.join(target_dir, os.path.basename(assoc)),
                        "mkdir": target_dir,
                        "desc": f"{os.path.basename(assoc)} → Season {season_num:02d}/",
                    })
            # 字幕文件（可能有多种后缀组合如 .zh.srt, .eng.ass）
            for sf in os.listdir(root_dir):
                sf_path = os.path.join(root_dir, sf)
                if not os.path.isfile(sf_path):
                    continue
                sf_base = os.path.splitext(f)[0]
                if sf.startswith(sf_base) and sf != f and os.path.splitext(sf)[1].lower() in subtitle_exts:
                    ops.append({
                        "action": "move", "old": sf_path,
                        "new": os.path.join(target_dir, sf),
                        "mkdir": target_dir,
                        "desc": f"{sf} → Season {season_num:02d}/",
                    })

    # 标准化已有季目录名（第1季 → Season 01，SP/OVA 不动）
    try:
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if not os.path.isdir(item_path) or item.startswith('.'):
                continue
            if _is_season_dir(item):
                sn = _get_season_number(item)
                if sn is not None:
                    standard_name = f"Season {sn:02d}"
                    if item != standard_name:
                        new_path = os.path.join(folder_path, standard_name)
                        if not os.path.exists(new_path):
                            ops.append({
                                "action": "rename_dir", "old": item_path, "new": new_path,
                                "desc": f"季目录标准化: {item} → {standard_name}",
                            })
    except OSError:
        pass

    # 执行
    if not dry_run:
        for op in ops:
            try:
                if op["action"] == "move":
                    if op.get("mkdir"):
                        os.makedirs(op["mkdir"], exist_ok=True)
                    if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                        shutil.move(op["old"], op["new"])
                elif op["action"] == "rename_dir":
                    if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                        os.rename(op["old"], op["new"])
            except Exception as e:
                print(f"Reorganize by NFO error: {e}")

    return {"status": "ok", "ops": ops, "count": len(ops)}


# ── 散落视频封装 ──

def wrap_loose_videos_in_category(category_path: str, dry_run: bool = True,
                                  category_tag: str = "") -> Dict:
    """封装一级分类目录下的散落视频到独立文件夹
    核心规则：每个末端视频必须有自己的文件夹。
    一级分类目录（如 动画电影/、电影/）下直接散落的视频需要各自封装。
    category_tag="tv" 时跳过（tv 标签下的散落视频交给 reorganize_seasons_by_nfo 处理）。
    """
    # tv 标签下不封装散落视频
    if category_tag == "tv":
        return {"status": "ok", "ops": [], "count": 0}

    from analyzer import _clean_filename_for_folder

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    subtitle_exts = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}
    ops = []

    try:
        items = os.listdir(category_path)
    except OSError:
        return {"status": "error", "ops": [], "count": 0}

    loose_videos = [f for f in items
                    if os.path.isfile(os.path.join(category_path, f))
                    and os.path.splitext(f)[1].lower() in video_exts]

    if not loose_videos:
        return {"status": "ok", "ops": [], "count": 0}

    # CD 分片分组
    cd_groups = {}
    standalone = []
    for vf in loose_videos:
        from analyzer import _extract_cd_group_key
        gk = _extract_cd_group_key(vf)
        if gk:
            cd_groups.setdefault(gk, []).append(vf)
        else:
            standalone.append(vf)

    def _find_associated(video_filename):
        """找到视频关联的字幕/NFO等文件"""
        base = os.path.splitext(video_filename)[0]
        associated = []
        for f in items:
            if f == video_filename or not os.path.isfile(os.path.join(category_path, f)):
                continue
            f_ext = os.path.splitext(f)[1].lower()
            if f == base + ".nfo":
                associated.append(f)
            elif f.startswith(base) and f_ext in subtitle_exts:
                associated.append(f)
            elif f.startswith(base) and f_ext in {'.jpg', '.png'}:
                associated.append(f)
        return associated

    def _make_wrap_ops(video_files, target_name):
        for vf in video_files:
            target_name_clean = re.sub(r'[<>:"/\\|?*]', '', target_name).strip() or os.path.splitext(vf)[0]
            target_dir = os.path.join(category_path, target_name_clean)
            old = os.path.join(category_path, vf)
            new = os.path.join(target_dir, vf)
            ops.append({"action": "move", "old": old, "new": new, "mkdir": target_dir,
                         "desc": f"{vf} → {target_name_clean}/"})
            for af in _find_associated(vf):
                ops.append({"action": "move", "old": os.path.join(category_path, af),
                             "new": os.path.join(target_dir, af), "mkdir": target_dir,
                             "desc": f"{af} → {target_name_clean}/"})

    # CD 分片组
    for group_key, files in cd_groups.items():
        folder_target = _clean_filename_for_folder(files[0])
        _make_wrap_ops(files, folder_target)

    # 独立文件
    for vf in standalone:
        folder_target = _clean_filename_for_folder(vf)
        _make_wrap_ops([vf], folder_target)

    # 执行
    if not dry_run:
        for op in ops:
            if op["action"] == "move":
                if op.get("mkdir"):
                    os.makedirs(op["mkdir"], exist_ok=True)
                if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
                    shutil.move(op["old"], op["new"])

    return {"status": "ok", "ops": ops, "count": len(ops)}


# ── 归类整理 ──

def organize_folder(folder_path: str, tmdb_client=None, dry_run: bool = True,
                    library_data: List[Dict] = None, folder_type: str = None,
                    category_hint: str = "") -> Dict:
    """归类整理 — 消费分析层输出执行文件操作
    folder_type: 由流水线传入，不传则由 analyze_folder 内部判断
    category_hint: 一级分类标签，传给 analyze_folder
    流程：分析判断 → 文件移动（结构归位）→ 返回操作列表
    """
    import analyzer

    report = analyzer.analyze_folder(folder_path, library_data, tmdb_client, category_hint=category_hint)
    structure_ops = report.get("structure_ops", [])
    folder_type = report.get("folder_type", "")

    if not structure_ops:
        # 即使没有结构操作，也检查孤立刮削文件
        pass

    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    subtitle_exts = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}
    ops = []

    def _find_associated_files(folder, video_filename):
        """找到视频文件关联的 NFO/poster/字幕/clearlogo 文件"""
        base = os.path.splitext(video_filename)[0]
        associated = []
        try:
            all_files = os.listdir(folder)
        except OSError:
            return associated
        for f in all_files:
            fp = os.path.join(folder, f)
            if not os.path.isfile(fp) or f == video_filename:
                continue
            if f == base + ".nfo":
                associated.append(f)
            elif f.startswith(base + "-") and os.path.splitext(f)[1].lower() in {".jpg", ".png"}:
                associated.append(f)
            elif f.startswith(base) and f != video_filename and os.path.splitext(f)[1].lower() in subtitle_exts:
                associated.append(f)
        return associated

    for s_op in structure_ops:
        if not s_op.get("auto_fixable"):
            continue

        action = s_op.get("action")

        if action == "wrap_in_folder":
            vf = s_op["file"]
            target_name = s_op["target_folder"]
            # 清理非法字符
            target_name = re.sub(r'[<>:"/\\|?*]', '', target_name).strip()
            if not target_name:
                target_name = os.path.splitext(vf)[0]
            target_dir = os.path.join(folder_path, target_name)
            # 移动视频
            old = os.path.join(folder_path, vf)
            new = os.path.join(target_dir, vf)
            ops.append({"action": "move", "old": old, "new": new, "mkdir": target_dir,
                         "desc": f"{vf} → {target_name}/"})
            # 移动关联文件
            for af in _find_associated_files(folder_path, vf):
                old_af = os.path.join(folder_path, af)
                new_af = os.path.join(target_dir, af)
                ops.append({"action": "move", "old": old_af, "new": new_af, "mkdir": target_dir,
                             "desc": f"{af} → {target_name}/"})

        elif action == "move_to_subdir":
            vf = s_op["file"]
            target_name = s_op["target_folder"]
            target_dir = os.path.join(folder_path, target_name)
            old = os.path.join(folder_path, vf)
            new = os.path.join(target_dir, vf)
            ops.append({"action": "move", "old": old, "new": new, "mkdir": target_dir,
                         "desc": f"{vf} → {target_name}/"})

        elif action == "flatten_single_subdir":
            sub_name = s_op["subdir"]
            sub_path = os.path.join(folder_path, sub_name)
            try:
                sub_items = os.listdir(sub_path)
            except OSError:
                continue
            folder_name = os.path.basename(folder_path)
            for item in sub_items:
                old = os.path.join(sub_path, item)
                new = os.path.join(folder_path, item)
                if not os.path.exists(new):
                    ops.append({"action": "move", "old": old, "new": new,
                                 "desc": f"{sub_name}/{item} → 提升到 {folder_name}/"})
                else:
                    ops.append({"action": "skip", "desc": f"{item} 已存在，跳过"})
            if sub_items:
                ops.append({"action": "rmdir", "path": sub_path,
                             "desc": f"删除空目录 {sub_name}"})

        elif action == "split_seasons":
            vf = s_op["file"]
            season_num = s_op["season"]
            season_dir_name = f"Season {season_num:02d}"
            season_dir = os.path.join(folder_path, season_dir_name)
            old = os.path.join(folder_path, vf)
            new = os.path.join(season_dir, vf)
            ops.append({"action": "move", "old": old, "new": new, "mkdir": season_dir,
                         "desc": f"{vf} → {season_dir_name}/"})

    # 执行主结构操作
    if not dry_run:
        for op in ops:
            try:
                if op["action"] == "move":
                    if op.get("mkdir"):
                        os.makedirs(op["mkdir"], exist_ok=True)
                    target_d = os.path.dirname(op["new"])
                    os.makedirs(target_d, exist_ok=True)
                    if os.path.exists(op["old"]):
                        shutil.move(op["old"], op["new"])
                elif op["action"] == "rmdir":
                    if os.path.isdir(op["path"]) and not os.listdir(op["path"]):
                        os.rmdir(op["path"])
            except Exception as e:
                print(f"Organize error: {e}")

    # ── 孤立刮削文件归位 ──
    # 主结构操作完成后，扫描父文件夹中残留的 NFO/poster/fanart/clearlogo
    # 模糊匹配到最合适的子文件夹并移入
    poster_suffixes = ["-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]

    def _is_scrape_file(filename):
        if filename.endswith(".nfo") and filename not in ("movie.nfo", "tvshow.nfo", "season.nfo"):
            return True
        for suf in poster_suffixes:
            if filename.endswith(suf):
                return True
        return False

    def _scrape_base(filename):
        """提取刮削文件的 base name"""
        for suf in poster_suffixes:
            if filename.endswith(suf):
                return filename[:-len(suf)]
        if filename.endswith(".nfo"):
            return filename[:-4]
        return os.path.splitext(filename)[0]

    def _normalize_for_match(name):
        """归一化名字用于模糊匹配"""
        n = re.sub(r'[_.\-\[\]()（）【】]', ' ', name)
        n = re.sub(r'\s+', ' ', n).strip().lower()
        return n

    def _compact(name):
        """去掉所有空格的紧凑形式，用于宽松匹配"""
        return re.sub(r'\s+', '', _normalize_for_match(name))

    try:
        remaining_files = [f for f in os.listdir(folder_path)
                          if os.path.isfile(os.path.join(folder_path, f)) and _is_scrape_file(f)]
    except OSError:
        remaining_files = []

    if remaining_files:
        try:
            subdirs = {d: _normalize_for_match(d)
                      for d in os.listdir(folder_path)
                      if os.path.isdir(os.path.join(folder_path, d)) and not d.startswith('.')}
        except OSError:
            subdirs = {}

        orphan_groups = {}
        for f in remaining_files:
            base = _scrape_base(f)
            orphan_groups.setdefault(base, []).append(f)

        for base, files in orphan_groups.items():
            base_norm = _normalize_for_match(base)
            base_compact = _compact(base)
            best_dir = None
            best_score = 0

            for dir_name, dir_norm in subdirs.items():
                dir_compact = _compact(dir_name)
                # 标准匹配：归一化后子串
                if base_norm in dir_norm or dir_norm in base_norm:
                    score = min(len(base_norm), len(dir_norm))
                    if score > best_score:
                        best_score = score
                        best_dir = dir_name
                # 紧凑匹配：去空格后子串
                elif base_compact in dir_compact or dir_compact in base_compact:
                    score = min(len(base_compact), len(dir_compact))
                    if score > best_score:
                        best_score = score
                        best_dir = dir_name
                else:
                    # 清洗后匹配（如 "阿甘正传cd1" → "阿甘正传"）
                    from analyzer import _clean_filename_for_folder
                    clean_base = _normalize_for_match(_clean_filename_for_folder(base + ".tmp"))
                    if clean_base and (clean_base in dir_norm or dir_norm in clean_base):
                        score = min(len(clean_base), len(dir_norm))
                        if score > best_score:
                            best_score = score
                            best_dir = dir_name

            if best_dir and best_score >= 2:
                target_dir = os.path.join(folder_path, best_dir)
                for f in files:
                    old_f = os.path.join(folder_path, f)
                    new_f = os.path.join(target_dir, f)
                    ops.append({"action": "move", "old": old_f, "new": new_f,
                                 "desc": f"孤立刮削 {f} → {best_dir}/"})
                    if not dry_run and os.path.exists(old_f) and not os.path.exists(new_f):
                        try:
                            shutil.move(old_f, new_f)
                        except Exception as e:
                            print(f"Orphan move error: {e}")

    # 自动创建快照
    if not dry_run and ops:
        from organize_history import history_m
        snapshot_ops = []
        for op in ops:
            if op.get("action") == "move" and op.get("old") and op.get("new"):
                is_dir = os.path.isdir(op["new"]) if os.path.exists(op["new"]) else False
                snapshot_ops.append({"old_path": op["old"], "new_path": op["new"], "is_dir": is_dir})
        if snapshot_ops:
            history_m.create_snapshot(snapshot_ops, label="organize")

    return {"status": "ok", "ops": ops, "count": len(ops), "report": report}


# ── 散落季合并 ──

def merge_scattered_seasons(scattered_issue: Dict, dry_run: bool = True) -> Dict:
    """合并散落的季目录到同一父目录
    
    输入: analyzer 产出的 scattered_seasons issue
    dry_run=True 时返回预览操作列表，不修改文件系统
    dry_run=False 时执行合并并创建快照
    """
    folders = scattered_issue.get("folders", [])
    core_name = scattered_issue.get("core_name", "")
    
    if len(folders) < 2 or not core_name:
        return {"status": "skip", "ops": [], "reason": "不足 2 个文件夹或缺少核心名"}
    
    # 确定父目录：所有散落目录的共同父目录
    parent_dir = os.path.dirname(folders[0]["path"])
    # 清理非法字符
    safe_name = re.sub(r'[<>:"/\\|?*]', '', core_name).strip()
    if not safe_name:
        safe_name = core_name
    target_dir = os.path.join(parent_dir, safe_name)
    
    ops = []
    
    # 检查是否有某个散落目录本身就是目标目录
    existing_target = None
    for f in folders:
        if os.path.basename(f["path"]) == safe_name:
            existing_target = f["path"]
            break
    
    if existing_target:
        target_dir = existing_target
    else:
        ops.append({"action": "mkdir", "path": target_dir, "desc": f"创建父目录 {safe_name}/"})
    
    # 移动每个散落目录到目标目录下
    for f in folders:
        if f["path"] == target_dir:
            continue
        season_name = os.path.basename(f["path"])
        new_path = os.path.join(target_dir, season_name)
        if os.path.exists(new_path):
            ops.append({"action": "skip", "old": f["path"], "new": new_path,
                         "desc": f"跳过 {season_name}（目标已存在同名目录）"})
        else:
            ops.append({"action": "move_dir", "old": f["path"], "new": new_path,
                         "desc": f"{season_name} → {safe_name}/{season_name}"})
    
    if not dry_run:
        os.makedirs(target_dir, exist_ok=True)
        snapshot_ops = []
        for op in ops:
            if op.get("action") == "move_dir" and os.path.exists(op["old"]):
                try:
                    shutil.move(op["old"], op["new"])
                    snapshot_ops.append({"old_path": op["old"], "new_path": op["new"], "is_dir": True})
                except Exception as e:
                    print(f"Merge seasons error: {e}")
        
        # 创建快照
        if snapshot_ops:
            from organize_history import history_m
            history_m.create_snapshot(snapshot_ops, label="merge_seasons")
    
    return {"status": "ok", "ops": ops, "target_dir": target_dir, "count": len([o for o in ops if o.get("action") == "move_dir"])}


# ── 旧刮削智能清理（V3 流水线 Step 1） ──

def smart_archive_plan(path: str) -> list:
    """推演模式：扫描旧刮削，返回清理 plan（不执行）"""
    import xml.etree.ElementTree as ET
    plan = []
    scrape_names = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                    'clearlogo.png', 'folder.jpg', 'movie.nfo', 'tvshow.nfo',
                    'season.nfo', 'theme.mp3'}
    poster_suffixes = ['-poster.jpg', '-poster.png', '-fanart.jpg', '-fanart.png',
                       '-clearlogo.png', '-thumb.jpg']

    def _scan_dir(dir_path):
        try:
            items = os.listdir(dir_path)
        except OSError:
            return
        nfo_valid = False
        for nfo_name in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            nfo_path = os.path.join(dir_path, nfo_name)
            if os.path.exists(nfo_path):
                try:
                    tree = ET.parse(nfo_path)
                    title = tree.getroot().findtext("title", "").strip()
                    if title:
                        nfo_valid = True
                except Exception:
                    pass
                break

        if nfo_valid:
            return

        files_to_archive = []
        for f in items:
            fp = os.path.join(dir_path, f)
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(f)[1].lower()
            if f in scrape_names or ext == '.nfo' or \
               (ext in {'.jpg', '.png'} and any(f.endswith(s) for s in poster_suffixes)):
                files_to_archive.append(f)

        if files_to_archive:
            plan.append({
                "dir": dir_path,
                "files": files_to_archive,
                "action": "archive_and_delete",
                "desc": f"清理 {len(files_to_archive)} 个无效刮削文件",
            })

        for item in items:
            sub = os.path.join(dir_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                _scan_dir(sub)

    _scan_dir(path)
    return plan


def smart_archive_recursive(path: str) -> int:
    """执行模式：递归清理无效旧刮削，保留有效 NFO"""
    import zipfile
    import xml.etree.ElementTree as ET
    total_archived = 0
    scrape_names = {'poster.jpg', 'poster.png', 'fanart.jpg', 'fanart.png',
                    'clearlogo.png', 'folder.jpg', 'cover.jpg', 'movie.nfo',
                    'tvshow.nfo', 'season.nfo', 'theme.mp3'}
    poster_suffixes = ['-poster.jpg', '-poster.png', '-fanart.jpg', '-fanart.png',
                       '-clearlogo.png', '-thumb.jpg']

    def _process_dir(dir_path):
        nonlocal total_archived
        try:
            items = os.listdir(dir_path)
        except OSError:
            return

        nfo_valid = False
        for nfo_name in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            nfo_path = os.path.join(dir_path, nfo_name)
            if os.path.exists(nfo_path):
                try:
                    tree = ET.parse(nfo_path)
                    title = tree.getroot().findtext("title", "").strip()
                    if title:
                        nfo_valid = True
                except Exception:
                    pass
                break

        if not nfo_valid:
            files = []
            for f in items:
                fp = os.path.join(dir_path, f)
                if not os.path.isfile(fp):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if f in scrape_names or ext == '.nfo' or \
                   (ext in {'.jpg', '.png'} and any(f.endswith(s) for s in poster_suffixes)):
                    files.append(f)

            if files:
                zp = os.path.join(dir_path, '.old_scrape.zip')
                if not os.path.exists(zp):
                    try:
                        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for f in files:
                                zf.write(os.path.join(dir_path, f), f)
                        for f in files:
                            try:
                                os.remove(os.path.join(dir_path, f))
                            except OSError:
                                pass
                        total_archived += len(files)
                    except Exception:
                        pass

        for item in items:
            sub = os.path.join(dir_path, item)
            if os.path.isdir(sub) and not item.startswith('.'):
                _process_dir(sub)

    _process_dir(path)
    return total_archived


def execute_archive_plan(archive_plan: list):
    """执行旧刮削清理 plan"""
    import zipfile
    for item in archive_plan:
        dir_path = item.get("dir", "")
        files = item.get("files", [])
        if not dir_path or not files:
            continue
        zp = os.path.join(dir_path, '.old_scrape.zip')
        if os.path.exists(zp):
            continue
        try:
            with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    fp = os.path.join(dir_path, f)
                    if os.path.exists(fp):
                        zf.write(fp, f)
            for f in files:
                try:
                    os.remove(os.path.join(dir_path, f))
                except OSError:
                    pass
        except Exception:
            pass
