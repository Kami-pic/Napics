# [一次性] PHASED_MIGRATION_PLAN.md

> open-core extraction 审计输出之五。  
> 范围：基于当前仓库的分阶段迁移计划。  
> 本文档不修改既有 Phase 顺序，只把本轮审计拆成可执行里程碑。

## 总原则

1. 每轮只做一种改动。
2. 先契约化，不搬目录。
3. 先建立测试/响应结构基线，再迁移 provider。
4. Core 行为保持等价，搜索评分、过滤、排序不和 provider 迁移混改。
5. Private provider 不进入公开 Core。
6. 新 provider 代码禁止 `from shared import xxx`。

## Phase 1：open-core 边界审计

状态：本轮文档输出。

产出：

- `.kiro/docs/_one-off/PUBLIC_CORE.md`
- `.kiro/docs/_one-off/PRIVATE_PROVIDERS.md`
- `.kiro/docs/_one-off/PLUGIN_BOUNDARY.md`
- `.kiro/docs/_one-off/FRONTEND_PROVIDER_HARDCODE.md`
- `.kiro/docs/_one-off/PHASED_MIGRATION_PLAN.md`

验证：

- `git diff --name-only` 只出现文档。
- 无 `backend/` / `frontend/` 业务逻辑变更。

## Phase 2：Provider 契约与 Registry

目标：

- 新增 Provider DTO、Context、Contracts、Registry。
- 新增 `GET /api/providers` 初版。
- 不迁移任何具体 provider。

建议涉及文件：

- `backend/provider_models.py`
- `backend/provider_context.py`
- `backend/provider_contracts.py`
- `backend/provider_registry.py`
- `backend/routes/providers.py`
- `backend/main.py`
- 对应测试文件
- Phase 2 TODO/设计文档

不碰范围：

- 不移动 `bt_scraper_*` / `pan_scraper_*` / `rss_source_*`。
- 不修改搜索评分、过滤、排序。
- 不修改下载状态机。

验证：

- 后端新增 provider API 测试。
- `GET /api/providers` 返回结构稳定。
- 旧 `GET /search/sources` 仍保持兼容。

风险等级：中。  
`shared.py` 依赖：新契约不得依赖，兼容层可临时读取现有配置。  
适合开源版：是。

## Phase 3：迁移 BT 直搜源为 SearchProvider

目标：

- `bt_scraper_*` 实现或适配 `SearchProvider`。
- `search_service.py` 从 registry 获取启用源。
- `routes/search.py` 不再维护具体源 getter 表。

建议优先顺序：

1. 先适配已有 `ScraperBase`，不改每个 scraper 内部 parser。
2. 保留 `SearchResult` 输出兼容。
3. `BT_SOURCE_DEFAULTS` 迁移为 provider metadata。
4. `shared.py` 中 BT getter 逐步废弃。

不碰范围：

- 不改 `match_scoring.py`。
- 不改 `secondary_matcher.py`。
- 不改结果排序策略。
- 不新增 provider。

验证：

- `test_search_route_snapshots.py`
- `test_searcher.py`
- `test_search_keyword_mapper.py`
- 单源搜索响应结构快照。

风险等级：高。  
`shared.py` 依赖：当前强依赖，迁移目标为移除。  
适合开源版：provider 实现不适合，契约和适配框架适合。

## Phase 4：迁移 RSS 源为 RSSProvider

目标：

- `rss_source_*` 通过 registry 注册。
- `routes/subscribe.py` 不再手动 import 具体 RSS 源。
- `RSSSourceManager` 消费 registry。

不碰范围：

- 不改订阅匹配逻辑。
- 不改轮询间隔策略。
- 不改自动下载决策。

验证：

- `test_rss_engine.py`
- `test_rss_engine_phase2a.py`
- `test_subscribe_api.py`
- `GET /subscribe/sources` 兼容旧结构。

风险等级：高。  
`shared.py` 依赖：注册链当前依赖，迁移目标为 provider context。  
适合开源版：RSS 框架适合，具体源不适合。

## Phase 5：迁移 MetadataProvider

目标：

- TMDB / Douban / Bangumi 通过 `MetadataProvider` 接入。
- 刮削、详情、发现推荐、别名解析不直接 import 具体 provider。
- `parse_filename` 从 `tmdb_client.py` 的 provider 语义中剥离到 Core。

不碰范围：

- 不改变刮削决策。
- 不改变 NFO 写入格式。
- 不新增 AniDB/AniList/Trakt。

验证：

