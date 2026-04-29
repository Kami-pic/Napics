# 季集完整性检测：从 TMDB 获取完整季/集结构，与本地文件做差集
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from nfo_handler import read_nfo, read_video_nfo

logger = logging.getLogger(__name__)

# 视频扩展名
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".rmvb", ".rm", ".flv", ".ts",
              ".m4v", ".mov", ".wmv", ".mpg", ".mpeg", ".webm", ".iso"}

# 从文件名提取季集号的正则
_EP_PATTERNS = [
    re.compile(r'[Ss](\d+)[Ee](\d+)'),                    # S01E02
    re.compile(r'[Ss](\d+)\s*-\s*[Ee]?(\d+)'),            # S01-02, S01-E02
    re.compile(r'[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)', re.I),  # Season 1 Episode 2
    re.compile(r'第(\d+)季.*?第(\d+)[集话話]'),              # 第1季第2集
    re.compile(r'第(\d+)季.*?[Ee](\d+)'),                  # 第1季E02
    re.compile(r'第(\d+)季.*?(\d{2,3})[集话話]'),           # 第2季02集
]
# 只有集号（季号从父目录推断）
_EP_ONLY_PATTERNS = [
    re.compile(r'[Ee][Pp]?(\d+)'),                         # E02, EP02
    re.compile(r'第(\d+)[集话話]'),                          # 第2集
    re.compile(r'(\d{2,3})[集话話]'),                        # 02集, 03话
    re.compile(r'[-]\s*(\d{2,3})(?:[\s\.\[]|$)'),          # Unnatural-02, Name-03.mp4
    re.compile(r'[\u4e00-\u9fff](\d{2,3})(?:[\s\.\[\]]|$)'),  # 高清02.rmvb, 第七季01.mp4
    re.compile(r'(?:^|[\s\[\(])(\d{2,3})(?:[\s\]\)v\.]|$)'), # 独立的 02, 03（2-3位数字）
]
# 从目录名提取季号
_SEASON_DIR_PATTERNS = [
    re.compile(r'[Ss]eason\s*(\d+)', re.I),
    re.compile(r'[Ss](\d+)(?:\s|$)'),
    re.compile(r'第(\d+)季'),
]

# 中文数字映射
_CN_NUM = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_CN_SEASON_PAT = re.compile(r'第([零一二三四五六七八九十]+)季')
_CN_EP_PAT = re.compile(r'第([零一二三四五六七八九十]+)[集话話]')


def _cn_num_to_int(cn_str: str) -> Optional[int]:
    """中文数字转阿拉伯数字（支持 一~九十九）"""
    if len(cn_str) == 1:
        return _CN_NUM.get(cn_str)
    if cn_str == "十":
        return 10
    if cn_str.startswith("十"):
        return 10 + (_CN_NUM.get(cn_str[1], 0))
    if cn_str.endswith("十"):
        return (_CN_NUM.get(cn_str[0], 0)) * 10
    if "十" in cn_str:
        parts = cn_str.split("十")
        return (_CN_NUM.get(parts[0], 0)) * 10 + (_CN_NUM.get(parts[1], 0))
    return None


def _extract_season_episode_from_filename(filename: str) -> Optional[Tuple[int, int]]:
    """从文件名提取 (season, episode)，返回 None 表示无法提取"""
    for pat in _EP_PATTERNS:
        m = pat.search(filename)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _extract_episode_only(filename: str) -> Optional[int]:
    """从文件名只提取集号（支持中文数字）"""
    for pat in _EP_ONLY_PATTERNS:
        m = pat.search(filename)
        if m:
            return int(m.group(1))
    # 中文数字集号
    m = _CN_EP_PAT.search(filename)
    if m:
        return _cn_num_to_int(m.group(1))
    return None


def _extract_season_from_dir(dirname: str) -> Optional[int]:
    """从目录名提取季号（支持阿拉伯数字和中文数字）"""
    for pat in _SEASON_DIR_PATTERNS:
        m = pat.search(dirname)
        if m:
            return int(m.group(1))
    # 中文数字季号
    m = _CN_SEASON_PAT.search(dirname)
    if m:
        return _cn_num_to_int(m.group(1))
    return None


