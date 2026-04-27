"""文件归位器：V3 整理流水线的客户端，两段式提交（推演+落盘）。

核心原则：
- 不实现任何文件名解析或重命名逻辑
- 复用 V3 流水线（organize_full 的内部逻辑）完成解析、重命名、NFO 生成
- 两段式：dry_run 推演 → 冲突检测 → 落盘执行

NFO 回收精准狙击规则：
- 移走旧视频文件
- 移走同名 episode.nfo 和海报
- 移走目录级 movie.nfo 和 season.nfo
- 绝对不可触碰 tvshow.nfo
"""

import os
import logging
import re
import glob
import time
from typing import List, Optional, Dict
from pydantic import BaseModel

from download_manager import DownloadTask
from recycle_bin import RecycleBin
from core.constants import RECYCLE_DIR_NFO_AND_ART, VIDEO_EXTS

logger = logging.getLogger(__name__)
class CoexistPair(BaseModel):
    """新旧文件共存冲突对"""
    new_file: str          # Action Plan 中的目标文件路径
    old_file: str          # 目标目录中已存在的旧文件路径
    new_size_gb: float = 0.0
    old_size_gb: float = 0.0
    category: str = "video"  # "video" | "folder" | "non_video" — 用于前端分类展示
    is_folder: bool = False  # 是否是文件夹


class RelocateResult(BaseModel):
    """归位结果"""
    success: bool = False
    status: str = ""       # "archived" | "awaiting_confirm" | "failed"
    action_plan: dict = {}
    relocated_count: int = 0
    coexist_pairs: List[CoexistPair] = []
    error: str = ""


def _safe_print(msg: str):
    """安全打印（避免 Windows GBK 编码崩溃）"""
    try:
        logger.info(msg)
    except UnicodeEncodeError:
        try:
            logger.error(msg.encode("utf-8", errors="replace").decode("utf-8"))
        except Exception:
            pass


def _scan_disk_for_whitelist(save_path: str) -> List[str]:
    """当 qB 白名单不可用时，通过磁盘扫描自动构建白名单。
    
    策略：扫描 save_path 下的子目录，找到包含视频的子目录，
    将其中所有文件视为"新资源"。
    
    适用场景：
    - downloader_hash 为空（种子已删除但文件还在）
    - qB 无法返回文件列表
    
    返回相对于 save_path 的文件路径列表。
    """
    result = []
    if not os.path.isdir(save_path):
        return result
    
    # 扫描 save_path 下的所有子目录，找到"看起来像种子文件夹"的目录
    # 特征：目录名包含字幕组标签、编码信息、分辨率等
    torrent_dir_patterns = re.compile(
        r'\[.*?\]|BDRip|BluRay|WEB-DL|HEVC|x264|x265|1080p|720p|FLAC|AAC|10-?bit',
        re.IGNORECASE
    )
    
    for item in os.listdir(save_path):
        item_path = os.path.join(save_path, item)
        if not os.path.isdir(item_path):
            continue
        if item.startswith('.') or item.startswith('[旧资源备份]'):
            continue
        
        # 检查是否像种子文件夹（包含字幕组标签等特征）
        if torrent_dir_patterns.search(item):
            # 收集该目录下所有文件
            for root, _, files in os.walk(item_path):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), save_path)
                    result.append(rel)
    
    if result:
        _safe_print(f"[Relocator] 磁盘扫描构建白名单: {len(result)} 个文件")
    
    return result


