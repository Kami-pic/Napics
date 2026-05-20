# [废弃] PRIVATE_PROVIDERS.md

> 全部完成，已归档。Phase 1 审计产出。

## 风险等级与结论

- 高风险：具体资源站、网盘搜索、自动转存、反爬 parser、Cookie/API 私有链路。不进入公开 Core。
- 中风险：用户显式配置的聚合器或下载器，例如 Prowlarr、qBittorrent、OpenList。可作为 builtin plugin 或外置插件，但 Core 不应直接依赖。
- 低风险：Provider SDK、DTO、Registry、示例 provider、开发文档。适合公开。

## BT SearchProvider 候选

| Provider | 当前模块 | 当前注册/调用点 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 建议去向 |
|---|---|---|---:|---|---|---|
| Prowlarr | `backend/searcher.py::ProwlarrClient` | `shared.get_clients`, `routes/search.py`, `search_service.py` | 中 | 是 | 可选插件 | `SearchProvider`，用户配置型 builtin plugin。 |
| Bitsearch | `backend/bt_scraper_bitsearch.py` | `shared._get_bitsearch_scraper`, `search_service.py` | 高 | 间接是 | 否 | private search plugin。 |
| 磁力熊 | `backend/bt_scraper_cilixiong.py` | `shared._get_cilixiong_scraper`, `routes/search.py` | 高 | 间接是 | 否 | private search plugin。 |
| XL720 | `backend/bt_scraper_xl720.py` | `shared._get_xl720_scraper`, `routes/search.py` | 高 | 间接是 | 否 | private search plugin。 |
| Nyaa | `backend/bt_scraper_nyaa.py` | `shared._get_nyaa_scraper`, `search_service.py` | 高 | 间接是 | 否 | private/plugin，公开版最多文档示例。 |
| 蜜柑计划 | `backend/bt_scraper_mikan.py` | `shared._get_mikan_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| YTS | `backend/bt_scraper_yts.py` | `shared._get_yts_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| LimeTorrents | `backend/bt_scraper_limetorrents.py` | `shared._get_limetorrents_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| ACG.RIP | `backend/bt_scraper_acgrip.py` | `shared._get_acgrip_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| Bangumi Moe | `backend/bt_scraper_bangumi_moe.py` | `shared._get_bangumi_moe_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| EZTV | `backend/bt_scraper_eztv.py` | `shared._get_eztv_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| 动漫花园 | `backend/bt_scraper_dmhy.py` | `shared._get_dmhy_scraper` | 高 | 间接是 | 否 | private/plugin。 |
| 1337x | `backend/bt_scraper_1337x.py` | `shared._get_1337x_scraper` | 高 | 间接是 | 否 | private/plugin。 |

审计要点：

- 当前 `BT_SOURCE_DEFAULTS` 在 `backend/search_service.py` 暴露所有具体源名称。
- `backend/routes/search.py` 的 `search_single_source` 直接维护 `source_getters`，route 仍知道具体 provider。
- `backend/shared.py` 持有所有 BT getter，全局单例污染明显。

## RSSProvider 候选

| Provider | 当前模块 | 当前注册/调用点 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 建议去向 |
|---|---|---|---:|---|---|---|
| Prowlarr RSS | `backend/rss_source_prowlarr.py` | `routes/subscribe.py::_get_source_manager` | 中 | 注册链依赖 | 可选插件 | 用户配置型 `RSSProvider`。 |
| 蜜柑 RSS | `backend/rss_source_mikan.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| Nyaa RSS | `backend/rss_source_nyaa.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| EZTV RSS | `backend/rss_source_eztv.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| 动漫花园 RSS | `backend/rss_source_dmhy.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| ACG.RIP RSS | `backend/rss_source_acgrip.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| Bangumi Moe RSS | `backend/rss_source_bangumi_moe.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |
| YTS RSS | `backend/rss_source_yts.py` | `routes/subscribe.py::_get_source_manager` | 高 | 注册链依赖 | 否 | private/plugin。 |

审计要点：

- `RSSSourceBase` 和 `RSSItem` 已接近契约形态，可以作为 Phase 2 的输入。
- 当前注册逻辑在路由层硬编码具体源，后续应迁移到 `ProviderRegistry`。
- RSS provider 只应产出候选条目，订阅匹配、自动下载决策仍属于 Core。

## Pan SearchProvider / StorageProvider 候选

> Phase 8 当前执行入口：`.kiro/docs/provider-pan-phase8-todo.md`。

