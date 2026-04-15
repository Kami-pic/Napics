"""下载任务队列管理器：持久化任务队列 + 沙盒隔离 + 进度监控 + 启动恢复。

核心设计：
- 状态机：pending → downloading → completed → relocating → archived | failed | lost
- Alist 双阶段：downloading(cloud_download) → downloading(local_sync) → completed
- 持久化策略：核心状态变更立刻落盘，高频进度只在内存更新（防抖落盘）
- 沙盒隔离：每个任务在 downloads/{task_id}/ 独立目录
- 启动恢复：加载 JSON 后对 downloading 任务向下载器对账
"""

import os
import json
import time
import uuid
import shutil
import threading
import requests
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel

from downloader import QBittorrentClient, AlistManager


TASK_FILE = "download_tasks.json"
SANDBOX_ROOT = "downloads"

# 落盘防抖间隔（秒）— 高频进度更新时最多这么久写一次磁盘
_SAVE_DEBOUNCE_SECONDS = 30


# ── 数据模型 ──

class DownloadTask(BaseModel):
    id: str = ""
    media_name: str = ""
    download_url: str = ""
    save_path: str = ""            # 最终目标路径（媒体库中的位置）
    download_dir: str = ""         # 隔离沙盒路径 downloads/{task_id}/
    channel: str = "qb"           # "qb" | "alist"
    downloader_hash: str = ""     # qB torrent hash 或 Alist task ID
    category_hint: str = ""       # "movie" | "tv"
    status: str = "pending"       # 核心状态（落盘）
    progress: float = 0.0         # 0.0-1.0（内存高频更新）
    speed: str = ""               # "12.5 MB/s"（内存）
    eta: str = ""                 # "00:15:30"（内存）
    phase: str = ""               # Alist: "cloud_download" | "local_sync"
    error: str = ""
    is_season_pack: bool = False
    season_number: int = 0
    organized: bool = False        # 已执行整理替换，跳过 qB 状态同步
    subscription_id: Optional[str] = None   # 关联的订阅 ID（订阅触发的下载）
    subscription_episode: Optional[int] = None  # 关联的集号（剧集订阅用）
    created_at: str = ""
    updated_at: str = ""


# ── 核心管理器 ──

