# [TODO] plugin-center-todo.md

> 插件中心：将非 Core 功能全部变成可安装/卸载的插件，前端提供统一管理入口。

---

## 目标

公开版初始化后只有 Core 功能可用。所有资源获取、外部服务连接能力以"插件"形式存在，用户在侧边栏"插件中心"中按需安装/卸载。

## Core（公开版默认可用，不可卸载）

| 能力 | 说明 |
|---|---|
| 媒体库扫描与浏览 | 扫描本地路径、目录树、文件详情 |
| 文件名清洗与解析 | clean_name_system、parse_filename |
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
| 文件夹监控 | 监控下载目录，新文件自动触发整理 |
| 配置管理 | config_manager |
| L1-L4 通用匹配链 | text_processing → match_scoring → data_filtering → result_sorting |
| AI 辅助框架 | ai_client（用户自配 API Key） |
| 搜索框架 | search_service + search_helpers（无具体源） |
| 插件系统 | plugin_manager + plugin_context + plugin_guard |

## 插件清单（可安装/卸载）

### 搜索源插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `search-prowlarr` | Prowlarr | BT/PT 聚合搜索（需自建） | 未安装 |
| `search-bt-direct` | BT 直搜源包 | 12 个直搜源（Bitsearch/Nyaa/蜜柑等） | 未安装 |
| `search-pan` | 网盘搜索 | 网盘源聚合 | 未安装 |

### 下载器插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `download-qbittorrent` | qBittorrent | BT 下载后端（进度追踪+自动整理） | 未安装 |
| `download-openlist` | OpenList/Alist | 网盘离线下载后端 | 未安装 |

### 元数据源插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `metadata-tmdb` | TMDB | 影视元数据（需 API Key + 代理） | 未安装 |
| `metadata-douban` | 豆瓣 | 中文元数据补充 | 未安装 |
| `metadata-bangumi` | Bangumi | 动画元数据 | 未安装 |

### RSS/订阅源插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `rss-anime` | 动画 RSS 源包 | 蜜柑/Nyaa/ACG.RIP/Bangumi Moe/动漫花园 | 未安装 |
| `rss-tv-movie` | 影视 RSS 源包 | EZTV/YTS/Prowlarr RSS | 未安装 |

### 存储插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `storage-openlist` | OpenList 浏览 | 网盘挂载浏览 | 未安装 |

### 增强功能插件

| 插件 ID | 名称 | 说明 | 默认状态 |
|---|---|---|---|
| `feature-completeness` | 季集完整性检测 | 基于 TMDB 的缺集分析（依赖 metadata-tmdb） | 未安装 |
| `feature-discover` | 发现推荐 | 豆瓣热门/TMDB 趋势/Bangumi 日历 | 未安装 |
| `feature-subscribe` | 订阅追更 | RSS 定时轮询 + 自动下载 | 未安装 |
| `feature-local-match` | 本地媒体感知 | 推荐/搜索中标记已有资源 | 未安装 |

---

## 后端设计

### 插件 manifest

每个插件有一个 `manifest.json`：

```json
{
  "id": "metadata-tmdb",
  "name": "TMDB",
  "version": "1.0.0",
  "description": "影视元数据源，提供搜索、详情、海报、季集信息",
  "category": "metadata",
  "icon": "🎬",
  "requires_config": ["tmdb_api_key"],
  "depends_on": [],
  "provides": ["MetadataProvider:tmdb"],
  "risk_level": "low"
}
```

### 插件状态管理

- `config.json` 新增 `installed_plugins: string[]` 字段
- 安装 = 将 plugin id 加入列表 + 注册到 ProviderRegistry
- 卸载 = 从列表移除 + 从 Registry 注销 + 清理相关配置（可选）
- 后端启动时只加载 `installed_plugins` 中的插件

### API

```
GET    /api/plugins              — 所有可用插件列表（含安装状态）
POST   /api/plugins/install      — 安装插件 { id: "metadata-tmdb" }
POST   /api/plugins/uninstall    — 卸载插件 { id: "metadata-tmdb" }
GET    /api/plugins/:id/config   — 获取插件配置项
PUT    /api/plugins/:id/config   — 保存插件配置
```

