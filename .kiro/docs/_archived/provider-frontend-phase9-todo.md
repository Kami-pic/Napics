# [废弃] provider-frontend-phase9-todo.md

## 范围

Phase 9：前端 Provider 动态感知。

本清单只跟踪前端从 `GET /api/providers` 读取 provider metadata，并逐步移除搜索、订阅、metadata UI 中的硬编码 provider 列表。

## 已完成子任务

- [x] 新增前端 `api.getProviders()` 和 Provider metadata 类型定义。
- [x] 搜索弹窗打开时优先读取 `GET /api/providers`，并保留旧 `/search/sources` 失败回退。
- [x] `SourceTabs` 去掉内置源名称映射，改用 provider metadata 传入展示名。
- [x] BT 直搜源识别从 provider metadata 派生，用于区分 Prowlarr 索引器。
- [x] BT 做种信息展示/筛选从 provider `capabilities` 派生，不再维护 `NO_SEEDER_INFO` 源名表。
- [x] `SearchSettingsPanel` 源列表优先从 `GET /api/providers` 构造，旧 `/search/sources` 仅用于保存接口与代理状态兼容。
- [x] BT 单源 Tab 默认搜索词从 provider `keyword_*` / `season_*` capabilities 派生，不再在前端维护源名→语言表。
- [x] Prowlarr 索引器筛选改为从 provider `indexers` capability 派生，不再在筛选逻辑中写死 `prowlarr`。
- [x] `SubscribeSourceSelect` 的 RSS/直搜分组从 provider metadata `kind=rss` 派生，不再维护 `RSS_SOURCES` 硬编码集合。
- [x] `SubscribeSourceSelect` 的内容类型推荐从 provider `recommended_*` capabilities 派生，不再维护 `RECOMMENDATIONS` 硬编码表。
- [x] `SubscribeSourceSelect` 的源展示名从 provider `name` 字段获取，不再硬编码源名→展示名映射。
- [x] `CandidatePicker` 的 metadata Tab 列表从 `GET /api/providers` 的 `metadata` 分类驱动，不再写死 tmdb/douban/bangumi。
- [x] `SettingsModal` 默认刮削源下拉从 `GET /api/providers` 的 `metadata` 分类动态渲染选项。

## 收口结论

Phase 9 前端 Provider 动态感知已完成主线目标：

**已消除的硬编码**：
- `DIRECT_SOURCES`（BT 直搜源集合）
- `NO_SEEDER_INFO`（无做种信息源集合）
- `BT_SOURCE_LABELS` / `PAN_SOURCE_LABELS`（源展示名映射）
- `RSS_SOURCES`（RSS 源集合）
- `RECOMMENDATIONS`（内容类型推荐表）
- `sourceDefaultKeywords`（源→语言搜索词映射）
- Metadata Tab 列表（tmdb/douban/bangumi 写死）

**保留为合理 fallback 或展示层**：
- `SubscribeSourceSelect` 中 provider 接口失败时的 RSS 源名 fallback 集合
- `CandidatePicker` 中 FALLBACK_TABS（provider 接口失败时的兜底）
- `CandidatePicker` 中 TAB_COLORS（UI 品牌色映射，展示层）
- `CandidatePicker` 中各源独立的搜索/选择函数（API 协议不同，需后端统一候选 API 才能消除）
- `SettingsModal` 中 FIELD_GROUPS 配置表单字段（用户表单，非 provider 业务判断）
- 搜索结果卡片品牌色（展示样式 fallback）

**达成的目标**：
- 新增 BT/RSS/网盘 provider 时，前端无需改代码即可出现在搜索 Tab、订阅源选择、设置页
- 新增 metadata provider 时，前端 Tab 自动出现（但搜索/选择逻辑仍需手动适配）
- 禁用 provider 后，前端自动隐藏或标记不可用
- 前端不再承担 provider 业务判断（做种信息、搜索词语言、源分组）

## 暂不做

- 不改搜索执行接口和 SSE 事件结构。
- 不改 `SearchSettingsPanel` 的源开关保存接口，仍使用旧 `/search/sources`。
- 不改 `SubscribeSourceSelect` 的源开关保存接口，仍使用旧 `/subscribe/sources`。
- 不改 `CandidatePicker` 各源独立的搜索/选择 API 调用（需后端统一候选 API）。
- 不改 `SettingsModal` 的 FIELD_GROUPS 配置表单为 provider `requires` 驱动（复杂度高、收益低）。
- 不改样式和交互布局。
- 不移除搜索结果源品牌色表；当前仅作为展示样式 fallback，不参与 provider 业务判断。

## 验证记录

- Phase 9-A 验证：`cd frontend && npx vitest --run`、`cd frontend && npm run build`、`cd backend && python -X utf8 -m pytest test_provider_api.py test_search_route_snapshots.py test_search_service_provider_bridge.py`
- Phase 9-B 验证：`cd frontend && npx vitest --run`（116 passed）、`cd frontend && npm run build`（通过）、`cd backend && python -X utf8 -m pytest test_provider_api.py test_provider_contracts.py test_provider_registry.py`（22 passed）
- Phase 9-C 验证：`cd frontend && npx vitest --run`（116 passed）、`cd frontend && npm run build`（通过）
