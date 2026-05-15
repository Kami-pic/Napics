# [TODO] provider-prowlarr-phase6-todo.md

## 范围

Phase 6：迁移 Prowlarr 为 `SearchProvider`。

本清单只跟踪 Prowlarr 搜索 API 的 provider 化，不包含 RSS Prowlarr 源、BT 直搜源、下载器、OpenList、qB 迁移。

## 当前现状

- Prowlarr 搜索客户端在 `backend/searcher.py`：`ProwlarrClient.search()` 返回旧 `SearchResult`。
- 搜索业务编排在 `backend/search_service.py`：`search_prowlarr()` 负责搜索词回退、基础相关性过滤，并返回旧 SSE/同步路径需要的结构。
- 搜索路由在 `backend/routes/search.py`：
  - `/api/search/source?source=prowlarr` 仍直接走旧 Prowlarr 单源调用链。
  - `/search/single?skip_filter=true` 的裸搜路径仍直接走旧 Prowlarr 调用链。
- RSS 侧已有 `rss_source_prowlarr.py` 并已在 Phase 4 通过 `RSSProvider` 兼容桥注册；本阶段不重复迁移 RSS。
- `/api/providers` 已有 `prowlarr` 静态 metadata，风险级别为 `user_configured`，并标记 `requires=["api_url", "api_key"]`。

## 当前子任务

- [x] 新增 `backend/prowlarr_search_provider_adapter.py`，将 `ProwlarrClient.search()` 包装为 `SearchProvider`，输出 `SearchCandidate`。
- [x] 新增 `backend/test_prowlarr_search_provider_adapter.py`，验证 adapter 满足 `SearchProvider` 协议并保持 Prowlarr 下载链接字段兼容。
- [x] 新增 `backend/prowlarr_search_provider_factory.py`，集中 Prowlarr provider 构造逻辑，读取现有 `config.prowlarr_url` / `config.prowlarr_api_key`。
- [x] `search_service.search_prowlarr()` 改为通过 Prowlarr `SearchProvider` adapter 调用，保留搜索词回退、过滤、返回结构。
- [ ] `/api/search/source?source=prowlarr` 单源路径改为通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。
- [ ] `/search/single?skip_filter=true` 裸搜路径改为通过 Prowlarr `SearchProvider` adapter 调用，响应结构保持兼容。

## 暂不做

- 不修改 `ProwlarrClient` 内部 API 请求、下载链接选择、429 错误处理。
- 不修改搜索评分、过滤、排序。
- 不修改 BT 直搜源 provider 迁移结果。
- 不修改 RSS Prowlarr 源。
- 不修改 qB / 下载状态机。
- 不修改前端 provider 感知逻辑。
- 不迁移索引器优先级管理 API（`/config/indexers`），它是 Prowlarr 管理接口，不是搜索 provider 执行入口。

## 验证

- `cd backend && python -X utf8 -m pytest test_prowlarr_search_provider_adapter.py test_provider_contracts.py test_provider_registry.py`
- `cd backend && python -X utf8 -m pytest test_search_route_snapshots.py test_search_service_provider_bridge.py test_searcher.py test_provider_api.py`