---

## 前端设计

### 侧边栏入口

侧边栏底部新增"🧩 插件中心"入口（固定位置，不随目录树滚动）。

### 插件中心页面

- 分类 Tab：全部 / 元数据 / 搜索 / 订阅 / 下载 / 增强
- 每个插件卡片：图标 + 名称 + 描述 + 安装/卸载按钮 + 配置入口
- 已安装插件有"卸载"按钮（红色）和"配置"按钮
- 未安装插件有"安装"按钮
- 有依赖关系的插件安装时自动提示依赖（如 completeness 依赖 metadata-tmdb）

### 卸载确认

卸载时弹出确认：
- 提示将失去哪些功能
- 提示是否清理相关配置数据
- 有依赖此插件的其他插件时，提示一并卸载或阻止

---

## 执行计划

### Phase A：后端插件框架

- [x] 新增 `backend/plugin_manager.py`：插件加载/注册/卸载逻辑
- [x] 新增 `backend/plugins/` 目录结构，每个插件一个子目录 + manifest.json
- [x] `config.json` 新增 `installed_plugins` 字段
- [x] 后端启动时根据 `installed_plugins` 选择性注册 provider
- [x] 新增 `/api/plugins` CRUD 端点
- [x] 未安装的插件对应的 API 端点返回空数据（通过 plugin_guard 守卫实现）

### Phase B：现有功能拆分为插件

- [x] 将 TMDB/豆瓣/Bangumi 客户端包装为 metadata 插件（manifest 已创建）
- [x] 将 BT 直搜源包装为 search 插件（manifest + 守卫已实现）
- [x] 将网盘搜索包装为 search-pan 插件（manifest + 守卫已实现）
- [x] 将 RSS 源包装为 rss 插件（manifest 已创建）
- [x] 将 qB/OpenList 包装为 download 插件（manifest + 守卫已实现）
- [x] 将 completeness/discover/subscribe/local-match 包装为 feature 插件（manifest + 守卫已实现）
- [x] 每个插件写 manifest.json
- [x] 第三方插件开发接口（PluginContext + register/unregister 机制）
- [x] 第三方插件开发指南（PLUGIN_DEV_GUIDE.md）
- [x] 示例第三方插件（search-example）

### Phase C：前端插件中心

- [x] 侧边栏底部新增"插件中心"入口
- [x] 新增 `/plugins` 页面（或抽屉面板）
- [x] 插件卡片列表（分类 Tab + 安装状态）
- [x] 安装/卸载交互（确认弹窗 + 依赖提示）
- [x] 插件配置入口（跳转到对应设置区域或内联配置）

### Phase D：Core 降级体验

- [x] 无 search 插件时：搜索源列表为空，SSE 搜索返回提示
- [x] 无 metadata 插件时：provider 列表不含元数据源
- [x] 无 download 插件时：下载提交返回"请先安装插件"
- [x] 无 subscribe 插件时：订阅列表返回空
- [x] 无 discover 插件时：发现源列表返回空
- [x] 无 completeness 插件时：完整性检测返回"请先安装插件"

---

## 验收标准

- [x] 公开版首次启动：只有媒体库扫描/浏览/整理/质量分析可用
- [x] 用户进入插件中心，安装 metadata-tmdb 后，刮削功能可用
- [x] 用户安装 search-prowlarr 后，搜索功能可用
- [x] 用户卸载某插件后，对应功能立即不可用（不报错，优雅降级）
- [ ] 私有自用版：`installed_plugins` 默认包含所有插件（行为等价于当前）

---

## 遗留事项（后续迭代）

- [ ] 私有自用版：`installed_plugins` 默认包含所有插件（行为等价于当前）
- [ ] DownloadManager 完全移除 qb/alist 兼容属性（当前保留了 self.qb/self.alist 兼容）
- [ ] 搜索弹窗下载按钮根据 hasDownload 状态显隐（当前后端已阻断，前端按钮仍显示）
- [ ] 文件夹监控检测到新文件后自动创建 DownloadTask 并触发归位（当前只打日志）
