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
                             tmdb_client_instance, force, proxy, results, whitelist=whitelist)
    else:
        if video_files:
            return _scrape_movie(folder_path, folder_name, video_files,
                                 tmdb_client_instance, force, proxy, results, whitelist=whitelist)
        results["self"] = {"status": "empty", "data": None}
        return results


def _search_tmdb(folder_name: str, tmdb_client_instance, prefer_tv: bool = False):
    """用清洗名搜 TMDB，返回 ScrapeResult。渐进式搜索。"""
    from analyzer import _clean_filename_for_folder
    import re as _re
    
    # 从原始文件夹名提取年份（清洗前提取，因为清洗会去掉年份）
    year_match = _re.search(r'\((\d{4})\)', folder_name) or _re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', folder_name)
    folder_year = year_match.group(1) if year_match else None
    
    clean_name = _clean_filename_for_folder(folder_name + ".tmp")
    search_name = clean_name if clean_name else folder_name
    search_name = _re.sub(r'[\s._-]*(?:S\d+|第\d+季|Season\s*\d+|TV版|电视剧版)$', '', search_name, flags=_re.I).strip() or search_name
    
    en_parts = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', search_name)
    en_query = max(en_parts, key=len).strip() if en_parts else ""
    
    # 搜索时把年份加回去给 scrape_by_filename，让 best_match 能用年份过滤
    search_with_year = f"{search_name} ({folder_year})" if folder_year else search_name
    en_with_year = f"{en_query} ({folder_year})" if folder_year and en_query else en_query
    
    result = tmdb_client_instance.scrape_by_filename(search_with_year)
    if en_query and len(en_query) >= 4:
        en_result = tmdb_client_instance.scrape_by_filename(en_with_year)
        if en_result.tmdb_id:
            if not result.tmdb_id:
                result = en_result
            else:
                from tmdb_client import calc_match_score
                from text_processing import normalize as normalize_text
                cn_s = calc_match_score(normalize_text(search_name), result.title, result.original_title, result.year, folder_year)
                en_s = calc_match_score(normalize_text(en_query), en_result.title, en_result.original_title, en_result.year, folder_year)
                if en_s > cn_s:
                    result = en_result
    
    # 年份校验：如果文件夹有年份但匹配结果年份差距>1，降低信任
    if folder_year and result.tmdb_id and result.year:
        try:
            if abs(int(folder_year) - int(result.year)) > 1:
                # 年份差距大，尝试用中文名+年份重新搜
                cn_match = _re.match(r'^([\u4e00-\u9fff\s·！？：]+)', search_name)
                if cn_match:
                    cn_query = cn_match.group(1).strip()
                    if cn_query and len(cn_query) >= 2:
                        retry = tmdb_client_instance.scrape_by_filename(f"{cn_query} ({folder_year})")
                        if retry.tmdb_id and retry.year:
                            if abs(int(folder_year) - int(retry.year)) <= 1:
                                result = retry
        except (ValueError, TypeError):
            pass
    
    if prefer_tv and (not result.tmdb_id or result.media_type == "movie"):
        search_q = search_name.replace("-", " ").replace("–", " ").strip()
        tv_results = tmdb_client_instance.search_tv(search_q)
        if not tv_results and en_query:
            tv_results = tmdb_client_instance.search_tv(en_query)
        if tv_results:
            from tmdb_client import best_match as _bm
            tv_match = _bm(search_name, tv_results, folder_year, type_key="name")
            if not tv_match and tv_results:
                tv_match = tv_results[0]
            if tv_match:
                result = tmdb_client_instance.get_tv_detail(tv_match["id"])
    
    if not result.tmdb_id and len(search_name) > 4:
        import re as _re2
        shorter = _re2.sub(r'\(\d{4}\)', '', search_name)
        shorter = _re2.sub(r'S\d+E?\d*', '', shorter, flags=_re2.I)
        shorter = _re2.sub(r'\d+$', '', shorter).strip()
        if shorter and shorter != search_name and len(shorter) >= 2:
            search_shorter = f"{shorter} ({folder_year})" if folder_year else shorter
            result = tmdb_client_instance.scrape_by_filename(search_shorter)
        if not result.tmdb_id:
            parts = _re2.split(r'[：:·]', shorter or search_name)
            if len(parts) > 1:
                for part in reversed(parts):
                    part = part.strip()
                    if len(part) >= 2:
                        search_part = f"{part} ({folder_year})" if folder_year else part
                        result = tmdb_client_instance.scrape_by_filename(search_part)
                        if result.tmdb_id:
                            break
        if not result.tmdb_id:
            cn_match = _re2.match(r'^([\u4e00-\u9fff]{2,6})', search_name)
            if cn_match:
                cn_q = f"{cn_match.group(1)} ({folder_year})" if folder_year else cn_match.group(1)
                result = tmdb_client_instance.scrape_by_filename(cn_q)
    
    if not result.tmdb_id and search_name != folder_name:
        result = tmdb_client_instance.scrape_by_filename(folder_name)
    
    return result


