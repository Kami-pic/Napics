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

    def relocate(self, task: DownloadTask) -> RelocateResult:
        """归位工作流（两段式提交）。

        第一步 — 推演（dry_run=True）：
        1. 调用 V3 流水线推演，获取 Action Plan
        2. 解析 Plan 中的目标路径，检测冲突
        3. 有冲突 → awaiting_confirm；无冲突 → 直接执行

        第二步 — 执行（dry_run=False）：
        4. 调用 V3 流水线落盘
        5. 更新任务状态为 archived
        """
        if not self._run_pipeline:
            return RelocateResult(success=False, status="failed", error="V3 流水线未注入")

        sandbox = task.download_dir
        if not sandbox or not os.path.isdir(sandbox):
            return RelocateResult(success=False, status="failed", error=f"沙盒目录不存在: {sandbox}")

        # ── 第一步：推演 ──
        try:
            plan = self._run_pipeline(
                path=sandbox,
                dry_run=True,
                use_ai=True,
                category_hint=task.category_hint,
            )
        except Exception as e:
            return RelocateResult(success=False, status="failed", error=f"V3 推演失败: {e}")

        if not plan:
            return RelocateResult(success=False, status="failed", error="V3 流水线返回空 Plan")

        # 检测冲突：Plan 中的目标路径是否已有旧文件
        conflicts = self._detect_conflicts(plan, task.save_path)

        if conflicts:
            return RelocateResult(
                success=False,
                status="awaiting_confirm",
                action_plan=plan,
                coexist_pairs=conflicts,
            )

        # 无冲突，直接执行
        return self._execute_plan(task, plan)

    def confirm_replace(self, task: DownloadTask, plan: dict) -> RelocateResult:
        """用户确认替换：旧文件入回收站 → V3 落盘。

        NFO 精准狙击规则：
        1. 移走旧视频文件
        2. 移走同名 episode.nfo 和海报（-poster.jpg/-thumb.jpg/-fanart.jpg）
        3. 移走目录级 movie.nfo 和 season.nfo
        4. 绝对不动 tvshow.nfo
        """
        conflicts = self._detect_conflicts(plan, task.save_path)

        # 旧文件入回收站
        for pair in conflicts:
            ok = self._recycle_old_files(pair, task.id)
            if not ok:
                return RelocateResult(
                    success=False, status="failed",
                    error=f"旧文件入回收站失败: {pair.old_file}",
                )

        # 障碍清除，执行 V3 落盘
        return self._execute_plan(task, plan)

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

    def _execute_plan(self, task: DownloadTask, plan: dict) -> RelocateResult:
        """调用 V3 流水线落盘执行。"""
        try:
            result = self._run_pipeline(
                path=task.download_dir,
                dry_run=False,
                use_ai=False,
                category_hint=task.category_hint,
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
            return RelocateResult(success=False, status="failed", error=f"V3 执行失败: {e}")

    def _detect_conflicts(self, plan: dict, target_base: str) -> List[CoexistPair]:
        """解析 V3 Action Plan，检测目标目录中是否已存在同名视频文件。

        Plan 结构中 plan_items 的每个 item 可能包含 target_path（V3 计算的目标路径）。
        如果 target_path 已存在旧文件，则构成冲突。
        """
        conflicts = []
        plan_items = plan.get("plan", [])

        for item in plan_items:
            target_path = item.get("target_path", "")
            if not target_path:
                continue

            # 检查目标路径是否已存在
            if os.path.exists(target_path):
                old_size = os.path.getsize(target_path) if os.path.isfile(target_path) else 0
                # 新文件大小从 plan item 或原始文件获取
                original = item.get("original_path", "")
                new_size = os.path.getsize(original) if original and os.path.isfile(original) else 0

                conflicts.append(CoexistPair(
                    new_file=target_path,
                    old_file=target_path,
                    new_size_gb=round(new_size / (1024 ** 3), 3),
                    old_size_gb=round(old_size / (1024 ** 3), 3),
                ))

        # 也检查目标目录中的视频文件（Plan 可能没有精确的 target_path）
        if not conflicts and target_base and os.path.isdir(target_base):
            for f in os.listdir(target_base):
                ext = os.path.splitext(f)[1].lower()
                if ext in _VIDEO_EXTS:
                    old_path = os.path.join(target_base, f)
                    old_size = os.path.getsize(old_path) if os.path.isfile(old_path) else 0
                    conflicts.append(CoexistPair(
                        new_file="",  # 具体新文件由 V3 Plan 决定
                        old_file=old_path,
                        old_size_gb=round(old_size / (1024 ** 3), 3),
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
        for dir_nfo in ["movie.nfo", "season.nfo"]:
            dir_nfo_path = os.path.join(target_dir, dir_nfo)
            if os.path.exists(dir_nfo_path):
                self.recycle_bin.move_to_bin(dir_nfo_path, task_id)

        return True
