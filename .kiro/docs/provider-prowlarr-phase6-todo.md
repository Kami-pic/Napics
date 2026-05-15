# [TODO] provider-prowlarr-phase6-todo.md

## 范围

Phase 6：迁移 Prowlarr 为 `SearchProvider`。

本清单只跟踪 Prowlarr 搜索 API 的 provider 化，不包含 RSS Prowlarr 源、BT 直搜源、下载器、OpenList、qB 迁移。

## 收口状态

- Prowlarr 搜索客户端在 `backend/searcher.py`：`ProwlarrClient.search()` 返回旧 `SearchResult`。
- Prowlarr `SearchProvider` 兼容桥在 `backend/prowlarr_search_provider_adapter.py` / `backend/prowlarr_search_provider_factory.py`。
- 搜索业务编排在 `backend/search_service.py`：`search_prowlarr()` 已通过 Prowlarr `SearchProvider` adapter 调用，仍负责搜索词回退、基础相关性过滤，并返回旧 SSE/同步路径需要的结构。
- 搜索路由在 `backend/routes/search.py`：
  - `/api/search/source?source=prowlarr` 已通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。
  - `/search/single?skip_filter=true` 的裸搜路径已通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。
- RSS 侧已有 `rss_source_prowlarr.py` 并已在 Phase 4 通过 `RSSProvider` 兼容桥注册；本阶段不重复迁移 RSS。
- `/api/providers` 已有 `prowlarr` 静态 metadata，风险级别为 `user_configured`，并标记 `requires=["api_url", "api_key"]`。

## 当前子任务

- [x] 新增 `backend/prowlarr_search_provider_adapter.py`，将 `ProwlarrClient.search()` 包装为 `SearchProvider`，输出 `SearchCandidate`。
- [x] 新增 `backend/test_prowlarr_search_provider_adapter.py`，验证 adapter 满足 `SearchProvider` 协议并保持 Prowlarr 下载链接字段兼容。
- [x] 新增 `backend/prowlarr_search_provider_factory.py`，集中 Prowlarr provider 构造逻辑，读取现有 `config.prowlarr_url` / `config.prowlarr_api_key`。
- [x] `search_service.search_prowlarr()` 改为通过 Prowlarr `SearchProvider` adapter 调用，保留搜索词回退、过滤、返回结构。
- [x] `/api/search/source?source=prowlarr` 单源路径改为通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。
- [x] `/search/single?skip_filter=true` 裸搜路径改为通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。

## 暂不做

- 不修改 `ProwlarrClient` 内部 API 请求、下载链接选择、429 错误处理。
- 不修改搜索评分、过滤、排序。
- 不修改 BT 直搜源 provider 迁移结果。
- 不修改 RSS Prowlarr 源。
- 不修改 qB / 下载状态机。
- 不修改前端 provider 感知逻辑。
- 不迁移索引器优先级管理 API（`/config/indexers`），它是 Prowlarr 管理接口，不是搜索 provider 执行入口。

## 收口审计

Phase 6 已完成的执行入口：

- `search_service.search_prowlarr()`：SSE 全源搜索和同步全源搜索继续调用该函数，函数内部已通过 Prowlarr `SearchProvider` adapter 获取候选，再转换回旧 `SearchResult`。
- `/api/search/source?source=prowlarr`：单源搜索已通过 Prowlarr `SearchProvider` adapter 调用，保留回退词链、去重、enrich 和响应结构。
- `/search/single?skip_filter=true`：裸搜路径已通过 Prowlarr `SearchProvider` adapter 调用，保留直搜源快速合并、去重、enrich 和响应结构。

Phase 6 后仍直接依赖 `ProwlarrClient` 或 Prowlarr 配置的位置，按边界归类如下：

- `prowlarr_search_provider_factory.py`：允许保留。它是 Provider 兼容桥，负责集中构造 `ProwlarrClient`。
- `searcher.py`：允许保留。`ProwlarrClient` 作为底层外部服务 client 继续存在，adapter 包装它，不在本阶段重写请求、下载链接选择或错误处理。
- `shared.py:get_clients()`：暂缓。它仍统一构造旧客户端对象，当前通过 provider factory 包装 `clients["search"]` 保持兼容；后续若全局 client 容器 provider 化，再单独收口。
- `routes/scrape.py:/config/indexers`：暂缓。它是 Prowlarr 索引器管理接口，不是搜索执行入口。
- `rss_provider_factory.py` / `rss_source_prowlarr.py`：暂缓。RSS Prowlarr 已在 Phase 4 通过 `RSSProvider` 注册，本阶段不重复迁移。
- `episode_search.py`：暂缓。它走 `enhanced_search()` 和剧集搜索策略，涉及整季包验证、逐集搜索、同源匹配，不纳入本阶段。
- `routes/search.py` 的旧兼容 `/search` enhanced fallback：暂缓。该端点仍调用 `searcher.enhanced_search()`，属于旧增强搜索兼容路径，后续若迁移 `enhanced_search()` 再整体处理。
- `routes/download.py:/batch-search`：暂缓。它属于下载前批量搜索辅助接口，和 Phase 7 下载器迁移更相关。

结论：

- Phase 6 目标“将 Prowlarr 作为特殊 `SearchProvider`，并让核心搜索执行入口通过 provider 调用”已完成。
- 剩余 Prowlarr 直接引用不是本阶段遗漏，而是底层 client、索引器管理、RSS、剧集策略、旧兼容增强搜索或下载辅助路径。
- 下一步按 V2 方案进入 Phase 7：迁移 qB / OpenList 为 `DownloadProvider` / `StorageProvider`，不要在 Phase 6 内继续扩大搜索核心之外的改动。

## 验证

- `cd backend && python -X utf8 -m pytest test_prowlarr_search_provider_adapter.py test_provider_contracts.py test_provider_registry.py`
- `cd backend && python -X utf8 -m pytest test_search_route_snapshots.py test_search_service_provider_bridge.py test_searcher.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_search_route_snapshots.py test_search_service_provider_bridge.py test_prowlarr_search_provider_adapter.py test_prowlarr_search_provider_factory.py test_searcher.py test_provider_api.py`
