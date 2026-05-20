# [废弃] PLUGIN_BOUNDARY.md

> 全部完成，已归档。Phase 2 已建立 Provider 契约。

## 目标边界

最终结构应满足：

```text
Core 负责理解媒体、匹配、过滤、排序、整理、状态机。
Plugin 负责连接外部世界、取回原始候选、执行外部动作。
Private 负责高风险资源站、网盘和私有策略。
```

Core 不应直接 import：

- `bt_scraper_*`
- `pan_scraper_*`
- `rss_source_*`
- `ProwlarrClient`
- `QBittorrentClient`
- `AlistManager`
- `QuarkTransfer`
- `douban_client` / `bangumi_client` / `TMDBClient` 的具体实现

Core 可以依赖：

- Provider 协议
- Pydantic DTO
- `ProviderRegistry`
- `ProviderContext`
- Core service，例如匹配、评分、过滤、整理、下载状态机

## ProviderContext

Provider 不允许 `from shared import xxx`。所有运行期依赖应由 `ProviderContext` 注入。

建议字段：

| 字段 | 类型方向 | 用途 | 是否必须 |
|---|---|---|---|
| `config` | 只读配置视图 | provider 读取自身配置、代理、API Key | 是 |
| `logger` | 标准 logger | 统一日志 | 是 |
| `http_client` | requests/httpx 包装 | HTTP 请求、代理、超时、UA 策略 | 是 |
| `cache` | key-value cache | provider 级缓存 | 建议 |
| `runtime_info` | profile/open-core/private 标识 | 控制私有 provider 加载 | 建议 |
| `feature_flags` | dict/模型 | 控制实验能力 | 可选 |
| `event_bus` | publish/subscribe | 通知状态变化 | 可选 |

禁止事项：

- Provider 内部读取 `shared.config_m`。
- Provider 内部获取下载器、媒体库、订阅管理器等 Core 单例。
- Provider 返回裸 dict 作为跨层接口。
- Provider 内部执行 Core 的评分、最终过滤、下载决策。

## 基础契约

建议所有 provider 共享基础字段：

| 字段/方法 | 说明 |
|---|---|
| `id` | 稳定机器名，例如 `prowlarr`。 |
| `display_name` | UI 展示名。 |
| `kind` | `search` / `metadata` / `rss` / `download` / `storage` / `notification`。 |
| `risk_level` | `low` / `medium` / `high` / `private` / `user_configured`。 |
| `capabilities` | 能力列表，例如 `seeders`, `magnet`, `rss`, `artwork`, `episodes`。 |
| `default_enabled` | 默认是否启用。公开版高风险 provider 应为 false 或不存在。 |
| `initialize(context)` | 注入依赖。 |
| `health_check()` | 可选，返回 provider 状态。 |
| `metadata()` | 返回前端可消费的 provider metadata。 |

## SearchProvider

用于 BT、Prowlarr、未来低风险搜索插件。

输入建议：

| DTO | 字段 |
|---|---|
| `SearchRequest` | `query`, `media_type`, `year`, `season`, `episode`, `keywords`, `limit`, `timeout_sec` |
| `SearchKeywordSet` | `cn`, `en`, `original`, `shadow`, `clean`, `fallbacks` |

输出建议：

| DTO | 字段 |
|---|---|
| `SearchCandidate` | `title`, `download_url`, `info_url`, `size_gb`, `seeders`, `leechers`, `published_at`, `raw_quality`, `provider_id`, `indexer`, `info_hash` |

边界：

- Provider 负责搜索和解析原始结果。
- Core 负责去重、二次匹配、质量解析、过滤、排序、推荐下载。
- Provider 可声明 `capabilities=["seeders", "size", "magnet", "torrent"]`，前端依据能力展示，不写死源名。

当前映射：

| 当前模块 | 建议 Provider |
|---|---|
| `backend/searcher.py::ProwlarrClient` | `ProwlarrSearchProvider` |
| `backend/bt_scraper_*.py` | `DirectBTSearchProvider` 子类或 private provider |
| `backend/search_service.py` | 保留 Core 搜索编排，移除具体 provider defaults |

## PanSearchProvider / StorageProvider

网盘搜索和网盘存储需拆开：

| 契约 | 职责 |
|---|---|
| `PanSearchProvider` | 搜索分享链接，输出候选。 |
| `StorageProvider` | 检查挂载、保存/转存、列目录、校验可用性。 |

`PanSearchCandidate` 建议字段：

- `title`
- `clean_title`
- `share_url`
- `pan_type`
- `password`
- `source_provider_id`
- `file_size`
- `resolution`
- `updated_at`

边界：

