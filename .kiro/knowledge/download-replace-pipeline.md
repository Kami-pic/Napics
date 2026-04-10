# 下载与归位替换流水线

## 架构概览

```
搜索结果 → 用户点击下载
    ↓
DownloadManager.submit()
    ├── BT 下载: qBittorrent WebAPI
    └── 网盘转存: Alist 转存 API (目前仅夸克自动)
    ↓
任务生命周期管理
    ├── downloading → completed → (归位)
    ├── 状态同步: _sync_qb_progress() / _sync_alist_progress()
    └── 持久化: download_tasks.json
    ↓
归位替换 (file_relocator.py)
    ├── 推演阶段: dry-run 计算冲突对
    ├── 确认阶段: confirm_replace / archive_both / cancel_replace
    └── 落盘阶段: 旧资源→回收站, 新资源→目标路径
```

## 下载通道

### BT/磁力 (qBittorrent)
- 客户端: downloader.py → QBittorrentClient
- 下载路径: 直接传 save_path 到 qB
- 完成后: _relocate_to_save_path 自动转移到目标目录

### 网盘转存 (Alist)
- 夸克: quark_transfer.py → Alist Cookie → stoken → 文件列表 → 转存
- 其他网盘: 暂不支持自动转存, 打开链接手动保存
- 双阶段: cloud_download → local_sync → completed

## 归位替换流程 (file_relocator.py)

```
1. relocate(task) — 推演
   ├── 扫描下载目录, 构建白名单
   ├── 匹配目标路径下的旧资源
   ├── 生成冲突对列表 (新文件 vs 旧文件)
   └── 返回 dry-run 结果 (awaiting_confirm)

2. confirm_replace(task_id) — 执行替换
   ├── 旧资源移入回收站 (RecycleBin)
   ├── 新资源移到目标路径
   ├── 更新 media_library.json
   └── 触发整理流水线 (organize_full)

3. archive_both(task_id) — 两者都保留
   └── 新资源移到目标路径, 旧资源不动

4. cancel_replace(task_id) — 取消
   └── 不做任何操作
```

## 任务状态机

```
pending → downloading → completed → relocating → awaiting_confirm → done
                ↓                        ↓
              failed                   failed
```

## 关键模块

| 模块 | 文件 | 职责 |
|---|---|---|
| 下载管理器 | download_manager.py | 任务队列 + 生命周期 + 持久化 |
| qB 客户端 | downloader.py | qBittorrent WebAPI 封装 |
| Alist 客户端 | downloader.py | Alist 挂载/离线下载/转存 |
| 夸克转存 | quark_transfer.py | 夸克网盘 API 转存 |
| 归位替换 | file_relocator.py | 两段式推演+落盘 |
| 回收站 | recycle_bin.py | 旧资源暂存, 可配置保留天数 |

## 持久化文件

- `download_tasks.json` — 下载任务队列 (重启后恢复)
- `folder_types.json` — 手动设置的文件夹类型 (持久化)
- `config.json` → `category_tags` — 一级分类标签 (持久化)
