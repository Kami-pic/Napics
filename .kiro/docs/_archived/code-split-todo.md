[废弃] 大文件拆分计划

> 全部完成，已归档。纯重构，不改任何业务逻辑和外部接口。

---

## 总览

| # | 文件 | 行数 | 建议 | 优先级 |
|---|------|------|------|--------|
| 1 | frontend/components/search/SearchModal.tsx | 849→163 | ✅ 已完成 | P1 |
| 2 | frontend/lib/api.ts | 484→已拆为 10 个子模块 | ✅ 已完成 | P2 |
| 3 | backend/routes/organize.py | 1238→602 | ✅ 已完成 | P3 |
| 4 | frontend/components/media/DiscoverPage.tsx | 597→184 | ✅ 已完成 | P4 |
| 5 | backend/scraper.py | 1124→472 | ✅ 已完成 | P5 |
| 6 | backend/analyzer.py | 936 | ⚠️ 观望 | — |
| 7 | backend/tmdb_client.py | 921 | ⚠️ 观望 | — |
| 8 | backend/download_manager.py | 809 | ❌ 不拆 | — |
| 9 | backend/structure_organizer.py | 787 | ❌ 不拆 | — |
| 10 | backend/routes/media_info.py | 737 | ⚠️ 观望 | — |
| 11 | backend/rss_engine.py | 725 | ❌ 不拆 | — |
| 12 | backend/routes/library.py | 630 | ⚠️ 观望 | — |
| 13 | backend/clean_name_system.py | 643 | ❌ 不拆 | — |
| 14 | backend/file_relocator.py | 583 | ❌ 不拆 | — |
| 15 | backend/renamer.py | 576 | ❌ 不拆 | — |
| 16 | backend/organizer.py | 546 | ❌ 不拆 | — |
| 17 | frontend/components/search/BatchUpgradePanel.tsx | 530 | ⚠️ 观望 | — |
| 18 | frontend/components/media/ExpandDetail.tsx | 377 | ❌ 不拆 | — |
| 19 | frontend/components/media/DoubanRecommend.tsx | 427 | 🗑️ 删除（已确认废弃，无任何 import 引用） | — |
| 20 | frontend/components/detail/FolderDetail.tsx | 414 | ⚠️ 观望 | — |
| 33 | frontend/app/page.tsx | 385 | ❌ 不拆 | — |
| 34 | frontend/app/manage/page.tsx | 359 | ⚠️ 观望 | — |
| 35 | backend/routes/download.py | 353 | ❌ 不拆（已低于红线） | — |
| 36 | frontend/types/index.ts | 468 | ❌ 不拆（纯类型定义，不适用拆分红线） | — |
| 21 | frontend/components/media/CardGrid.tsx | 351 | ❌ 不拆 | — |
| 22 | frontend/hooks/useLibrary.ts | 357 | ❌ 不拆 | — |
| 23 | frontend/components/search/FilterBar.tsx | 324 | ❌ 不拆 | — |
| 24 | frontend/components/settings/SettingsModal.tsx | 308 | ❌ 不拆 | — |
| 25 | frontend/components/media/ExplorePage.tsx | 300 | ❌ 不拆 | — |
| 26 | frontend/components/download/DownloadManagerPanel.tsx | 375 | ❌ 不拆 | — |
| 27 | frontend/components/search/SearchSettingsPanel.tsx | 298 | ❌ 不拆 | — |
| 28 | frontend/components/media/SubscribeInline.tsx | 264 | ❌ 不拆 | — |
| 29 | backend/routes/search.py | 517 | ⚠️ 观望 | — |
| 30 | backend/routes/discover.py | 462 | ❌ 不拆 | — |
| 31 | backend/routes/relocate.py | 658 | ⚠️ 观望（今日膨胀 +170 行，超红线 64%） | — |
| 32 | backend/routes/scrape.py | 508 | ❌ 不拆 | — |

---

## 不拆理由（逐个说明）

### 后端 ❌ 不拆