- `test_scraper_tv_dry_run_actions.py`
- `test_detail_operations.py`
- `test_douban_api_v2.py`
- `test_alias_resolver.py`
- 媒体详情 API 响应结构快照。

风险等级：中到高。  
`shared.py` 依赖：`_tmdb_client` 和 `get_clients` 当前强依赖。  
适合开源版：TMDB provider 适合，Douban/Bangumi 作为可选插件。

## Phase 6：迁移 Prowlarr

目标：

- Prowlarr 作为特殊 `SearchProvider`。
- Prowlarr indexer priority 作为 provider capability 或附属 metadata。
- Core 不直接调用 `ProwlarrClient`。

不碰范围：

- 不改变 Prowlarr 配置字段。
- 不改变结果字段。
- 不内置 indexer。

验证：

- `test_searcher.py`
- `test_search_route_snapshots.py`
- 搜索设置页索引器列表兼容。

风险等级：中。  
`shared.py` 依赖：当前通过 `get_clients` 强依赖。  
适合开源版：作为用户自配 builtin plugin 适合。

## Phase 7：迁移 qB / OpenList

目标：

- qB 抽象为 `DownloadProvider`。
- OpenList 抽象为 `StorageProvider` 或 `DownloadProvider`。
- `DownloadManager` 只依赖 provider 契约。

不碰范围：

- 不改下载任务数据结构。
- 不改下载完成归位逻辑。
- 不改回收站/替换流程。

验证：

- `test_download_manager_relocate_flow.py`
- `test_downloader_alist.py`
- `test_batch_manage_side_effects.py`
- 下载任务 API 快照。

风险等级：高。  
`shared.py` 依赖：当前强依赖。  
适合开源版：qB 可选 plugin；OpenList/转存默认不进入 Core。

## Phase 8：网盘源私有化

目标：

- 公开版不包含具体网盘搜索实现。
- 保留 Provider SDK、example provider 和开发文档。
- private provider 可在私有环境加载。

建议处理：

- `pan_scraper_*` 迁移到 private plugin。
- `PanSearchService` 保留聚合/过滤/分组 Core 能力，但从 registry 获取 provider。
- `quark_transfer.py` 私有化。

不碰范围：

- 不把网盘搜索作为公开版默认能力。
- 不在公开 README 中宣传自动转存。

验证：

- 无 private provider 时 Core 可启动。
- 搜索页不显示 pan provider，或显示“未安装 provider”。
- 媒体库扫描/整理/刮削仍可用。

风险等级：高。  
`shared.py` 依赖：当前 `_get_pan_search_service` 强依赖。  
适合开源版：具体实现不适合，SDK 和 example 适合。

## Phase 9：前端 Provider 动态感知

目标：

- 前端从 `GET /api/providers` 获取 provider metadata。
- 删除前端硬编码源列表和能力判断。
- 新增 provider 时前端无需改代码。

建议顺序：

1. 新增 `api.getProviders()`。
2. 搜索 Tab 用 metadata 渲染。
3. 订阅源选择用 metadata 分组。
4. Metadata 候选 Tab 用 provider 列表渲染。
5. 设置页根据 `requires` 渲染 provider 配置入口。

不碰范围：

- 不改变搜索结果卡片业务字段。
- 不改变下载提交流程。

验证：

- 前端测试：`cd frontend && npm run test`
- 前端构建：`cd frontend && npm run build`
- 手动验证搜索弹窗、订阅配置、设置页。

风险等级：中。  
`shared.py` 依赖：不适用。  
适合开源版：是。

## 阶段间验收矩阵

| 阶段 | 用户可见行为是否应变化 | 最小验证 |
|---|---|---|
| Phase 1 | 否 | 仅文档 diff |
| Phase 2 | 否，新增 API 不影响旧 UI | provider API 测试 + 旧测试 |
| Phase 3 | 否 | 搜索 API 快照 + 单源搜索 |
| Phase 4 | 否 | 订阅源列表 + RSS 匹配测试 |
| Phase 5 | 否 | 刮削/详情/别名测试 |
| Phase 6 | 否 | Prowlarr 搜索测试 |
| Phase 7 | 否 | 下载任务/归位测试 |
| Phase 8 | 公开版能力有裁剪，私有版行为不变 | open-core profile 启动 + private profile 回归 |
| Phase 9 | 否 | 前端测试 + 手动 UI 验证 |

## 本轮后推荐下一步

推荐进入 Phase 2 的最小实现：只建立 `ProviderContext`、DTO、Registry 和 `GET /api/providers` 静态兼容输出。不要在同一轮迁移任何具体 scraper。

