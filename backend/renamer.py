"""
重命名与影子名生成模块：从 organizer.py 拆分出来
包含标准命名、影子名生成、文件夹+视频文件统一重命名功能
"""
import os
import re
from typing import List, Dict, Optional

from tmdb_client import parse_filename, ScrapeResult
import scraper
from core.constants import SIDE_CAR_SUFFIXES, VIDEO_EXTS

# 注意：不在顶层 import organizer，避免循环依赖
# organizer 的分类函数在 rename_videos_in_folder 内部延迟导入


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
    folder_name = os.path.basename(folder_path)
    
    # 延迟导入 organizer 的分类函数，避免循环依赖
    from organizer import classify_folder, _is_ignorable_subdir, _is_season_dir, _extract_season_number
    
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
                    en = tmdb_client.get_english_title(mt, nfo["tmdb_id"], nfo.get("original_title", ""))
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
        if not os.path.isfile(full) or os.path.splitext(item)[1].lower() not in VIDEO_EXTS:
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
                    for suffix in SIDE_CAR_SUFFIXES:
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
                    en = tmdb_client.get_english_title(mt, file_nfo["tmdb_id"], file_nfo.get("original_title", ""))
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
                for suffix in SIDE_CAR_SUFFIXES:
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

# ── 影子名生成 ──

def generate_shadow_name_from_nfo(video_path: str, folder_path: str, folder_type: str) -> str:
    """V3：严格从 NFO 生成影子名。没有 NFO 则返回 None，不回退到文件名清洗。"""
    import scraper as _scraper

    # 文件名不带 SxxExx 的剧集（`[VCB-Studio] Jormungand [01].mkv` 这类）会被调用方
    # 判成 movie，而 movie 分支取 NFO 的 <title> —— episode.nfo 里那是**分集标题**
    # （「炎兔」「脉冲星」），作品名在 <showtitle>。NFO 自己声明了是分集就以它为准。
    if folder_type in ("movie", "collection", "series", "mixed"):
        probe = _scraper.read_video_nfo(video_path)
        if probe and (probe.get("media_type") == "episodedetails" or probe.get("showtitle")):
            folder_type = "tv"

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
