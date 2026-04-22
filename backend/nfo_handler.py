"""
NFO 读写模块：兼容 Kodi/Jellyfin/Emby 的 NFO 格式
从 scraper.py 拆分而来，负责所有 NFO 文件的读取和写入。
"""
import os
import logging
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional, Dict
from tmdb_client import ScrapeResult

logger = logging.getLogger(__name__)
# ── NFO 读取 ──

def read_nfo(folder_path: str, no_fallback: bool = False) -> Optional[Dict]:
    """读取文件夹下的 NFO 文件，返回解析后的 dict
    查找顺序：
    1. 文件夹级保留字 NFO：movie.nfo / tvshow.nfo / season.nfo / seasonXX.nfo
    2. 如果 no_fallback=False，fallback 到第一个视频的同名 NFO（仅 movie 文件夹）
    """
    nfo_path = None
    
    # 1. 标准文件夹级 NFO
    for name in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
        p = os.path.join(folder_path, name)
        if os.path.exists(p):
            nfo_path = p
            break
    
    # 2. 季编号 NFO（season01.nfo, season02.nfo ...）
    if not nfo_path:
        try:
            for f in os.listdir(folder_path):
                if re.match(r'^season\d+\.nfo$', f, re.I):
                    nfo_path = os.path.join(folder_path, f)
                    break
        except OSError:
            pass
    
    # 3. Fallback 到视频同名 NFO（仅 movie 文件夹，tv/season 不 fallback）
    if not nfo_path and not no_fallback:
        try:
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            video_files = [f for f in sorted(os.listdir(folder_path)) if os.path.splitext(f)[1].lower() in video_exts]
            folder_name = os.path.basename(folder_path)
            if video_files and not _is_category_folder(folder_name, video_files):
                for vf in video_files:
                    candidate = os.path.splitext(os.path.join(folder_path, vf))[0] + ".nfo"
                    if os.path.exists(candidate):
                        nfo_path = candidate
                        break
        except OSError:
            pass
    
    if not nfo_path:
        return None
    
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        data = {
            "tmdb_id": 0,
            "media_type": root.tag,  # "movie" or "tvshow"
            "title": _text(root, "title"),
            "original_title": _text(root, "originaltitle"),
            "english_title": _text(root, "englishtitle"),
            "year": _text(root, "year"),
            "overview": _text(root, "plot"),
            "rating": float(_text(root, "rating") or 0),
            "genres": [g.text for g in root.findall("genre") if g.text],
            "director": _text(root, "director"),
            "cast": [a.findtext("name", "") for a in root.findall("actor") if a.findtext("name")],
            "runtime": int(_text(root, "runtime") or 0),
            "status": _text(root, "status"),
            "poster_url": None,
            "backdrop_url": None,
        }
        
        # TMDB ID
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tmdb":
                data["tmdb_id"] = int(uid.text or 0)
        
        # 检查本地海报
        poster_names = ["poster.jpg", "poster.png", "folder.jpg"]
        for pn in poster_names:
            pp = os.path.join(folder_path, pn)
            if os.path.exists(pp):
                data["local_poster"] = pp
                break
        
        return data
    except Exception as e:
        logger.error(f"NFO parse error: {e}")
        return None


def read_video_nfo(video_path: str) -> Optional[Dict]:
    """读取单个视频文件对应的 NFO（同名风格优先）"""
    base = os.path.splitext(video_path)[0]
    nfo_path = base + ".nfo"
    if not os.path.exists(nfo_path):
        # 尝试读取所在文件夹的 NFO（仅当文件夹有标准 movie.nfo/tvshow.nfo 时）
        folder = os.path.dirname(video_path)
        for standard_name in ["movie.nfo", "tvshow.nfo"]:
            p = os.path.join(folder, standard_name)
            if os.path.exists(p):
                return read_nfo(folder)
        return None
    
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        data = {
            "tmdb_id": 0,
            "media_type": root.tag,
            "title": _text(root, "title"),
            "showtitle": _text(root, "showtitle"),
            "original_title": _text(root, "originaltitle"),
            "english_title": _text(root, "englishtitle"),
            "year": _text(root, "year"),
            "overview": _text(root, "plot"),
            "rating": float(_text(root, "rating") or 0),
            "genres": [g.text for g in root.findall("genre") if g.text],
            "season_number": int(_text(root, "season") or 0),
            "episode_number": int(_text(root, "episode") or 0),
            "episode_title": _text(root, "title"),
            "director": _text(root, "director"),
            "cast": [a.findtext("name", "") for a in root.findall("actor") if a.findtext("name")],
            "runtime": int(_text(root, "runtime") or 0),
        }
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tmdb":
                data["tmdb_id"] = int(uid.text or 0)
        return data
    except:
        return None


