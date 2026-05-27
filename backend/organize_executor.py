"""
业务层：organize_executor — Action Plan 执行器（文件操作+路径计算）
从 routes/organize.py 拆分的纯业务逻辑，不含路由。
"""
import os
import logging
import shutil
from typing import List

logger = logging.getLogger(__name__)

_PLAN_POSTER_SUFFIXES = (
    ".nfo",
    "-poster.jpg", "-poster.png",
    "-thumb.jpg", "-thumb.png",
    "-fanart.jpg", "-fanart.png",
    "-clearlogo.png",
)
_PLAN_SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}


def _find_duplicate_target_paths(plan_items: list) -> list[str]:
    """返回 action_plan 中重复命中的目标路径。"""
    seen = set()
    duplicates = set()
    for item in plan_items or []:
        target_path = item.get("target_path") or ""
        if not target_path:
            continue
        norm_target = os.path.normcase(os.path.normpath(target_path))
        if norm_target in seen:
            duplicates.add(target_path)
        else:
            seen.add(norm_target)
    return sorted(duplicates)


def _find_duplicate_logical_targets(plan_items: list) -> list[str]:
    """返回 action_plan 中重复命中的逻辑目标 basename（忽略扩展名）。"""
    seen = set()
    duplicates = {}
    for item in plan_items or []:
        target_path = item.get("target_path") or ""
        if not target_path:
            continue
        target_dir = os.path.dirname(target_path)
        target_stem = os.path.splitext(os.path.basename(target_path))[0]
        if not target_dir or not target_stem:
            continue
        logical_key = os.path.normcase(os.path.normpath(os.path.join(target_dir, target_stem)))
        duplicates.setdefault(logical_key, os.path.join(target_dir, target_stem))
        if logical_key in seen:
            continue
        seen.add(logical_key)

    counts = {}
    for item in plan_items or []:
        target_path = item.get("target_path") or ""
        if not target_path:
            continue
        target_dir = os.path.dirname(target_path)
        target_stem = os.path.splitext(os.path.basename(target_path))[0]
        if not target_dir or not target_stem:
            continue
        logical_key = os.path.normcase(os.path.normpath(os.path.join(target_dir, target_stem)))
        counts[logical_key] = counts.get(logical_key, 0) + 1

    return sorted(
        display_path for logical_key, display_path in duplicates.items()
        if counts.get(logical_key, 0) > 1
    )


def _cleanup_empty_dirs(base_path: str):
    """自底向上清理 base_path 下的空目录和只剩垃圾文件的种子目录壳。
    
    不删除 base_path 本身，也不删除 Season 开头的目录。
    "垃圾文件"指 txt、jpg（非标准海报名）、nfo（种子目录内的，非根目录的）等。
    """
    from core.constants import VIDEO_EXTS
    # 种子目录内可安全删除的垃圾文件扩展名
    _junk_exts = {".txt", ".nfo", ".jpg", ".png", ".url", ".lnk", ".exe", ".html", ".htm"}
    
    for root, dirs, files in os.walk(base_path, topdown=False):
        if os.path.normcase(os.path.normpath(root)) == os.path.normcase(os.path.normpath(base_path)):
            continue
        dir_name = os.path.basename(root)
        if dir_name.lower().startswith("season"):
            continue
        try:
            remaining = os.listdir(root)
            if not remaining:
                os.rmdir(root)
                logger.info(f"[ActionPlan] 清理空目录: {root}")
                continue
            # 检查是否只剩垃圾文件（无视频、无子目录）
            has_video = False
            has_subdir = False
            for item in remaining:
                item_path = os.path.join(root, item)
                if os.path.isdir(item_path):
                    has_subdir = True
                    break
                ext = os.path.splitext(item)[1].lower()
                if ext in VIDEO_EXTS:
                    has_video = True
                    break
            if not has_video and not has_subdir:
                # 只剩垃圾文件，全部删除后清理目录
                for item in remaining:
                    item_path = os.path.join(root, item)
                    ext = os.path.splitext(item)[1].lower()
                    if ext in _junk_exts or item.startswith("."):
                        try:
                            os.remove(item_path)
                        except OSError:
                            pass
                # 再次检查是否为空
                if not os.listdir(root):
                    os.rmdir(root)
                    logger.info(f"[ActionPlan] 清理种子目录壳: {root}")
        except OSError:
            pass


