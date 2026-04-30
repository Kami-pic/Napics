"""
刮削器：递归刮削主逻辑
NFO 读写已拆分到 nfo_handler.py，海报下载已拆分到 poster_downloader.py
"""
import os
import logging
import json
import re
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional, Dict, List
from tmdb_client import ScrapeResult

# ── 从拆分模块 re-export，保持对外兼容 ──
from nfo_handler import (
    read_nfo, read_video_nfo, _text,
    write_movie_nfo, write_tvshow_nfo, write_season_nfo, write_episode_nfo,
    _add, _write_xml, _is_category_folder,
)
from nfo_handler import write_movie_nfo_for_video as _write_movie_nfo_for_video
from poster_downloader import download_poster

logger = logging.getLogger(__name__)
# ── 完整刮削流程 ──



# ── 从 scraper_tv 导入 TV 刮削逻辑 ──
from scraper_tv import (
    _episode_nfo_matches_target,
    _search_tmdb,
    _scrape_collection,
    _scrape_tv_v3,
    _scrape_tv,
)


def scrape_folder(folder_path: str, tmdb_client_instance, force: bool = False,
                  folder_type: str = None, depth: int = 0, max_depth: int = 2,
                  dry_run: bool = False, use_ai: bool = False,
                  whitelist: List[str] = None) -> Dict:
    """刮削一个文件夹。folder_type 由流水线传入，不传则保底调 classify_folder。
    根据 folder_type 分发：movie→_scrape_movie, tv→_scrape_tv_v3, collection→_scrape_collection
    dry_run=True 时只计算 plan 不落盘（仅 tv 类型支持）。
    """
    folder_name = os.path.basename(folder_path)
    results = {"self": None, "children": []}
    proxy = getattr(tmdb_client_instance, 'proxy', '') or ''
    
    # 保底：没传 folder_type 就自己判断
    if folder_type is None:
        from organizer import classify_folder as _clf
        folder_type = _clf(folder_path, None).get("type", "unknown")
    
    # 收集子目录和视频文件
    from organizer import _is_ignorable_subdir
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    subdirs = []
    video_files = []
    if os.path.isdir(folder_path):
        for item in os.listdir(folder_path):
            full = os.path.join(folder_path, item)
            if os.path.isdir(full) and not item.startswith('.') and not _is_ignorable_subdir(item):
                subdirs.append(item)
            elif os.path.isfile(full) and os.path.splitext(item)[1].lower() in video_exts:
                video_files.append(item)
    
    # 按类型分发
    if folder_type in ("series", "collection", "mixed"):
        return _scrape_collection(folder_path, folder_name, subdirs, video_files,
                                  tmdb_client_instance, force, depth, max_depth, proxy, results)
    elif folder_type == "tv":
        return _scrape_tv_v3(folder_path, folder_name, subdirs, video_files,
                             tmdb_client_instance, force, depth, max_depth, proxy, results,
                             dry_run=dry_run, use_ai=use_ai, whitelist=whitelist)
    elif folder_type == "movie":
        return _scrape_movie(folder_path, folder_name, video_files,
                             tmdb_client_instance, force, proxy, results,
                             whitelist=whitelist, dry_run=dry_run)
    else:
        if video_files:
            return _scrape_movie(folder_path, folder_name, video_files,
                                 tmdb_client_instance, force, proxy, results,
                                 whitelist=whitelist, dry_run=dry_run)
        results["self"] = {"status": "empty", "data": None}
        return results