def _text(root, tag) -> str:
    """XML 文本提取辅助"""
    el = root.find(tag)
    return el.text.strip() if el is not None and el.text else ""


# ── NFO 写入 ──

def write_movie_nfo(folder_path: str, scrape: ScrapeResult):
    """写入电影 NFO（文件夹级别：movie.nfo）"""
    root = ET.Element("movie")
    _add(root, "title", scrape.title)
    _add(root, "originaltitle", scrape.original_title)
    if scrape.english_title:
        _add(root, "englishtitle", scrape.english_title)
    _add(root, "year", scrape.year)
    _add(root, "plot", scrape.overview)
    _add(root, "rating", str(scrape.rating))
    _add(root, "runtime", str(scrape.runtime))
    for g in scrape.genres:
        _add(root, "genre", g)
    if scrape.director:
        _add(root, "director", scrape.director)
    for name in scrape.cast:
        actor = ET.SubElement(root, "actor")
        _add(actor, "name", name)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(scrape.tmdb_id)
    if scrape.imdb_id:
        uid2 = ET.SubElement(root, "uniqueid", type="imdb")
        uid2.text = scrape.imdb_id
    
    _write_xml(os.path.join(folder_path, "movie.nfo"), root)


def write_movie_nfo_for_video(video_path: str, scrape: ScrapeResult):
    """写入电影 NFO（同名风格：{filename}.nfo，兼容 Kodi/Emby/tinyMediaManager）"""
    root = ET.Element("movie")
    _add(root, "title", scrape.title)
    _add(root, "originaltitle", scrape.original_title)
    if scrape.english_title:
        _add(root, "englishtitle", scrape.english_title)
    _add(root, "year", scrape.year)
    _add(root, "plot", scrape.overview)
    _add(root, "rating", str(scrape.rating))
    _add(root, "runtime", str(scrape.runtime))
    for g in scrape.genres:
        _add(root, "genre", g)
    if scrape.director:
        _add(root, "director", scrape.director)
    for name in scrape.cast:
        actor = ET.SubElement(root, "actor")
        _add(actor, "name", name)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(scrape.tmdb_id)
    if scrape.imdb_id:
        uid2 = ET.SubElement(root, "uniqueid", type="imdb")
        uid2.text = scrape.imdb_id
    
    nfo_path = os.path.splitext(video_path)[0] + ".nfo"
    _write_xml(nfo_path, root)


def write_tvshow_nfo(folder_path: str, scrape: ScrapeResult):
    """写入剧集 NFO（tvshow 级别，写到母文件夹）"""
    root = ET.Element("tvshow")
    _add(root, "title", scrape.title)
    _add(root, "originaltitle", scrape.original_title)
    if scrape.english_title:
        _add(root, "englishtitle", scrape.english_title)
    _add(root, "year", scrape.year)
    _add(root, "plot", scrape.overview)
    _add(root, "rating", str(scrape.rating))
    _add(root, "status", scrape.status)
    for g in scrape.genres:
        _add(root, "genre", g)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(scrape.tmdb_id)
    _write_xml(os.path.join(folder_path, "tvshow.nfo"), root)


def write_season_nfo(folder_path: str, scrape: ScrapeResult):
    """写入季 NFO（season 级别，写到季文件夹）"""
    root = ET.Element("season")
    _add(root, "seasonnumber", str(scrape.season_number))
    _add(root, "title", scrape.title)
    _add(root, "plot", scrape.overview)
    _add(root, "aired", scrape.air_date)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(scrape.tmdb_id)
    _write_xml(os.path.join(folder_path, "season.nfo"), root)


def write_episode_nfo(video_path: str, scrape: ScrapeResult, showtitle: str = ""):
    """写入单集 NFO（和视频同名 .nfo）"""
    root = ET.Element("episodedetails")
    if showtitle:
        _add(root, "showtitle", showtitle)
    _add(root, "title", scrape.episode_title or scrape.title)
    _add(root, "season", str(scrape.season_number))
    _add(root, "episode", str(scrape.episode_number))
    _add(root, "plot", scrape.overview)
    _add(root, "rating", str(scrape.rating))
    _add(root, "aired", scrape.air_date)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(scrape.tmdb_id)
    
    nfo_path = os.path.splitext(video_path)[0] + ".nfo"
    _write_xml(nfo_path, root)


