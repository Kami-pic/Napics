# [TODO] provider-frontend-phase9-todo.md

## 范围

Phase 9：前端 Provider 动态感知。

本清单只跟踪前端从 `GET /api/providers` 读取 provider metadata，并逐步移除搜索、订阅、metadata UI 中的硬编码 provider 列表。

## 当前子任务

- [x] 新增前端 `api.getProviders()` 和 Provider metadata 类型定义。
- [x] 搜索弹窗打开时优先读取 `GET /api/providers`，并保留旧 `/search/sources` 失败回退。
- [x] `SourceTabs` 去掉内置源名称映射，改用 provider metadata 传入展示名。
- [x] BT 直搜源识别从 provider metadata 派生，用于区分 Prowlarr 索引器。

## 暂不做

- 不改搜索执行接口和 SSE 事件结构。
- 不改 `SearchSettingsPanel` 的源开关保存逻辑，仍使用旧 `/search/sources`。
- 不改 `NO_SEEDER_INFO` 能力判断，需后端 provider metadata 补充能力字段后再迁移。
- 不改订阅源、刮削候选、设置页 provider 动态化。
- 不改样式和交互布局。

## 验证记录

- 前端构建：`cd frontend && npm run build`