def _scrape_movie(folder_path, folder_name, video_files,
                  tmdb_client_instance, force, proxy, results, whitelist=None,
                  dry_run=False):
    """单部电影：写 movie.nfo + poster。
    dry_run=True 时只计算 plan 不落盘。
    """
    from tmdb_client import parse_filename as _pf

    plan = []
    tmdb_match_info = {"tmdb_id": 0, "title": "", "english_title": "",
                       "total_seasons": 0, "match_source": "none"}

    if not force and not dry_run:
        existing = read_nfo(folder_path)
        if existing and existing.get("title"):
            # 旧刮削有效（title 非空），跳过
            results["self"] = {"status": "exists", "data": existing}
            results["plan"] = plan
            results["tmdb_match"] = tmdb_match_info
            return results
    
    result = _search_tmdb(folder_name, tmdb_client_instance)
    
    if not result.tmdb_id and video_files:
        # 规范化白名单路径方便对比
        w_set = {os.path.normpath(p.replace("/", os.sep).replace("\\", os.sep)).lower() for p in whitelist} if whitelist else None

        from analyzer import _clean_filename_for_folder
        import re as _re
        for vf in video_files[:3]:
            # 检查白名单
            vf_path = os.path.join(folder_path, vf)
            full_vf = os.path.normpath(os.path.abspath(vf_path))
            if w_set is not None and full_vf.lower() not in w_set:
                continue

            vc = _clean_filename_for_folder(vf)
            if not vc or len(vc) < 2: continue
            ve = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', vc)
            veq = max(ve, key=len).strip() if ve else ""
            if veq and len(veq) >= 4:
                result = tmdb_client_instance.scrape_by_filename(veq)
                if result.tmdb_id: break
    
    if not result.tmdb_id:
        results["self"] = {"status": "not_found", "data": None}
        results["plan"] = plan
        results["tmdb_match"] = tmdb_match_info
        return results

    tmdb_match_info = {
        "tmdb_id": result.tmdb_id,
        "title": result.title,
        "english_title": getattr(result, "english_title", ""),
        "total_seasons": 0,
        "match_source": "search",
    }

    # 构建电影标准名
    movie_title = result.title or folder_name
    year = getattr(result, "year", None) or ""
    if year:
        std_base = f"{movie_title} ({year})"
    else:
        std_base = movie_title
    # 清理文件名中不合法的字符
    std_base = "".join(c for c in std_base if c not in r'\/:*?"<>|').strip()

    # 构建 plan：为白名单中的视频文件生成重命名计划
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    w_set = None
    w_basenames = set()
    if whitelist:
        folder_base_norm = os.path.normpath(folder_path).lower()
        folder_last = os.path.basename(folder_base_norm)
        w_set = set()
        for p in whitelist:
            p_sep = p.replace("/", os.sep).replace("\\", os.sep)
            p_norm = os.path.normpath(p_sep)
            w_basenames.add(os.path.basename(p_norm).lower())
            if os.path.isabs(p_norm):
                abs_p = p_norm
            else:
                parts = p_norm.split(os.sep)
                if len(parts) > 1 and parts[0].lower() == folder_last:
                    abs_p = os.path.join(folder_path, *parts[1:])
                else:
                    abs_p = os.path.join(folder_path, p_norm)
            w_set.add(os.path.normpath(abs_p).lower())

    # 收集所有视频（含子目录）
    all_videos = []
    for root_dir, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in video_exts:
                all_videos.append(os.path.join(root_dir, f))

    # 白名单过滤
    if w_set:
        filtered = []
        for v in all_videos:
            v_norm = os.path.normpath(v).lower()
            v_base = os.path.basename(v_norm)
            if v_norm in w_set or v_base in w_basenames:
                filtered.append(v)
        all_videos = filtered

    for vpath in all_videos:
        vname = os.path.basename(vpath)
        ext = os.path.splitext(vname)[1]
        std_name = f"{std_base}{ext}"

        item = {
            "original_path": vpath,
            "original_filename": vname,
            "parsed": {"method": "movie"},
            "mapped": None,
            "scraped_title": movie_title,
            "episode_title": "",
            "target_season_dir": None,
            "target_filename": std_name,
            "target_path": os.path.join(folder_path, std_name),
            "target_shadow_name": None,
            "actions": [],
            "skip_reason": None,
        }

        # 判断是否需要移动/重命名
        norm_original = os.path.normcase(os.path.normpath(vpath))
        norm_target = os.path.normcase(os.path.normpath(item["target_path"]))
        actions = []
        if norm_original != norm_target:
            actions.append("move_to_season")  # 复用 action 名，实际是重命名/移动
        actions.append("write_movie_nfo")
        item["actions"] = actions
        plan.append(item)

    if not dry_run:
        # 落盘：写 NFO + 海报
        for old in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            p = os.path.join(folder_path, old)
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        
        write_movie_nfo(folder_path, result)
        if result.poster_url:
            download_poster(folder_path, result.poster_url, proxy=proxy)
        if result.backdrop_url:
            download_poster(folder_path, result.backdrop_url, "fanart.jpg", proxy=proxy)
    
    results["self"] = {"status": "ok", "data": result.dict()}
    results["plan"] = plan
    results["tmdb_match"] = tmdb_match_info
    results["summary"] = {
        "total_videos": len(all_videos),
        "will_process": len([i for i in plan if not i.get("skip_reason")]),
        "will_skip": 0,
        "seasons_to_create": [],
        "nfo_to_write": 1 if result.tmdb_id else 0,
        "files_to_move": len([i for i in plan if "move_to_season" in i.get("actions", [])]),
        "shadows_to_fill": 0,
    }
    return results