def collect_local_episodes(folder_path: str) -> Dict[int, List[int]]:
    """统计本地文件夹下的季/集号。
    返回 {season_number: [episode_numbers]} 的字典。
    优先从 NFO 读取，回退到文件名正则提取。
    """
    result: Dict[int, set] = {}

    if not os.path.isdir(folder_path):
        logger.debug(f"[completeness] 路径不可达: {folder_path}")
        return {}

    # 先尝试从目录名推断当前目录的季号（如果是 season 目录）
    dir_season = _extract_season_from_dir(os.path.basename(folder_path))

    # 遍历当前目录下的视频文件
    try:
        entries = os.listdir(folder_path)
    except OSError:
        return {}

    for entry in entries:
        full_path = os.path.join(folder_path, entry)

        if os.path.isdir(full_path):
            # 递归子目录
            sub_result = collect_local_episodes(full_path)
            for s, eps in sub_result.items():
                result.setdefault(s, set()).update(eps)
            continue

        ext = os.path.splitext(entry)[1].lower()
        if ext not in VIDEO_EXTS:
            continue

        season_num = None
        episode_num = None

        # 优先从 NFO 读取
        nfo_data = read_video_nfo(full_path)
        if nfo_data and nfo_data.get("episode_number"):
            season_num = nfo_data.get("season_number", 0)
            episode_num = nfo_data["episode_number"]
        else:
            # 回退到文件名提取
            se = _extract_season_episode_from_filename(entry)
            if se:
                season_num, episode_num = se
            else:
                ep = _extract_episode_only(entry)
                if ep is not None:
                    # 季号从目录名推断
                    season_num = dir_season if dir_season is not None else 1
                    episode_num = ep

        if season_num is not None and episode_num is not None:
            result.setdefault(season_num, set()).add(episode_num)

    # 转为排序列表
    return {s: sorted(eps) for s, eps in result.items()}


def get_tmdb_id_from_folder(folder_path: str) -> Optional[int]:
    """从文件夹的 NFO 中获取 TMDB ID"""
    nfo = read_nfo(folder_path, no_fallback=True)
    if nfo and nfo.get("tmdb_id"):
        return nfo["tmdb_id"]
    # 尝试父目录（season 目录的 tvshow.nfo 在父级）
    parent = os.path.dirname(folder_path)
    if parent and parent != folder_path:
        nfo = read_nfo(parent, no_fallback=True)
        if nfo and nfo.get("tmdb_id"):
            return nfo["tmdb_id"]
    return None