def _scrape_collection(folder_path, folder_name, subdirs, video_files,
                       tmdb_client_instance, force, depth, max_depth, proxy, results):
    """聚合文件夹：不写父目录 NFO，递归子目录各自独立刮削。"""
    if subdirs and depth < max_depth:
        for sub in subdirs:
            sub_path = os.path.join(folder_path, sub)
            sub_result = scrape_folder(sub_path, tmdb_client_instance, force, depth=depth+1, max_depth=max_depth)
            results["children"].append({"name": sub, "result": sub_result})
    
    if video_files:
        for vf in video_files:
            vf_path = os.path.join(folder_path, vf)
            vr = scrape_video(vf_path, tmdb_client_instance, force)
            results.setdefault("video_results", []).append({"file": vf, "result": vr})
    
    results["self"] = {"status": "aggregate", "data": None}
    return results


def _scrape_tv_v3(folder_path, folder_name, subdirs, video_files,
                  tmdb_client_instance, force, depth, max_depth, proxy, results,
                  dry_run=False, use_ai=False, whitelist=None):
    """V3 确权式 TV 刮削。
    三步：确定 TMDB ID → 建绝对集数映射表 → 遍历视频计算/写 episode.nfo。
    dry_run=True 时只计算 plan 不落盘。
    返回 results dict，额外含 plan 列表和 tmdb_match 信息。
    """
    from organizer import _is_season_dir, _extract_season_number
    from analyzer import _clean_filename_for_folder
    from tmdb_client import parse_filename as _pf, build_absolute_episode_map
    import re as _re

    plan = []
    tmdb_match_info = {"tmdb_id": 0, "title": "", "english_title": "",
                       "total_seasons": 0, "match_source": "none"}

    # ── 第一步：确定 TMDB ID ──
    parent_nfo = read_nfo(folder_path)
    tv_detail = None

    if parent_nfo and parent_nfo.get("title") and parent_nfo.get("tmdb_id"):
        # 父级信任锁定：有效 tvshow.nfo，直接用
        tmdb_id = parent_nfo["tmdb_id"]
        tv_detail = tmdb_client_instance.get_tv_detail(tmdb_id)
        tmdb_match_info = {
            "tmdb_id": tmdb_id,
            "title": tv_detail.title if tv_detail else parent_nfo.get("title", ""),
            "english_title": tv_detail.english_title if tv_detail else parent_nfo.get("english_title", ""),
            "total_seasons": tv_detail.total_seasons if tv_detail else 0,
            "match_source": "existing_nfo",
        }
    else:
        # 搜索 TMDB
        result = _search_tmdb(folder_name, tmdb_client_instance, prefer_tv=True)

        # 搜不到 → 从子目录/视频文件名提取搜索词重试
        if not result.tmdb_id and subdirs:
            for sub in subdirs[:3]:
                sub_path = os.path.join(folder_path, sub)
                try:
                    vexts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                    sv = [f for f in os.listdir(sub_path) if os.path.splitext(f)[1].lower() in vexts]
                    if sv:
                        sc = _clean_filename_for_folder(sv[0])
                        se = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', sc)
                        seq = max(se, key=len).strip() if se else ""
                        if seq and len(seq) >= 4:
                            result = tmdb_client_instance.scrape_by_filename(seq)
                            if result.tmdb_id:
                                break
                except OSError:
                    pass

        if not result.tmdb_id and video_files:
            for vf in video_files[:3]:
                vc = _clean_filename_for_folder(vf)
                if not vc or len(vc) < 2:
                    continue
                ve = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', vc)
                veq = max(ve, key=len).strip() if ve else ""
                if veq and len(veq) >= 4:
                    result = tmdb_client_instance.scrape_by_filename(veq)
                    if result.tmdb_id:
                        break

        if not result.tmdb_id:
            results["self"] = {"status": "not_found", "data": None}
            results["plan"] = plan
            results["tmdb_match"] = tmdb_match_info
            return results

        tmdb_id = result.tmdb_id
        # 确保拿到完整的 tv_detail（含 seasons_info）
        if result.media_type in ("tv", "tvshow"):
            tv_detail = result if result.seasons_info else tmdb_client_instance.get_tv_detail(tmdb_id)
        else:
            tv_detail = tmdb_client_instance.get_tv_detail(tmdb_id)

        # 验证 tv_detail 有效（get_tv_detail 可能返回空结果，如 TMDB ID 已失效）
        if not tv_detail or not tv_detail.tmdb_id or not tv_detail.title:
            results["self"] = {"status": "not_found", "data": None}
            results["plan"] = plan
            results["tmdb_match"] = tmdb_match_info
            return results

        tmdb_match_info = {
            "tmdb_id": tmdb_id,
            "title": tv_detail.title,
            "english_title": tv_detail.english_title,
            "total_seasons": tv_detail.total_seasons,
            "match_source": "search",
        }

    # ── 第二步：构建绝对集数映射表 ──
    abs_map = {}
    if tv_detail and tv_detail.seasons_info:
        abs_map = build_absolute_episode_map(tv_detail.seasons_info)
    elif tv_detail and tv_detail.tmdb_id and not tv_detail.seasons_info:
        # 旧缓存没有 seasons_info，重新请求获取
        try:
            raw = tmdb_client_instance._get(f"/tv/{tv_detail.tmdb_id}")
            seasons_raw = raw.get("seasons", [])
            tv_detail.seasons_info = [
                {"season_number": s["season_number"], "episode_count": s["episode_count"]}
                for s in seasons_raw
                if isinstance(s, dict) and "season_number" in s and "episode_count" in s
            ]
            if tv_detail.seasons_info:
                abs_map = build_absolute_episode_map(tv_detail.seasons_info)
                # 更新缓存
                cp = tmdb_client_instance._cache_path("tv", tv_detail.tmdb_id)
                tmdb_client_instance._save_cache(cp, tv_detail.dict())
        except Exception as e:
            logger.error(f"[V3] Failed to fetch seasons_info: {e}")

    tmdb_id = tmdb_match_info["tmdb_id"]
    showtitle = tv_detail.title if tv_detail else ""

    # ── 第三步：遍历所有视频，计算 plan ──
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}

    def _collect_videos(base_path):
        """收集文件夹下所有视频（含子目录），只屏蔽设定集和原声带所属的附加非视频内容目录"""
        vids = []
        # Plex/Kodi/Emby 标准中无需扫描媒体引擎的非正片资料文件夹
        ignore_dirs = {"subtitles", "subs", "font", "fonts", "scans", "ost", "cd", 
                       "soundtrack", "booklet", "artbook", "covers"}
        
        for root_dir, dirs, files in os.walk(base_path):
            # 将隐藏目录以及那些音乐、画册和字幕目录踢出递归
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ignore_dirs]
            
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in video_exts:
                    # 我们希望保留 ova, sp, extra，因为系统标准化整理时，
                    # 能把乱放的它们拉平到类似 Season 0 或者直接同级存放
                    vids.append(os.path.join(root_dir, f))
        return vids

    all_videos = _collect_videos(folder_path)
    
    # ── 如果有白名单，只保留白名单中的文件 ──
    if whitelist:
        w_set = set()
        w_basenames = set() # 兜底逻辑：只看文件名
        
        folder_base_norm = os.path.normpath(folder_path).lower()
        folder_parent, folder_last = os.path.split(folder_base_norm)
        
        for p in whitelist:
            # 1. 强制标准化分隔符：处理来自 qB 的 / (Unix)
            p_sep = p.replace("/", os.sep).replace("\\", os.sep)
            p_norm = os.path.normpath(p_sep)
            
            # 记录文件名作为兜底
            w_basenames.add(os.path.basename(p_norm).lower())
            
            # 2. 智能路径拼合（与 file_relocator.py 逻辑对照）
            if os.path.isabs(p_norm):
                abs_p = p_norm
            else:
                parts = p_norm.split(os.sep)
                if len(parts) > 1 and parts[0].lower() == folder_last.lower():
                    # 去除重复根目录：如果种子里的第一级目录名和保存目录名一样
                    abs_p = os.path.join(folder_path, *parts[1:])
                    logger.info(f"[DEBUG_WHITELIST] Overlap Stripped in scraper: '{parts[0]}', Final: {abs_p}")
                else:
                    abs_p = os.path.join(folder_path, p_norm)
            
            w_set.add(os.path.normpath(abs_p).lower())
            
        if not w_set:
            # 如果白名单提供了但最终计算结果为空，说明路径匹配全军覆没。
            # 为了防止“新文件栏为空”的问题，此时回退到不使用白名单。
            pass
        else:
            # 过滤策略：精准路径匹配优先，文件名匹配作为极其备用的参考（防止目录层级错乱）
            filtered_videos = []
            for v in all_videos:
                v_norm = os.path.normpath(v).lower()
                v_base = os.path.basename(v_norm)
                if v_norm in w_set:
                    filtered_videos.append(v)
                elif v_base in w_basenames:
                    filtered_videos.append(v)
            all_videos = filtered_videos

    for vpath in all_videos:
        vname = os.path.basename(vpath)
        parsed = _pf(vname)
        method = "regex"

        season_num = parsed.get("season")
        episode_num = parsed.get("episode")
        abs_ep = parsed.get("absolute_episode")

        mapped_season = None
        mapped_episode = None
        skip_reason = None
        
        # 🛡️ 智能防冲撞：针对特典/垃圾选项做 "Season 00" 的强制保护性避让
        import re
        rel_path = os.path.relpath(vpath, folder_path).lower()
        path_words = set(re.findall(r'[a-z0-9]+', rel_path))
        sp_keywords = {"sp", "sp00", "sp01", "sp02", "sp03", "menu", "ova", "omake", "extra", "extras", "bonus", "trailer", "ncop", "nced", "interview", "featurette"}
        is_special = bool(path_words.intersection(sp_keywords))

        if is_special:
            mapped_season = 0
            # 集号尽量使用提取到的，没有就降级保底为 1
            mapped_episode = episode_num if episode_num is not None else (abs_ep if abs_ep is not None else 1)
        elif season_num is not None and episode_num is not None:
            # 标准 SxxExx 或有明确季号
            mapped_season = season_num
            mapped_episode = episode_num
        elif abs_ep is not None:
            # 绝对集数 → 查映射表
            if abs_ep in abs_map:
                mapped_season, mapped_episode = abs_map[abs_ep]
            else:
                skip_reason = f"绝对集数 {abs_ep} 超出映射表范围（最大 {max(abs_map.keys()) if abs_map else 0}）"
        else:
            # 三个全为 None → 正则失败
            if use_ai:
                from ai_organizer import ai_extract_episode
                ai_result = ai_extract_episode(vname)
                if ai_result:
                    method = "ai"
                    ai_s = ai_result.get("season")
                    ai_e = ai_result.get("episode")
                    ai_abs = ai_result.get("absolute_episode")
                    if ai_s is not None and ai_e is not None:
                        mapped_season = ai_s
                        mapped_episode = ai_e
                    elif ai_abs is not None:
                        if ai_abs in abs_map:
                            mapped_season, mapped_episode = abs_map[ai_abs]
                            abs_ep = ai_abs
                        else:
                            skip_reason = f"AI 提取绝对集数 {ai_abs} 超出映射表范围"
                            method = "ai_failed"
                    else:
                        skip_reason = "AI 也无法提取集号"
                        method = "ai_failed"
                else:
                    skip_reason = "AI 提取失败"
                    method = "ai_failed"
            else:
                skip_reason = "无法提取集号"
                method = "regex_failed"

        # 构建标准化预览文件名（仅用于 UI 展示，不影响实际操作）
        ext = os.path.splitext(vname)[1]
        if mapped_season is not None and mapped_episode is not None and showtitle:
            std_name = f"{showtitle} - S{mapped_season:02d}E{mapped_episode:02d}{ext}"
        elif mapped_season is not None and showtitle:
            std_name = f"{showtitle} - S{mapped_season:02d}{ext}"
        else:
            std_name = vname  # 无法标准化，保留原名

        # 构建 plan item
        item = {
            "original_path": vpath,
            "original_filename": vname,
            "parsed": {
                "method": method,
                "season": season_num,
                "episode": episode_num,
                "absolute_episode": abs_ep,
            },
            "mapped": {"season": mapped_season, "episode": mapped_episode} if mapped_season is not None else None,
            "scraped_title": showtitle,
            "episode_title": "",
            "target_season_dir": f"Season {mapped_season:02d}" if mapped_season is not None else None,
            "target_filename": std_name,
            "target_path": os.path.join(folder_path, f"Season {mapped_season:02d}", std_name) if mapped_season is not None else vpath,
            "target_shadow_name": None,
            "actions": [],
            "skip_reason": skip_reason,
        }

        if mapped_season is not None and mapped_episode is not None:
            # 尝试获取分集详情
            try:
                ep_detail = tmdb_client_instance.get_episode_detail(tmdb_id, mapped_season, mapped_episode)
                if ep_detail and ep_detail.episode_title:
                    item["episode_title"] = ep_detail.episode_title
                    # 更新标准化名称：加入分集标题
                    std_name = f"{showtitle} - S{mapped_season:02d}E{mapped_episode:02d} - {ep_detail.episode_title}{ext}"
                    # 清理文件名中不合法的字符
                    std_name = "".join(c for c in std_name if c not in r'\/:*?"<>|').strip()
                    item["target_filename"] = std_name
                    item["target_path"] = os.path.join(folder_path, f"Season {mapped_season:02d}", std_name)
            except Exception:
                pass  # 404 等错误 → 简化 NFO

            # 构建影子名
            shadow = showtitle
            en = tv_detail.english_title if tv_detail else ""
            if en and en != showtitle:
                shadow += f" {en}"
            shadow += f" S{mapped_season:02d}E{mapped_episode:02d}"
            item["target_shadow_name"] = shadow

            item["actions"] = ["write_episode_nfo", "move_to_season", "write_shadow"]

        plan.append(item)


    # ── 第四步：落盘（仅 dry_run=False）──
    if not dry_run:
        # 写/更新 tvshow.nfo + poster
        if tv_detail and tv_detail.tmdb_id:
            for old in ["movie.nfo", "tvshow.nfo"]:
                p = os.path.join(folder_path, old)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            write_tvshow_nfo(folder_path, tv_detail)
            if tv_detail.poster_url:
                download_poster(folder_path, tv_detail.poster_url, proxy=proxy)
            if tv_detail.backdrop_url:
                download_poster(folder_path, tv_detail.backdrop_url, "fanart.jpg", proxy=proxy)

        # 写每个视频的 episode.nfo
        for item in plan:
            if "write_episode_nfo" not in item.get("actions", []):
                continue
            mapped = item["mapped"]
            if not mapped:
                continue
            s, e = mapped["season"], mapped["episode"]
            vpath = item["original_path"]

            # 构建 ScrapeResult 用于写 NFO
            ep_scrape = ScrapeResult(
                tmdb_id=tmdb_id,
                media_type="episode",
                title=item.get("episode_title") or showtitle,
                episode_title=item.get("episode_title", ""),
                season_number=s,
                episode_number=e,
            )
            write_episode_nfo(vpath, ep_scrape, showtitle=showtitle)

        # 写季封面
        if tv_detail and tv_detail.tmdb_id:
            # 收集 plan 中涉及的所有季号
            season_nums = set()
            for item in plan:
                if item.get("mapped") and item["mapped"].get("season"):
                    season_nums.add(item["mapped"]["season"])
            for sn in sorted(season_nums):
                season_dir = os.path.join(folder_path, f"Season {sn:02d}")
                if not os.path.isdir(season_dir):
                    continue  # 季目录还没建（Step 4 才建），跳过
                if not force and os.path.exists(os.path.join(season_dir, "season.nfo")):
                    continue
                try:
                    sd = tmdb_client_instance.get_season_detail(tmdb_id, sn)
                    if sd and sd.tmdb_id:
                        sd.season_number = sn
                        write_season_nfo(season_dir, sd)
                        if sd.poster_url:
                            download_poster(season_dir, sd.poster_url,
                                            f"season{sn:02d}-poster.jpg", proxy)
                except Exception as e:
                    logger.error(f"[Scrape] Season {sn} detail failed: {e}")

    # 构建 summary
    will_process = len([i for i in plan if not i.get("skip_reason")])
    will_skip = len([i for i in plan if i.get("skip_reason")])
    seasons_to_create = sorted(set(
        i["target_season_dir"] for i in plan
        if i.get("target_season_dir") and not i.get("skip_reason")
    ))

    results["self"] = {"status": "ok" if tmdb_id else "not_found", "data": parent_nfo}
    results["plan"] = plan
    results["tmdb_match"] = tmdb_match_info
    results["summary"] = {
        "total_videos": len(all_videos),
        "will_process": will_process,
        "will_skip": will_skip,
        "seasons_to_create": seasons_to_create,
        "nfo_to_write": will_process,
        "files_to_move": will_process,
        "shadows_to_fill": will_process,
    }
    return results


