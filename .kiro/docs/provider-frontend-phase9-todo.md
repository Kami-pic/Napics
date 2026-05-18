# [TODO] provider-frontend-phase9-todo.md

## 范围

Phase 9：前端 Provider 动态感知。

本清单只跟踪前端从 `GET /api/providers` 读取 provider metadata，并逐步移除搜索、订阅、metadata UI 中的硬编码 provider 列表。

## 当前子任务

- [x] 新增前端 `api.getProviders()` 和 Provider metadata 类型定义。
- [x] 搜索弹窗打开时优先读取 `GET /api/providers`，并保留旧 `/search/sources` 失败回退。
- [x] `SourceTabs` 去掉内置源名称映射，改用 provider metadata 传入展示名。
- [x] BT 直搜源识别从 provider metadata 派生，用于区分 Prowlarr 索引器。
- [x] BT 做种信息展示/筛选从 provider `capabilities` 派生，不再维护 `NO_SEEDER_INFO` 源名表。
- [x] `SearchSettingsPanel` 源列表优先从 `GET /api/providers` 构造，旧 `/search/sources` 仅用于保存接口与代理状态兼容。
- [x] BT 单源 Tab 默认搜索词从 provider `keyword_*` / `season_*` capabilities 派生，不再在前端维护源名→语言表。
- [x] Prowlarr 索引器筛选改为从 provider `indexers` capability 派生，不再在筛选逻辑中写死 `prowlarr`。

## 暂不做

- 不改搜索执行接口和 SSE 事件结构。
- 不改 `SearchSettingsPanel` 的源开关保存接口，仍使用旧 `/search/sources`。
- 不改订阅源、刮削候选、设置页 provider 动态化。
- 不改样式和交互布局。
- 不移除搜索结果源品牌色表；当前仅作为展示样式 fallback，不参与 provider 业务判断。

## 验证记录

- 前端构建：`cd frontend && npm run build`
- 后端 provider metadata：`cd backend && python -X utf8 -m pytest test_provider_api.py`
- Phase 9-A 验证：`cd frontend && npm run test`、`cd frontend && npm run build`、`cd backend && python -X utf8 -m pytest test_provider_api.py test_search_route_snapshots.py test_search_service_provider_bridge.py`
