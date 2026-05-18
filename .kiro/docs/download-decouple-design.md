# [当前] 下载系统解耦设计

> 目标：将 qBittorrent / OpenList / Prowlarr 从 Core 中解耦为可插拔插件，Core 下载管理器不依赖任何具体下载器。

---

## 一、现状分析

### 当前耦合点

| 模块 | 耦合对象 | 耦合方式 |
|------|---------|---------|
| `download_manager.py` | qBittorrent | 构造函数直接接收 `QBittorrentClient`，`_push_to_qb` / `_sync_qb_progress` / `_get_qb_hashes` 直接调 qB API |
| `download_manager.py` | OpenList/Alist | 构造函数直接接收 `AlistManager`，`_push_to_alist` / `_sync_alist_progress` 直接调 Alist API |
| `routes/download.py` | qBittorrent | `sync_from_qb` 端点直接遍历 qB 种子列表 |
| `routes/search.py` | Prowlarr | `get_prowlarr_provider_map` 作为搜索源之一 |
| `shared.py` | qB/Alist | 单例初始化 `QBittorrentClient` / `AlistManager` |
| 设置页（前端） | qB/Prowlarr/Alist | 配置项硬编码显示 |

### 当前下载流程

```
搜索结果 → 用户点击下载 → routes/download.py
  → DownloadManager.submit(task)
    → _push_to_qb() 或 _push_to_alist()
    → 状态: downloading

定时/手动触发 → sync_progress()
  → _sync_qb_progress() 或 _sync_alist_progress()
  → 完成 → _relocate_to_save_path() → 归位替换
```

---

## 二、目标架构

### Core 保留

| 模块 | 职责 |
|------|------|
| DownloadManager（重构） | 任务状态机 + 持久化 + 归位触发 |
| DownloadBackend Protocol | 下载后端接口定义 |
| 文件夹监控（新增） | 监控指定目录，新文件触发整理 |
| file_relocator | 归位替换（已解耦） |
| 下载管理面板（前端） | 任务列表 + 状态展示 |

### 插件化

| 插件 | 提供 |
|------|------|
| `download-qbittorrent` | DownloadBackend 实现 + qB 配置 UI |
| `download-openlist` | DownloadBackend 实现 + Alist 配置 UI |
| `search-prowlarr` | SearchProvider 实现 + Prowlarr 配置 UI |
| 未来 `download-aria2` | DownloadBackend 实现 |
| 未来 `download-transmission` | DownloadBackend 实现 |

---

## 三、DownloadBackend Protocol

```python
class DownloadBackend(Protocol):
    """下载后端接口 — 所有下载器插件必须实现"""

    id: str           # "qbittorrent" / "openlist" / "aria2"
    display_name: str # "qBittorrent" / "OpenList"

    def submit(self, url: str, save_path: str, name: str = "") -> SubmitResult:
        """提交下载任务，返回任务标识"""
        ...

    def get_progress(self, task_id: str) -> ProgressResult:
        """查询单个任务进度"""
        ...

    def list_tasks(self) -> List[TaskInfo]:
        """列出所有任务（用于全量同步）"""
        ...

    def is_available(self) -> bool:
        """检查下载器是否可用（连接测试）"""
        ...


class SubmitResult(BaseModel):
    success: bool
    task_id: str = ""      # 下载器内部的任务标识（qB hash / aria2 gid）
    error: str = ""


class ProgressResult(BaseModel):
    status: str = ""       # "downloading" / "completed" / "paused" / "error" / "not_found"
    progress: float = 0.0  # 0.0 ~ 1.0
    speed: str = ""        # "12.5 MB/s"
    eta: str = ""          # "00:15:30"
    name: str = ""
    save_path: str = ""


class TaskInfo(BaseModel):
    task_id: str
    name: str = ""
    save_path: str = ""
    status: str = ""
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
```

---

## 四、重构后的 DownloadManager

### 构造函数变化