- 网盘 provider 不进入公开 Core。
- Core 可保留去重、敏感词过滤、质量过滤、分组逻辑。
- OpenList 属于 `StorageProvider`，不是 Core 全局工具。
- 夸克转存属于 private storage action，不应挂在 `routes/search.py`。

当前映射：

| 当前模块 | 建议 Provider |
|---|---|
| `backend/pan_scraper_*.py` | private `PanSearchProvider` |
| `backend/pan_search_service.py` | Core 聚合器，后续只依赖 registry |
| `backend/downloader.py::AlistManager` | `OpenListStorageProvider` |
| `backend/quark_transfer.py` | private `StorageTransferProvider` |

## RSSProvider

当前 `RSSSourceBase` 已接近目标契约，可作为迁移起点。

建议保留/补充：

| DTO/方法 | 说明 |
|---|---|
| `RSSFetchRequest` | `subscription`, `keywords`, `limit`, `since` |
| `RSSItem` | 当前已有结构可继续演进 |
| `fetch(request)` | 拉取候选 |
| `can_download(item)` | 是否可直接下载 |

边界：

- RSS provider 只拉取条目。
- 订阅匹配、已下载集数判断、通知/自动下载决策属于 Core。
- `routes/subscribe.py` 不应手动 import 每个 RSS 源。

当前映射：

| 当前模块 | 建议 |
|---|---|
| `backend/rss_source_base.py` | 合并到 `provider_contracts.py` 或保持为兼容适配层 |
| `backend/rss_source_*.py` | `RSSProvider` 实现 |
| `backend/rss_engine.py::RSSSourceManager` | 迁移为 registry consumer |

## MetadataProvider

元数据源与搜索源同等重要，不能附属于 scraper。

建议能力：

| capability | 说明 |
|---|---|
| `search` | 按标题/年份/类型搜索候选 |
| `detail` | 获取电影/剧集详情 |
| `episodes` | 获取季集信息 |
| `artwork` | 海报、背景图 |
| `aliases` | 别名、原名、英文名 |
| `ratings` | 评分信息 |
| `trending` | 趋势/榜单，可选 |

DTO：

- `MetadataSearchRequest`
- `MetadataCandidate`
- `MetadataDetail`
- `EpisodeInfo`
- `ArtworkInfo`
- `AliasSet`

边界：

- Core 可以做多源候选匹配、置信度判定、NFO 写入。
- Provider 只返回标准化元数据。
- `parse_filename` 不属于 TMDB provider，应进入 Core 文件名解析模块。

当前映射：

| 当前模块 | 建议 Provider |
|---|---|
| `backend/tmdb_client.py` | `TMDBMetadataProvider` + Core filename parser 拆出 |
| `backend/douban_client.py`, `backend/douban_api_v2.py` | `DoubanMetadataProvider` |
| `backend/bangumi_client.py` | `BangumiMetadataProvider` |
| `backend/alias_resolver.py` | Core alias service，依赖多个 MetadataProvider |

## DownloadProvider

下载 provider 执行外部下载动作，但下载任务状态机和归位仍属于 Core。

建议 DTO：

- `DownloadRequest`: `url`, `save_path`, `category`, `metadata`
- `DownloadSubmitResult`: `success`, `external_task_id`, `error_code`, `message`
- `DownloadProgress`: `external_task_id`, `progress`, `speed`, `eta`, `status`, `files`

当前映射：

| 当前模块 | 建议 |
|---|---|
| `backend/downloader.py::QBittorrentClient` | `QBDownloadProvider` |
| `backend/download_manager.py` | Core download orchestration，注入 provider |
| `backend/routes/download.py` | route 调用 Core manager，不直接知道 qB/OpenList |

## ProviderRegistry

建议职责：

1. 加载 builtin provider metadata。
2. 按 runtime profile 加载 private provider。
3. 提供 `list(kind=None)`、`get(id)`、`enabled(kind)`。
4. 统一 `GET /api/providers` 输出。
5. 负责启用/禁用状态，不把源列表散落在前后端。

Provider metadata 建议返回：

```json
{
  "id": "prowlarr",
  "name": "Prowlarr",
  "kind": "search",
  "type": "bt",
  "enabled": true,
  "capabilities": ["search", "seeders", "size", "magnet"],
  "riskLevel": "user_configured",
  "requires": ["api_url", "api_key"],
  "supportsProxy": false
}
```

## Phase 2 最小可落地范围

只新增契约，不迁移业务：

- `backend/provider_models.py`
- `backend/provider_context.py`
- `backend/provider_contracts.py`
- `backend/provider_registry.py`
- `GET /api/providers` 返回当前静态/半静态列表

验收标准：

- 新文件不从 `shared.py` import provider 实例。
- DTO 使用 Pydantic。
- 前端暂不改也可以，但 API 输出能覆盖现有 `search/sources` 和 `subscribe/sources` 的基础信息。