def _resolve_plan_whitelist_path(raw_path: str, base_path: str) -> str:
    """将 qB/file_relocator 白名单路径解析为当前工作区中的绝对路径。"""
    if not raw_path:
        return ""

    normalized_base = os.path.normpath(base_path or "")
    normalized_raw = os.path.normpath(raw_path.replace("/", os.sep).replace("\\", os.sep))
    if os.path.isabs(normalized_raw):
        return normalized_raw

    parts = normalized_raw.split(os.sep)
    if len(parts) > 1:
        base_name = os.path.basename(normalized_base)
        if base_name and parts[0].lower() == base_name.lower():
            normalized_raw = os.path.join(*parts[1:])

    return os.path.join(normalized_base, normalized_raw)


def _apply_action_plan_moves(plan_items: list, base_path: str = "", whitelist: List[str] = None) -> list:
    """按 action_plan 直接落盘视频与附属文件。"""
    ops = []
    handled_old_paths = set()
    planned_original_paths = set()
    plan_contexts = []
    target_dir_by_season = {}

    for item in plan_items or []:
        original_path = item.get("original_path") or ""
        target_path = item.get("target_path") or ""
        if not original_path or not target_path or original_path == target_path:
            continue
        if not os.path.exists(original_path):
            continue

        planned_original_paths.add(os.path.normcase(os.path.normpath(os.path.abspath(original_path))))
        source_dir = os.path.dirname(original_path)
        source_base, source_ext = os.path.splitext(os.path.basename(original_path))
        target_dir = os.path.dirname(target_path)
        target_base, target_ext = os.path.splitext(os.path.basename(target_path))
        mapped = item.get("mapped") or {}
        mapped_season = mapped.get("season")
        if mapped_season is not None:
            target_dir_by_season[mapped_season] = target_dir
        plan_contexts.append(
            {
                "source_dir": os.path.abspath(source_dir),
                "target_dir": os.path.abspath(target_dir),
                "season": mapped_season,
            }
        )

        ops.append({
            "action": "move",
            "old": original_path,
            "new": target_path,
            "mkdir": target_dir,
        })
        handled_old_paths.add(os.path.normcase(os.path.normpath(os.path.abspath(original_path))))

        try:
            siblings = os.listdir(source_dir)
        except OSError:
            siblings = []

        for sibling in siblings:
            sibling_path = os.path.join(source_dir, sibling)
            if sibling_path == original_path or not os.path.isfile(sibling_path):
                continue

            sibling_lower = sibling.lower()
            moved = False

            for suffix in _PLAN_POSTER_SUFFIXES:
                if sibling_lower == f"{source_base.lower()}{suffix}":
                    ops.append({
                        "action": "move",
                        "old": sibling_path,
                        "new": os.path.join(target_dir, f"{target_base}{suffix}"),
                        "mkdir": target_dir,
                    })
                    handled_old_paths.add(os.path.normcase(os.path.normpath(os.path.abspath(sibling_path))))
                    moved = True
                    break
            if moved:
                continue

            if sibling_lower.startswith(f"{source_base.lower()}."):
                subtitle_ext = os.path.splitext(sibling)[1].lower()
                if subtitle_ext in _PLAN_SUBTITLE_EXTS:
                    suffix = sibling[len(source_base):]
                    ops.append({
                        "action": "move",
                        "old": sibling_path,
                        "new": os.path.join(target_dir, f"{target_base}{suffix}"),
                        "mkdir": target_dir,
                    })
                    handled_old_paths.add(os.path.normcase(os.path.normpath(os.path.abspath(sibling_path))))

    if whitelist and plan_contexts:
        from organizer import _extract_season_number
        from tmdb_client import parse_filename

        source_dirs = [ctx["source_dir"] for ctx in plan_contexts]
        try:
            common_source_root = os.path.commonpath(source_dirs)
        except ValueError:
            common_source_root = source_dirs[0]

        ancestor_target_dirs = {}
        root_norm = os.path.normcase(os.path.normpath(common_source_root))
        for ctx in plan_contexts:
            current_dir = ctx["source_dir"]
            target_dir = ctx["target_dir"]
            while current_dir:
                current_norm = os.path.normcase(os.path.normpath(current_dir))
                ancestor_target_dirs.setdefault(current_norm, set()).add(target_dir)
                if current_norm == root_norm:
                    break
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:
                    break
                current_dir = parent_dir

        unique_target_dirs = {ctx["target_dir"] for ctx in plan_contexts}
        single_target_dir = next(iter(unique_target_dirs)) if len(unique_target_dirs) == 1 else ""

        def _resolve_extra_target_path(extra_path: str) -> str:
            current_dir = os.path.dirname(extra_path)
            while current_dir:
                current_norm = os.path.normcase(os.path.normpath(current_dir))
                mapped_dirs = ancestor_target_dirs.get(current_norm)
                if mapped_dirs and len(mapped_dirs) == 1:
                    target_dir = next(iter(mapped_dirs))
                    rel_tail = os.path.relpath(extra_path, current_dir)
                    return os.path.join(target_dir, rel_tail)
                if current_norm == root_norm:
                    break
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:
                    break
                current_dir = parent_dir

            rel_path = os.path.relpath(extra_path, common_source_root)
            rel_parts = rel_path.split(os.sep)
            for idx in range(len(rel_parts) - 1):
                season_num = _extract_season_number(rel_parts[idx])
                if season_num is None:
                    continue
                target_dir = target_dir_by_season.get(season_num)
                if target_dir:
                    rel_tail = os.path.join(*rel_parts[idx + 1:]) if idx + 1 < len(rel_parts) else os.path.basename(extra_path)
                    return os.path.join(target_dir, rel_tail)

            parsed = parse_filename(os.path.basename(extra_path))
            season_num = parsed.get("season")
            if season_num is not None and season_num in target_dir_by_season:
                return os.path.join(target_dir_by_season[season_num], os.path.basename(extra_path))

            if single_target_dir:
                rel_tail = os.path.relpath(extra_path, common_source_root)
                return os.path.join(single_target_dir, rel_tail)

            return ""

        # 构建集号→目标文件名映射，用于字幕文件重命名
        episode_target_map = {}  # {(season, episode): target_base_name}
        for item in plan_items or []:
            mapped = item.get("mapped") or {}
            s, e = mapped.get("season"), mapped.get("episode")
            tp = item.get("target_path") or ""
            if s is not None and e is not None and tp:
                t_base = os.path.splitext(os.path.basename(tp))[0]
                episode_target_map[(s, e)] = t_base

        for raw_path in whitelist:
            abs_path = os.path.abspath(_resolve_plan_whitelist_path(raw_path, base_path))
            norm_abs_path = os.path.normcase(os.path.normpath(abs_path))
            if not os.path.isfile(abs_path):
                continue
            if norm_abs_path in handled_old_paths or norm_abs_path in planned_original_paths:
                continue
            target_path = _resolve_extra_target_path(abs_path)
            if not target_path:
                continue

            # 字幕文件扁平化：如果字幕被放到了子目录中（如 Season 01/Subs/xxx.ass），
            # 将其提升到和视频同级，并尝试用视频的标准名作为前缀
            file_ext = os.path.splitext(abs_path)[1].lower()
            if file_ext in _PLAN_SUBTITLE_EXTS:
                target_dir_resolved = os.path.dirname(target_path)
                # 检查目标路径是否在某个 plan target_dir 的子目录中
                for ctx in plan_contexts:
                    ctx_target = ctx["target_dir"]
                    if (os.path.normcase(target_dir_resolved) != os.path.normcase(ctx_target)
                            and os.path.normcase(target_dir_resolved).startswith(
                                os.path.normcase(ctx_target) + os.sep)):
                        # 字幕在子目录中，需要扁平化到 ctx_target
                        sub_basename = os.path.basename(abs_path)
                        # 尝试从字幕文件名解析集号，匹配到对应视频的标准名
                        # 多重扩展名处理（如 xxx.chs.ass → lang_suffix=".chs.ass"）
                        lang_suffix = ""
                        temp_name = sub_basename
                        while True:
                            base_part, ext_part = os.path.splitext(temp_name)
                            if ext_part.lower() in _PLAN_SUBTITLE_EXTS:
                                lang_suffix = ext_part + lang_suffix
                                temp_name = base_part
                            elif ext_part.lower() in {".chs", ".cht", ".sc", ".tc", ".zh",
                                                      ".en", ".jp", ".ja", ".ko",
                                                      ".chi", ".eng", ".jpn", ".kor",
                                                      ".zh-hans", ".zh-hant",
                                                      ".simplified", ".traditional",
                                                      ".chinese", ".japanese", ".english",
                                                      ".chn"}:
                                lang_suffix = ext_part + lang_suffix
                                temp_name = base_part
                            else:
                                break
                        # 用去掉语言标签后的核心名解析集号（parse_filename 不认识 .chs.ass）
                        parsed_sub = parse_filename(temp_name)
                        sub_season = parsed_sub.get("season")
                        sub_episode = parsed_sub.get("episode")

                        matched_target_base = None
                        if sub_episode is not None:
                            # 有集号：精确匹配
                            lookup_season = sub_season if sub_season is not None else (ctx.get("season") or 1)
                            matched_target_base = episode_target_map.get((lookup_season, sub_episode))
                        if matched_target_base and lang_suffix:
                            target_path = os.path.join(ctx_target, matched_target_base + lang_suffix)
                        else:
                            # 无法匹配集号，直接扁平化文件名
                            target_path = os.path.join(ctx_target, sub_basename)
                        break
            else:
                # 非字幕文件（字体包、OAD 等）：不应跟随视频进入 Season 目录
                # 如果目标路径在 Season 目录下（直接或子目录），提升到剧集根目录
                target_dir_resolved = os.path.dirname(target_path)
                for ctx in plan_contexts:
                    ctx_target = ctx["target_dir"]
                    ctx_target_norm = os.path.normcase(ctx_target)
                    target_dir_norm = os.path.normcase(target_dir_resolved)
                    if (target_dir_norm == ctx_target_norm
                            or target_dir_norm.startswith(ctx_target_norm + os.sep)):
                        # 文件被放到了 Season 目录下，提升到 base_path 下
                        if target_dir_norm == ctx_target_norm:
                            # 直接在 Season 下：提升到 base_path
                            target_path = os.path.join(os.path.abspath(base_path), os.path.basename(abs_path))
                        else:
                            # 在 Season 的子目录中：保留子目录结构，提升到 base_path
                            rel_in_season = os.path.relpath(target_path, ctx_target)
                            target_path = os.path.join(os.path.abspath(base_path), rel_in_season)
                        break

            ops.append({
                "action": "move",
                "old": abs_path,
                "new": target_path,
                "mkdir": os.path.dirname(target_path),
            })
            handled_old_paths.add(norm_abs_path)

    for op in ops:
        if op.get("mkdir"):
            os.makedirs(op["mkdir"], exist_ok=True)
        if os.path.exists(op["old"]) and not os.path.exists(op["new"]):
            shutil.move(op["old"], op["new"])

    # 清理空的种子目录壳：所有文件移走后，种子文件夹可能残留空子目录
    if base_path and os.path.isdir(base_path):
        _cleanup_empty_dirs(base_path)

    return ops