| Provider | 当前模块 | 当前注册/调用点 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 建议去向 |
|---|---|---|---:|---|---|---|
| PanSearch | `backend/pan_scraper_pansearch.py` | `PanSearchService.__init__`, `shared._get_pan_search_service` | 高 | 间接是 | 否 | private pan search plugin。 |
| 狗狗盘搜 | `backend/pan_scraper_gogopanso.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| GitHub 资源仓库 | `backend/pan_scraper_github.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 人人电影 | `backend/pan_scraper_rrdynb.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 低端影视 | `backend/pan_scraper_ddys.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| PanSou | `backend/pan_scraper_pansou.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 多站聚合 | `backend/pan_scraper_sites.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 慢读 | `backend/pan_scraper_slowread.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 我能搜 | `backend/pan_scraper_wnsearch.py` | `PanSearchService.__init__` | 高 | 间接是 | 否 | private pan search plugin。 |
| 夸克转存 | `backend/quark_transfer.py` | `routes/search.py::transfer_pan_resource` | 高 | 是 | 否 | private storage/transfer plugin。 |
| OpenList | `backend/downloader.py::AlistManager` | `shared.get_clients`, download/search routes | 高 | 是 | 可选插件 | `StorageProvider` 或 `DownloadProvider`。 |

审计要点：

- 网盘搜索和自动转存不应进入公开 Core。
- `PanSearchService` 当前同时负责源实例化、并发聚合、去重、过滤、分组、OpenList 挂载标记。迁移时应把“源连接”移到 provider，把聚合/过滤/排序保留在 Core。
- `PanResult` / `PanSearchResponse` 可作为 DTO 参考，但 provider 侧不应泄漏私有站点字段。

## MetadataProvider 候选

| Provider | 当前模块 | 当前注册/调用点 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 建议去向 |
|---|---|---|---:|---|---|---|
| TMDB | `backend/tmdb_client.py` | `shared._tmdb_client`, `shared.get_clients`, scraper/analyzer/completeness | 中 | 是 | 是，用户配置型 | `MetadataProvider` builtin plugin。 |
| Douban Web/API | `backend/douban_client.py`, `backend/douban_api_v2.py` | discover/media_info/alias/combined_recommend | 中到高 | 间接 | 谨慎 | 插件化，公开版默认关闭或文档说明。 |
| Bangumi | `backend/bangumi_client.py` | discover/media_info/alias/subscribe calendar | 中 | 间接 | 可选插件 | `MetadataProvider` plugin。 |
| Poster downloader | `backend/poster_downloader.py` | scrape/poster routes | 低到中 | 间接 | 是 | Core 工具或 metadata 附属能力。 |

审计要点：

- TMDB 是公开版最适合保留的官方元数据源，但必须用户自配 API Key。
- Douban/Bangumi 可作为 provider，但 Core 不应 import 具体模块。
- `tmdb_client.py` 中包含 `parse_filename` 等非 TMDB 逻辑，后续应从 provider 中拆出到 Core。

## DownloadProvider / StorageProvider 候选

| Provider | 当前模块 | 当前调用点 | 风险等级 | 依赖 `shared.py` | 适合进入开源版 | 建议去向 |
|---|---|---|---:|---|---|---|
| qBittorrent | `backend/downloader.py::QBittorrentClient` | `shared.get_clients`, `DownloadManager` | 中 | 是 | 可选插件 | `DownloadProvider`。 |
| OpenList/Alist | `backend/downloader.py::AlistManager` | `shared.get_clients`, `DownloadManager`, pan transfer | 高 | 是 | 可选插件 | `StorageProvider`/`DownloadProvider`。 |
| DownloadManager | `backend/download_manager.py` | `shared._get_download_manager` | 中 | 是 | Core 编排 | 保留任务状态机，下载执行通过 provider。 |

审计要点：

- 下载任务、状态机、完成后归位逻辑属于 Core。
- qB/OpenList 的 API 连接、登录、离线下载、挂载状态属于 provider。
- Phase 7 前不应触碰下载状态机。

## 当前最强耦合点

| 耦合点 | 风险等级 | 依赖 `shared.py` | 问题 |
|---|---:|---|---|
| `backend/shared.py` provider getter | 高 | 是 | 集中持有具体资源站、下载器、配置、媒体库索引等单例。 |
| `backend/routes/search.py` | 高 | 是 | route 直接知道所有 BT 源 getter、Prowlarr、网盘转存。 |
| `backend/search_service.py` | 高 | 是 | Core 搜索流中硬编码 provider defaults 和 source proxy。 |
| `backend/routes/subscribe.py` | 高 | 是 | 路由层直接注册具体 RSS 源。 |
| `backend/pan_search_service.py` | 高 | 间接是 | 聚合服务直接 import 所有网盘源。 |
| 前端 provider UI | 中 | 不适用 | 多处写死源名、分类、能力和推荐策略。 |
