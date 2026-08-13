"""下载任务队列管理器：持久化任务队列 + 沙盒隔离 + 进度监控 + 启动恢复。

核心设计：
- 状态机：pending → downloading → completed → relocating → archived | failed | lost
- OpenList 双阶段：downloading(cloud_download) → downloading(local_sync) → completed
- 持久化策略：核心状态变更立刻落盘，高频进度只在内存更新（防抖落盘）
- 沙盒隔离：每个任务在 downloads/{task_id}/ 独立目录
- 启动恢复：加载 JSON 后对 downloading 任务向下载器对账
"""

import os
import logging
import json
import time
import uuid
import shutil
import threading
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote_plus, urlparse
from pydantic import BaseModel

from downloader import QBittorrentClient, AlistManager
from download_provider_adapter import DownloadProviderAdapter, DownloadProviderListStatusError
from provider_models import DownloadRequest as ProviderDownloadRequest, ProviderKind, ProviderMetadata

logger = logging.getLogger(__name__)
TASK_FILE = "download_tasks.json"
DELETED_HASHES_FILE = "download_deleted_hashes.json"
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
    downloader_hash: str = ""     # qB torrent hash 或 OpenList task ID
    category_hint: str = ""       # "movie" | "tv"
    status: str = "pending"       # 核心状态（落盘）
    progress: float = 0.0         # 0.0-1.0（内存高频更新）
    speed: str = ""               # "12.5 MB/s"（内存）
    eta: str = ""                 # "00:15:30"（内存）
    phase: str = ""               # OpenList: "cloud_download" | "local_sync"
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
        base_path: str = ".",
        # 兼容旧调用（逐步移除）
        qb_client=None,
        alist_client=None,
    ):
        self.base_path = base_path
        self._backends: Dict[str, Any] = {}  # channel -> DownloadProviderAdapter
        self.tasks: List[DownloadTask] = []
        self._download_providers: Dict[str, Any] = {}
        self._deleted_hashes: set = set()
        self._lock = threading.Lock()
        self._last_save_time: float = 0
        self._dirty = False
        self._load()
        self._load_deleted_hashes()

        # 兼容旧调用方式（如果直接传入 client）
        if qb_client is not None:
            self.qb = qb_client
        else:
            self.qb = None
        if alist_client is not None:
            self.alist = alist_client
        else:
            self.alist = None

    def register_backend(self, channel: str, backend) -> None:
        """注册下载后端（插件安装时调用）"""
        self._backends[channel] = backend
        # 同步设置兼容属性
        if channel == "qb":
            self.qb = backend._get_client() if backend else None
        elif channel == "alist":
            self.alist = backend._get_client() if backend else None

    def unregister_backend(self, channel: str) -> None:
        """注销下载后端（插件卸载时调用）"""
        self._backends.pop(channel, None)
        if channel == "qb":
            self.qb = None
        elif channel == "alist":
            self.alist = None

    def get_available_backends(self) -> List[str]:
        """返回当前可用的下载后端 channel 列表"""
        return list(self._backends.keys())

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
            url = task.download_url
            # Prowlarr 代理链接预处理：解析重定向获取真正的磁力链接
            if url and "/download?apikey=" in url and not url.startswith("magnet:"):
                try:
                    resp = requests.get(url, timeout=10, allow_redirects=False,
                                        proxies={"http": None, "https": None}, stream=True)
                    loc = resp.headers.get("Location", "")
                    if loc.startswith("magnet:"):
                        logger.info(f"[DM] Prowlarr 代理链接解析为磁力: {loc[:80]}")
                        url = loc
                    resp.close()
                except Exception as e:
                    logger.warning(f"[DM] Prowlarr 代理链接解析失败，使用原始 URL: {e}")

            # 先记录提交前的种子列表
            before_hashes = self._get_qb_hashes()

            provider = self._get_download_provider("qb")
            result = provider.submit(ProviderDownloadRequest(url=url, savePath=task.save_path or ""))
            if not result.success and "已在下载队列" in result.message:
                return False, "该种子已在下载队列中，无需重复添加"
            if not result.success:
                if result.message and result.message != "qBittorrent 推送失败":
                    return False, result.message
                return False, f"qBittorrent 推送失败（登录状态: {getattr(self.qb, '_logged_in', False)}，URL: {url[:80]}）"

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
            provider = self._get_download_provider("qb")
            return {task.external_task_id for task in provider.list_tasks() if task.external_task_id}
        except Exception:
            pass
        return set()

    def _push_to_alist(self, task: DownloadTask) -> tuple:
        """推送到 OpenList，返回 (success, task_id_or_error)。"""
        try:
            provider = self._get_download_provider("alist")
            result = provider.submit(ProviderDownloadRequest(url=task.download_url, savePath=task.download_dir))
            if result.success:
                return True, result.external_task_id or f"alist_{task.id}"
            if result.message and result.message != "OpenList 推送失败":
                return False, result.message
            return False, "Alist 所有工具均失败"
        except Exception as e:
            return False, str(e)

    def _get_download_provider(self, channel: str) -> DownloadProviderAdapter:
        # 优先从已注册的 backends 获取
        if channel in self._backends:
            return self._backends[channel]

        provider_id = "qbittorrent" if channel == "qb" else "openlist" if channel == "alist" else ""
        if not provider_id:
            raise ValueError(f"不支持的下载通道: {channel}")
        if provider_id not in self._download_providers:
            client = self.qb if provider_id == "qbittorrent" else self.alist
            if client is None:
                raise RuntimeError(f"下载通道 {channel} 未配置")
            self._download_providers[provider_id] = DownloadProviderAdapter(
                ProviderMetadata(
                    id=provider_id,
                    name="qBittorrent" if provider_id == "qbittorrent" else "OpenList",
                    kind=ProviderKind.DOWNLOAD,
                    type="download",
                    enabled=True,
                    defaultEnabled=True,
                    capabilities=["submit", "progress"],
                ),
                lambda client=client: client,
            )
        return self._download_providers[provider_id]

    # ── 进度同步 ──

    def sync_progress(self):
        """轮询所有 downloading / unknown 任务的进度。

        由外部定时调用（如 FastAPI BackgroundTasks 或定时器）。
        高频进度只更新内存，防抖落盘。
        下载完成后自动转移文件到 save_path。
        `unknown` 代表下载器短时异常后的待恢复态，下一轮同步仍应继续尝试对账。
        """
        with self._lock:
            active = [t for t in self.tasks if t.status in ("downloading", "unknown")]

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
            if task.status == "completed" and old_status in ("downloading", "unknown"):
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
                logger.info(f"[DownloadManager] 已转移 {moved} 个文件到 {task.save_path}")
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
            logger.error(f"[DownloadManager] 转移失败: {e}")
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
                    logger.info(f"[DownloadManager] 局部刷新：{save_path} 新增 {len(added)} 个文件")
            except Exception as e:
                logger.error(f"[DownloadManager] 局部刷新失败: {e}")
        threading.Thread(target=_do_refresh, daemon=True).start()

    def _sync_qb_progress(self, task: DownloadTask):
        """通过 qBittorrent API 同步单个任务的进度。"""
        if not self.qb or not task.downloader_hash:
            return
        # 已整理的任务跳过 qB 同步（文件可能已被重命名/移动）
        if task.organized:
            return

        try:
            provider = self._get_download_provider("qb")
            progress = provider.progress(task.downloader_hash)
            if progress.status == "unknown":
                task.status = "unknown"
                return

            if progress.status == "lost":
                task.status = "lost"
                task.error = "种子在 qBittorrent 中不存在"
                return

            task.progress = progress.progress
            task.speed = progress.speed
            task.eta = progress.eta

            # 状态判定：增加对 100% 进度和 pausedUP 等状态的保底判定
            qb_state = progress.status.lower()
            completed_states = ("uploading", "stalledup", "pausedup", "forcedup", "queuedup", "finished", "seeding")
            if task.progress >= 1.0 or any(s in qb_state for s in completed_states):
                task.status = "completed"
                task.progress = 1.0
                task.speed = ""
                task.eta = ""
            else:
                task.status = "downloading"

        except Exception:
            task.status = "unknown"

    def _sync_alist_progress(self, task: DownloadTask):
        """通过 Alist API 同步进度，区分云端下载/本地同步两阶段。"""
        if not self.alist:
            return

        try:
            if self._sync_alist_progress_by_task_id(task):
                return

            provider = self._get_download_provider("alist")
            try:
                data = provider.list_tasks("undone")
            except Exception:
                task.status = "unknown"
                return

            # 在未完成任务中查找
            found = False
            for item in data:
                if self._match_alist_task_item(task, item):
                    found = True
                    state = item.status
                    task.progress = item.progress

                    if self._is_alist_done_state(state):
                        task.phase = "local_sync"
                    else:
                        task.phase = "cloud_download"
                    break

            if not found:
                # 不在未完成列表中，检查已完成列表
                try:
                    done_data = provider.list_tasks("done")
                except DownloadProviderListStatusError:
                    done_data = []
                for item in done_data:
                    if self._match_alist_task_item(task, item):
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

    def _sync_alist_progress_by_task_id(self, task: DownloadTask) -> bool:
        task_id = (task.downloader_hash or "").strip()
        if not task_id or task_id.startswith("alist_"):
            return False

        provider = self._get_download_provider("alist")
        progress = provider.progress(task_id)
        if progress.status == "unknown":
            return False
        task.progress = progress.progress

        if self._is_alist_done_state(progress.status):
            if self._check_local_files_exist(task.download_dir):
                task.status = "completed"
                task.progress = 1.0
                task.phase = ""
            else:
                task.phase = "local_sync"
                task.progress = max(task.progress, 0.8)
            return True

        task.status = "downloading"
        task.phase = "cloud_download"
        error = str(progress.extra.get("error", "")).strip()
        if error:
            task.error = self._refine_alist_error(task, error)
        return True

    @staticmethod
    def _normalize_alist_progress(progress) -> float:
        try:
            value = float(progress)
        except (TypeError, ValueError):
            return 0.0
        if value <= 0:
            return 0.0
        if value > 1:
            value = value / 100
        return round(min(value, 1.0), 4)

    @staticmethod
    def _is_alist_done_state(state) -> bool:
        if state == 2:
            return True
        if isinstance(state, str):
            return state.strip().lower() in {"2", "done", "success", "succeeded", "completed"}
        return False

    @staticmethod
    def _alist_task_name_candidates(task: DownloadTask) -> List[str]:
        candidates = [task.download_url, task.id, task.downloader_hash]
        try:
            parsed = urlparse(task.download_url or "")
            file_name = parse_qs(parsed.query).get("file", [""])[0]
            if file_name:
                decoded = unquote_plus(file_name).strip()
                if decoded:
                    candidates.append(decoded)
        except Exception:
            pass
        return [item for item in candidates if item]

    def _match_alist_task_item(self, task: DownloadTask, item: dict) -> bool:
        if hasattr(item, "external_task_id"):
            item_id = str(item.external_task_id).strip()
            item_name = str(item.name).strip()
        else:
            item_id = str(item.get("id", "")).strip()
            item_name = str(item.get("name", "")).strip()
        for candidate in self._alist_task_name_candidates(task):
            if candidate == item_id:
                return True
            if candidate in item_name:
                return True
        return False

    def _refine_alist_error(self, task: DownloadTask, error: str) -> str:
        message = error.strip()
        if message != "http status code 429":
            return message

        try:
            response = requests.get(task.download_url, timeout=5)
            if response.status_code != 429:
                return message
            root = ET.fromstring(response.text)
            description = (root.attrib.get("description") or "").strip()
            if description:
                return f"Prowlarr 429: {description}"
        except Exception:
            pass
        return message

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
        removed_hash = ""
        with self._lock:
            before = len(self.tasks)
            for t in self.tasks:
                if t.id == task_id and t.downloader_hash:
                    removed_hash = t.downloader_hash
                    break
            self.tasks = [t for t in self.tasks if t.id != task_id]
            removed = len(self.tasks) < before
        if removed:
            if removed_hash:
                self._add_deleted_hash(removed_hash)
            self._save_now()
        return removed

    def delete_tasks(self, task_ids: List[str]) -> int:
        """批量删除任务记录。"""
        id_set = set(task_ids)
        removed_hashes = []
        with self._lock:
            before = len(self.tasks)
            for t in self.tasks:
                if t.id in id_set and t.downloader_hash:
                    removed_hashes.append(t.downloader_hash)
            self.tasks = [t for t in self.tasks if t.id not in id_set]
            removed = before - len(self.tasks)
        if removed:
            for h in removed_hashes:
                self._add_deleted_hash(h)
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
            logger.error(f"[DownloadManager] 加载任务队列失败: {e}")
            self.tasks = []

    def _notify_subscription_complete(self, task: DownloadTask):
        """下载完成时通知订阅管理器更新 downloaded_episodes，洗版模式触发归位"""
        try:
            from shared import _get_sub_manager
            mgr = _get_sub_manager()
            info_hash = task.downloader_hash or task.download_url or ""
            mgr.on_download_complete(
                subscription_id=task.subscription_id,
                episode=task.subscription_episode,
                info_hash=info_hash,
                title=task.media_name,
                quality_tag="",  # TODO: 从下载文件名解析质量标签
                source=task.category_hint or "unknown",
                channel=task.channel,
                task_id=task.id,
            )
            # 洗版模式：自动触发归位替换（旧资源进回收站）
            sub = mgr.get(task.subscription_id)
            if sub and sub.best_version and task.save_path:
                self._auto_relocate(task, sub)
            # 洗版订阅（purpose=upgrade）：电影下载完成后自动标记 completed
            is_upgrade = sub and getattr(sub, "purpose", "follow") == "upgrade" and sub.type != "tv"
            if is_upgrade:
                mgr.update(sub.id, {"state": "completed", "note": "洗版完成，已下载更高质量版本"})

            # 发送通知
            try:
                from notification_service import add_notification
                ep_label = f" E{task.subscription_episode:02d}" if task.subscription_episode else ""
                if is_upgrade:
                    add_notification(mgr, task.subscription_id, "upgrade_complete",
                                     f"洗版完成{ep_label}，已下载更高质量版本")
                else:
                    add_notification(mgr, task.subscription_id, "download_complete",
                                     f"下载完成: {task.media_name}")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[DownloadManager] 订阅回调失败: {e}")

    def _auto_relocate(self, task: DownloadTask, sub=None):
        """洗版自动归位：在新线程中执行 file_relocator。归位失败时不标记 completed。"""
        import threading

        def _run():
            try:
                import asyncio
                from shared import _get_file_relocator, _get_sub_manager

                # 校验 local_file_path 是否存在
                local_path = getattr(sub, "local_file_path", "") if sub else ""
                if local_path and not os.path.exists(local_path):
                    logger.warning(f"[DownloadManager] 洗版归位: local_file_path 不存在 {local_path}，尝试重新定位")
                    try:
                        from shared import media_matcher
                        status, folder = media_matcher.match({
                            "title": sub.title, "year": sub.year,
                            "tmdb_id": sub.tmdb_id,
                        })
                        if folder:
                            mgr = _get_sub_manager()
                            mgr.update(sub.id, {"local_file_path": folder})
                            logger.info(f"[DownloadManager] 洗版归位: 重新定位到 {folder}")
                    except Exception as e:
                        logger.error(f"[DownloadManager] 重新定位失败: {e}")

                relocator = _get_file_relocator()
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(relocator.relocate(task))
                loop.close()
                if result.status == "awaiting_confirm":
                    loop2 = asyncio.new_event_loop()
                    loop2.run_until_complete(relocator.confirm_replace(task, result.action_plan))
                    loop2.close()
                    logger.info(f"[DownloadManager] 洗版归位完成: {task.media_name}")
                elif result.status == "archived":
                    logger.info(f"[DownloadManager] 洗版归位（无冲突）: {task.media_name}")
                else:
                    # 归位失败：不标记 completed，保留订阅继续搜索
                    logger.error(f"[DownloadManager] 洗版归位失败: {result.status} {result.error}")
            except Exception as e:
                logger.error(f"[DownloadManager] 洗版归位异常: {e}")

        threading.Thread(target=_run, daemon=True, name=f"relocate-{task.id}").start()

    def _write_json(self):
        """将任务队列写入 JSON 文件。"""
        path = os.path.join(self.base_path, TASK_FILE)
        try:
            with self._lock:
                data = [t.model_dump() for t in self.tasks]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[DownloadManager] 保存任务队列失败: {e}")

    # ── 已删除 hash 黑名单 ──

    def _load_deleted_hashes(self):
        """加载已删除任务的 hash 黑名单。"""
        path = os.path.join(self.base_path, DELETED_HASHES_FILE)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._deleted_hashes = set(json.load(f))
        except Exception as e:
            logger.error(f"[DownloadManager] 加载已删除 hash 黑名单失败: {e}")

    def _save_deleted_hashes(self):
        """保存已删除任务的 hash 黑名单。"""
        path = os.path.join(self.base_path, DELETED_HASHES_FILE)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(self._deleted_hashes), f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[DownloadManager] 保存已删除 hash 黑名单失败: {e}")

    def _add_deleted_hash(self, h: str):
        """将 hash 加入黑名单并持久化。"""
        if not h:
            return
        self._deleted_hashes.add(h)
        self._save_deleted_hashes()
