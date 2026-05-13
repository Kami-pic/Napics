# [TODO] provider-bt-phase3-todo.md

## 范围

Phase 3：迁移 BT 直搜源为 `SearchProvider`。

本清单只跟踪 BT 直搜源适配，不包含 Prowlarr、RSS、网盘、下载器迁移。

## 当前子任务

- [x] 新增 `backend/bt_search_provider_adapter.py`，用通用 adapter 包装已有 `search_as_search_results()`。
- [x] 新增 `backend/test_bt_search_provider_adapter.py`，验证 adapter 满足 `SearchProvider` 协议并输出 `SearchCandidate`。
- [x] adapter 支持从 metadata + scraper factory 映射批量构建 provider 对象，不直接依赖具体爬虫或 `shared.py`。
- [x] 新增 `backend/bt_search_provider_factory.py`，集中现有直搜 scraper getter 映射，作为后续替换 `search_service.py` 的兼容桥。
- [x] `search_service.py` 的直搜源清单改为从 `bt_search_provider_factory.py` 获取，返回结构保持 `(name, getter)` 兼容。
- [x] `routes/search.py` 单源搜索和裸搜快速合并已从分散 shared getter 收口到 `bt_search_provider_factory.py`。
- [x] `/api/search/source` 的 BT 直搜单源路径改为通过 `SearchProvider` adapter 调用，响应结构保持兼容。
- [x] `search_service.py` 的 SSE/同步全源直搜路径改为通过 `SearchProvider` adapter 调用，事件结构保持兼容。
- [x] `/search/single?skip_filter=true` 的快速合并直搜路径改为通过 `SearchProvider` adapter 调用，响应结构保持兼容。

## 暂不做

- 不修改 `bt_scraper_*` 内部 parser。
- 不改 `routes/search.py` 的 Prowlarr 单源搜索调用链。
- 不改 `search_service.py` 并发搜索编排与结果处理逻辑。
- 不改搜索评分、过滤、排序。

## 验证

- `cd backend && python -X utf8 -m pytest test_bt_search_provider_adapter.py test_provider_contracts.py test_provider_registry.py test_search_route_snapshots.py test_searcher.py`