- **download_manager.py (809行)**：单一类 DownloadManager，所有方法服务于下载生命周期管理。职责单一，拆开反而破坏内聚。
- **structure_organizer.py (787行)**：从 organizer.py 拆出来的，职责已经收窄到"季目录整理+结构归位+归档清理"。内部函数互相调用紧密。
- **rss_engine.py (725行)**：SubscriptionScheduler 类 + 几个辅助类（SearchResultCache/RateLimiter/RSSSourceManager），都服务于订阅调度这一个功能。
- **routes/library.py (630行)**：7 个路由函数，scan_path 最大（~130行）但逻辑自洽。超 400 行红线 57%。**下次改动该文件时评估是否将 scan SSE 逻辑下沉到业务层。**
- **clean_name_system.py (643行)**：12 个纯函数，全部服务于"清洗名"这一个领域。函数间有共享的正则和常量，拆开会增加跨文件依赖。
- **file_relocator.py (583行)**：FileRelocator 单一类，所有方法服务于"归位替换"。
- **renamer.py (576行)**：从 organizer.py 拆出来的，职责已收窄到"重命名+影子名生成"。
- **organizer.py (546行)**：分类判定核心，20+ 个内部函数互相调用，拆开会破坏分类逻辑的完整性。
- **routes/discover.py (462行)**：9 个路由函数，每个都不大，总量可控。
- **routes/relocate.py (658行)**：今日膨胀 +170 行（新增 plan_tree 预览对齐），超 400 行红线 64%。4 个路由 + 3 个辅助函数（_build_*_tree），辅助函数是纯 UI 展示用的树构建。**下次改动该文件时评估是否将 _build_*_tree 下沉到业务层。**
- **routes/scrape.py (508行)**：13 个路由函数，每个都不大。超 400 行红线但拆分收益低。
- **routes/download.py (353行)**：实际已低于 400 行红线，不需要拆。

### 后端 ⚠️ 观望

- **analyzer.py (936行)**：17 个函数，分为"分析入口"和"诊断子函数"两组。诊断子函数（_diagnose_structure/scrape/shadow/quality/rename）可以拆到 `analyzer_diagnose.py`，但目前它们只被 analyze_folder 调用，拆分收益有限。**如果后续新增诊断维度导致超过 1000 行，再拆。**
- **tmdb_client.py (921行)**：TMDBClient 类 + parse_filename + ScrapeResult 数据类。parse_filename（~200行）是独立的文件名解析逻辑，和 TMDB API 无关，可以拆到 `filename_parser.py`。**但目前没有其他模块需要单独引用 parse_filename，拆分收益有限。如果后续有新模块需要引用，再拆。**
- **routes/media_info.py (737行)**：15 个函数，路由 + 多源详情获取逻辑（_try_douban_detail/_try_bangumi_detail/_try_tmdb_detail 等）。多源详情获取逻辑（~300行）可以下沉到业务层 `media_detail_service.py`。**超过 400 行红线较多，建议在下次改动该文件时顺手拆。**
- **routes/search.py (517行)**：9 个路由函数，search_single_keyword 最大（~140行）包含回退链逻辑。超 400 行红线，但回退链逻辑和路由绑定紧密。**如果后续新增搜索路由导致继续膨胀，再拆。**
- **routes/library.py (630行)**：7 个路由函数，scan_path 最大（~130行）。超 400 行红线 57%。**下次改动该文件时评估是否将 scan SSE 逻辑下沉到业务层。**
- **BatchUpgradePanel.tsx (530行)**：单一组件 + 内嵌 StatusIcon 子组件。530 行超过 300 行红线，但内部是一个完整的批量升级流程（选择→搜索→下载），拆开会破坏流程完整性。**如果后续新增功能导致继续膨胀，再拆。**
- **FolderDetail.tsx (414行)**：单一组件，文件夹详情页。超 300 行红线 38%。**下次改动该文件时评估是否拆出操作面板。**

### 前端 ❌ 不拆

- **ExpandDetail.tsx (377行)**：3 个子组件（ExpandDetail/NoDetailFallback/DetailContent），都服务于"展开详情面板"。略超 300 行红线但内聚度高。
- **DoubanRecommend.tsx (427行)**：已确认废弃——全文搜索无任何 import 引用，DiscoverPage 已完全替代其功能，且内部重复定义了 ExpandDetail/MediaDetail 等类型。**建议直接删除。**
- **routes/download.py (404行)**：19 个路由/函数，刚好踩线。每个函数都不大，sync_from_qb 最大（~130行）但逻辑自洽。不拆。

### 前端 ⚠️ 观望（文档遗漏，审查补充）