def _add(parent, tag, text):
    """XML 元素添加辅助"""
    if text:
        el = ET.SubElement(parent, tag)
        el.text = str(text)


def _write_xml(path, root):
    """格式化写入 XML 文件"""
    rough = ET.tostring(root, encoding="unicode")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")
    with open(path, "wb") as f:
        f.write(pretty)


# ── 内部辅助（read_nfo fallback 需要） ──

def _is_category_folder(folder_name: str, video_files: list) -> bool:
    """智能判断文件夹是分类聚合还是系列作品（从 scraper.py 迁移，read_nfo fallback 依赖）"""
    if len(video_files) <= 1:
        return False

    # 1. 文件夹名是通用分类词 → 分类
    category_keywords = {'电影', '动画', '剧场版', '合集', '短片', '纪录片', '综艺',
                         '欧美', '日韩', '国产', '经典', '其他', '视频', '小视频',
                         'movie', 'movies', 'film', 'films', 'video', 'videos',
                         '欧美电影', '韩国电影', '香港电影', '其他地区', '动画电影',
                         '动画短片合集', '经典电影'}
    fn_clean = re.sub(r'[^\u4e00-\u9fff\w]', '', folder_name.lower()).strip()
    if fn_clean in category_keywords:
        return True

    # 2. 文件名有集号特征 → 剧集，不是分类
    ep_pattern = re.compile(r'(?:E\d{1,3}|EP\d{1,3}|第\d{1,3}[集话]|S\d+E\d+|\b\d{2,3}\b(?=\.\w{2,4}$))', re.I)
    ep_count = sum(1 for f in video_files if ep_pattern.search(f))
    if ep_count >= len(video_files) * 0.4:
        return False  # 40% 以上有集号 → 剧集

    # 3. 文件名是纯数字或短编号（如 01.rmvb, 02.rmvb）→ 剧集
    short_num_pattern = re.compile(r'^\d{1,3}\.\w{2,4}$')
    short_count = sum(1 for f in video_files if short_num_pattern.match(f))
    if short_count >= len(video_files) * 0.5:
        return False  # 纯数字文件名 → 剧集

    # 4. 文件名共同前缀分析
    def extract_core(filename):
        name = os.path.splitext(filename)[0]
        name = re.sub(r'[\[\(【（].*?[\]\)】）]', ' ', name)
        name = re.sub(r'(?i)(2160p|1080p|720p|480p|BluRay|WEB-?DL|HDTV|BDRip|x264|x265|HEVC|AAC|DTS|FLAC|Remux)', '', name)
        name = re.sub(r'(中英双字|中文字幕|中字|日语|国语|粤语|BD|HD)', '', name)
        name = re.sub(r'\b\w+\.(com|co|net|org|cc|tv)\b', '', name, flags=re.I)
        name = re.sub(r'[._\-]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        chinese = re.findall(r'[\u4e00-\u9fff]+', name)
        english = re.findall(r'[a-zA-Z]{2,}', name)
        return (chinese[0][:4] if chinese else "") + " " + (english[0].lower() if english else "")

    cores = [extract_core(f) for f in video_files]

    if len(cores) >= 2:
        first_core = cores[0].strip()
        if first_core and len(first_core) >= 2:
            match_count = sum(1 for c in cores[1:] if first_core[:3] in c or c.strip()[:3] in first_core)
            similarity = match_count / (len(cores) - 1)
            if similarity >= 0.4:
                return False  # 有共同前缀 → 系列

    # 5. 文件夹名和文件名的关联度
    folder_core = re.sub(r'[^\u4e00-\u9fff\w\s]', '', folder_name).strip()
    if folder_core and len(folder_core) >= 2:
        folder_match = sum(1 for c in cores if folder_core[:3].lower() in c.lower())
        if folder_match >= len(cores) * 0.2:
            return False  # 文件夹名和文件名有关联 → 系列

    # 6. 文件名差异大且数量 >5 → 分类
    if len(video_files) > 5:
        unique_cores = set(c.strip()[:4] for c in cores if c.strip())
        if len(unique_cores) > len(cores) * 0.7:
            return True

    return False