class FileRelocator:
    """文件归位器：作为 V3 整理流水线的客户端。"""

    def __init__(self, recycle_bin: RecycleBin, run_pipeline_fn=None):
        """
        参数:
            recycle_bin: 回收站实例
            run_pipeline_fn: V3 流水线调用函数，签名:
                fn(path, dry_run, use_ai, category_hint, action_plan=None) -> dict
                由 main.py 注入，避免循环导入
        """
        self.recycle_bin = recycle_bin
        self._run_pipeline = run_pipeline_fn

    async def relocate(self, task: DownloadTask, new_files_whitelist: List[str] = None) -> RelocateResult:
        """归档整理探测（原洗版探测）。
        
        1. 获取新资源白名单（由外部注入，或磁盘扫描自动构建）。
        2. 对新资源进行 V3 推演，获取标准化改名预览。
        3. 对旧资源（非名单内文件）进行扫描，探测同季冲突。
        """
        if not self._run_pipeline:
            return RelocateResult(success=False, status="failed", error="整理引擎未就绪")

        # 确定扫描路径：直接扫描正式下载目录
        scan_path = task.save_path
        if not os.path.exists(scan_path or ""):
            return RelocateResult(success=False, status="failed", error=f"下载目录尚未就绪: {scan_path}")

        # 白名单兜底：如果 qB 没给白名单，通过磁盘扫描自动构建
        if not new_files_whitelist:
            new_files_whitelist = _scan_disk_for_whitelist(scan_path)
            if new_files_whitelist:
                _safe_print(f"[Relocator] 使用磁盘扫描白名单（{len(new_files_whitelist)} 个文件）")

        # ── 第一步：对新资源进行标准化命名推演 ──
        try:
            plan = await self._run_pipeline(
                path=scan_path,
                dry_run=True,
                use_ai=True,
                whitelist=new_files_whitelist if new_files_whitelist else None
            )
        except Exception as e:
            import traceback
            try:
                traceback.print_exc()
            except UnicodeEncodeError:
                pass
            return RelocateResult(success=False, status="failed", error=f"推演失败: {e}")

        if not plan:
            return RelocateResult(success=False, status="failed", error="无法识别新下载的文件结构")

        # ── 第二步：识别并对比老兵 ──
        conflicts = self._detect_conflicts_v2(plan, scan_path, new_files_whitelist)

        if conflicts:
            return RelocateResult(
                success=False,
                status="awaiting_confirm",
                action_plan=plan,
                coexist_pairs=conflicts,
            )

        # 无冲突 → 直接返回归档状态
        return RelocateResult(
            success=True,
            status="archived",
            action_plan=plan,
        )

    async def confirm_replace(self, task: DownloadTask, plan: dict) -> RelocateResult:
        """用户确认替换：旧资源入回收站 -> 新资源整理归档。"""
        whitelist = plan.get("whitelist", [])
        if not whitelist:
            whitelist = _scan_disk_for_whitelist(task.save_path)
        conflicts = self._detect_conflicts_v2(plan, task.save_path, whitelist)

        # 旧文件入回收站
        for pair in conflicts:
            ok = self._recycle_old_files(pair, task.id)
            if not ok:
                return RelocateResult(
                    success=False, status="failed",
                    error=f"旧资源入回收站失败: {pair.old_file}",
                )

        # 障碍清除，执行落盘
        return await self._execute_plan(task, plan)

    async def archive_both(self, task: DownloadTask, conflicts: List[CoexistPair]) -> RelocateResult:
        """用户确认保留两者：将旧资源移动到 [OLD] 子目录归档。"""
        if not conflicts:
            return RelocateResult(success=True, status="archived", message="已跳过（无旧资源）")

        base_dir = task.save_path
        old_dir_name = f"[旧资源备份] - {os.path.basename(base_dir)}"
        old_dir = os.path.join(base_dir, old_dir_name)
        
        try:
            os.makedirs(old_dir, exist_ok=True)
            for pair in conflicts:
                src = pair.old_file
                if os.path.exists(src):
                    dst = os.path.join(old_dir, os.path.basename(src))
                    if os.path.exists(dst):
                        base, ext = os.path.splitext(dst)
                        dst = f"{base}_{int(time.time())}{ext}"
                    os.rename(src, dst)
            
            return RelocateResult(success=True, status="archived", message="已完成共处归档")
        except Exception as e:
            return RelocateResult(success=False, status="failed", error=f"封箱归档失败: {e}")

    def cancel_replace(self, task: DownloadTask) -> RelocateResult:
        """用户取消替换：沙盒中的新文件入回收站。"""
        sandbox = task.download_dir
        if not sandbox or not os.path.isdir(sandbox):
            return RelocateResult(success=False, status="failed", error="沙盒目录不存在")

        recycled = 0
        for root, _, files in os.walk(sandbox):
            for f in files:
                fpath = os.path.join(root, f)
                self.recycle_bin.move_to_bin(fpath, task.id)
                recycled += 1

        return RelocateResult(success=True, status="cancelled", relocated_count=recycled)

    async def _execute_plan(self, task: DownloadTask, plan: dict) -> RelocateResult:
        """调用整理引擎落盘执行。"""
        try:
            execute_path = task.save_path or task.download_dir
            result = await self._run_pipeline(
                path=execute_path,
                dry_run=False,
                use_ai=False,
                action_plan=plan,
            )

            steps = result.get("steps", {})
            total_ops = sum(
                v if isinstance(v, int) else (v.get("nfo_written", 0) if isinstance(v, dict) else 0)
                for v in steps.values()
            )
            return RelocateResult(
                success=True,
                status="archived",
                action_plan=plan,
                relocated_count=total_ops,
            )
        except Exception as e:
            return RelocateResult(success=False, status="failed", error=f"整理执行失败: {e}")

    def _detect_conflicts_v2(self, plan: dict, target_base: str, whitelist: List[str]) -> List[CoexistPair]:
        """V2 冲突探测：通过白名单区分新旧资源。
        
        白名单匹配策略（三层兜底）：
        - 第一层：绝对路径精确匹配（种子目录名 == save_path 目录名）
        - 第二层：文件名匹配（种子目录名 ≠ save_path 目录名，但文件名相同）
        - 第三层：种子子目录名匹配（排除新下载的整个文件夹）
        """
        from tmdb_client import parse_filename
        
        conflicts = []
        plan_items = plan.get("plan", [])
        if not plan_items:
            return conflicts

        target_base = os.path.normpath(os.path.abspath(target_base))

        def _collect_planned_targets() -> tuple[set, set]:
            """收集当前 plan 的目标文件与目标目录，避免执行后重跑时把新资源误判成旧资源。"""
            planned_files = set()
            planned_dirs = set()
            for item in plan_items:
                if not item:
                    continue
                target_path = item.get("target_path") or ""
                if not target_path:
                    continue
                norm_target_path = os.path.normcase(os.path.normpath(os.path.abspath(target_path)))
                planned_files.add(norm_target_path)
                current_dir = os.path.dirname(norm_target_path)
                base_norm = os.path.normcase(target_base)
                while current_dir and os.path.normcase(current_dir).startswith(base_norm):
                    if os.path.normcase(current_dir) == base_norm:
                        break
                    planned_dirs.add(os.path.normcase(current_dir))
                    parent_dir = os.path.dirname(current_dir)
                    if parent_dir == current_dir:
                        break
                    current_dir = parent_dir
            return planned_files, planned_dirs
        
        # 智能路径拼合逻辑
        def get_abs_path(rel_p, base):
            rel_p = rel_p.replace("/", os.sep).replace("\\", os.sep)
            rel_p = os.path.normpath(rel_p)
            base = os.path.normpath(base)
            
            if os.path.isabs(rel_p):
                return rel_p
            
            parts = rel_p.split(os.sep)
            if len(parts) > 1:
                first_dir = parts[0]
                base_name = os.path.basename(base)
                if first_dir.lower() == base_name.lower():
                    modified_rel = os.path.join(*parts[1:])
                    return os.path.join(base, modified_rel)
                    
            return os.path.join(base, rel_p)

        # ── 构建三层白名单集合 ──
        w_path_set = set()       # 绝对路径匹配
        w_basename_set = set()   # 文件名兜底匹配
        w_subdir_set = set()     # 种子内所有层级的目录名匹配
        planned_target_files, planned_target_dirs = _collect_planned_targets()
        
        if whitelist:
            base_name_lower = os.path.normcase(os.path.basename(target_base))
            for p in whitelist:
                # 第一层：绝对路径
                abs_p = get_abs_path(p, target_base)
                w_path_set.add(os.path.normcase(os.path.normpath(abs_p)))
                
                # 第二层：文件名（无论路径怎么拼，文件名总是对的）
                p_sep = p.replace("/", os.sep).replace("\\", os.sep)
                basename = os.path.basename(p_sep)
                if basename:
                    w_basename_set.add(os.path.normcase(basename))
                
                # 第三层：种子内所有层级的目录名（SPs、音乐CD等子目录都要收集）
                p_norm = os.path.normpath(p_sep)
                parts = p_norm.split(os.sep)
                # 收集路径中每一层目录名（排除文件名本身，即最后一个 part）
                for i in range(len(parts) - 1):
                    dir_name = os.path.normcase(parts[i])
                    if dir_name and dir_name != base_name_lower:
                        w_subdir_set.add(dir_name)
                    # 如果第一层和 save_path 同名，跳过它但继续收集后续层
                # 同时把绝对路径版本的中间目录也加入
                abs_dir = os.path.dirname(os.path.normcase(os.path.normpath(abs_p)))
                while abs_dir and os.path.normcase(abs_dir) != os.path.normcase(target_base):
                    w_path_set.add(abs_dir)
                    abs_dir = os.path.dirname(abs_dir)

        _safe_print(
            f"[Conflicts] 白名单: paths={len(w_path_set)}, basenames={len(w_basename_set)}, "
            f"subdirs={len(w_subdir_set)}, planned_files={len(planned_target_files)}, "
            f"planned_dirs={len(planned_target_dirs)}"
        )

        def _is_file_in_whitelist(file_path: str, file_name: str) -> bool:
            """判断文件是否在白名单中"""
            norm_file_path = os.path.normcase(os.path.normpath(file_path))
            if norm_file_path in planned_target_files:
                return True
            if not whitelist:
                return False
            # 第一层：绝对路径
            if norm_file_path in w_path_set:
                return True
            # 第二层：文件名
            if os.path.normcase(file_name) in w_basename_set:
                return True
            return False

        def _is_dir_in_whitelist(dir_path: str, dir_name: str) -> bool:
            """判断目录是否属于新下载的种子文件夹"""
            norm_dir_path = os.path.normcase(os.path.normpath(dir_path))
            if norm_dir_path in planned_target_dirs:
                has_unplanned_video = False
                try:
                    for walk_root, _, walk_files in os.walk(dir_path):
                        for walk_file in walk_files:
                            if os.path.splitext(walk_file)[1].lower() not in VIDEO_EXTS:
                                continue
                            walk_path = os.path.normcase(os.path.normpath(os.path.join(walk_root, walk_file)))
                            if walk_path not in planned_target_files:
                                has_unplanned_video = True
                                break
                        if has_unplanned_video:
                            break
                except Exception:
                    has_unplanned_video = True
                if not has_unplanned_video:
                    return True
            if not whitelist:
                return False
            if norm_dir_path in w_path_set:
                return True
            if os.path.normcase(dir_name) in w_subdir_set:
                return True
            return False

        # ── 扫描目录下的所有旧视频 ──
        old_candidates = []
        if os.path.isdir(target_base):
            for root, dirs, files in os.walk(target_base):
                norm_root = os.path.normpath(root).lower()
                if any(x in norm_root for x in [".recycle", "$recycle.bin", "#recycle", "@recycle"]):
                    continue
                if "[旧资源备份]" in root:
                    continue
                
                # 扫描散装视频文件
                for f in files:
                    if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                        f_path = os.path.abspath(os.path.join(root, f))
                        if not _is_file_in_whitelist(f_path, f):
                            p_info = parse_filename(f)
                            old_candidates.append({
                                "path": f_path,
                                "season": p_info.get("season"),
                                "raw_name": f,
                                "is_folder": False
                            })
                
                # 扫描非白名单子目录
                from organizer import _is_ignorable_subdir
                for d in dirs:
                    d_path = os.path.abspath(os.path.join(root, d))
                    
                    if d.startswith('.') or _is_ignorable_subdir(d) or _is_dir_in_whitelist(d_path, d):
                        continue
                        
                    has_video = False
                    try:
                        for item in os.listdir(d_path):
                            if os.path.splitext(item)[1].lower() in VIDEO_EXTS or os.path.isdir(os.path.join(d_path, item)):
                                has_video = True
                                break
                    except Exception:
                        pass
                    
                    if has_video:
                        from organizer import _extract_season_number

                        s_num = _extract_season_number(d)
                        old_candidates.append({
                            "path": d_path,
                            "season": s_num,
                            "raw_name": d,
                            "is_folder": True
                        })
        
        _safe_print(f"[Conflicts] 旧资源候选: {len(old_candidates)} 个")

        # ── 季号判定 ──
        involved_seasons = set()
        for item in plan_items:
            mapped = item.get("mapped") if item else None
            if mapped:
                s = mapped.get("season")
            else:
                s = None
            if s is not None:
                involved_seasons.add(s)
            else:
                involved_seasons.add(-1)
            
        if not involved_seasons and plan_items:
            involved_seasons.add(-1)
            
        example_new = plan_items[0].get("target_path", "新兵重命名")

        # ── 匹配：找出磁盘上与新资源同季的"旧视频" ──
        for old in old_candidates:
            o_season = old.get("season")
            is_folder = old.get("is_folder", False)
            matched = False
            if -1 in involved_seasons: 
                matched = True
            elif o_season is not None and o_season in involved_seasons: 
                matched = True
            elif o_season is None and 1 in involved_seasons:
                matched = True
            elif not involved_seasons and plan_items:
                matched = True
                
            if matched:
                old_path = old["path"]
                old_size = 0
                
                # 判断分类
                if is_folder:
                    # 文件夹：检查内部是否有视频文件来决定分类
                    has_video_inside = False
                    try:
                        for item in os.listdir(old_path):
                            if os.path.splitext(item)[1].lower() in VIDEO_EXTS:
                                has_video_inside = True
                                break
                    except Exception:
                        pass
                    category = "folder" if has_video_inside else "non_video"
                    # 文件夹大小取内部所有文件总和
                    try:
                        for r, _, fs in os.walk(old_path):
                            for ff in fs:
                                fp = os.path.join(r, ff)
                                if os.path.isfile(fp):
                                    old_size += os.path.getsize(fp)
                    except Exception:
                        pass
                else:
                    category = "video"
                    old_size = os.path.getsize(old_path) if os.path.exists(old_path) else 0
                
                conflicts.append(CoexistPair(
                    new_file=example_new,
                    old_file=old_path,
                    new_size_gb=round(old_size / (1024 ** 3), 3),
                    old_size_gb=round(old_size / (1024 ** 3), 3),
                    category=category,
                    is_folder=is_folder,
                ))
        
        _safe_print(f"[Conflicts] 最终冲突: {len(conflicts)} 对")
        return conflicts

    def _recycle_old_files(self, pair: CoexistPair, task_id: str) -> bool:
        """将旧文件及其配套元数据移入回收站。

        精准狙击规则：
        1. 旧视频文件 → 回收站
        2. 同名 episode.nfo → 回收站（非 tvshow.nfo）
        3. 同名海报（-poster.jpg/-thumb.jpg/-fanart.jpg）→ 回收站
        4. 目录级 movie.nfo → 回收站
        5. 目录级 season.nfo → 回收站
        6. tvshow.nfo → 绝对不动
        """
        old_video = pair.old_file
        if not old_video or not os.path.exists(old_video):
            return True  # 文件已不存在，视为成功

        base = os.path.splitext(old_video)[0]
        target_dir = os.path.dirname(old_video)

        # 1. 旧视频文件
        entry = self.recycle_bin.move_to_bin(old_video, task_id)
        if not entry:
            return False

        # 2. 同名 NFO（episode.nfo，排除 tvshow.nfo）
        nfo_path = base + ".nfo"
        if os.path.exists(nfo_path) and not nfo_path.endswith("tvshow.nfo"):
            self.recycle_bin.move_to_bin(nfo_path, task_id)

        # 3. 同名海报
        for suffix in ["-poster.jpg", "-thumb.jpg", "-fanart.jpg"]:
            poster = base + suffix
            if os.path.exists(poster):
                self.recycle_bin.move_to_bin(poster, task_id)

        # 4 & 5. 目录级 NFO：movie.nfo 和 season.nfo（绝对不动 tvshow.nfo）
        for dir_nfo in RECYCLE_DIR_NFO_AND_ART:
            dir_file_path = os.path.join(target_dir, dir_nfo)
            if os.path.exists(dir_file_path):
                self.recycle_bin.move_to_bin(dir_file_path, task_id)
        
        # 6. 查找同级/父级的 seasonXX-poster.jpg 等
        parent_dir = os.path.dirname(target_dir)
        season_num = None
        dir_name = os.path.basename(target_dir).lower()
        if "season" in dir_name:
            m = re.search(r"season\s*(\d+)", dir_name)
            if m:
                season_num = int(m.group(1))
        
        if season_num is not None:
            prefix = f"season{season_num:02d}-"
            for extra in ["poster.jpg", "fanart.jpg", "thumb.jpg", "banner.jpg"]:
                extra_path = os.path.join(parent_dir, prefix + extra)
                if os.path.exists(extra_path):
                    self.recycle_bin.move_to_bin(extra_path, task_id)

        return True