class DownloadManager:
    """下载任务队列管理器。"""

    def __init__(
        self,
        qb_client: Optional[QBittorrentClient],
        alist_client: Optional[AlistManager],
        base_path: str = ".",
    ):
        self.qb = qb_client
        self.alist = alist_client
        self.base_path = base_path
        self.tasks: List[DownloadTask] = []
        self._lock = threading.Lock()
        self._last_save_time: float = 0
        self._dirty = False  # 是否有未落盘的进度变更
        self._load()

    # ── 沙盒管理 ──

    def _create_sandbox(self, task_id: str) -> str:
        """为任务创建隔离沙盒目录 downloads/{task_id}/"""
        sandbox = os.path.join(self.base_path, SANDBOX_ROOT, task_id)
        os.makedirs(sandbox, exist_ok=True)
        return sandbox

    # ── 任务提交 ──

    def submit(self, task: DownloadTask) -> DownloadTask:
        """提交新下载任务。

        流程：
        1. 生成 UUID，创建沙盒目录
        2. 推送到下载器（qB/Alist），save_path 指向沙盒
        3. 成功 → downloading + 记录 hash；失败 → failed
        4. 核心状态变更，立刻落盘
        """
        task.id = str(uuid.uuid4())[:8]
        task.created_at = datetime.now().isoformat()
        task.updated_at = task.created_at
        task.download_dir = self._create_sandbox(task.id)
        task.status = "pending"

        with self._lock:
            self.tasks.append(task)

        # 推送到下载器
        success = False
        error_msg = ""

        if task.channel == "qb" and self.qb:
            success, hash_or_err = self._push_to_qb(task)
            if success:
                task.downloader_hash = hash_or_err
            else:
                error_msg = hash_or_err
        elif task.channel == "alist" and self.alist:
            success, hash_or_err = self._push_to_alist(task)
            if success:
                task.downloader_hash = hash_or_err
                task.phase = "cloud_download"
            else:
                error_msg = hash_or_err
        else:
            error_msg = f"下载通道 {task.channel} 未配置"

        # 更新状态
        if success:
            task.status = "downloading"
        else:
            task.status = "failed"
            task.error = error_msg

        task.updated_at = datetime.now().isoformat()
        self._save_now()  # 核心状态变更，立刻落盘
        return task

    def _push_to_qb(self, task: DownloadTask) -> tuple:
        """推送到 qBittorrent，返回 (success, hash_or_error)。

        提交后通过 qB API 查询最近添加的种子获取 hash。
        """
        try:
            # 先记录提交前的种子列表
            before_hashes = self._get_qb_hashes()

            # 传 save_path 给 qB（用户指定的目标路径，不是沙盒）
            ok = self.qb.add_torrent(task.download_url, task.save_path or "")
            if not ok:
                return False, f"qBittorrent 推送失败（URL: {task.download_url[:80]}）"

            # 等待 qB 处理（最多 5 秒）
            for _ in range(10):
                time.sleep(0.5)
                after_hashes = self._get_qb_hashes()
                new_hashes = after_hashes - before_hashes
                if new_hashes:
                    return True, new_hashes.pop()

            # 超时未找到新 hash，但推送成功了
            return True, ""
        except Exception as e:
            return False, str(e)

    def _get_qb_hashes(self) -> set:
        """获取 qBittorrent 当前所有种子的 hash 集合。"""
        try:
            if not self.qb._login():
                return set()
            r = self.qb.session.get(
                f"{self.qb.url}/api/v2/torrents/info", timeout=5
            )
            if r.status_code == 200:
                return {t["hash"] for t in r.json()}
        except Exception:
            pass
        return set()

    def _push_to_alist(self, task: DownloadTask) -> tuple:
        """推送到 Alist，返回 (success, task_id_or_error)。"""
        try:
            ok = self.alist.transfer_link(task.download_url, task.download_dir)
            if ok:
                # Alist 不返回 task ID，用 URL hash 作为标识
                return True, f"alist_{task.id}"
            return False, "Alist 所有工具均失败"
        except Exception as e:
            return False, str(e)

    # ── 进度同步 ──

    def sync_progress(self):
        """轮询所有 downloading 任务的进度。

        由外部定时调用（如 FastAPI BackgroundTasks 或定时器）。
        高频进度只更新内存，防抖落盘。
        下载完成后自动转移文件到 save_path。
        """
        with self._lock:
            active = [t for t in self.tasks if t.status == "downloading"]

        state_changed = False
        for task in active:
            old_status = task.status
            if task.channel == "qb":
                self._sync_qb_progress(task)
            elif task.channel == "alist":
                self._sync_alist_progress(task)
            task.updated_at = datetime.now().isoformat()

            # 核心状态变更检测
            if task.status != old_status:
                state_changed = True

            # 下载完成 → 自动转移到 save_path
            if task.status == "completed" and old_status == "downloading":
                self._relocate_to_save_path(task)
                # 订阅回调：更新 downloaded_episodes
                if task.subscription_id:
                    self._notify_subscription_complete(task)

        if state_changed:
            self._save_now()
        else:
            self._save_debounced()

    def _relocate_to_save_path(self, task: DownloadTask):
        """下载完成后，将沙盒中的文件转移到用户指定的 save_path。"""
        if not task.save_path or not task.download_dir:
            return
        if not os.path.isdir(task.download_dir):
            return

        try:
            os.makedirs(task.save_path, exist_ok=True)
            moved = 0
            for item in os.listdir(task.download_dir):
                src = os.path.join(task.download_dir, item)
                dst = os.path.join(task.save_path, item)
                # 同名文件跳过（避免覆盖）
                if os.path.exists(dst):
                    continue
                shutil.move(src, dst)
                moved += 1
            if moved > 0:
                print(f"[DownloadManager] 已转移 {moved} 个文件到 {task.save_path}")
                task.status = "completed"
                # 自动触发局部刷新（后台线程，不阻塞）
                self._trigger_local_refresh(task.save_path)
            # 清理空沙盒
            try:
                if os.path.isdir(task.download_dir) and not os.listdir(task.download_dir):
                    os.rmdir(task.download_dir)
            except Exception:
                pass
        except Exception as e:
            print(f"[DownloadManager] 转移失败: {e}")
            task.error = f"转移失败: {e}"

    def _trigger_local_refresh(self, save_path: str):
        """下载完成后自动触发该文件夹的局部刷新（后台线程）。"""
        import threading
        def _do_refresh():
            try:
                from config_manager import ConfigManager
                cm = ConfigManager()
                library = cm.load_library()
                if not library:
                    return
                # 找到 save_path 下的新文件，和 library 对比
                import scanner
                new_files = scanner.scan_folder(save_path)
                if not new_files:
                    return
                existing_paths = {v.get("file_path") for v in library}
                added = [f for f in new_files if f.get("file_path") not in existing_paths]
                if added:
                    library.extend(added)
                    cm.save_library(library)
                    print(f"[DownloadManager] 局部刷新：{save_path} 新增 {len(added)} 个文件")
            except Exception as e:
                print(f"[DownloadManager] 局部刷新失败: {e}")
        threading.Thread(target=_do_refresh, daemon=True).start()

    def _sync_qb_progress(self, task: DownloadTask):
        """通过 qBittorrent API 同步单个任务的进度。"""
        if not self.qb or not task.downloader_hash:
            return
        # 已整理的任务跳过 qB 同步（文件可能已被重命名/移动）
        if task.organized:
            return

        try:
            if not self.qb._login():
                task.status = "unknown"
                return

            r = self.qb.session.get(
                f"{self.qb.url}/api/v2/torrents/info",
                params={"hashes": task.downloader_hash},
                timeout=5,
            )
            if r.status_code != 200:
                task.status = "unknown"
                return

            torrents = r.json()
            if not torrents:
                # hash 在 qB 中不存在
                task.status = "lost"
                task.error = "种子在 qBittorrent 中不存在"
                return

            t = torrents[0]
            task.progress = round(t.get("progress", 0), 4)
            # 速度格式化
            dl_speed = t.get("dlspeed", 0)
            if dl_speed > 0:
                if dl_speed >= 1024 * 1024:
                    task.speed = f"{dl_speed / (1024*1024):.1f} MB/s"
                else:
                    task.speed = f"{dl_speed / 1024:.0f} KB/s"
            else:
                task.speed = ""
            # ETA
            eta_secs = t.get("eta", 0)
            if eta_secs and eta_secs < 8640000:  # < 100 天
                h, rem = divmod(int(eta_secs), 3600)
                m, s = divmod(rem, 60)
                task.eta = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                task.eta = ""

            # 状态判定：增加对 100% 进度和 pausedUP 等状态的保底判定
            qb_state = t.get("state", "").lower()
            completed_states = ("uploading", "stalledup", "pausedup", "forcedup", "queuedup", "finished", "seeding")
            if task.progress >= 1.0 or any(s in qb_state for s in completed_states):
                task.status = "completed"
                task.progress = 1.0
                task.speed = ""
                task.eta = ""

        except Exception:
            task.status = "unknown"

    def _sync_alist_progress(self, task: DownloadTask):
        """通过 Alist API 同步进度，区分云端下载/本地同步两阶段。"""
        if not self.alist:
            return

        try:
            # 查询 Alist 离线下载任务列表
            r = requests.post(
                f"{self.alist.api_url}/api/admin/task/offline_download/undone",
                headers=self.alist.headers,
                timeout=5,
            )
            if r.status_code != 200:
                task.status = "unknown"
                return

            data = r.json().get("data", []) or []

            # 在未完成任务中查找
            found = False
            for item in data:
                # Alist 任务名通常包含下载 URL 或文件名
                if task.download_url in str(item.get("name", "")) or task.id in str(item.get("name", "")):
                    found = True
                    state = item.get("state", 0)
                    progress = item.get("progress", 0)
                    task.progress = round(progress / 100, 4) if progress else 0.0

                    if state == 2:  # 完成
                        task.phase = "local_sync"
                    else:
                        task.phase = "cloud_download"
                    break

            if not found:
                # 不在未完成列表中，检查已完成列表
                r2 = requests.post(
                    f"{self.alist.api_url}/api/admin/task/offline_download/done",
                    headers=self.alist.headers,
                    timeout=5,
                )
                done_data = r2.json().get("data", []) or [] if r2.status_code == 200 else []
                for item in done_data:
                    if task.download_url in str(item.get("name", "")) or task.id in str(item.get("name", "")):
                        found = True
                        # 云端已完成，检查本地文件是否存在
                        if self._check_local_files_exist(task.download_dir):
                            task.status = "completed"
                            task.progress = 1.0
                            task.phase = ""
                        else:
                            task.phase = "local_sync"
                            task.progress = 0.8  # 估算
                        break

                if not found:
                    # 完全找不到 → lost
                    task.status = "lost"
                    task.error = "Alist 中未找到对应任务"

        except Exception:
            task.status = "unknown"

    @staticmethod
    def _check_local_files_exist(directory: str) -> bool:
        """检查目录中是否存在视频文件。"""
        if not os.path.isdir(directory):
            return False
        video_exts = {".mp4", ".mkv", ".avi", ".ts", ".m4v", ".wmv", ".rmvb"}
        for f in os.listdir(directory):
            if os.path.splitext(f)[1].lower() in video_exts:
                return True
        return False

    # ── 启动恢复 ──

    def on_startup(self):
        """服务启动时：加载队列，对 downloading 任务向下载器对账。

        孤儿任务处理：
        - qB 中找不到 hash → lost
        - Alist 中找不到任务 → lost
        - pending 状态的任务（上次崩溃时还没推送完）→ failed
        """
        with self._lock:
            for task in self.tasks:
                if task.status == "pending":
                    # 上次崩溃时卡在 pending，标记失败
                    task.status = "failed"
                    task.error = "服务重启时任务未完成推送"
                elif task.status == "downloading":
                    self._reconcile_task(task)

        self._save_now()

    def _reconcile_task(self, task: DownloadTask):
        """对账单个 downloading 任务。"""
        if task.channel == "qb" and task.downloader_hash:
            hashes = self._get_qb_hashes()
            if task.downloader_hash not in hashes:
                task.status = "lost"
                task.error = "qBittorrent 中未找到该种子"
            # 存在则保持 downloading，等下次 sync_progress 更新
        elif task.channel == "alist":
            # Alist 对账比较复杂，先保持 downloading，等 sync_progress 处理
            pass
        elif not task.downloader_hash:
            task.status = "lost"
            task.error = "无下载器 Hash，无法对账"

    # ── 查询 ──

    def get_tasks(self, status: Optional[str] = None) -> List[DownloadTask]:
        """查询任务列表，按创建时间倒序，支持状态过滤。"""
        with self._lock:
            if status:
                filtered = [t for t in self.tasks if t.status == status]
            else:
                filtered = list(self.tasks)
        # 按创建时间倒序
        filtered.sort(key=lambda t: t.created_at or "", reverse=True)
        return filtered

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """按 ID 查询单个任务。"""
        with self._lock:
            for t in self.tasks:
                if t.id == task_id:
                    return t
        return None

    def update_status(self, task_id: str, status: str, error: str = ""):
        """手动更新任务状态（核心状态变更，立刻落盘）。"""
        with self._lock:
            for t in self.tasks:
                if t.id == task_id:
                    t.status = status
                    if error:
                        t.error = error
                    t.updated_at = datetime.now().isoformat()
                    break
        self._save_now()

    def archive_task(self, task_id: str, organized: bool = False):
        """标记任务为已归档。organized=True 表示已执行整理替换，跳过后续 qB 状态同步。"""
        with self._lock:
            for t in self.tasks:
                if t.id == task_id:
                    t.status = "archived"
                    if organized:
                        t.organized = True
                    t.updated_at = datetime.now().isoformat()
                    break
        self._save_now()


    def delete_task(self, task_id: str) -> bool:
        """删除任务记录（仅删除记录，不影响已下载文件）。"""
        with self._lock:
            before = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.id != task_id]
            removed = len(self.tasks) < before
        if removed:
            self._save_now()
        return removed

    def delete_tasks(self, task_ids: List[str]) -> int:
        """批量删除任务记录。"""
        id_set = set(task_ids)
        with self._lock:
            before = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.id not in id_set]
            removed = before - len(self.tasks)
        if removed:
            self._save_now()
        return removed

    # ── 下载通道推荐 ──

    def recommend_channel(self, seeders: int, size_gb: float) -> str:
        """推荐下载通道。

        规则：
        - seeders >= 5 且 size_gb <= 50 → qb
        - seeders < 5 或 size_gb > 50 → alist
        - 仅配置一种通道 → 直接使用
        """
        has_qb = self.qb is not None
        has_alist = self.alist is not None

        if has_qb and not has_alist:
            return "qb"
        if has_alist and not has_qb:
            return "alist"
        if not has_qb and not has_alist:
            return "qb"  # 默认

        if seeders >= 5 and size_gb <= 50:
            return "qb"
        return "alist"

    # ── 持久化（防抖策略）──

    def _save_now(self):
        """立刻落盘（核心状态变更时调用）。"""
        self._last_save_time = time.time()
        self._dirty = False
        self._write_json()

    def _save_debounced(self):
        """防抖落盘（高频进度更新时调用）。

        距上次落盘超过 _SAVE_DEBOUNCE_SECONDS 才真正写磁盘。
        """
        self._dirty = True
        now = time.time()
        if now - self._last_save_time >= _SAVE_DEBOUNCE_SECONDS:
            self._save_now()

    def flush(self):
        """强制落盘（服务退出时调用）。"""
        if self._dirty:
            self._save_now()

    def _load(self):
        """从 JSON 文件加载任务队列。"""
        path = os.path.join(self.base_path, TASK_FILE)
        if not os.path.exists(path):
            self.tasks = []
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = [DownloadTask(**item) for item in data]
        except Exception as e:
            print(f"[DownloadManager] 加载任务队列失败: {e}")
            self.tasks = []

    def _notify_subscription_complete(self, task: DownloadTask):
        """下载完成时通知订阅管理器更新 downloaded_episodes，洗版模式触发归位"""
        try:
            from subscriber import SubscriptionManager
            mgr = SubscriptionManager(base_path=self.base_path)
            info_hash = task.downloader_hash or task.download_url or ""
            mgr.on_download_complete(
                subscription_id=task.subscription_id,
                episode=task.subscription_episode,
                info_hash=info_hash,
                title=task.media_name,
                quality_tag="",
                source="prowlarr",
                channel=task.channel,
                task_id=task.id,
            )
            # 洗版模式：自动触发归位替换（旧资源进回收站）
            sub = mgr.get(task.subscription_id)
            if sub and sub.best_version and task.save_path:
                self._auto_relocate(task)
        except Exception as e:
            print(f"[DownloadManager] 订阅回调失败: {e}")

    def _auto_relocate(self, task: DownloadTask):
        """洗版自动归位：在新线程中执行 file_relocator"""
        import threading

        def _run():
            try:
                import asyncio
                from shared import _get_file_relocator
                relocator = _get_file_relocator()
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(relocator.relocate(task))
                loop.close()
                if result.status == "awaiting_confirm":
                    # 有冲突，自动确认替换（洗版模式不需要用户确认）
                    loop2 = asyncio.new_event_loop()
                    loop2.run_until_complete(relocator.confirm_replace(task, result.action_plan))
                    loop2.close()
                    print(f"[DownloadManager] 洗版归位完成: {task.media_name}")
                elif result.status == "archived":
                    print(f"[DownloadManager] 洗版归位（无冲突）: {task.media_name}")
                else:
                    print(f"[DownloadManager] 洗版归位状态: {result.status} {result.error}")
            except Exception as e:
                print(f"[DownloadManager] 洗版归位失败: {e}")

        threading.Thread(target=_run, daemon=True, name=f"relocate-{task.id}").start()

    def _write_json(self):
        """将任务队列写入 JSON 文件。"""
        path = os.path.join(self.base_path, TASK_FILE)
        try:
            with self._lock:
                data = [t.dict() for t in self.tasks]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[DownloadManager] 保存任务队列失败: {e}")
