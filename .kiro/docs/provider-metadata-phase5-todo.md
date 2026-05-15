# [TODO] provider-metadata-phase5-todo.md

## 范围

Phase 5：迁移 MetadataProvider。

本清单只跟踪 TMDB / 豆瓣 / Bangumi 元数据源适配，不包含 Prowlarr、BT、RSS、网盘、下载器迁移。

## 当前子任务

- [x] 新增 `backend/metadata_provider_adapter.py`，用通用 adapter 包装已有元数据客户端搜索与详情能力。
- [x] 新增 `backend/test_metadata_provider_adapter.py`，验证 adapter 满足 `MetadataProvider` 协议并输出 `MetadataCandidate` / `MetadataDetail`。
- [x] 新增 `backend/metadata_provider_factory.py`，集中现有 TMDB / 豆瓣 / Bangumi 元数据源构造函数，作为后续替换刮削调用链的兼容桥。
- [x] 新增 `backend/test_metadata_provider_factory.py`，验证 Metadata provider 清单与静态 metadata 一致。
- [x] `/api/providers` 的 metadata 分类补充 TMDB / 豆瓣 / Bangumi 静态清单。
- [x] `/scrape/bangumi` 候选搜索改为通过 `MetadataProvider` adapter 调用，响应结构保持兼容。
- [x] `/scrape/douban` 候选搜索主路径改为通过 `MetadataProvider` adapter 调用，API v2 响应结构和旧网页 fallback 保持兼容。
- [x] `/scrape/select` 的 TMDB 详情获取改为通过 `MetadataProvider` adapter 调用，NFO 写入链路保持不变。
- [x] `get_media_info` 的 TMDB ID 直取详情路径改为通过 `MetadataProvider` adapter 调用，movie/tv 互试行为保持兼容。
- [x] `/scrape/bangumi-select` 的 Bangumi 详情获取改为通过 `MetadataProvider` adapter 调用，写入 NFO 链路保持不变。
- [x] `/scrape/douban-select` 的豆瓣 API v2 详情获取改为通过 `MetadataProvider` adapter 调用，旧网页 fallback 与写入链路保持不变。
- [x] `get_media_info` 无 ID 的 TMDB 搜索匹配与详情获取路径改为通过 `MetadataProvider` adapter 调用，匹配逻辑保持不变。
- [x] `/scrape/execute` 的豆瓣自动刮削分支改为通过 `MetadataProvider` adapter 搜索与获取详情，写入链路保持不变。

## 暂不做

- 不修改 TMDB / 豆瓣 / Bangumi client 内部请求与 parser。
- 不改现有刮削决策逻辑。
- 不改发现推荐与探索接口。
- 不新增元数据源。
- 不改前端 provider 感知逻辑。
- 不改 `/scrape/execute` 的 TMDB 默认分支和 `scraper.scrape_folder` / `scraper.scrape_video` 内部调用链。

## 收口审计

Phase 5 已完成的收口范围：

- Provider 契约、工厂、静态 metadata、`/api/providers` metadata 分类已建立。
- 用户手动候选路径已覆盖：`/scrape/bangumi`、`/scrape/douban`、`/scrape/select`、`/scrape/bangumi-select`、`/scrape/douban-select`。
- `get_media_info` 的 TMDB ID 直取、TMDB 无 ID 搜索匹配与详情路径已覆盖。
- `/scrape/execute` 的豆瓣自动刮削分支已覆盖。

Phase 5 后仍直接依赖元数据 client 的位置，按边界归类如下：

- `metadata_provider_factory.py`：允许保留。它是 Provider 兼容桥，负责集中构造 TMDB / 豆瓣 / Bangumi source。
- `routes/scrape.py` 的 TMDB 默认分支：暂缓。该分支把 `TMDBClient` 传给 `scraper.scrape_folder()` / `scraper.scrape_video()`，旧 scraper 依赖 `scrape_by_filename`、`search_movie/search_tv`、`get_movie_detail/get_tv_detail` 等完整客户端方法，不能用当前 `MetadataProvider` 简单替换。
- `scraper.py` / `scraper_tv.py` / `organizer.py` / `renamer.py` / `analyzer.py` / `shadow_name_manager.py`：暂缓。这些属于刮削核心、整理、重命名或影子名内部流程，迁移需要先设计 `ScrapeMetadataClient` 兼容层或重构 scraper 调用协议。
- `routes/media_info.py` 中豆瓣旧网页 fallback、Bangumi 详情搜索 fallback、TMDB 候选搜索 `/scrape/candidates`：暂缓。这些是兼容或独立候选入口，继续迁移会改变 fallback 行为或扩大本阶段范围。
- `routes/discover.py` / `combined_recommend.py` / `discover_enrich.py` / `local_media_matcher.py`：暂缓。发现推荐与本地媒体感知不属于本阶段范围。
- `completeness.py` / `subscriber.py` / `rss_engine.py`：暂缓。完整性检测与订阅系统属于后续单独阶段或跨模块迁移。

结论：

- Phase 5 当前可安全迁移的路由入口已经收口。
- 剩余直接 client 调用不是简单遗漏，而是依赖旧 scraper / 推荐 / 订阅 / 完整性模块的内部协议。
- 下一步不应继续在 Phase 5 内零散替换这些调用；应进入 Phase 6 迁移 Prowlarr，或另开后续阶段设计 `ScrapeMetadataClient` 兼容层后再处理 scraper 核心。

## 验证

- `cd backend && python -X utf8 -m pytest test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py test_provider_contracts.py`
- `cd backend && python -X utf8 -m pytest test_metadata_route_snapshots.py test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_metadata_select_route_snapshots.py test_metadata_route_snapshots.py test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_metadata_info_route_snapshots.py test_metadata_route_snapshots.py test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py`
- `cd backend && python -X utf8 -m pytest test_metadata_info_route_snapshots.py test_metadata_route_snapshots.py test_metadata_select_route_snapshots.py test_metadata_provider_adapter.py test_metadata_provider_factory.py test_provider_api.py test_provider_contracts.py`
