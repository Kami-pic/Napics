# [TODO] provider-pan-phase8-todo.md

## 范围

Phase 8：网盘搜索源与自动转存能力私有化。

本清单只跟踪网盘搜索 provider、OpenList 转存/私有存储动作和 private plugin 组织方式，不包含 BT、RSS、Metadata、qB/OpenList 下载状态机或前端动态感知。

## 当前审计结论

### 必须私有化的网盘搜索实现

| 源 | 当前模块 | 当前入口 | 风险 | Phase 8 去向 |
|---|---|---|---|---|
| PanSearch | `backend/pan_scraper_pansearch.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| PanSou | `backend/pan_scraper_pansou.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 狗狗盘搜 | `backend/pan_scraper_gogopanso.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| GitHub 资源仓库 | `backend/pan_scraper_github.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 人人电影 | `backend/pan_scraper_rrdynb.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 低端影视 | `backend/pan_scraper_ddys.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 多站聚合 | `backend/pan_scraper_sites.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 慢读 | `backend/pan_scraper_slowread.py` | `PanSearchService.__init__` | 高 | private pan search provider |
| 我能搜 | `backend/pan_scraper_wnsearch.py` | `PanSearchService.__init__` | 高 | private pan search provider |

### 必须私有化的转存能力

| 能力 | 当前模块 | 当前入口 | 风险 | Phase 8 去向 |
|---|---|---|---|---|
| 夸克自动转存 | `backend/quark_transfer.py` | `routes/search.py::transfer_pan_resource` (`/alist/transfer`) | 高 | private storage transfer provider |
| OpenList 挂载状态标记 | `PanSearchService._mark_mount_status` | `AlistManager.is_mounted()` | 中到高 | Core 聚合器调用 `StorageProvider` 能力 |

## 当前强耦合点

- `backend/pan_search_service.py` 直接 import 所有 `pan_scraper_*` 并在 `__init__` 中按配置实例化。
- `backend/shared.py::_get_pan_search_service()` 写死网盘源默认启用状态和 PanSou API URL。
- `backend/search_service.py::PAN_SOURCE_DEFAULTS` 暴露具体网盘源清单，并被 `/api/providers` 和 `/search/sources` 复用。
- `backend/routes/search.py::search_pan()` 直接调用 `_get_pan_search_service()`，当前接口默认仍代表内置网盘聚合能力。
- `backend/routes/search.py::transfer_pan_resource()` 直接 import `QuarkTransfer` 并执行私有转存动作。
- 前端仍可通过旧搜索源接口看到具体 pan source；这是 Phase 9 的 UI 动态感知范围。

## 建议迁移顺序

1. [x] 新增 `PanSearchProvider` adapter / factory，把现有 `pan_scraper_*` 包装为 provider，但先不移动文件。  
   验证：provider adapter 单测 + `PanSearchService` 响应结构快照。

2. [x] `PanSearchService` 改为接收 provider 列表，保留 Core 聚合、去重、相关性过滤、敏感词过滤、质量过滤、分组逻辑。  
   验证：`/search/pan` 响应结构不变，`source_statuses` 仍包含 disabled / success / failed。

3. [x] 将 `PAN_SOURCE_DEFAULTS` 的公开输出改为按 runtime/private 开关裁剪，公开 Core 默认不暴露具体 pan provider。  
   验证：无 private provider 时 `/api/providers.panSearch` 为空或只含 example disabled provider，Core 可启动。

4. [x] 新增 private plugin 目录占位与 `.gitignore` 规则：`backend/plugins/**/private_*/`。  
   验证：公开仓库不会纳入 private 实现；example provider 仍可作为 SDK 示例。

5. 将 `/alist/transfer` / `QuarkTransfer` 迁移到 private storage transfer provider 或在 open-core profile 下禁用。  
   验证：私有环境转存行为保持；公开 Core 不暴露自动转存入口。

## 本轮不做

- 不移动任何 `pan_scraper_*` 文件。
- 不修改 `PanSearchService` 执行逻辑。
- 不修改 `PanResult` / `PanSearchResponse` 字段。
- 不修改 `/search/pan`、`/alist/transfer` API 行为。
- 不修改前端搜索 Tab、设置页或 provider 感知逻辑。
- 不新增 Docker / runtime profile 实现。

## 验证记录

- 审计命令：`rg -n "PAN_SOURCE_DEFAULTS|PanSearchService|pan_scraper|pansearch|pansou|gogopanso|github|rrdynb|ddys|QuarkTransfer|/alist/transfer|transfer_pan|share_url|pan_type|private_pan|private_" backend .kiro/docs -g "*.py" -g "*.md"`
- 本轮为纯文档审计，无业务测试。
- adapter / factory 验证命令：`cd backend && python -X utf8 -m pytest test_pan_search_provider_adapter.py test_provider_contracts.py`
- `PanSearchService` provider bridge 验证命令：`cd backend && python -X utf8 -m pytest test_pan_search_service_provider_bridge.py test_pan_search_provider_adapter.py test_provider_contracts.py`
- provider 输出裁剪验证命令：`cd backend && python -X utf8 -m pytest test_provider_api.py test_pan_search_provider_adapter.py test_provider_contracts.py`
- private plugin 占位验证命令：`git check-ignore backend/plugins/search/private_pan/example.py`；`cd backend && python -m py_compile plugins/search/example_provider.py`
