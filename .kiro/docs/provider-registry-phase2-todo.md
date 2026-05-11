# [TODO] provider-registry-phase2-todo.md

## 范围

Phase 2：Provider 契约与 Registry。

本清单只跟踪 Provider DTO、Context、Contracts、Registry 和只读 API 接入，不包含任何具体 provider 迁移。

## 已完成

- [x] 新增 `backend/provider_models.py`，定义 Provider metadata、搜索、RSS、元数据、下载、存储等 DTO。
- [x] 新增 `backend/provider_context.py`，定义 ProviderContext 与注入依赖边界。
- [x] 新增 `backend/provider_contracts.py`，定义 Search/RSS/Metadata/Download/Storage Provider 协议。
- [x] 新增 `backend/provider_registry.py`，支持注册、去重、按 kind 列表和 catalog 输出。
- [x] 新增 `backend/providers.py`，提供 `/api/providers` 只读入口。
- [x] 接入 `backend/main.py`，注册 `/api/providers` 路由。
- [x] 新增 Provider 契约、Registry、API 入口测试。
- [x] 新增 `backend/provider_builtin_metadata.py`，将现有搜索、网盘、RSS 源清单投影为静态 provider metadata。

## 不做

- 不迁移 `bt_scraper_*` / `pan_scraper_*` / `rss_source_*`。
- 不修改搜索评分、过滤、排序。
- 不修改下载状态机。
- 不修改前端硬编码 provider 列表。

## 验证

- `cd backend && python -X utf8 -m pytest test_provider_api.py test_provider_contracts.py test_provider_registry.py`
