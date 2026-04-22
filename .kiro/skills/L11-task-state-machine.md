---
name: task-state-machine
description: >
  任务状态机模式：多阶段任务生命周期管理 + 持久化 + 启动恢复 + 失败重试。
  Use when modifying download task lifecycle, adding new task types,
  or debugging task state transitions.
---

# L11 任务状态机

> 通用的多阶段任务生命周期管理。项目中下载任务是主要实例。

## 状态转换图

```
pending → downloading → completed → relocating → awaiting_confirm → done
    ↓          ↓            ↓           ↓
  failed     failed       failed      failed
                                        ↓
                                      lost（下载器中找不到任务）
```

## 核心能力

| 能力 | 实现 |
|------|------|
| 状态持久化 | `download_tasks.json`，每次状态变更后写入 |
| 启动恢复 | 启动时加载 JSON，downloading 状态的任务重新同步进度 |
| 进度同步 | 定时从 qB/Alist 同步 progress/speed/eta |
| 失败重试 | 订阅系统检测到 failed/lost 时从候选列表选下一个重试 |
| 并发安全 | `threading.Lock` 保护任务列表的读写 |

## 下载任务字段

```python
class DownloadTask:
    id: str                    # UUID
    status: str                # pending/downloading/completed/relocating/...
    progress: float            # 0.0 ~ 1.0
    channel: str               # "qb" / "alist"
    downloader_hash: str       # qB hash 或 Alist task ID
    save_path: str             # 最终目标路径
    download_dir: str          # 沙盒路径
    subscription_id: str       # 关联的订阅 ID（订阅下载用）
    subscription_episode: str  # 关联的集号
```

## 双通道适配

| 通道 | 提交 | 进度同步 | 完成判定 |
|------|------|---------|---------|
| qBittorrent | 传 magnet/torrent + save_path | `_sync_qb_progress()` 轮询 | qB 报告 completed |
| Alist | 两阶段：cloud_download → local_sync | `_sync_alist_progress()` 轮询 | local_sync 完成 |

## 订阅系统联动

- 下载完成 → `_notify_subscription_complete()` → 更新订阅的 downloaded_episodes
- 下载失败 → 订阅调度器 `_retry_failed_downloads()` → 从 found_resources 选下一个候选
- 洗版下载完成 → 触发 `file_relocator.relocate()` → 归位替换
