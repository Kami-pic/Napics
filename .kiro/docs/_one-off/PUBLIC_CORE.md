# [一次性] PUBLIC_CORE.md

> open-core extraction 审计输出之一。  
> 范围：基于当前仓库静态扫描，判断哪些能力适合进入公开 Core。  
> 本文档只做边界审计，不要求立即迁移代码。

## 结论

公开 Core 应聚焦“AI 媒体资产管理与整理系统”，保留低法律风险、低资源站耦合、长期可复用的媒体理解能力。当前代码中可公开能力已经较完整，但很多入口仍通过 `shared.py` 获取全局单例，需要在后续 Phase 2 之后逐步收口。

风险等级说明：

- 低：可直接作为公开核心能力保留，主要是本地媒体分析、整理、展示、配置能力。
- 中：能力本身可公开，但当前实现依赖外部 API、全局单例或特定平台路径，需要契约化后保留。
- 高：能力不应作为 Core 默认能力公开，最多作为插件框架或示例保留。

## 可公开核心能力清单

| 能力 | 当前主要模块 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 审计说明 |
|---|---|---:|---|---|---|
| 媒体库扫描与索引 | `backend/scanner.py`, `backend/routes/library.py`, `frontend/hooks/useLibrary.ts` | 低 | 路由依赖 | 是 | Core 基础能力。需要后续减少路由对 `shared.config_m`、`media_matcher` 的直接依赖。 |
| 媒体库树与文件浏览 | `backend/routes/library.py`, `frontend/components/layout/Sidebar.tsx`, `frontend/components/detail/FolderDetail.tsx` | 低 | 路由依赖 | 是 | 公开版核心体验，和资源获取无直接耦合。 |
| 本地文件信息读取 | `backend/routes/media_info.py`, `backend/nfo_handler.py`, `backend/completeness.py` | 中 | 路由依赖 | 是 | 可公开，但 `media_info.py` 混入 TMDB/Douban/Bangumi 详情回退，应在 MetadataProvider 后拆边界。 |
| 视频质量解析与评分 | `backend/quality_parser.py`, `backend/enhanced_scorer.py`, `backend/result_sorting.py` | 低 | 间接或无 | 是 | 可作为核心价值公开。注意不要把具体资源站权重泄漏进 Core。 |
| 低质量资源识别 | `backend/quality_parser.py`, `backend/analyzer.py`, `backend/batch_recommend.py` | 低 | 部分入口依赖 | 是 | 本地媒体资产管理能力，适合公开。 |
| 季集完整性检测 | `backend/completeness.py`, `frontend/components/detail/CompletenessBar.tsx` | 中 | 通过 TMDB 客户端入口依赖 | 是 | 能力适合公开，但外部元数据源需通过 `MetadataProvider` 注入。 |
| NFO 读写 | `backend/nfo_handler.py`, `backend/scraper.py`, `backend/scraper_tv.py` | 低 | 部分调用链依赖 | 是 | 公开 Core 必备能力。 |
| 海报与图片管理 | `backend/poster_downloader.py`, `backend/routes/poster.py`, `frontend/components/detail/PosterUpload.tsx` | 中 | 路由依赖 | 是 | 可公开。远端图片下载应通过元数据 provider 或通用 HTTP 能力注入。 |
| 文件整理流水线 | `backend/organizer.py`, `backend/structure_organizer.py`, `backend/organize_executor.py`, `backend/routes/organize.py` | 低 | 路由依赖 | 是 | Core 关键能力。保持行为等价，避免与下载器/provider 迁移混做。 |
| Action Plan / dry-run | `backend/organizer.py`, `backend/organize_executor.py`, `frontend/components/media/OrganizeProgress.tsx` | 低 | 路由依赖 | 是 | 非资源获取能力，适合公开。 |
| 文件归位替换 | `backend/file_relocator.py`, `backend/routes/relocate.py` | 中 | 路由和管理器依赖 | 是 | 本地文件副作用高，但不是版权风险。需保留现有测试基线后再抽象。 |
| 回收站 | `backend/recycle_bin.py`, `frontend/components/download/RecycleBinPanel.tsx` | 低 | 通过 `shared._get_recycle_bin` | 是 | 公开 Core 能力。 |
| 重命名与影子名 | `backend/renamer.py`, `backend/shadow_name_manager.py`, `backend/routes/rename.py` | 低 | 路由依赖 | 是 | 公开 Core 能力，名称来源枚举中可保留 `tmdb/douban/bangumi` 作为数据来源标识。 |
| 文件名清洗与解析 | `backend/clean_name_system.py`, `backend/tmdb_client.py::parse_filename`, `backend/text_processing.py` | 中 | 局部导入 | 是 | `parse_filename` 目前在 `tmdb_client.py` 中，不应长期绑定 TMDB provider。 |
| AI 文件名解析 | `backend/ai_organizer.py`, `backend/ai_prompts.py`, `backend/routes/analyze.py` | 中 | `ai_organizer.py` 和路由依赖 | 是 | 能力适合公开，但 API Key 与模型配置必须保持用户自配。 |
| AI 媒体库诊断 | `backend/analyzer.py`, `backend/ai_client.py`, `frontend/components/ai/SmartManager.tsx` | 中 | `ai_client.py` 依赖 `shared.config_m` | 是 | 可公开，后续应通过 Core service 注入 AI client。 |
| AI 候选匹配 | `backend/ai_organizer.py`, `backend/ai_prompts.py` | 中 | 依赖 `shared.config_m` | 是 | 属于核心差异化能力，需保证不包含私有资源站策略。 |
| L1-L4 通用匹配链 | `backend/match_scoring.py`, `backend/secondary_matcher.py`, `backend/search_helpers.py`, `backend/search_query_builder.py` | 中 | `search_helpers.py` 依赖 | 是 | 匹配算法可公开，但 provider 名称、资源站策略要移出 Core。 |
| 全局过滤规则 | `backend/global_filter.py`, `backend/content_filter.py` | 中 | 无或间接 | 是 | 可公开为用户配置能力。避免预置过多私有资源生态规则。 |
| 订阅模型与调度框架 | `backend/subscriber.py`, `backend/rss_engine.py`, `backend/routes/subscribe.py` | 中 | 多处依赖 | 是 | 框架可公开，具体 RSS 源必须插件化。 |
| 本地媒体匹配索引 | `backend/local_media_matcher.py` | 中 | `get_clients` 依赖 | 是 | 本地匹配能力适合公开；外部元数据补全应通过 MetadataProvider。 |
| 发现推荐聚合框架 | `backend/combined_recommend.py`, `backend/routes/discover.py`, `frontend/components/media/DiscoverPage.tsx` | 中 | 后端依赖 | 是，需裁剪 | 推荐框架可公开，但 Douban/Bangumi/TMDB 具体拉取应进入 provider。 |
| 配置管理 | `backend/config_manager.py`, `backend/routes/config.py`, `frontend/components/settings/SettingsModal.tsx` | 中 | 路由依赖 | 是 | 可公开，但默认配置中不应出现私有路径和高风险 provider 默认启用。 |
| 前端媒体管理 UI | `frontend/app/page.tsx`, `frontend/components/media/*`, `frontend/components/detail/*` | 低 | 不适用 | 是 | 公开版主客户端。 |
| 前端下载/搜索 UI 框架 | `frontend/components/search/*`, `frontend/components/download/*` | 中 | 不适用 | 是，需动态 provider | UI 框架可公开，但源列表和能力判断不能硬编码。 |