def _scrape_tv(folder_path, folder_name, subdirs, video_files,
               tmdb_client_instance, force, depth, max_depth, proxy, results, whitelist=None):
    """TV 类型：写 tvshow.nfo + 递归季目录 + 分集 episode.nfo。"""
    from organizer import _is_season_dir, _extract_season_number
    from analyzer import _clean_filename_for_folder
    import re as _re
    
    parent_nfo = read_nfo(folder_path)
    if not parent_nfo or not parent_nfo.get("title") or force:
        result = _search_tmdb(folder_name, tmdb_client_instance, prefer_tv=True)
        
        if not result.tmdb_id and subdirs:
            for sub in subdirs[:3]:
                sub_path = os.path.join(folder_path, sub)
                try:
                    vexts = {".mp4",".mkv",".avi",".mov",".wmv",".rmvb",".rm",".flv",".ts",".m4v"}
                    sv = [f for f in os.listdir(sub_path) if os.path.splitext(f)[1].lower() in vexts]
                    if sv:
                        sc = _clean_filename_for_folder(sv[0])
                        se = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', sc)
                        seq = max(se, key=len).strip() if se else ""
                        if seq and len(seq) >= 4:
                            result = tmdb_client_instance.scrape_by_filename(seq)
                            if result.tmdb_id:
                                break
                except OSError:
                    pass
        
        if not result.tmdb_id and video_files:
            for vf in video_files[:3]:
                vc = _clean_filename_for_folder(vf)
                if not vc or len(vc) < 2: continue
                ve = _re.findall(r'[A-Za-z][A-Za-z\s\':.\-]{3,}', vc)
                veq = max(ve, key=len).strip() if ve else ""
                if veq and len(veq) >= 4:
                    result = tmdb_client_instance.scrape_by_filename(veq)
                    if result.tmdb_id: break
        
        if result.tmdb_id:
            for old in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
                p = os.path.join(folder_path, old)
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass
            write_tvshow_nfo(folder_path, result)
            if result.poster_url:
                download_poster(folder_path, result.poster_url, proxy=proxy)
            if result.backdrop_url:
                download_poster(folder_path, result.backdrop_url, "fanart.jpg", proxy=proxy)
    
    if subdirs and depth < max_depth:
        for sub in subdirs:
            sub_path = os.path.join(folder_path, sub)
            sub_result = scrape_folder(sub_path, tmdb_client_instance, force,
                                       folder_type="tv", depth=depth+1, max_depth=max_depth)
            results["children"].append({"name": sub, "result": sub_result})
    
    parent_nfo = read_nfo(folder_path)
    tv_tmdb_id = parent_nfo.get("tmdb_id") if parent_nfo else 0
    if tv_tmdb_id and parent_nfo.get("media_type") in ("tvshow", "tv"):
        for sub in subdirs:
            sub_path = os.path.join(folder_path, sub)
            if not _is_season_dir(sub): continue
            if not force and os.path.exists(os.path.join(sub_path, "season.nfo")): continue
            season_num = _extract_season_number(sub)
            if season_num is None: continue
            try:
                sd = tmdb_client_instance.get_season_detail(tv_tmdb_id, season_num)
                if sd and sd.tmdb_id:
                    sd.season_number = season_num
                    write_season_nfo(sub_path, sd)
                    if sd.poster_url:
                        poster_name = f"season{season_num:02d}-poster.jpg"
                        download_poster(sub_path, sd.poster_url, poster_name, proxy)
            except Exception as e:
                logger.error(f"[Scrape] Season {season_num} failed: {e}")
    
    if video_files and tv_tmdb_id:
        # 规范化白名单路径方便对比
        w_set = {os.path.normpath(p).lower() for p in whitelist} if whitelist else None
        from tmdb_client import parse_filename as _pf
        for vf in video_files:
            vf_path = os.path.join(folder_path, vf)
            # 检查白名单
            full_vf = os.path.normpath(os.path.abspath(vf_path))
            if w_set is not None and full_vf.lower() not in w_set:
                continue
            parsed = _pf(vf)
            ep_num = parsed.get("episode")
            s_num = parsed.get("season") or 1
            if ep_num is not None:
                try:
                    ed = tmdb_client_instance.get_episode_detail(tv_tmdb_id, s_num, ep_num)
                    if ed and ed.tmdb_id:
                        write_episode_nfo(vf_path, ed)
                        base = os.path.splitext(vf_path)[0]
                        if parent_nfo.get("poster_url"):
                            download_poster(folder_path, parent_nfo["poster_url"], os.path.basename(base) + "-poster.jpg", proxy=proxy)
                        results.setdefault("video_results", []).append({"file": vf, "result": {"status": "ok"}})
                        continue
                except Exception:
                    pass
            base = os.path.splitext(vf_path)[0]
            poster_url = parent_nfo.get("poster_url") or (parent_nfo.get("local_poster") if parent_nfo else None)
            results.setdefault("video_results", []).append({"file": vf, "result": {"status": "ok_folder"}})
    
    results["self"] = {"status": "ok" if tv_tmdb_id else "not_found", "data": parent_nfo}
    return results


def _scrape_movie(folder_path, folder_name, video_files,
                  tmdb_client_instance, force, proxy, results, whitelist=None):
    """单部电影：写 movie.nfo + poster。"""
    if not force:
        existing = read_nfo(folder_path)
        if existing and existing.get("title"):
            # 旧刮削有效（title 非空），跳过
            results["self"] = {"status": "exists", "data": existing}
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
        return results
    
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