- **app/manage/page.tsx (359行)**：ManagePage 主组件 + 内嵌 ShadowCell 子组件（~65行）。ShadowCell 是独立的可编辑单元格，超过 40 行红线，可以拆为独立文件。**下次改动该文件时顺手拆出 ShadowCell。**

### 前端 ❌ 不拆（文档遗漏，审查补充）

- **app/page.tsx (385行)**：Home 主页组件，包含 normalizeLibraryPath/findLibraryNodeByPath 两个工具函数。超 300 行红线，但工具函数很短（~40行），主组件逻辑自洽。不拆。
- **types/index.ts (468行)**：纯类型定义文件，不适用组件/模块拆分红线。不拆。
- **CardGrid.tsx (351行)**：单一组件 + 几个工具函数（getSeasonLabel/getSeasonNum/getSeriesPrefix）。略超 300 行但内聚。
- **useLibrary.ts (357行)**：单一 hook，媒体库数据管理。略超但职责单一。
- **FilterBar.tsx (324行)**：已经拆成 AllFilterBar + SourceFilterBar + FilterBar 三层，结构清晰。
- **SettingsModal.tsx (308行)**：略超 300 行，单一设置弹窗。
- **ExplorePage.tsx (300行)**：刚好 300 行，不需要拆。
- **DownloadManagerPanel.tsx (375行)**：单一组件，下载管理面板。略超但内聚。
- **SearchSettingsPanel.tsx (298行)**：未超红线。
- **SubscribeInline.tsx (264行)**：未超红线。

---

## P1: SearchModal.tsx（849行 → 目标 ~250行）

### 现状
- 状态声明：~30 个 useState + 多个 useRef（约 80 行）
- 搜索逻辑：doSearch（SSE 流式）、doPanSearch、doSourceSearch、源 Tab 切换（约 300 行）
- 派生计算：searchTags、sourceDefaultKeywords、displayResults 排序/过滤（约 120 行）
- UI 渲染：顶栏 + 结果列表 + toast（约 350 行）

### 拆分方案

| 新文件 | 职责 | 预估行数 |
|--------|------|---------|
| `search/useSearchState.ts` | 所有状态 + doSearch/doPanSearch/doSourceSearch + 缓存/SSE 管理 + displayResults 排序 + searchTags/sourceDefaultKeywords 派生 | ~350 |
| `search/SearchHeader.tsx` | 顶栏 UI：标题行、搜索框（回退链+input+按钮）、BT/网盘 Tab、保存路径、SourceTabs + FilterBar | ~200 |
| `search/SearchModal.tsx` | 瘦壳：调用 useSearchState，组装 SearchHeader + BT 结果列表 + PanResultsView + toast | ~250 |

### 切割边界
- useSearchState 返回扁平对象（所有状态值 + 操作函数）
- SearchHeader 通过 props 接收状态和回调，纯展示+交互
- 瘦壳只做组装，不含业务逻辑

### 顺手清理
- 未使用的 import：EpisodeTable、INDEXER_TAG_STYLE、alistConfigured、shadowName、cleanName、totalRaw

### 验证
- [x] getDiagnostics 无新增错误
- [x] 前端构建通过
- [ ] 手动测试：打开搜索弹窗 → BT 搜索 → 切换源 Tab → 网盘搜索 → 下载

### 拆分结果
- `useSearchState.ts`：602 行（含所有状态+逻辑+缓存+SSE）
- `SearchHeader.tsx`：242 行（顶栏 UI）
- `SearchModal.tsx`：163 行（瘦壳）
- 清理了未使用的 import：EpisodeTable、INDEXER_TAG_STYLE、totalRaw

---

## P2: lib/api.ts（475行 → 每个文件 ~60-100行）

### 现状
一个巨大的 `api` 对象包含所有领域的 API 调用（~80 个方法）。

### 拆分方案