def scrape_video(video_path: str, tmdb_client_instance, force: bool = False) -> Dict:
    """刮削单个视频文件（同名风格：{filename}.nfo / {filename}-poster.jpg）"""
    filename = os.path.basename(video_path)
    folder = os.path.dirname(video_path)
    base = os.path.splitext(video_path)[0]  # 不含扩展名的完整路径
    proxy = getattr(tmdb_client_instance, 'proxy', '') or ''
    
    if not force:
        existing = read_video_nfo(video_path)
        if existing and existing.get("title"):
            return {"status": "exists", "data": existing}
    
    # 优先用清洗后的纯净名字搜 TMDB
    from analyzer import _clean_filename_for_folder
    import re as _re
    clean_name = _clean_filename_for_folder(filename)
    search_name = clean_name if clean_name else os.path.splitext(filename)[0]
    
    # 提取英文部分（从清洗后的名字）
    en_parts = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', search_name)
    en_query = max(en_parts, key=len).strip() if en_parts else ""
    
    result = tmdb_client_instance.scrape_by_filename(search_name)
    if en_query and len(en_query) >= 4:
        en_result = tmdb_client_instance.scrape_by_filename(en_query)
        if en_result.tmdb_id:
            if not result.tmdb_id:
                result = en_result
            else:
                from tmdb_client import calc_match_score
                from text_processing import normalize as normalize_text

                cn_score = calc_match_score(normalize_text(search_name), result.title, result.original_title, result.year, None)
                en_score = calc_match_score(normalize_text(en_query), en_result.title, en_result.original_title, en_result.year, None)
                if en_score > cn_score:
                    result = en_result
    
    # 渐进缩短
    if not result.tmdb_id and len(search_name) > 4:
        shorter = _re.sub(r'\(\d{4}\)', '', search_name)
        shorter = _re.sub(r'S\d+E?\d*', '', shorter, flags=_re.I)
        shorter = _re.sub(r'\d+$', '', shorter).strip()
        if shorter and shorter != search_name and len(shorter) >= 2:
            result = tmdb_client_instance.scrape_by_filename(shorter)
        if not result.tmdb_id:
            parts = _re.split(r'[：:·]', shorter or search_name)
            if len(parts) > 1:
                for part in reversed(parts):
                    part = part.strip()
                    if len(part) >= 2:
                        result = tmdb_client_instance.scrape_by_filename(part)
                        if result.tmdb_id:
                            break
        if not result.tmdb_id:
            cn_match = _re.match(r'^([\u4e00-\u9fff]{2,6})', search_name)
            if cn_match:
                result = tmdb_client_instance.scrape_by_filename(cn_match.group(1))
    
    if not result.tmdb_id and search_name != os.path.splitext(filename)[0]:
        # 清洗名搜不到，用原始名兜底
        result = tmdb_client_instance.scrape_by_filename(filename)
    if not result.tmdb_id:
        return {"status": "not_found", "data": None}
    
    if result.media_type == "episode":
        write_episode_nfo(video_path, result)
        if not os.path.exists(os.path.join(folder, "tvshow.nfo")):
            tv_detail = tmdb_client_instance.get_tv_detail(result.tmdb_id)
            write_tvshow_nfo(folder, tv_detail)
            if tv_detail.poster_url:
                download_poster(folder, tv_detail.poster_url, proxy=proxy)
    else:
        # 电影：写同名 NFO（{filename}.nfo）
        _write_movie_nfo_for_video(video_path, result)
    
    # 下载同名 poster 和 fanart
    if result.poster_url:
        download_poster(folder, result.poster_url, os.path.basename(base) + "-poster.jpg", proxy=proxy)
    if result.backdrop_url:
        download_poster(folder, result.backdrop_url, os.path.basename(base) + "-fanart.jpg", proxy=proxy)
    
    return {"status": "ok", "data": result.dict()}

