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
import glob
from typing import List, Optional
from pydantic import BaseModel

from download_manager import DownloadTask
from recycle_bin import RecycleBin


class CoexistPair(BaseModel):
    """新旧文件共存冲突对"""
    new_file: str          # Action Plan 中的目标文件路径
    old_file: str          # 目标目录中已存在的旧文件路径
    new_size_gb: float = 0.0
    old_size_gb: float = 0.0


class RelocateResult(BaseModel):
    """归位结果"""
    success: bool = False
    status: str = ""       # "archived" | "awaiting_confirm" | "failed"
    action_plan: dict = {}
    relocated_count: int = 0
    coexist_pairs: List[CoexistPair] = []
    error: str = ""


# 视频文件扩展名
_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}


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
        
        1. 获取新资源白名单（由外部注入）。
        2. 对新资源进行 V3 推演，获取标准化改名预览。
        3. 对旧资源（非名单内文件）进行扫描，探测同季冲突。
        """
        if not self._run_pipeline:
            return RelocateResult(success=False, status="failed", error="整理引擎未就绪")

        # 确定扫描路径：直接扫描正式下载目录
        scan_path = task.save_path
        if not os.path.exists(scan_path or ""):
             # 如果 save_path 还没创建（极少见），fallback 到根目录
             return RelocateResult(success=False, status="failed", error=f"下载目录尚未就绪: {scan_path}")

        print(f"[Relocator] 开始原地整理探测: {scan_path}")
        print(f"[Relocator] 已识别新资源数: {len(new_files_whitelist) if new_files_whitelist else 0}")

        # ── 第一步：对新资源进行标准化命名推演 ──
        try:
            plan = await self._run_pipeline(
                path=scan_path,
                dry_run=True,
                use_ai=True,
                whitelist=new_files_whitelist
            )
        except Exception as e:
            print(f"[Relocator] ❌ 推演失败: {e}")
            import traceback; traceback.print_exc()
            return RelocateResult(success=False, status="failed", error=f"推演失败: {e}")


        if not plan:
            return RelocateResult(success=False, status="failed", error="无法识别新下载的文件结构")

        # ── 第二步：识别并对比老兵 ──
        # 此时的 conflicts 列表就是我们的“待回收老兵”清单
        conflicts = self._detect_conflicts_v2(plan, scan_path, new_files_whitelist)

        if conflicts:
            return RelocateResult(
                success=False,
                status="awaiting_confirm",
                action_plan=plan,
                coexist_pairs=conflicts,
            )

        # 无冲突 → 直接返回归档状态（让 API 层决定是否标记归档）
        return RelocateResult(
            success=True,
            status="archived",
            action_plan=plan,
        )

    async def confirm_replace(self, task: DownloadTask, plan: dict) -> RelocateResult:
        """用户确认替换：旧资源入回收站 -> 新资源整理归档。"""
        # 重新探测冲突确保实时性
        # 注意：这里需要再次传入 whitelist，因为 confirm_replace 此时没有这个信息
        # 生产环境下建议在 plan 中携带 whitelist
        whitelist = plan.get("whitelist", [])
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
                    # 如果目标已存在，加后缀
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
            result = await self._run_pipeline(
                path=task.download_dir,
                dry_run=False,
                use_ai=False,
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
        1. whitelist 中的文件是刚刚下载的任务文件（新资源）。
        2. target_base 目录下，不在名单中且属于同一季的文件是“旧资源”。
        """
        from tmdb_client import parse_filename
        import os
        
        conflicts = []
        plan_items = plan.get("plan", [])
        if not plan_items:
            return conflicts

        target_base = os.path.abspath(target_base)
        print(f"\n[DEBUG_RELOCATE] --- 开始冲突探测 ---")
        print(f"[DEBUG_RELOCATE] target_base: {target_base}")
        
        # 智能路径拼合逻辑
        def get_abs_path(rel_p, base):
            # 1. 强制标准化分隔符：彻底处理 qB 的 / 或 \
            # 如果是正斜杠 /，我们在 Windows 下显式转为 os.sep
            rel_p = rel_p.replace("/", os.sep).replace("\\", os.sep)
            rel_p = os.path.normpath(rel_p)
            base = os.path.normpath(base)
            
            if os.path.isabs(rel_p): return rel_p
            
            # 使用 split 拆分。由于已经对齐了 os.sep，现在能正确拆分
            parts = rel_p.split(os.sep)
            if len(parts) > 1:
                first_dir = parts[0]
                base_name = os.path.basename(base)
                # 2. 智能去重叠逻辑：如果种子里的第一层目录就是当前所在目录名
                if first_dir.lower() == base_name.lower():
                    modified_rel = os.path.join(*parts[1:])
                    abs_p = os.path.join(base, modified_rel)
                    print(f"[DEBUG_PATH] Overlap Stripped: '{first_dir}', Final: {abs_p}")
                    return abs_p
                    
            return os.path.join(base, rel_p)

        # 规范化白名单
        w_set = set()
        if whitelist:
            for p in whitelist:
                abs_p = get_abs_path(p, target_base)
                w_set.add(os.path.normcase(os.path.normpath(abs_p)))
        
        print(f"[DEBUG_RELOCATE] w_set (size): {len(w_set)}")
        if w_set: print(f"[DEBUG_RELOCATE] w_set (first 3): {list(w_set)[:3]}")

        # 1. 扫描目录下的所有旧视频
        old_candidates = []
        if os.path.isdir(target_base):
            for root, _, files in os.walk(target_base):
                norm_root = os.path.normpath(root).lower()
                if any(x in norm_root for x in [".recycle", "$recycle.bin", "#recycle", "@recycle"]): continue
                if "[旧资源备份]" in root: continue
                
                for f in files:
                    if os.path.splitext(f)[1].lower() in _VIDEO_EXTS:
                        f_path = os.path.abspath(os.path.join(root, f))
                        f_norm = os.path.normcase(os.path.normpath(f_path))
                        if f_norm not in w_set:
                            p_info = parse_filename(f)
                            old_candidates.append({
                                "path": f_path,
                                "season": p_info.get("season"),
                                "raw_name": f
                            })
                            if len(old_candidates) <= 3:
                                print(f"[DEBUG_RELOCATE] Found Old Candidate: {f_norm}")
        
        print(f"[DEBUG_RELOCATE] Total Old Candidates: {len(old_candidates)}")

        # 2. 季号判定
        involved_seasons = set()
        for item in plan_items:
            s = item.get("mapped", {}).get("season")
            if s is not None:
                involved_seasons.add(s)
            else:
                involved_seasons.add(-1)
        
        print(f"[Debug] w_set: {list(w_set)[:5]}")
        print(f"[Debug] old_candidates count: {len(old_candidates)}")
            
        # 兜底：如果识别不到季号（如单文件电影），则开启全局匹配模式 (-1)
        if not involved_seasons and plan_items:
            involved_seasons.add(-1)
            
        # 选取一个代表性的新兵预览名（用于表格展示）
        example_new = plan_items[0].get("target_path", "新兵重命名")

        # 3. 匹配：找出磁盘上与新资源同季的“旧视频”
        for old in old_candidates:
            o_season = old.get("season")
            matched = False
            # 如果新资源是全局匹配，或者季号相同
            if -1 in involved_seasons: 
                matched = True
            elif o_season is not None and o_season in involved_seasons: 
                matched = True
            elif not involved_seasons and plan_items:
                # 极端兜底：如果完全推导不出季号但有推算项，为安全起见也算冲突
                matched = True
                
            if matched:
                old_size = os.path.getsize(old["path"]) if os.path.exists(old["path"]) else 0
                conflicts.append(CoexistPair(
                    new_file=example_new,
                    old_file=old["path"],
                    new_size_gb=0.0,
                    old_size_gb=round(old_size / (1024 ** 3), 3)
                ))
            
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
        for dir_nfo in ["movie.nfo", "season.nfo", "poster.jpg", "fanart.jpg", "banner.jpg"]:
            dir_file_path = os.path.join(target_dir, dir_nfo)
            if os.path.exists(dir_file_path):
                self.recycle_bin.move_to_bin(dir_file_path, task_id)
        
        # 6. 查找同级/父级的 seasonXX-poster.jpg 等
        # 如果当前在 Season X 目录下，我们需要清理父目录里的该季海报
        parent_dir = os.path.dirname(target_dir)
        season_num = None
        # 尝试从路径中提取季号 (例如 .../Season 01/...)
        dir_name = os.path.basename(target_dir).lower()
        if "season" in dir_name:
            import re
            m = re.search(r"season\s*(\d+)", dir_name)
            if m:
                season_num = int(m.group(1))
        
        if season_num is not None:
             # 清理父目录下的 seasonXX-poster.jpg 等
             prefix = f"season{season_num:02d}-"
             for extra in ["poster.jpg", "fanart.jpg", "thumb.jpg", "banner.jpg"]:
                 extra_path = os.path.join(parent_dir, prefix + extra)
                 if os.path.exists(extra_path):
                     self.recycle_bin.move_to_bin(extra_path, task_id)

        return True