def compute_completeness(tmdb_client, tmdb_id: int, local_episodes: Dict[int, List[int]],
                         include_specials: bool = False) -> Dict:
    """计算季集完整度。
    
    Args:
        tmdb_client: TMDBClient 实例
        tmdb_id: TMDB 剧集 ID
        local_episodes: {season_number: [episode_numbers]}
        include_specials: 是否包含特别篇（Season 0）
    
    Returns:
        {
            "tmdb_id": int,
            "title": str,
            "total_seasons": int,
            "seasons": [
                {
                    "season_number": int,
                    "episode_count": int,       # TMDB 总集数
                    "local_count": int,          # 本地已有集数
                    "missing_episodes": [        # 缺失的集
                        {"episode": int, "title": str, "air_date": str, "aired": bool}
                    ],
                    "status": "complete" | "partial" | "missing"
                }
            ],
            "total_episodes": int,
            "local_total": int,
            "completeness_pct": float,
            "status": "ok"
        }
    """
    # 获取剧集基本信息
    tv_detail = tmdb_client.get_tv_detail(tmdb_id)
    if not tv_detail or not tv_detail.tmdb_id:
        return {"status": "tmdb_error", "message": "无法获取 TMDB 剧集信息"}

    today = datetime.now().strftime("%Y-%m-%d")
    seasons_result = []
    total_episodes = 0
    local_total = 0

    for season_info in tv_detail.seasons_info:
        s_num = season_info["season_number"]
        
        # 跳过特别篇（除非明确要求）
        if s_num == 0 and not include_specials:
            continue

        ep_count = season_info["episode_count"]
        total_episodes += ep_count
        local_eps = set(local_episodes.get(s_num, []))
        local_count = len(local_eps)
        local_total += local_count

        # 获取该季详细集列表（用于知道缺哪些集）
        missing_episodes = []
        if local_count < ep_count:
            season_detail = tmdb_client.get_season_detail(tmdb_id, s_num)
            # get_season_detail 返回的是 ScrapeResult，没有 episodes 列表
            # 需要直接调用 TMDB API 获取集列表
            try:
                season_raw = tmdb_client._get(f"/tv/{tmdb_id}/season/{s_num}")
                episodes = season_raw.get("episodes", [])
                for ep in episodes:
                    ep_num = ep.get("episode_number", 0)
                    if ep_num not in local_eps:
                        air_date = ep.get("air_date", "")
                        aired = bool(air_date and air_date <= today)
                        missing_episodes.append({
                            "episode": ep_num,
                            "title": ep.get("name", ""),
                            "air_date": air_date,
                            "aired": aired,
                        })
            except Exception as e:
                logger.warning(f"[completeness] 获取 S{s_num} 集列表失败: {e}")
                # 降级：只知道缺多少集，不知道具体缺哪些
                for ep_num in range(1, ep_count + 1):
                    if ep_num not in local_eps:
                        missing_episodes.append({
                            "episode": ep_num,
                            "title": "",
                            "air_date": "",
                            "aired": True,  # 保守假设已播出
                        })

        # 状态判定
        if local_count >= ep_count:
            status = "complete"
        elif local_count == 0:
            status = "missing"
        else:
            status = "partial"

        seasons_result.append({
            "season_number": s_num,
            "episode_count": ep_count,
            "local_count": local_count,
            "missing_episodes": missing_episodes,
            "status": status,
        })

    completeness_pct = round(local_total / total_episodes * 100, 1) if total_episodes > 0 else 0

    return {
        "tmdb_id": tmdb_id,
        "title": tv_detail.title,
        "english_title": tv_detail.english_title,
        "total_seasons": len(seasons_result),
        "seasons": seasons_result,
        "total_episodes": total_episodes,
        "local_total": local_total,
        "completeness_pct": completeness_pct,
        "local_episodes": local_episodes,  # 保留原始数据，用于判断是否真的为空
        "status": "ok",
    }

# ── 持久化缓存层 ──

import json
import time
import threading as _cache_threading

CACHE_FILE = os.path.join(os.path.dirname(__file__), "completeness_cache.json")
_cache_lock = _cache_threading.Lock()


def _load_cache() -> Dict:
    """加载完整度缓存"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict):
    """保存完整度缓存"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[completeness] 缓存写入失败: {e}")


def get_cached_completeness(folder_path: str) -> Optional[Dict]:
    """读取缓存的完整度数据"""
    with _cache_lock:
        cache = _load_cache()
        return cache.get(folder_path)


def save_completeness_to_cache(folder_path: str, data: Dict):
    """保存完整度数据到缓存"""
    with _cache_lock:
        cache = _load_cache()
        data["_cached_at"] = time.time()
        cache[folder_path] = data
        _save_cache(cache)


def remove_from_cache(folder_path: str):
    """从缓存中移除指定路径"""
    with _cache_lock:
        cache = _load_cache()
        if folder_path in cache:
            del cache[folder_path]
            _save_cache(cache)


