"""
结构整理模块：从 organizer.py 拆分而来
负责季目录整理、结构归位、散落视频封装、归档清理。
"""
import os
import logging
import re
import shutil
from typing import List, Dict, Optional

from tmdb_client import parse_filename
import scraper

logger = logging.getLogger(__name__)
# 注意：不在顶层 import organizer，避免循环依赖
# organizer 的分类函数在各函数内部延迟导入


# ── 多季规整 ──

def reorganize_seasons(folder_path: str, tmdb_client=None, dry_run: bool = True, category_hint: str = "") -> Dict:
    """检测同作品不同季，建立标准文件夹结构
    目标结构: 作品名/Season XX/作品名 - S01E01.ext
    仅对能确定季号的目录做标准化，SP/OVA/剧场版等保持原名不动
    """
    from organizer import classify_folder, _is_ignorable_subdir, _is_season_dir, _get_season_number
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
                logger.error(f"Reorganize error: {e}")
    
    return {"status": "ok", "ops": ops, "count": len(ops)}


def reorganize_seasons_by_nfo(folder_path: str, dry_run: bool = True) -> Dict:
    """V3：读取 episode.nfo 确定季号，按季号建目录并移入。
    核心规则：没有 NFO 的文件完全不动（Leave it alone）。
    """
    import scraper as _scraper
    from organizer import _is_season_dir, _get_season_number

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
                logger.error(f"Reorganize by NFO error: {e}")

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
                logger.error(f"Organize error: {e}")

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
                            logger.error(f"Orphan move error: {e}")

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
                    logger.error(f"Merge seasons error: {e}")
        
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