```python
# 之前
class DownloadManager:
    def __init__(self, qb_client, alist_client, base_path):
        self.qb = qb_client
        self.alist = alist_client

# 之后
class DownloadManager:
    def __init__(self, base_path: str = "."):
        self._backends: Dict[str, DownloadBackend] = {}
        # 不再直接持有任何具体客户端

    def register_backend(self, backend: DownloadBackend):
        """插件安装时注册下载后端"""
        self._backends[backend.id] = backend

    def unregister_backend(self, backend_id: str):
        """插件卸载时注销"""
        self._backends.pop(backend_id, None)

    def get_available_backends(self) -> List[str]:
        """返回当前可用的下载后端列表"""
        return [bid for bid, b in self._backends.items() if b.is_available()]
```

### submit 变化

```python
def submit(self, task: DownloadTask) -> DownloadTask:
    backend = self._backends.get(task.channel)
    if not backend:
        task.status = "failed"
        task.error = f"下载后端 {task.channel} 未安装"
        return task

    result = backend.submit(task.download_url, task.download_dir, task.media_name)
    if result.success:
        task.downloader_hash = result.task_id
        task.status = "downloading"
    else:
        task.status = "failed"
        task.error = result.error
    return task
```

### sync_progress 变化

```python
def sync_progress(self):
    for task in active_tasks:
        backend = self._backends.get(task.channel)
        if not backend:
            task.status = "unknown"
            continue
        progress = backend.get_progress(task.downloader_hash)
        task.progress = progress.progress
        task.speed = progress.speed
        task.eta = progress.eta
        if progress.status == "completed":
            task.status = "completed"
            self._relocate_to_save_path(task)
```

### sync_from_backend（替代 sync_from_qb）

```python
def sync_from_backend(self, backend_id: str):
    """从指定下载后端全量同步任务"""
    backend = self._backends.get(backend_id)
    if not backend:
        return {"error": f"下载后端 {backend_id} 未安装"}

    all_tasks = backend.list_tasks()
    # ... 和现有 sync_from_qb 逻辑类似，但通用化
```

---

## 五、文件夹监控模式（无下载器时的兜底）

### 设计

Core 新增配置项 `download_watch_dirs: List[str]`（下载监控目录列表）。

当没有任何下载后端插件安装时，用户可以：
1. 在设置中配置"下载监控目录"（如 `D:\Downloads\Movies`）
2. 用任意工具下载文件到该目录
3. Core 定时扫描（每 60 秒），发现新文件/文件夹后：
   - 创建一个 `DownloadTask`（status=completed，channel="watch"）
   - 自动触发归位替换流程

### 监控逻辑

```python
class FolderWatcher:
    """下载目录监控器 — Core 能力，不依赖任何下载器"""

    def __init__(self, watch_dirs: List[str]):
        self._watch_dirs = watch_dirs
        self._known_files: Set[str] = set()  # 已知文件，避免重复触发

    def scan(self) -> List[str]:
        """扫描监控目录，返回新增的文件/文件夹路径"""
        new_items = []
        for dir_path in self._watch_dirs:
            if not os.path.isdir(dir_path):
                continue
            for item in os.listdir(dir_path):
                full_path = os.path.join(dir_path, item)
                if full_path not in self._known_files:
                    self._known_files.add(full_path)
                    new_items.append(full_path)
        return new_items
```

### 前端交互

- 无下载器插件时：搜索结果只显示"复制磁力链接"按钮
- 下载管理面板显示：
  - 监控目录配置入口
  - "最近检测到的文件"列表
  - 每个文件的整理状态（待整理 / 已整理 / 跳过）

---

## 六、Prowlarr 插件化

### 现状

Prowlarr 在搜索系统中是"一个源"，和直搜源并行。SSE 搜索中 `prowlarr_enabled` 控制是否搜它。

### 改动