def refresh_completeness_for_path(tmdb_client, folder_path: str, clear_tmdb_cache: bool = False) -> Optional[Dict]:
    """刷新单个文件夹的完整度并写入缓存。
    返回完整度数据，或 None（无 tmdb_id / 非 tv / 路径不可达）。
    """
    if not os.path.isdir(folder_path):
        logger.debug(f"[completeness] 路径不可达，跳过: {folder_path}")
        return None

    tmdb_id = get_tmdb_id_from_folder(folder_path)
    if not tmdb_id:
        return None

    if clear_tmdb_cache:
        import glob
        cache_dir = os.path.join(os.path.dirname(__file__), "scrape_cache")
        for pattern in [f"tv_{tmdb_id}.json", f"tv{tmdb_id}_s_*.json"]:
            for f in glob.glob(os.path.join(cache_dir, pattern)):
                try:
                    os.remove(f)
                except OSError:
                    pass

    local_episodes = collect_local_episodes(folder_path)
    result = compute_completeness(tmdb_client, tmdb_id, local_episodes)
    if result.get("status") == "ok":
        save_completeness_to_cache(folder_path, result)
    return result


def batch_refresh_all(tmdb_client, nas_paths: List[str], category_tags: Dict[str, str] = None):
    """批量预计算所有 TV 文件夹的完整度。
    遍历 NAS 路径下的 tv 标签目录，找到有 tmdb_id 的文件夹，逐个计算并缓存。
    """
    if not tmdb_client:
        logger.warning("[completeness] 无 TMDB 客户端，跳过批量预计算")
        return

    tv_folders = []
    for base in nas_paths:
        if not base or not os.path.isdir(base):
            continue
        # 遍历一级分类目录
        try:
            for entry in os.listdir(base):
                entry_path = os.path.join(base, entry)
                if not os.path.isdir(entry_path):
                    continue
                # 判断是否是 tv 标签
                tag = (category_tags or {}).get(entry_path, "")
                if not tag:
                    # 自动推断：名字含"剧"/"番"/"动画番"
                    name_lower = entry.lower()
                    if any(k in name_lower for k in ["电视剧", "剧集", "动画番", "番剧", "tv"]):
                        tag = "tv"
                if tag != "tv":
                    continue
                # 遍历该分类下的子目录（每个是一部剧）
                for show in os.listdir(entry_path):
                    show_path = os.path.join(entry_path, show)
                    if os.path.isdir(show_path):
                        tv_folders.append(show_path)
        except OSError:
            continue

    total = len(tv_folders)
    success = 0
    skipped = 0
    for i, folder in enumerate(tv_folders):
        tmdb_id = get_tmdb_id_from_folder(folder)
        if not tmdb_id:
            skipped += 1
            continue
        try:
            local_eps = collect_local_episodes(folder)
            result = compute_completeness(tmdb_client, tmdb_id, local_eps)
            if result.get("status") == "ok":
                save_completeness_to_cache(folder, result)
                success += 1
                pct_str = f"{result['completeness_pct']}%"
                logger.info(f"[completeness] [{i+1}/{total}] {os.path.basename(folder)} → {pct_str}")
        except Exception as e:
            logger.warning(f"[completeness] [{i+1}/{total}] {os.path.basename(folder)} 失败: {e}")

    logger.info(f"[completeness] 批量预计算完成: {success} 成功, {skipped} 跳过（无 TMDB ID）, {total} 总计")
    return {"success": success, "skipped": skipped, "total": total}


def refresh_affected_folders(tmdb_client, changed_paths: List[str]):
    """同步后刷新受影响的 TV 文件夹完整度。
    changed_paths: 新增/删除/变更的文件路径列表。
    从文件路径向上找到 TV 根文件夹，去重后逐个刷新。
    """
    if not tmdb_client or not changed_paths:
        return

    # 收集受影响的 TV 文件夹（去重）
    affected = set()
    for fp in changed_paths:
        # 向上找到有 tvshow.nfo 的目录（TV 根目录）
        folder = os.path.dirname(fp) if os.path.isfile(fp) else fp
        checked = set()
        while folder and folder not in checked:
            checked.add(folder)
            nfo_path = os.path.join(folder, "tvshow.nfo")
            if os.path.exists(nfo_path):
                affected.add(folder)
                break
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent

    for folder in affected:
        try:
            refresh_completeness_for_path(tmdb_client, folder)
            logger.info(f"[completeness] 同步后刷新: {os.path.basename(folder)}")
        except Exception as e:
            logger.warning(f"[completeness] 同步后刷新失败 {os.path.basename(folder)}: {e}")