def batch_scrape(paths: list, tmdb_client_instance) -> Dict:
    """批量刮削多个路径。AI 开启时，对 not_found 的路径尝试 AI 候选匹配。"""
    from ai_organizer import ai_select_scrape_candidate
    from ai_client import get_ai_client

    results = {"success": 0, "failed": 0, "skipped": 0, "details": []}
    ai_client = get_ai_client()
    use_ai_candidate = ai_client.is_feature_enabled("scrape_candidate")

    for p in paths:
        try:
            if os.path.isdir(p):
                r = scrape_folder(p, tmdb_client_instance, force=True)
                status = r.get("self", {}).get("status", "not_found")
            elif os.path.isfile(p):
                r = scrape_video(p, tmdb_client_instance, force=True)
                status = r.get("status", "not_found")
            else:
                status = "not_found"
                r = {}

            # AI 候选匹配：刮削失败时尝试用 AI 从候选中选择
            if status == "not_found" and use_ai_candidate and os.path.isdir(p):
                ai_result = _ai_fallback_scrape(p, tmdb_client_instance)
                if ai_result:
                    r = ai_result
                    status = r.get("self", {}).get("status", "not_found")

            if status == "ok":
                results["success"] += 1
            elif status == "exists":
                results["skipped"] += 1
            else:
                results["failed"] += 1

            detail = {"path": p, "status": status}
            # 标记 AI 参与
            if r.get("ai_selected"):
                detail["ai_selected"] = True
                detail["ai_confidence"] = r.get("ai_confidence", "")
                detail["ai_reason"] = r.get("ai_reason", "")
            results["details"].append(detail)
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"path": p, "status": "error", "error": str(e)})
    return results


def _ai_fallback_scrape(folder_path: str, tmdb_client_instance) -> Optional[Dict]:
    """AI 候选匹配 fallback：搜索 TMDB 候选列表，让 AI 选择最佳匹配。"""
    from ai_organizer import ai_select_scrape_candidate
    from analyzer import _clean_filename_for_folder
    import re as _re

    folder_name = os.path.basename(folder_path)
    clean_name = _clean_filename_for_folder(folder_name + ".tmp") or folder_name

    # 收集文件列表（只传文件名，不传路径）
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    try:
        file_list = [f for f in os.listdir(folder_path)
                     if os.path.splitext(f)[1].lower() in video_exts][:15]
    except OSError:
        file_list = []

    # 搜索 TMDB 候选
    movie_candidates = tmdb_client_instance.search_movie(clean_name)
    tv_candidates = tmdb_client_instance.search_tv(clean_name)
    all_candidates = []
    for c in movie_candidates[:5]:
        all_candidates.append({
            "title": c.get("title", ""),
            "original_title": c.get("original_title", ""),
            "year": (c.get("release_date", "") or "")[:4],
            "overview": (c.get("overview", "") or "")[:100],
            "media_type": "movie",
            "tmdb_id": c.get("id"),
        })
    for c in tv_candidates[:5]:
        all_candidates.append({
            "title": c.get("name", ""),
            "original_title": c.get("original_name", ""),
            "year": (c.get("first_air_date", "") or "")[:4],
            "overview": (c.get("overview", "") or "")[:100],
            "media_type": "tv",
            "tmdb_id": c.get("id"),
        })

    if len(all_candidates) <= 1:
        return None

    # 让 AI 选择
    ai_result = ai_select_scrape_candidate(folder_name, file_list, all_candidates)
    if not ai_result or ai_result.get("selected_index", -1) < 0:
        return None
    if ai_result.get("confidence") == "low":
        return None  # 低置信度不自动选择

    idx = ai_result["selected_index"]
    if idx >= len(all_candidates):
        return None

    selected = all_candidates[idx]
    tmdb_id = selected.get("tmdb_id")
    media_type = selected.get("media_type", "movie")

    # 用选中的候选执行刮削
    try:
        if media_type == "movie":
            detail = tmdb_client_instance.get_movie_detail(tmdb_id)
        else:
            detail = tmdb_client_instance.get_tv_detail(tmdb_id)

        if detail and detail.tmdb_id:
            # 写 NFO
            proxy = getattr(tmdb_client_instance, 'proxy', '') or ''
            write_nfo(folder_path, detail, proxy)
            # 下载海报
            if detail.poster_url:
                download_poster(folder_path, detail.poster_url, proxy)
            return {
                "self": {"status": "ok", "data": detail.dict() if hasattr(detail, "dict") else {}},
                "children": [],
                "ai_selected": True,
                "ai_confidence": ai_result.get("confidence", ""),
                "ai_reason": ai_result.get("reason", ""),
            }
    except Exception as e:
        logger.error(f"[AI Scrape] AI 选中候选后刮削失败: {e}")

    return None