1. 从 `BT_SOURCE_DEFAULTS` 中移除 `prowlarr`
2. `search-prowlarr` 插件的 `__init__.py` 通过 `ctx.register_search_provider` 注册
3. 设置页中 Prowlarr 配置区域根据插件安装状态显隐
4. `plugin_guard.py` 中 Prowlarr 不再特殊处理，和直搜源一样走插件守卫

---

## 七、OpenList 插件化

### 现状

OpenList 在系统中有两个角色：
1. **网盘浏览**：`/alist/mounts`、`/alist/list` — 浏览网盘文件
2. **离线下载后端**：`DownloadManager` 通过 `AlistManager` 提交离线下载

### 改动

1. `download-openlist` 插件实现 `DownloadBackend` 接口
2. `storage-openlist` 插件提供网盘浏览能力
3. 两者可以独立安装（浏览不需要下载，下载不需要浏览）
4. 设置页中 Alist 配置区域根据插件安装状态显隐

---

## 八、设置页动态化

### 原则

设置页只显示：
- Core 配置（NAS 路径、排除目录、播放器路径、回收站、AI 配置）
- 已安装插件的配置（通过 `/api/plugins/:id/config` 获取）

### 实现

前端设置页根据 `useInstalledPlugins` 动态渲染配置区域：

```tsx
// 之前：硬编码所有配置区域
<ProwlarrConfig />
<QBConfig />
<AlistConfig />

// 之后：根据插件状态动态渲染
{plugins.has("search-prowlarr") && <ProwlarrConfig />}
{plugins.has("download-qbittorrent") && <QBConfig />}
{plugins.has("download-openlist") && <AlistConfig />}
```

---

## 九、下载管理面板变化

### 有下载器插件时（和现在基本一致）

- 任务列表 + 进度条 + 速度/ETA
- 同步按钮（从下载器全量同步）
- 一键下载入口

### 无下载器插件时

- 顶部提示："未安装下载器插件，可在插件中心安装 qBittorrent / aria2 等"
- 显示"监控目录"配置
- 显示"最近检测到的文件"列表
- 每个文件可手动触发整理

### 混合模式

- 有下载器 + 有监控目录：两种来源的任务都显示在同一个列表中
- `channel` 字段区分来源："qb" / "alist" / "watch"

---

## 十、插件最终清单

### Core（不可卸载）

| 能力 | 说明 |
|------|------|
| 媒体库扫描与浏览 | 扫描本地路径、目录树、文件详情 |
| 文件名清洗与解析 | clean_name_system |
| 视频质量解析与评分 | quality_parser、enhanced_scorer |
| 低质量资源识别 | analyzer、batch_recommend |
| 文件整理流水线 | organizer、structure_organizer、organize_executor |
| Action Plan / dry-run | 整理预览与执行 |
| 重命名与影子名 | renamer、shadow_name_manager |
| NFO 读写 | nfo_handler |
| 海报管理 | poster_downloader（本地上传/URL 下载） |
| 回收站 | recycle_bin |
| 文件归位替换 | file_relocator |
| 下载管理核心 | 任务状态机 + 持久化 + 归位触发（不含具体下载器） |
| 文件夹监控 | 监控下载目录，新文件触发整理 |
| 配置管理 | config_manager |
| L1-L4 通用匹配链 | text_processing → match_scoring → data_filtering → result_sorting |
| AI 辅助框架 | ai_client（用户自配 API Key） |
| 搜索框架 | search_service + search_helpers（无具体源） |
| 插件系统 | plugin_manager + plugin_context + plugin_guard |

### 插件（可安装/卸载）