| 新文件 | 包含的 API 方法 | 预估行数 |
|--------|----------------|---------|
| `lib/api/base.ts` | request 函数 + BASE_URL 常量 | ~20 |
| `lib/api/search.ts` | search*/searchPan/getSearchSources/toggleSearchSource* | ~80 |
| `lib/api/scrape.ts` | scrape*/readScrape/executeScrape/batchScrape/uploadPoster/getLocalPoster/setPosterFromUrl/deletePoster/deleteScrape | ~80 |
| `lib/api/organize.ts` | classify/analyze*/rename*/scrapeSupplement/reorganizeSeasons/organize*/merge*/getOrganizeHistory* | ~90 |
| `lib/api/download.ts` | download/submitDownload/getDownloadTasks/getDownloadProgress/syncDownloadProgress/deleteDownloadTask*/recommendChannel/batchSearch/batchDownload/organizeDryRun/organizeExecute/archiveBoth/purgeOldData/cancelReplace | ~100 |
| `lib/api/discover.ts` | doubanHot/mediaInfo/doubanSearch/discoverRecommend/discoverExplore/discoverSources/discoverRefresh/addMedia | ~60 |
| `lib/api/subscribe.ts` | getSubscriptions/getSubscription/addSubscription/updateSubscription/deleteSubscription/triggerSubscriptionSearch/checkSubscribed/getSubscription*/getUnreadNotificationCount | ~80 |
| `lib/api/config.ts` | getConfig/saveConfig/getSearchFilter/saveSearchFilter/getSortWeights/saveSortWeights/getIndexerPriorities/saveIndexerPriorities/getNoScrape/setNoScrape/backup/restore | ~60 |
| `lib/api/system.ts` | getLibrary/getLibraryTree/scan/play/batchManage/getPosterUrl/getRecycleBin/restoreFromBin/cleanupRecycleBin/getBlacklist/*/getAnalysisReport/invalidateAnalysisCache/restartSystem | ~70 |
| `lib/api/ai.ts` | getAISuggestions/executeAISuggestions/getAIHistory/rollbackAI/rollbackRename/testAIConnection/getAIStatus/aiDiagnosis/aiSearchRecommend/setShadowName/clearShadowName/batchGenerateShadowNames | ~60 |
| `lib/api/index.ts` | 聚合导出 `api` 对象，保持 `import { api } from "@/lib/api"` 不变 | ~30 |

### 关键设计
- 保持 `import { api } from "@/lib/api"` 调用方式不变
- index.ts 从各子模块 import 后合并成一个 api 对象导出
- 所有调用方零改动

### 验证
- [x] getDiagnostics 无新增错误
- [x] 前端构建通过
- [x] 全文搜索确认无遗漏的 api 方法

### 拆分结果
- `api/base.ts`(13行) `api/search.ts`(75行) `api/scrape.ts`(31行) `api/organize.ts`(38行) `api/download.ts`(96行) `api/discover.ts`(54行) `api/subscribe.ts`(48行) `api/config.ts`(53行) `api/system.ts`(56行) `api/ai.ts`(48行) `api/index.ts`(22行)
- 旧 api.ts 已删除，Next.js 自动解析 api/index.ts，所有调用方零改动

---

## P3: routes/organize.py（1076行 → 目标每文件 ~300-400行）

### 现状
- 辅助函数（_find_duplicate_* / _resolve_plan_whitelist_path / _apply_action_plan_moves）：~250 行，纯业务逻辑不应在路由层
- organize_full + organize_full_stream：~400 行，整理流水线核心编排
- rename_item：~130 行，手动重命名 + 联动改名，独立功能
- 其他路由（rollback/rename_videos/supplement/seasons/folder/structure/merge/history）：~300 行

### 拆分方案

| 新/改文件 | 职责 | 预估行数 |
|-----------|------|---------|
| `backend/organize_executor.py`（新建业务层） | _find_duplicate_*、_resolve_plan_whitelist_path、_apply_action_plan_moves 下沉 | ~250 |
| `routes/organize.py` | 保留所有整理路由，辅助函数改为 import | ~400 |
| `routes/rename.py`（新建路由） | /rename 路由独立（和整理流水线无关） | ~140 |
| `routes/organize_stream.py`（新建路由） | /organize/full-stream SSE 流式路由独立 | ~120 |

### 注意事项
- 新路由文件需要在 main.py 中注册 router
- _apply_action_plan_moves 被 organize_full 调用，下沉后改为 from organize_executor import
- rename_item 中的媒体库同步逻辑较复杂，保持完整不拆散

### 验证
- [x] 后端 pytest 通过（test_subtitle_flatten 8/8, test_plan_tree_preview 3/3, test_season_dir_no_nest 2/2）
- [ ] 手动测试：一键整理（dry_run + 执行）、手动重命名、整理历史
- [x] 前端调用无变化（路由路径不变）

### 拆分结果
- `organize_executor.py`(399行)：辅助函数下沉到业务层
- `routes/rename.py`(159行)：/rename 路由独立
- `routes/organize_stream.py`(~110行)：/organize/full-stream SSE 路由独立
- `routes/organize.py`(602行)：保留整理路由，organize_full 仍较大但逻辑完整不宜再拆
- main.py 已注册新路由，相关测试 import 已更新

---

## P4: DiscoverPage.tsx（597行 → 目标 ~250行）

### 现状
- 已拆出 DiscoverHeader、ExplorePage、RecommendTabContent、ExpandDetail、DiscoverCard、SkeletonGrid 等子组件
- 剩余大头：订阅逻辑（~100行）、展开面板逻辑（~80行）、数据加载（~80行）、状态声明（~50行）、JSX（~150行）

### 拆分方案

| 新文件 | 职责 | 预估行数 |
|--------|------|---------|
| `media/useDiscoverState.ts` | Tab 数据管理 + 搜索 + 展开面板逻辑 + 响应式列数 + 刷新 | ~250 |
| `media/useDiscoverSubscribe.ts` | 订阅相关（handleSubscribe/Unsubscribe/SubscribeConfirm + isSubscribed 包装 + 弹窗状态） | ~120 |
| `media/DiscoverPage.tsx` | 瘦壳：调用两个 hook，组装子组件 | ~250 |

### 注意事项
- useDiscoverState 依赖 scrollContainerRef（从 props 传入），通过参数传递
- 两个 hook 之间有交互（展开面板的 detail 被订阅逻辑引用），通过返回值桥接

### 验证
- [x] getDiagnostics 无新增错误
- [x] 前端构建通过
- [ ] 手动测试：发现页切 Tab、展开详情、搜索、订阅/取消订阅

### 拆分结果
- `useDiscoverState.ts`(332行)：Tab 数据管理 + 搜索 + 展开面板 + 响应式列数
- `useDiscoverSubscribe.ts`(121行)：订阅逻辑 + 配置弹窗状态
- `DiscoverPage.tsx`(184行)：瘦壳

---

## P5: scraper.py（989行 → 目标 ~400行）

### 现状
- _scrape_tv_v3：202-612 行（~410 行），V3 TV 刮削核心，单函数最大
- _scrape_tv（旧版）：~110 行
- _scrape_collection：~20 行
- scrape_folder（入口）+ _search_tmdb + _episode_nfo_matches_target：~150 行
- _scrape_movie：~50 行
- scrape_video + batch_scrape + _ai_fallback_scrape：~210 行

### 拆分方案

| 新/改文件 | 职责 | 预估行数 |
|-----------|------|---------|
| `backend/scraper_tv.py`（新建） | _scrape_tv_v3 + _scrape_tv（旧版）+ _scrape_collection | ~540 |
| `backend/scraper.py` | 入口函数 + _search_tmdb + _scrape_movie + scrape_video + batch_scrape + _ai_fallback_scrape | ~400 |

### 注意事项
- _scrape_tv_v3 内部调用 _search_tmdb、_episode_nfo_matches_target（留在 scraper.py），拆分后从 scraper import
- 避免循环导入：scraper_tv 从 scraper 导入工具函数，scraper 从 scraper_tv 导入 _scrape_tv_v3/_scrape_tv/_scrape_collection
- 如果循环导入无法避免，将共享工具函数（_search_tmdb、_episode_nfo_matches_target）提取到 scraper_utils.py

### 验证
- [x] 后端 pytest 通过（test_scraper_tv_dry_run_actions 1/1, test_season_dir_no_nest 2/2, test_subtitle_flatten 8/8）
- [ ] 手动测试：刮削文件夹（TV + Movie）、批量刮削、AI 回退刮削

### 拆分结果
- `scraper_tv.py`(688行)：_search_tmdb + _episode_nfo_matches_target + _scrape_collection + _scrape_tv_v3 + _scrape_tv
- `scraper.py`(472行)：scrape_folder + _scrape_movie + scrape_video + batch_scrape + _ai_fallback_scrape + re-export
- 循环导入通过延迟导入解决（_scrape_collection 和 _scrape_tv 中 `from scraper import scrape_folder/scrape_video`）

---

## 执行节奏

- 每次只做一个拆分，独立验证后提交
- 拆分顺序按优先级 P1 → P5
- 每个拆分完成后更新本文档勾选状态
- 观望项（⚠️）在下次改动该文件时评估是否顺手拆
