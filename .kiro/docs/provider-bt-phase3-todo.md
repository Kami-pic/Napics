# [TODO] provider-bt-phase3-todo.md

## 范围

Phase 3：迁移 BT 直搜源为 `SearchProvider`。

本清单只跟踪 BT 直搜源适配，不包含 Prowlarr、RSS、网盘、下载器迁移。

## 当前子任务

- [x] 新增 `backend/bt_search_provider_adapter.py`，用通用 adapter 包装已有 `search_as_search_results()`。
- [x] 新增 `backend/test_bt_search_provider_adapter.py`，验证 adapter 满足 `SearchProvider` 协议并输出 `SearchCandidate`。
- [x] adapter 支持从 metadata + scraper factory 映射批量构建 provider 对象，不直接依赖具体爬虫或 `shared.py`。
- [x] 新增 `backend/bt_search_provider_factory.py`，集中现有直搜 scraper getter 映射，作为后续替换 `search_service.py` 的兼容桥。

## 暂不做

- 不修改 `bt_scraper_*` 内部 parser。
- 不改 `routes/search.py` 单源搜索调用链。
- 不改 `search_service.py` 并发搜索编排。
- 不改搜索评分、过滤、排序。

## 验证

- `cd backend && python -X utf8 -m pytest test_bt_search_provider_adapter.py test_provider_contracts.py test_provider_registry.py test_search_route_snapshots.py test_searcher.py`