| 插件 ID | 名称 | 分类 | 说明 |
|---------|------|------|------|
| `search-prowlarr` | Prowlarr | search | BT/PT 聚合搜索（需自建） |
| `search-bt-direct` | BT 直搜源包 | search | 12 个直搜源 |
| `search-pan` | 网盘搜索 | search | 网盘源聚合 |
| `download-qbittorrent` | qBittorrent | download | BT 下载后端 |
| `download-openlist` | OpenList 下载 | download | 网盘离线下载后端 |
| `storage-openlist` | OpenList 浏览 | storage | 网盘挂载浏览 |
| `metadata-tmdb` | TMDB | metadata | 影视元数据 |
| `metadata-douban` | 豆瓣 | metadata | 中文元数据 |
| `metadata-bangumi` | Bangumi | metadata | 动画元数据 |
| `feature-discover` | 发现推荐 | feature | 豆瓣热门/TMDB 趋势/Bangumi 日历 |
| `feature-subscribe` | 订阅追更 | feature | RSS 定时轮询 + 自动下载 |
| `feature-completeness` | 季集完整性 | feature | 基于 TMDB 的缺集分析 |
| `feature-local-match` | 本地媒体感知 | feature | 推荐/搜索中标记已有资源 |
| `rss-anime` | 动画 RSS 源包 | rss | 蜜柑/Nyaa/ACG.RIP/Bangumi Moe/动漫花园 |
| `rss-tv-movie` | 影视 RSS 源包 | rss | EZTV/YTS/Prowlarr RSS |

### 默认安装（开箱即用）

新用户首次启动时 `installed_plugins` 默认包含：
```json
[
  "search-prowlarr",
  "search-bt-direct",
  "download-qbittorrent",
  "metadata-tmdb",
  "metadata-douban",
  "feature-discover",
  "feature-subscribe",
  "feature-completeness",
  "feature-local-match"
]
```

用户可以在插件中心卸载任何一个，卸载后对应功能立即消失。

---

## 十一、实施计划

### Phase 1：DownloadBackend 接口抽象

1. 定义 `DownloadBackend` Protocol + 数据模型
2. 重构 `DownloadManager` 构造函数，移除 qb/alist 直接依赖
3. 实现 `QBDownloadBackend`（包装现有 `QBittorrentClient`）
4. 实现 `AlistDownloadBackend`（包装现有 `AlistManager`）
5. 通过 `register_backend` 注入，行为等价验证

### Phase 2：文件夹监控

1. 新增 `folder_watcher.py`
2. `config.json` 新增 `download_watch_dirs` 字段
3. 定时扫描 + 新文件触发整理
4. 前端下载管理面板适配无下载器模式

### Phase 3：Prowlarr 插件化

1. 从 `BT_SOURCE_DEFAULTS` 移除 prowlarr
2. `search-prowlarr` 插件 `__init__.py` 注册 SearchProvider
3. `plugin_guard.py` 移除 prowlarr 特殊处理
4. 前端设置页 Prowlarr 区域动态化

### Phase 4：下载器插件化

1. `download-qbittorrent` 插件 `__init__.py` 注册 DownloadBackend
2. `download-openlist` 插件 `__init__.py` 注册 DownloadBackend
3. 前端设置页 qB/Alist 区域动态化
4. 下载管理面板根据已安装后端动态显示

### Phase 5：设置页 + 前端全面动态化

1. 设置页只显示 Core 配置 + 已安装插件配置
2. 搜索弹窗下载按钮根据下载器插件状态显隐
3. 所有功能入口根据插件状态完整守卫

---

## 十二、验收标准

- [ ] 纯 Core（卸载所有插件）：只有扫描/浏览/整理/质量分析可用，设置页只有 Core 配置
- [ ] 安装 `search-bt-direct`：搜索弹窗出现直搜源 Tab
- [ ] 安装 `download-qbittorrent`：搜索结果出现"下载"按钮，下载管理面板可用
- [ ] 无下载器插件 + 配置监控目录：手动下载文件到监控目录后自动触发整理
- [ ] 安装 `feature-discover`：发现推荐区域出现
- [ ] 卸载任何插件：对应功能立即消失，不报错
- [ ] 第三方开发者可以写一个 `download-aria2` 插件接入下载系统