## 不应放入 Core 的内容

| 内容 | 当前位置 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 处理建议 |
|---|---|---:|---|---|---|
| 内置 BT 资源站实现 | `backend/bt_scraper_*.py` | 高 | 通过 getter 间接依赖 | 否，最多 private/plugin | 迁移为 `SearchProvider` 后放入 private 或独立插件。 |
| 内置网盘搜索源 | `backend/pan_scraper_*.py` | 高 | 通过 `PanSearchService` 间接依赖 | 否 | 公开版只保留 `Storage/SearchProvider` SDK 和 example。 |
| 自动转存链路 | `backend/quark_transfer.py`, `/alist/transfer` | 高 | 依赖配置和 OpenList | 否 | 私有插件或用户自配插件。 |
| qBittorrent 具体实现 | `backend/downloader.py::QBittorrentClient` | 中 | 通过 `shared.get_clients` | 插件化后可选 | 作为 `DownloadProvider` builtin/plugin，不属于 Core。 |
| OpenList 具体实现 | `backend/downloader.py::AlistManager` | 高 | 通过 `shared.get_clients` | 插件化后可选 | 作为 `StorageProvider`/`DownloadProvider` 插件。 |
| Prowlarr client | `backend/searcher.py::ProwlarrClient` | 中 | 通过 `shared.get_clients` | 插件化后可选 | 可作为用户配置型 provider，不应被 Core 直接调用。 |
| 具体 RSS 源 | `backend/rss_source_*.py` | 高 | 在 `routes/subscribe.py` 手动注册 | 否，除低风险示例 | 迁移到 `RSSProvider` 插件。 |

## 公开版保留建议

1. Core 默认能在没有 BT、网盘、qB、OpenList 的情况下启动和使用。
2. Core 默认展示媒体库、扫描、整理、刮削、诊断、NFO、海报和本地质量分析。
3. 外部能力只通过 provider metadata 暴露，前端不直接知道具体站点名称。
4. `shared.py` 在 Phase 1 后不得继续扩张；Phase 2 起新增 provider 只能通过 `ProviderContext` 获取配置、日志、HTTP、缓存等依赖。

