# [TODO] 项目整体优化 — 收口校准阶段任务清单

> 当前阶段：功能已基本完成，优先证明主链路没有被破坏。
> 执行原则：只做低风险收口与验证底座，不做功能扩展，不做架构升级。
> 来源：`optimization-master-plan.md` 的“当前阶段覆盖协议”。

---

## 0. 执行红线

- [ ] 每轮只做一种改动：结构收口 / 类型补强 / 测试补强 / 文档补强
- [ ] 当前阶段默认不改业务逻辑
- [ ] 默认不碰高风险链路：naming 规则、search filter/sort、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环
- [ ] 前端当前只记录技术债，不改 UI / 样式 / design token
- [ ] 无法证明行为等价时停止修改

---

## 1. 行为基线优先

目标：先有证据，再做收口。

### 本轮基线记录（2026-04-23）

- 工作区状态：基线运行时已有未提交改动，涉及 `optimization-master-plan.md`、`backend/analyzer.py`、`backend/file_relocator.py`、`backend/nfo_handler.py`、`backend/organizer.py`、`backend/renamer.py`、`backend/core/`、`backend/test_core_constants.py`、本 TODO 文件。
- 搜索 / 命名 / 智能过滤逻辑基线：`cd backend && python -X utf8 -m pytest -s test_search_query_builder.py test_search_keyword_mapper.py test_result_sorting.py test_smart_filter.py test_smart_filter_multilang.py test_clean_name_system.py test_english_name_fix.py`，结果 `206 passed, 1 warning`。
  - 已记录样本：短名保护、跨语言 match_names、中文噪声、不相关结果 unmatched、source keyword 回退链、clean_name cn/en/original 拆分与 original_title 语言判断。
  - warning：`.pytest_cache` 写入权限残留，属于 Windows 环境噪声。
- 整理 / NFO / dry-run 本地基线：`cd backend && python -X utf8 test_code_split.py`，结果 `33/33 passed`。
  - 覆盖：NFO 写读、标准名、shadow_name、classify_folder、smart_archive_plan、reorganize_seasons dry_run、关键路由注册。
  - 注意：`python -m pytest test_code_split.py` 不适合作为基线入口；文件内辅助函数 `test(name, fn)` 会被 pytest 错误收集。
- 未运行真实 NAS 整理回归：`test_organize_pipeline.py` 会访问 `\\DS218play\share\视频`，包含 `archive_old_scrape(..., delete_after=True)`、强制刮削和恢复旧刮削动作；当前收口阶段不作为默认基线运行。
- 订阅后端测试不作为当前默认基线：`test_subscriber.py` / `test_subscribe_e2e.py` / `test_subscribe_integration.py` 会读写当前订阅状态，且检测到本机 8000 后端时会请求真实本地 API；本轮运行结果显示数据隔离失败、fixture 收集错误、手动搜索 10s 超时。
- 前端 vitest 基线：`cd frontend && npm run test` 非沙盒运行结果 `97 passed, 9 failed`，失败集中在订阅 / 网盘筛选测试断言与当前 UI 行为不一致。

- [ ] 搜索链路基线
  - 范围：`/api/search/stream`、`/api/search/source`、订阅直搜调用
  - 记录：输入关键词、辅助名称、命中源、排序前后结果、过滤原因
  - 验证：同一输入下排序 / 过滤 / 命中词可复现
  - 当前部分基线：已完成搜索词构造、排序、智能过滤逻辑层测试；尚未记录真实 `/api/search/stream` / `/api/search/source` SSE/API 输出。

- [ ] 命名链路基线
  - 范围：文件名解析、clean_name、shadow_name、cn/en/original 写入
  - 记录：真实样本输入 → 结构化名称输出
  - 验证：短名保护、中英混合、original_title 语言判断不漂移
  - 当前部分基线：已完成 clean_name 单元样本与 NFO → shadow_name 本地回归；尚未记录真实媒体库样本输出快照。

- [ ] 刮削 / TV 映射基线
  - 范围：候选选择、TV 确权、分集映射、NFO 输出字段
  - 记录：样本目录、候选列表、最终选择、episode 映射
  - 验证：同一输入下候选选择和映射一致

- [ ] organize dry-run / execute 基线
  - 范围：wrap、archive、rename、reorganize seasons
  - 记录：dry-run plan、execute 消费字段、落盘动作摘要
  - 验证：execute 只执行 dry-run 计划中的动作
  - 当前部分基线：已完成本地临时目录 dry-run / NFO / 路由注册回归；未运行 execute，也未访问真实 NAS。

- [ ] 下载 → 归位闭环基线
  - 范围：下载完成检测、relocate dry-run、冲突探测、confirm_replace / archive_both
  - 记录：白名单、plan、coexist_pairs、回收站动作
  - 验证：旧资源识别与新资源白名单不漂移
  - 当前部分基线：已完成 `file_relocator.py` 冲突探测 / 回收动作测试，新增 `routes/relocate.py` 隔离测试，锁定 `/organize/dry-run` 返回的 `old_tree/new_tree/plan_tree` 结构、qB 白名单注入、`/organize/execute` 成功归档与失败不归档、`/organize/archive-both` 的重新探测与成功归档、`/organize/purge-old` 的“无白名单即停止”和“逐个回收旧资源”行为；已新增 `download_manager.py` 隔离测试，锁定订阅下载完成回调会在 `best_version=true` 时触发 `_auto_relocate()`，`_auto_relocate()` 会以 `daemon=True`、线程名 `relocate-{task.id}` 启动后台线程，在 `local_file_path` 缺失时先尝试 `media_matcher.match()` 补定位并写回订阅，再继续执行 `relocate()`，且在 `awaiting_confirm` 时继续 `confirm_replace()`、在 `archived` 时不重复确认；`sync_progress()` 在 qB/alist 任务从 `downloading -> completed` 时会触发 `_relocate_to_save_path()` 并在订阅任务场景下继续调用 `_notify_subscription_complete()`，`on_startup()` 会把残留 `pending` 任务标记为 `failed` 并对 `downloading` 任务执行 `_reconcile_task()`，以及 `_sync_qb_progress()` / `_sync_alist_progress()` / `_reconcile_task()` 的关键边界状态：qB `pausedUP` / `stalledUP` 视为 completed、qB `missingFiles` 维持 `downloading`、qB 查不到 hash 或启动对账丢 hash 视为 lost、qB 登录失败或 info 接口非 200 视为 unknown、无 downloader hash 的启动对账任务视为 lost、Alist undone `state!=2` 维持 `cloud_download`、Alist undone `state=2` 进入 `local_sync`、Alist done+本地文件存在视为 completed、Alist done+本地文件缺失维持 `local_sync`、Alist undone 请求失败视为 unknown、Alist 两侧都找不到任务视为 lost；尚未覆盖真实下载器长时间卡住、真实 RecycleBin 落盘和真实线程并发竞争。

---

## 2. 低风险结构收口

目标：只收口稳定、重复、可回滚的静态结构。

- [x] 建立基础规则中心 `backend/core/constants.py`
  - 已完成：视频扩展名、字幕扩展名、标准 NFO 名、同名刮削后缀等低风险静态规则
  - 风险记录：第一轮曾触碰 `file_relocator.py` 常量引用，后续默认不再主动碰该链路

- [x] 规则中心剩余重复点盘点
  - 只列清单，不直接改代码
  - 输出：重复规则位置、是否高风险、是否已有测试、建议处理时机

### 规则中心剩余重复点盘点（2026-04-23）

> 本节只记录候选，不迁移代码。后续如要收口，每轮只选一个低风险重复点，并先跑对应行为基线。

| 重复规则 | 位置 | 是否高风险 | 现有测试 / 基线 | 建议处理时机 |
|---|---|---|---|---|
| 视频扩展名集合 | 已接入：`analyzer.py`、`organizer.py`、`nfo_handler.py`、`renamer.py`、`file_relocator.py`；仍重复：`download_manager.py`、`routes/organize.py`、`routes/scrape.py`、`routes/tools.py`、`routes/poster.py`、`scraper.py`、`shared.py`、`structure_organizer.py`、`tmdb_client.py`、`episode_search.py`、`clean_name_system.py`、`test_l1l4_integration.py`、`test_sandbox_name_pipeline.py` | 中到高；`routes/organize.py`、`scraper.py`、`structure_organizer.py`、`file_relocator.py` 属于整理 / 刮削 / 归位链路 | `test_core_constants.py` 覆盖常量本身；`test_code_split.py` 覆盖部分整理 / NFO smoke；搜索 / 命名基线已记录 | 先从测试文件或只读扫描入口开始；整理、刮削、下载归位相关文件必须单独一轮并带基线 |
| 字幕扩展名集合 | 已接入：`analyzer.py`；仍重复：`structure_organizer.py` 多处 | 高；字幕归属会影响结构整理与关联文件移动 | 当前只有 `test_code_split.py` 间接覆盖部分整理场景，缺少字幕关联专项断言 | 等 organize dry-run / execute 行为保护补强后再迁移 |
| 标准 NFO 名：`movie.nfo` / `tvshow.nfo` / `season.nfo` | 已接入：`nfo_handler.py`；仍重复：`analyzer.py`、`scanner.py`、`scraper.py`、`routes/library.py`、`routes/media_info.py`、`routes/scrape.py`、`shadow_name_manager.py`、`structure_organizer.py`、测试样本 | 高；涉及 NFO 读取优先级、刮削写回、清理旧刮削和 TV 信任锁定 | `test_code_split.py` 覆盖 NFO 写读；`test_core_constants.py` 覆盖常量顺序；缺少 scraper / routes mock 行为保护 | 先迁移只读检测位点；`scraper.py`、`routes/scrape.py` 必须等刮削 / TV 映射基线补齐 |
| 文件夹级海报名：`poster.jpg` / `poster.png` / `folder.jpg` / `cover.jpg` 等 | `nfo_handler.py`、`organizer.py`、`scanner.py`、`routes/poster.py`、`routes/scrape.py`、`structure_organizer.py` | 中到高；影响封面发现、清理旧刮削、前端图片展示 | 现有测试多为 NFO / dry-run smoke，缺少 poster lookup 专项快照 | 可作为独立“只读图片查找规则”收口；不要和刮削清理规则同轮改 |
| 视频同名 sidecar 后缀：`.nfo`、`-poster.jpg`、`-poster.png`、`-fanart.jpg`、`-clearlogo.png`、`-thumb.jpg` | 已接入：`renamer.py`；仍重复：`routes/organize.py`、`routes/scrape.py`、`routes/tools.py`、`structure_organizer.py`、`file_relocator.py` 局部同名图片处理 | 高；影响重命名关联文件、刮削清理、归位回收 | `test_core_constants.py` 覆盖常量；缺少同名 sidecar 删除 / 移动专项行为保护 | 暂缓；先补 sidecar 行为测试，再按“重命名”或“清理旧刮削”单链路迁移 |
| 回收 / 清理旧刮削文件集合 | 已接入部分：`file_relocator.py` 使用 `RECYCLE_DIR_NFO_AND_ART`；仍重复：`routes/scrape.py`、`structure_organizer.py`、`scraper.py` | 高；直接涉及删除 / 移动 / 覆盖 | 当前不运行真实 NAS 整理回归；`test_organize_pipeline.py` 因真实路径与删除动作不作为默认基线 | 当前阶段只记录，不迁移；必须先有临时目录级 delete/dry-run 行为保护 |
| 测试内重复媒体扩展名 | `test_l1l4_integration.py`、`test_sandbox_name_pipeline.py`、局部测试样本 | 低；只影响测试自身 | `test_core_constants.py` 已覆盖规则中心 | 可作为下一轮低风险测试补强 / 结构收口候选，避免触碰业务链路 |

- [x] shared.py 职责盘点
  - 只列新增禁止项和现有职责，不迁移代码
  - 输出：单例工厂 / 配置装配 / 生命周期 / 业务 helper 分类表

### `shared.py` 职责盘点（2026-04-23）

> 本节只盘点职责边界，不迁移代码。`shared.py` 当前是多数路由的依赖入口，后续任何拆分都必须先证明导入链和启动副作用不漂移。

| 分类 | 当前内容 | 主要调用方 | 风险等级 | 后续处理建议 |
|---|---|---|---|---|
| 启动级全局副作用 | logging 配置、Windows stdout/stderr UTF-8 重包、`config_m` / `shadow_m` / `indexer_m` / `torrent_bl` / `analysis_cache` / `media_matcher` 初始化、启动时媒体库索引构建、`save_library` 回调注册 | 应用启动、所有导入 `shared.py` 的路由 / 服务 | 高；导入即执行，拆错会影响全局启动和媒体库索引 | 当前只记录，不迁移；如要收口，必须先有启动 smoke 和索引刷新行为验证 |
| 单例工厂 | `_get_sub_manager()`、`_get_download_manager()`、`_get_pan_search_service()`、`_get_recycle_bin()`、`_get_file_relocator()` | `routes/download.py`、`routes/relocate.py`、`routes/subscribe.py`、`routes/config.py`、`routes/system.py`、`download_manager.py` | 高；涉及订阅状态、下载状态、归位器循环导入和回收站配置 | 保留为当前稳定入口；禁止在未补隔离测试前拆分 |
| 搜索源懒加载工厂 | `_get_bitsearch_scraper()`、`_get_cilixiong_scraper()`、`_get_xl720_scraper()`、`_get_nyaa_scraper()`、`_get_mikan_scraper()`、`_get_yts_scraper()`、`_get_limetorrents_scraper()`、`_get_acgrip_scraper()`、`_get_bangumi_moe_scraper()`、`_get_eztv_scraper()`、`_get_dmhy_scraper()`、`_get_1337x_scraper()` | `routes/search.py`、`search_service.py`、`test_bt_expand.py` | 中到高；涉及代理选择、源初始化和搜索链路 | 后续可单独评估“搜索源工厂”模块，但必须不改变 source proxy 和懒加载时机 |
| 配置驱动客户端装配 | `get_clients()`、`_tmdb_client()` | `routes/search.py`、`routes/discover.py`、`routes/media_info.py`、`combined_recommend.py`、`rss_engine.py`、`local_media_matcher.py` | 中；重复创建客户端但行为稳定，改动会影响多模块外部服务调用 | 暂不迁移；如迁移，先锁定客户端字段集合与代理传参基线 |
| 路径 / 分类 helper | `_get_category_from_path()`、`_is_top_category()` | `routes/analyze.py`、`routes/organize.py`、`routes/relocate.py`、`routes/config.py` 等 | 高；影响整理分类、电影顶层目录特殊处理、归位判断 | 属于 organize 主链路保护区，当前禁止迁移 |
| 媒体库路径同步 helper | `_sync_library_paths()` | `routes/organize.py`、`routes/scrape.py`、`routes/download.py`、`routes/library.py` 等 | 高；写 `media_library.json`，影响移动后的库路径一致性 | 不与结构收口同轮修改；必须先有 dry-run/execute 消费字段测试 |
| 名称可信度 helper | `NAME_SOURCE_PRIORITY`、`safe_set_clean_name()` | `test_name_trust.py`，并与 `clean_name_system.py` / `shadow_name_manager.py` 的优先级规则存在对应关系 | 中到高；涉及命名覆盖优先级 | 不在 shared 收口轮修改；后续如统一，先解决重复优先级表并跑命名基线 |
| 刮削后回写 helper | `_update_clean_names_after_scrape()` | `routes/scrape.py`，多个路由批量导入但未必直接使用 | 高；读写媒体库并调用 `clean_name_system.safe_update_clean_name()` | 属于刮削 / 命名交叉链路，当前只记录，不迁移 |

#### `shared.py` 新增禁止项

- 禁止继续新增业务流程编排逻辑；流程应留在对应 route / service / manager 中。
- 禁止新增会删除、移动、覆盖文件的 helper；文件操作应留在明确的整理 / 归位模块，并带 dry-run 或专项测试。
- 禁止新增搜索过滤 / 排序规则；搜索规则应留在搜索链路模块，并先有排序 / 过滤基线。
- 禁止新增命名清洗规则；命名规则应留在 `clean_name_system.py` / 对应命名模块，并跑命名基线。
- 禁止新增前端接口响应字段拼装；路由层应保持当前字段约定，不借 `shared.py` 隐式改变接口。
- 禁止在导入期新增外部网络请求或真实 NAS 文件访问；当前导入期副作用已足够重，后续只能减少，不能扩张。

- [x] 路由层重逻辑盘点
  - 范围：超过 400 行路由、超过 20 行辅助函数
  - 输出：候选下沉点、风险等级、前置测试需求

### 路由层重逻辑盘点（2026-04-23）

> 本节只列候选，不下沉代码。当前阶段默认不改路由行为；高风险链路候选必须先补行为保护测试。

#### 超过 400 行路由

| 路由文件 | 行数 | 主要重逻辑 | 风险等级 | 前置测试需求 |
|---|---:|---|---|---|
| `routes/organize.py` | 803 | `rename_videos()`、`organize_full()`、`rename_item()`、`organize_full_stream()` 内含文件移动、NFO 写入、影子名写入、媒体库路径同步、SSE 流程编排 | 高；属于 organize executor / naming / TV 映射保护区 | `test_code_split.py` smoke 之外，需补 action_plan execute 只消费 dry-run plan、单文件重命名 sidecar、SSE 事件顺序测试 |
| `routes/media_info.py` | 737 | 豆瓣 / Bangumi / TMDB 多源详情、评分补全、候选选择、enrich_cache 回写、NFO / poster 写入 | 中到高；影响详情页、发现推荐补全、刮削选择 | 需 mock 豆瓣 v2 / Bangumi / TMDB，覆盖 source/id 直拉、fallback 顺序、返回字段稳定 |
| `routes/library.py` | 608 | `/scan` 和 `/sync` SSE 扫描、媒体库增删同步、树构建、folder_type 推断、clean_name 继承和 NFO 读取补全 | 高；影响媒体库入口、命名展示、文件系统扫描 | 需用临时目录覆盖 scan/sync 增删、树结构快照、folder_type 推断、clean_name 字段稳定 |
| `routes/search.py` | 517 | `/api/search/source` 回退链、单源 dedupe/enrich、`/search/single` 裸搜和智能过滤、源开关配置 | 高；属于 search filter / sort 保护区 | 已有搜索逻辑层基线；若下沉需补 `/api/search/source` mock 源测试和 `/search/single` skip_filter 行为测试 |
| `routes/scrape.py` | 508 | 索引器配置同步、`scrape_select()` 写 NFO / poster / shadow_name、`execute_scrape()` 强制季化 + 递归刮削、`delete_scrape()` 删除刮削文件 | 高；涉及刮削、TV 映射、删除文件 | 需临时目录 + mock TMDB 覆盖 select/execute/delete，尤其 delete 必须先 dry-run 或专项删除断言 |
| `routes/relocate.py` | 485 | 旧/新/计划三栏树构建、download task dry-run、confirm_replace、archive_both、purge_old | 高；属于 file_relocator 冲突探测和下载→归位闭环保护区 | 需 mock DownloadManager / FileRelocator / qB 文件列表，覆盖 whitelist、coexist_pairs、plan_tree、confirm/archive/purge |
| `routes/discover.py` | 462 | 热榜缓存、TMDB 并发补全、推荐源 fallback、探索筛选 / 补位、缓存清理 | 中；主要影响发现页展示和外部源回退 | 需 mock 豆瓣 / TMDB / Bangumi，覆盖缓存命中、fallback、评分过滤补位、返回字段稳定 |

#### 超过 20 行的辅助函数 / 内嵌函数候选

| 候选 | 位置 | 当前职责 | 风险等级 | 建议处理 |
|---|---|---|---|---|
| `event_generator()` | `routes/library.py` / `scan_path()` 内嵌 | 扫描文件、ffprobe、clean_name 初始化、保存媒体库、SSE 输出 | 高 | 先补 scan SSE 集成测试；后续可考虑下沉到扫描服务，但不能改变事件字段 |
| `event_gen()` | `routes/library.py` / `quick_sync()` 内嵌 | 文件系统增删对账、大小变化检测、快速模式、影子名填充、SSE 输出 | 高 | 先补临时目录 sync 行为测试；不要和 scan 同轮改 |
| `finalize()` / `post_process()` | `routes/library.py` / `get_library_tree()` 内嵌 | 树结构聚合、folder_type 推断、clean_name 继承、NFO 补全 | 高 | 先做树结构快照测试；命名继承属于 naming 保护区 |
| `_build_old_tree()` / `_build_new_tree()` / `_build_plan_tree()` | `routes/relocate.py` | 前端三栏树数据构建 | 中到高 | 可作为相对独立的只读 DTO/展示层候选，但需锁定字段快照 |
| `_enrich_ratings()`、`_try_*_detail()`、`_format_*_detail()` | `routes/media_info.py` | 多源详情拉取、评分补全、格式统一 | 中 | 可作为 media info service 候选；前置 mock 外部源和字段快照 |
| `enrich_item()` | `routes/discover.py` / `douban_hot()` 内嵌 | TMDB 并发补封面、年份、英文名 | 中 | 可先下沉为纯函数候选，但需缓存/fallback 快照 |
| `discover_explore()` 内筛选 / 补位逻辑 | `routes/discover.py` | 豆瓣 / TMDB / Bangumi 探索参数分派、评分过滤、补位 | 中 | 不与 UI 调整同轮改；先补 provider mock 测试 |
| `/api/search/source` 内 source getter / fallback / dedupe | `routes/search.py` | 单源搜索回退链和命中词记录 | 高 | 属于 search 保护区；先补 mock 源测试 |
| `/search/single` 内 skip_filter 直搜合并 | `routes/search.py` | Prowlarr + 多直搜源合并、hash 去重、过滤切换 | 高 | 属于 search sort/filter 保护区；当前只记录 |
| `scrape_select()` / `delete_scrape()` 内文件写删逻辑 | `routes/scrape.py` | NFO / poster 写入、旧刮削清理、单视频文件夹判断 | 高 | 删除 / 覆盖类逻辑暂不下沉；先补临时目录专项测试 |
| `sync_from_qb()` | `routes/download.py` | qB 全量状态同步、导入任务、状态映射 | 中到高 | 路由未超过 400 行但函数重；如改动需 mock qB API 和 DownloadManager 状态迁移 |

#### 路由层新增禁止项

- 禁止在路由中继续新增文件移动 / 删除 / 覆盖细节；新增前必须有对应 manager/service 或专项测试。
- 禁止在路由中新增搜索排序 / 过滤规则；搜索行为应进入搜索链路模块并跑基线。
- 禁止在路由中新增命名清洗 / 覆盖优先级规则；命名规则应留在命名模块。
- 禁止在一个 PR / 一轮中同时下沉多个高风险路由；每轮只处理一个候选，并保留接口字段不变。
- 禁止仅因行数长就拆分；没有前置测试的高风险候选只记录，不实施。

---

## 3. DTO / 类型补强准入

目标：先定义边界，不做全量迁移。

- [x] DTO 候选清单
  - 命名域：MediaNameBundle / NameSource / WritebackResult
  - 搜索域：SearchRequest / SearchResult / SearchContext
  - 刮削域：ScrapePlan / ScrapeCandidate / EpisodeMapping
  - 整理域：OrganizePlan / OrganizeResult
  - 下载域：RelocatePlan / RelocateResult / CoexistPair

### DTO 候选清单（2026-04-23）

> 本节只定义候选边界，不新增 DTO，不迁移 dict，不改变接口字段。已有模型优先复用；新增 DTO 只能作为内部边界，不能直接改变前端响应。

| 领域 | 候选 DTO | 已有模型 / 字段关系 | 风险等级 | 当前建议 |
|---|---|---|---|---|
| 命名域 | `MediaNameBundle` | 已有 `clean_name_system.CleanNameResult`，媒体库 item 仍散落 `clean_name`、`clean_name_cn`、`clean_name_en`、`clean_name_original`、`clean_name_source` | 高；属于 naming 规则保护区 | 不新增；如需要，优先评估 `CleanNameResult` 是否足够表达，不另起重复模型 |
| 命名域 | `NameSource` | 已有 `NAME_SOURCE_PRIORITY` 重复存在于 `shared.py` / `clean_name_system.py`，`shadow_name_manager.py` 也有优先级说明 | 中到高；影响覆盖优先级 | 只记录；后续应先统一优先级来源，再考虑枚举化 |
| 命名域 | `WritebackResult` | 当前 `safe_update_clean_name()` 返回 bool，`_update_clean_names_after_scrape()` 只内部吞异常 | 中；影响调试可见性但不应改行为 | 可作为低风险内部测试辅助候选，但必须保持外部调用返回不变 |
| 搜索域 | `SearchRequest` | 路由参数分布在 `/api/search`、`/api/search/stream`、`/api/search/source`、`/search/single`；`search_service.build_keywords()` 已形成隐式请求边界 | 高；属于 search filter / sort 保护区 | 暂不新增；先补 `/api/search/source` mock 源测试后再评估 |
| 搜索域 | `SearchResult` | 已有 `searcher.SearchResult`；路由 enrich 后额外增加 `match_score`、`quality_score`、`is_junk`、`junk_reasons` 等 dict 字段 | 高；影响前端搜索结果展示与排序过滤 | 不创建并列 `SearchResult`；后续若补强，应考虑 `EnrichedSearchResult` 但必须字段兼容 |
| 搜索域 | `SearchContext` | 当前由 `query`、`shadow_name`、`clean_name`、`cn/en/original_name`、`season_number`、fallback keywords 组合而成 | 高 | 只记录；上下文对象会影响回退链和命中词，不在当前阶段实现 |
| 刮削域 | `ScrapeCandidate` | TMDB / 豆瓣 / Bangumi 候选 dict 字段不完全一致；已有 `tmdb_client.ScrapeResult` 表示详情结果，不等同候选 | 中到高；影响候选选择和详情页 | 可作为后续 media_info service 的内部候选；先补多源 mock 字段快照 |
| 刮削域 | `ScrapePlan` | `scraper.scrape_folder(..., dry_run=True)` 和 `routes/organize.py` action_plan 使用 dict：`tmdb_match`、`plan`、`summary` 等 | 高；涉及刮削 / TV 映射 / organize dry-run | 暂不新增；必须先锁定 action_plan 字段快照 |
| 刮削域 | `EpisodeMapping` | 当前散落字段：`season`、`episode`、`episode_title`、`target_season_dir`、`target_filename`、`mapped` | 高；属于 TV 映射保护区 | 只记录；等 TV 映射基线完成后再评估 |
| 整理域 | `OrganizePlan` | 当前 `organize_full(dry_run=True)` 返回 `wrap_plan`、`archive_plan`、`tmdb_match`、`plan`、`summary` | 高；属于 organize executor 保护区 | 不新增；先补 execute 只消费 dry-run plan 的行为测试 |
| 整理域 | `OrganizeResult` | 当前多路由返回 dict：`ops`、`count`、`steps`、`mode`、`status`、`snapshot_id` 等 | 高；涉及文件移动和媒体库路径同步 | 只记录；短期不要统一字段，避免接口漂移 |
| 下载 / 归位域 | `RelocatePlan` | `file_relocator.RelocateResult.action_plan` 仍为 dict；`routes/relocate.py` 额外构造 `old_tree`、`new_tree`、`plan_tree` | 高；属于 file_relocator 冲突探测和下载→归位闭环 | 暂不新增；可先把三栏树作为展示层快照测试对象 |
| 下载 / 归位域 | `RelocateResult` / `CoexistPair` | 已有 `file_relocator.RelocateResult` 与 `CoexistPair` | 高 | 复用现有模型，不另建；若扩展字段必须先补冲突探测测试 |
| 下载域 | `DownloadTaskSnapshot` | 已有 `download_manager.DownloadTask`；路由读取任务后组合进度、qB 状态、归位状态 | 中到高 | 只记录；如要补强，先 mock qB sync 状态迁移 |
| 测试辅助域 | `RouteResponseSnapshot` | 当前测试多直接断言 dict 字段；缺少统一快照 helper | 低 | 可作为第一批低风险候选，仅用于测试辅助，不进入生产接口 |

#### 已有模型优先级

- 搜索结果优先复用 `searcher.SearchResult`，不要新增同名模型。
- 刮削详情优先复用 `tmdb_client.ScrapeResult`，候选和计划不能混用详情模型。
- 归位结果优先复用 `file_relocator.RelocateResult` / `CoexistPair`。
- 命名结构优先复用 `clean_name_system.CleanNameResult`，不要再新增并行 clean-name dict 规范。
- 订阅 / 下载状态优先复用 `subscriber.Subscription`、`subscriber.SearchLogEntry`、`download_manager.DownloadTask`。

- [x] DTO 准入检查
  - 是否存在重复 dict 字段
  - 是否行为稳定
  - 是否不改变接口字段
  - 是否有测试覆盖
  - 是否可完全回滚

### DTO 准入检查（2026-04-23）

> 本节只定义准入结果，不实施 DTO。结论以“当前是否适合进入第一批”为准；高风险候选即使字段重复，也不准入。

#### 准入判定表

| 候选 | 重复 dict 字段 | 行为稳定 | 不改变接口字段 | 测试覆盖 | 可完全回滚 | 当前准入 |
|---|---|---|---|---|---|---|
| `MediaNameBundle` / `CleanNameResult` 包装 | 是：`clean_name*` 字段分散在媒体库、library tree、discover enrich | 部分稳定；命名基线已有但真实媒体库快照不足 | 可做到，但易误改前端字段 | 有 `test_clean_name_system.py` / `test_english_name_fix.py`，缺真实树快照 | 可回滚 | 暂不准入；属于 naming 保护区 |
| `NameSource` | 是：优先级表重复 | 部分稳定 | 可做到 | `test_name_trust.py` 覆盖旧逻辑，需同步 clean_name_system | 可回滚 | 暂不准入；先统一优先级来源 |
| `WritebackResult` | 否，当前只是 bool / 吞异常 | 稳定 | 可做到 | 现有测试不足 | 可回滚 | 可作为低风险内部候选，但优先级低 |
| `SearchRequest` | 是：多个 search 路由参数重复 | 不足；回退链仍是高风险行为 | 理论可做到 | 逻辑层测试有，API/source mock 不足 | 可回滚 | 不准入 |
| `EnrichedSearchResult` | 是：`match_score`、`quality_score`、`is_junk`、`junk_reasons` 等 enrich 字段 | 部分稳定；已有排序 / 智能过滤基线 | 必须完全兼容现有 dict | `test_result_sorting.py`、`test_smart_filter*.py` 覆盖较多；缺 API 快照 | 可回滚 | 暂不准入；先补 `/api/search/source` mock 源测试 |
| `SearchContext` | 是：query + 多语言名 + season + fallback 组合重复 | 不足；影响命中词顺序 | 理论可做到 | `test_search_query_builder.py` / keyword mapper 覆盖部分 | 可回滚 | 不准入 |
| `ScrapeCandidate` | 是：TMDB / 豆瓣 / Bangumi 候选字段相似但不一致 | 不足；多源 fallback 复杂 | 可作为内部，不直接改响应 | 缺多源 mock 字段快照 | 可回滚 | 暂不准入 |
| `ScrapePlan` | 是：`tmdb_match`、`plan`、`summary`、episode mapping dict 重复 | 不足；涉及 TV 映射和 dry-run | 不能保证 | 缺 action_plan 字段快照 | 可回滚但风险高 | 不准入 |
| `EpisodeMapping` | 是：`mapped.season/episode` 等字段重复 | 不足；TV 映射保护区 | 理论可做到 | 缺绝对集数 / 特别篇专项测试 | 可回滚 | 不准入 |
| `OrganizePlan` | 是：`wrap_plan`、`archive_plan`、`plan` 等 | 不足；execute 消费 plan 风险高 | 不能保证 | `test_code_split.py` smoke，不足以锁字段 | 可回滚但风险高 | 不准入 |
| `OrganizeResult` | 是：`ops`、`count`、`steps` 等 | 不足；各路由返回语义不同 | 容易漂移 | 现有覆盖不足 | 可回滚 | 不准入 |
| `RelocatePlan` | 是：`action_plan` dict + 三栏树字段 | 不足；冲突探测保护区 | 不能保证 | 缺 relocator 临时目录 / qB mock 测试 | 可回滚但风险高 | 不准入 |
| `RelocateResult` / `CoexistPair` 扩展 | 已有模型，非新增 | 部分稳定 | 扩展字段需谨慎 | 现有覆盖不足 | 可回滚 | 不准入扩展；只允许复用 |
| `DownloadTaskSnapshot` | 是：路由组合 qB / 下载 / 归位字段 | 部分稳定 | 可作为内部 | 缺 qB sync 状态迁移 mock | 可回滚 | 暂不准入 |
| `RouteResponseSnapshot` | 是：测试内直接断言 dict 字段分散 | 稳定性取决于测试样本 | 不影响生产接口 | 可新增测试辅助覆盖 | 可完全回滚 | 准入；仅限测试辅助，不进生产接口 |

#### 当前 DTO 准入规则

- 第一批 DTO 只能用于测试辅助、只读快照或内部调试结果，不得直接改变接口响应。
- 已有模型能表达的场景，禁止创建同名 / 并行 DTO。
- 任一候选只要触碰 search sort/filter、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环，即使字段重复也不准入。
- 准入前必须有字段快照或行为测试；没有测试的候选只能继续留在清单。
- DTO 迁移必须保持输入 / 输出字段名、默认值、排序、过滤结果不变；无法证明时停止。
- 每轮最多迁移一个 DTO 边界，并且必须能通过删除新增 DTO 回滚到原 dict 实现。

- [x] 第一批 DTO 只允许从低风险边界开始
  - 候选：只读分析结果、内部配置快照、测试辅助模型
  - 排除：search sort/filter、organize executor、file_relocator 冲突探测
  - 已完成：新增测试辅助模型 `RouteResponseSnapshot`，只记录响应结构快照，不接入生产路由 / 接口。

---

## 4. 测试与验证债务

目标：把“无法证明”的地方显性化。

- [x] 记录当前前端 vitest 失败项
  - 现状：订阅 / 网盘筛选相关测试存在既有失败
  - 要求：不在收口轮顺手修，单独开测试修复任务
  - 2026-04-23 记录：`npm run test` 非沙盒结果 `97 passed, 9 failed`；失败项集中在 `split-components.test.tsx` 3 个、`subscribe-components.test.tsx` 1 个、`subscribe-deep.test.tsx` 1 个、`subscribe-final.test.tsx` 4 个。

- [x] 记录 Windows 权限残留
  - 现状：`.pytest_cache/`、`backend/.pytest_cache/`、`backend/tmp*` 可能出现权限 warning
  - 要求：不使用激进权限命令作为常规验证步骤
  - 2026-04-23 记录：`git status` / `rg --files` / pytest 均复现 `.pytest_cache`、`backend/.pytest_cache`、`backend/tmp*` 权限 warning；沙盒内运行文件写入类测试会留下不可访问 `backend/tmp*`。

- [x] 为每个高风险链路补最小行为保护测试计划
  - 输出：测试入口、样本数据、断言字段、预期风险

### 高风险链路最小行为保护测试计划（2026-04-23）

> 本节只定义后续测试准入，不在本轮新增测试代码。

| 链路 | 建议测试入口 | 样本数据 | 最小断言字段 | 预期风险 |
|---|---|---|---|---|
| naming 规则 | `backend/test_clean_name_system.py` + `backend/test_english_name_fix.py` | 短中文名、短英文名、中英混合、日文 / 韩文 original_title、已有 manual/tmdb 高优先级 clean_name | `clean_name`、`clean_name_cn`、`clean_name_en`、`clean_name_original`、`clean_name_source`、`safe_update_clean_name()` 返回值 | 短名保护漂移；original_title 被误当英文名；低优先级覆盖高优先级 |
| search filter / sort | `backend/test_search_keyword_mapper.py` + `backend/test_result_sorting.py` + `backend/test_smart_filter_multilang.py`，后续补 `/api/search/source` 的 mock 源测试 | `芙莉莲第二季` + en/original 辅助名；`流浪地球` + 英文标题；无做种数信息源；磁力源 `seeders=0,size=0` | `search_keywords`、`hit_keyword`、`match_score`、`quality_score`、`is_junk`、`junk_reasons`、排序后 title 顺序 | fallback 词顺序漂移；无做种数源被误判死种；磁力源被错误过滤；智能过滤漏传 match_names |
| 订阅直搜调用 | 后续单独隔离 `SubscriptionManager.trigger_search` / `/subscribe/{id}/search`，禁止连接真实 8000 服务 | 临时订阅数据文件 + mock 搜索服务，含 movie 与 tv season | `found_resources`、`last_search_at`、`search_logs`、`state`、返回 `status` | 当前测试会读写真实订阅状态；本机后端运行时会打真实 API；外部搜索超时导致基线不稳定 |
| 刮削 / TV 映射 | 后续补 `scraper` / `routes/organize.py` 的 TMDB mock 测试；现有本地 NFO 读写由 `test_code_split.py` 覆盖 | TV：绝对集数、S01E01、Season 00 特别篇；movie：中文名 + 英文名 + 年份 | `tmdb_id`、`media_type`、`season_number`、`episode_number`、`episode_title`、写出的 `episode.nfo` 字段 | TMDB 候选选择漂移；绝对集数映射漂移；特别篇误归普通季；NFO 字段缺失 |
| organize dry-run / execute | `python -X utf8 test_code_split.py` 继续作为本地 smoke；后续新增隔离 action_plan 测试 | 临时目录：散落 TV 文件、已有有效 NFO、孤立 poster / 空 NFO、扁平季目录 | dry-run: `status`、`count`、`ops[].action`、`ops[].old/new`；execute: 只消费 dry-run plan 中动作 | dry-run 产生计划但 execute 另算；有效 NFO 被误清理；没有 NFO 的视频被误移动 |
| file_relocator 冲突探测 | 已补 `test_file_relocator_conflicts.py` 临时目录单元测试，不走真实下载器；已用 fake recycle bin 覆盖旧视频配套文件回收路径记录 | 新文件白名单、旧资源目录、同名 / 不同清晰度资源、字幕 / poster 关联文件 | `coexist_pairs.old_file`、`category`、`is_folder`、白名单排除效果、回收路径集合 | 白名单漂移导致旧资源被当新资源；当前基线显示同季旧季目录和目录内旧视频会同时生成冲突对；`-clearlogo.png` 不在当前回收集合；真实 RecycleBin 落盘仍未覆盖 |
| 下载 → 归位闭环 | 后续 mock `DownloadManager` + `FileRelocator`，不调用 qB / Alist | completed 任务、save_path、local_file_path、relocate awaiting_confirm、confirm_replace / archive_both | 任务 `state`、`progress`、`relocate_plan`、`done/failed`、`media_library` 路径更新 | 下载完成不等于归位完成；confirm_replace 重算 plan；archive_both 与 replace 行为混淆 |

---

## 5. 每轮交付检查

每次收口任务完成前，必须填写：

```text
【本轮目标】
【涉及文件】
【改动性质】
【已完成】
【未触碰】
【验证结果】
- 静态检查
- 搜索检查
- 测试结果
【未能证明的风险】
【风险检查】
- 是否改业务逻辑：
- 是否改接口字段：
- 是否改路由行为：
- 是否影响主链路：
【结论】
```

### 本轮交付检查（2026-04-23：规则中心剩余重复点盘点）

```text
【本轮目标】
完成“规则中心剩余重复点盘点”，只记录候选，不迁移代码。

【涉及文件】
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
文档 / TODO 补强

【已完成】
- 勾选“规则中心剩余重复点盘点”
- 记录视频扩展名、字幕扩展名、标准 NFO 名、海报名、sidecar 后缀、回收 / 清理旧刮削集合、测试内重复媒体扩展名的剩余重复位置
- 标注每类重复点的风险等级、已有测试 / 基线、建议处理时机

【未触碰】
- 未修改后端业务代码
- 未修改前端代码、UI、样式、design token
- 未迁移任何常量引用
- 未触碰高风险链路行为

【验证结果】
- 静态检查：已用 rg 排查 `core.constants` 当前引用点、视频 / 字幕扩展名重复点、NFO / poster / sidecar 名称重复点
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：本轮仅文档补强，未运行 pytest / vitest

【未能证明的风险】
- 未证明各候选迁移后的行为等价；本轮按协议只记录，不执行迁移

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
本轮为纯文档收口，完成规则中心剩余重复点盘点，可作为后续单点低风险收口的准入清单。
```

### 本轮交付检查（2026-04-23：`shared.py` 职责盘点）

```text
【本轮目标】
完成 `shared.py` 职责盘点，只记录边界，不迁移代码。

【涉及文件】
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
文档 / TODO 补强

【已完成】
- 勾选 `shared.py` 职责盘点
- 记录启动级全局副作用、单例工厂、搜索源懒加载工厂、配置驱动客户端装配、路径 / 分类 helper、媒体库路径同步 helper、名称可信度 helper、刮削后回写 helper
- 记录 `shared.py` 新增禁止项，避免继续膨胀职责

【未触碰】
- 未修改 `backend/shared.py`
- 未修改任何调用方导入
- 未拆分单例 / 工厂 / helper
- 未触碰搜索、整理、刮削、下载归位、命名主链路行为

【验证结果】
- 静态检查：已读取 `backend/shared.py`，并用 rg 排查函数定义与主要调用方
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：本轮仅文档补强，未运行 pytest / vitest

【未能证明的风险】
- 未证明未来拆分 `shared.py` 后导入副作用、单例生命周期、媒体库索引刷新行为等价；本轮按协议只盘点，不执行拆分

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
本轮为纯文档收口，完成 `shared.py` 职责边界记录；后续如要拆分，必须先补启动 / 单例 / 主链路行为保护。
```

### 本轮交付检查（2026-04-23：路由层重逻辑盘点）

```text
【本轮目标】
完成路由层重逻辑盘点，只记录候选下沉点、风险等级和前置测试需求，不下沉代码。

【涉及文件】
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
文档 / TODO 补强

【已完成】
- 勾选“路由层重逻辑盘点”
- 记录超过 400 行的路由：organize、media_info、library、search、scrape、relocate、discover
- 记录超过 20 行的辅助函数 / 内嵌函数候选
- 标注每个候选的风险等级和前置测试需求
- 补充路由层新增禁止项

【未触碰】
- 未修改任何 `backend/routes/*.py`
- 未移动函数、未拆服务、未改接口字段
- 未触碰 organize executor、search filter/sort、刮削 / TV 映射、file_relocator、下载→归位闭环行为

【验证结果】
- 静态检查：已统计 `backend/routes/*.py` 行数，并阅读主要超过 400 行路由和函数定义
- 搜索检查：本轮不涉及搜索链路行为，只记录搜索路由风险
- 测试结果：本轮仅文档补强，未运行 pytest / vitest

【未能证明的风险】
- 未证明任何候选下沉后的行为等价；本轮按协议只盘点，不执行拆分

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
本轮为纯文档收口，完成路由层重逻辑候选清单；后续必须按单候选、单链路、先测试后下沉的方式推进。
```

### 本轮交付检查（2026-04-23：DTO 候选清单）

```text
【本轮目标】
完成 DTO 候选清单，只定义候选边界和已有模型关系，不新增 DTO。

【涉及文件】
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
文档 / TODO 补强

【已完成】
- 勾选“DTO 候选清单”
- 记录命名、搜索、刮削、整理、下载 / 归位、测试辅助域的 DTO 候选
- 标注已有模型关系、风险等级和当前建议
- 明确已有模型优先级，避免重复建模

【未触碰】
- 未新增 Python 类型 / DTO / BaseModel
- 未迁移任何 dict 字段
- 未修改接口响应字段
- 未触碰 search sort/filter、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环行为

【验证结果】
- 静态检查：已用 rg 排查既有 BaseModel / dataclass / TypedDict，以及 clean_name、SearchResult、ScrapeResult、RelocateResult 等字段使用
- 搜索检查：本轮不涉及搜索链路行为，只记录 DTO 候选风险
- 测试结果：本轮仅文档补强，未运行 pytest / vitest

【未能证明的风险】
- 未证明任何 DTO 迁移后的行为等价；本轮按协议只记录候选，不实施迁移

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
本轮为纯文档收口，完成 DTO 候选边界记录；后续第一批 DTO 只能从低风险内部 / 测试辅助边界开始。
```

### 本轮交付检查（2026-04-23：DTO 准入检查）

```text
【本轮目标】
完成 DTO 准入检查，明确当前哪些候选可进入第一批，哪些必须暂缓。

【涉及文件】
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
文档 / TODO 补强

【已完成】
- 勾选“DTO 准入检查”
- 按重复字段、行为稳定、接口字段不变、测试覆盖、可回滚五项检查候选 DTO
- 明确当前仅 `RouteResponseSnapshot` 这类测试辅助边界准入
- 记录 DTO 准入规则，限制高风险链路 DTO 迁移

【未触碰】
- 未新增 DTO / BaseModel / dataclass
- 未修改生产代码
- 未修改接口字段
- 未触碰 search sort/filter、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环行为

【验证结果】
- 静态检查：已复核 DTO 候选清单，并用 rg 排查关键 dict 字段、现有测试覆盖和高风险字段位置
- 搜索检查：本轮不涉及搜索链路行为，只记录 DTO 准入风险
- 测试结果：本轮仅文档补强，未运行 pytest / vitest

【未能证明的风险】
- 未证明任何生产 DTO 迁移后的行为等价；因此本轮不准入生产链路 DTO

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
本轮为纯文档收口，完成 DTO 准入门槛记录；当前第一批只允许从测试辅助 / 只读快照边界开始。
```

### 本轮交付检查（2026-04-23：第一批 DTO 低风险边界）

```text
【本轮目标】
从低风险测试辅助边界落地第一批 DTO：`RouteResponseSnapshot`。

【涉及文件】
backend/test_support/__init__.py
backend/test_support/route_response_snapshot.py
backend/test_route_response_snapshot.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
类型补强

【已完成】
- 勾选“第一批 DTO 只允许从低风险边界开始”
- 新增 `RouteResponseSnapshot` 测试辅助模型，只记录 status_code、body_type、field_paths、field_types、list_lengths
- 新增模型自身单元测试，覆盖嵌套 dict、空 list、顶层 list 三类响应形状
- 未把该模型接入生产路由，也未改变任何接口响应字段

【未触碰】
- 未修改后端业务代码
- 未修改前端代码、UI、样式、design token
- 未修改任何 route / service / manager
- 未触碰 search sort/filter、organize executor、file_relocator 冲突探测、TV 映射、下载→归位闭环

【验证结果】
- 静态检查：已确认新增模型位于 `backend/test_support/`，生产代码无引用
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_route_response_snapshot.py -q`：3 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_core_constants.py -q`：3 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 尚未把 `RouteResponseSnapshot` 应用于真实路由响应快照；本轮只证明测试辅助模型自身稳定。
- 未运行前端 vitest；本轮未改前端，且既有 vitest 失败已在本文档记录为测试债务。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否

【结论】
安全。第一批 DTO 仅落在测试辅助边界，可完全通过删除 `backend/test_support/` 与对应测试回滚，不影响生产行为。
```

### 本轮交付检查（2026-04-23：file_relocator 冲突探测测试补强）

```text
【本轮目标】
为 `file_relocator.py` 的冲突探测补最小行为保护测试，先记录当前行为基线，不修改生产逻辑。

【涉及文件】
backend/test_file_relocator_conflicts.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 新增 `test_file_relocator_conflicts.py`
- 覆盖白名单内新资源不会进入旧资源候选
- 覆盖同季旧资源会生成 `coexist_pairs`
- 记录当前行为：同季旧季目录和目录内旧视频会同时生成冲突对（folder + video 各一条）

【未触碰】
- 未修改 `backend/file_relocator.py`
- 未调用真实下载器 / qB / Alist
- 未调用回收站移动、confirm_replace、archive_both、cancel_replace
- 未执行真实归位、删除、移动、覆盖
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试只导入 `FileRelocator` 并调用 `_detect_conflicts_v2()`；测试数据使用临时目录，未访问真实 NAS
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - 首次使用 pytest `tmp_path` 失败：`backend/pytest-of-icat2` 权限拒绝，属于 Windows 临时目录残留问题
  - 改用 `tempfile.mkdtemp()` 后仍失败：新建目录 ACL 异常，子目录创建被拒绝
  - 已改为 `uuid + Path.mkdir` 创建并清理本轮专属临时目录
  - 清理 `tempfile.mkdtemp()` 生成的 `backend/relocator_conflict_file_xh_podvw`、`backend/relocator_conflict_folder_fhnflg97` 失败；普通权限与提权 `Remove-Item -Recurse -Force` 均返回 Access denied，后续纳入 Windows 权限残留统一处理
  - `cd backend && python -X utf8 -m pytest test_file_relocator_conflicts.py -q`：2 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_route_response_snapshot.py test_core_constants.py -q`：6 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 未覆盖 `_recycle_old_files()` 的旧视频 / 同名 NFO / 海报 / movie.nfo / season.nfo 回收动作。
- 未覆盖 confirm_replace / archive_both / cancel_replace。
- 未证明当前“季目录 + 内部视频重复冲突对”是否为期望行为；本轮只记录基线，不做业务修正。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试，未执行真实归位动作）

【结论】
安全。完成 file_relocator 冲突探测最小测试补强，并显性化当前重复冲突对行为；后续若要修正，必须单独开业务逻辑修复轮并补 confirm_replace 行为保护。
```

### 本轮交付检查（2026-04-23：file_relocator 回收动作测试补强）

```text
【本轮目标】
为 `file_relocator.py` 的旧资源回收动作补最小行为保护测试，使用 fake recycle bin 记录路径，不执行真实移动。

【涉及文件】
backend/test_file_relocator_conflicts.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 在 `test_file_relocator_conflicts.py` 中新增 `RecordingRecycleBin`
- 覆盖 `_recycle_old_files()` 当前会提交回收的路径集合：
  - 旧视频文件
  - 同名 `.nfo`
  - 同名 `-poster.jpg` / `-thumb.jpg` / `-fanart.jpg`
  - 目录级 `movie.nfo` / `season.nfo`
  - 父目录 `season01-poster.jpg` / `season01-fanart.jpg` / `season01-thumb.jpg` / `season01-banner.jpg`
- 覆盖 `tvshow.nfo` 不进入回收路径
- 记录当前行为：同名 `-clearlogo.png` 不进入 `_recycle_old_files()` 回收路径

【未触碰】
- 未修改 `backend/file_relocator.py`
- 未调用真实 `RecycleBin`
- 未执行真实归位、删除、移动、覆盖
- 未调用 confirm_replace / archive_both / cancel_replace
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试使用 fake recycle bin，只记录 `move_to_bin()` 入参
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - 初次运行失败原因 1：测试构造 `CoexistPair` 缺少必填 `new_file`，已补占位路径
  - 初次运行失败原因 2：测试用 `Path.with_suffix(".nfo")` 误把 `.1080p` 当扩展替换；已改为追加 `.nfo`，对齐当前实现
  - `cd backend && python -X utf8 -m pytest test_file_relocator_conflicts.py -q`：3 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_route_response_snapshot.py test_core_constants.py -q`：6 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- fake recycle bin 只证明 `_recycle_old_files()` 提交了哪些路径，不证明真实 RecycleBin 落盘行为。
- 未证明 confirm_replace 是否只消费已确认 plan，也未覆盖 archive_both / cancel_replace。
- `-clearlogo.png` 当前未回收是否符合产品预期未确认；本轮只记录基线，不改行为。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试，未执行真实归位动作）

【结论】
安全。完成 file_relocator 旧资源回收路径的最小行为基线；后续如要调整 clearlogo 或真实回收落盘，必须单独开业务逻辑修复轮。
```

### 本轮交付检查（2026-04-24：relocate 路由闭环测试补强）

```text
【本轮目标】
为 `routes/relocate.py` 增加隔离测试，记录下载→归位闭环在路由层的当前基线，不修改归位业务逻辑。

【涉及文件】
backend/test_relocate_routes.py
backend/routes/relocate.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 新增 `test_relocate_routes.py`
- 覆盖 `/organize/dry-run` 在 `awaiting_confirm` 场景下的响应结构快照，锁定 `coexist_pairs`、`plan`、`old_tree`、`new_tree`、`plan_tree`
- 覆盖 dry-run 会把 qB `get_torrent_files()` 返回的路径名单传给 `FileRelocator.relocate()`
- 覆盖 `/organize/execute` 会在执行前把 qB 文件列表注入 `plan["whitelist"]`
- 覆盖 `/organize/execute` 成功后调用 `archive_task(..., organized=True)`，失败时不归档
- 清理 `routes/relocate.py` 中的 Pydantic V2 兼容 warning：`p.dict()` 改为 `p.model_dump()`

【未触碰】
- 未修改 `backend/file_relocator.py`
- 未修改下载完成检测、真实 qB 同步、真实 RecycleBin 落盘
- 未覆盖 `/organize/archive-both`、`/organize/purge-old`
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：测试通过 monkeypatch 隔离 `DownloadManager`、qB 客户端和 `FileRelocator`，未访问真实 NAS / qB / 回收站
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py -q`：3 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：9 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 尚未证明下载完成检测到 `routes/relocate.py` 的端到端衔接。
- 尚未覆盖 `/organize/archive-both` 的共存归档路径。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试；`model_dump()` 为等价序列化替换）

【结论】
安全。下载→归位闭环的路由层基线已向前推进一小步，但仍属于“部分验证”；后续若要勾选整项，至少还需补 archive-both 和下载完成衔接测试。
```

### 本轮交付检查（2026-04-24：relocate 路由补齐 archive-both / purge-old 测试）

```text
【本轮目标】
继续为 `routes/relocate.py` 增加隔离测试，补齐 `/organize/archive-both` 与 `/organize/purge-old` 的当前路由行为基线。

【涉及文件】
backend/test_relocate_routes.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 在 `test_relocate_routes.py` 中新增 `/organize/archive-both` 行为测试
- 锁定 archive-both 会先用 qB 文件列表重新调用 `relocate()`，再把返回的 `coexist_pairs` 传给 `archive_both()`
- 锁定 archive-both 成功后调用 `archive_task(..., organized=True)`
- 新增 `/organize/purge-old` 两个分支测试
- 锁定 purge-old 在无法识别 qB 文件列表时直接返回 failed，且不触发 `relocate()`
- 锁定 purge-old 在存在冲突时会对每个 `coexist_pair` 调用 `_recycle_old_files()`

【未触碰】
- 未修改 `backend/routes/relocate.py`
- 未修改 `backend/file_relocator.py`
- 未覆盖下载完成检测到归位路由的自动衔接
- 未覆盖真实 qB、真实 RecycleBin、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试继续通过 monkeypatch 隔离 `DownloadManager`、qB 客户端和 `FileRelocator`
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py -q`：6 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：9 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明下载完成后 `DownloadManager` 自动触发归位的端到端衔接。
- purge-old 当前只验证“会调用 `_recycle_old_files()`”，未验证真实回收站落盘结果。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。`routes/relocate.py` 的主要路由胶水行为已基本锁住，但“下载→归位闭环基线”仍是部分验证；下一步应转向下载完成衔接测试，而不是继续在 relocate 路由内部打转。
```

### 本轮交付检查（2026-04-24：download_manager 自动归位衔接测试补强）

```text
【本轮目标】
为 `download_manager.py` 增加隔离测试，补上“订阅下载完成回调 -> 自动归位”这段闭环胶水的当前行为基线。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 新增 `test_download_manager_relocate_flow.py`
- 锁定 `_notify_subscription_complete()` 在 `best_version=true` 且存在 `save_path` 时会触发 `_auto_relocate()`
- 锁定 `_notify_subscription_complete()` 会把 `subscription_id`、`episode`、`info_hash`、`title`、`channel` 等字段传给 `SubscriptionManager.on_download_complete()`
- 锁定 `_auto_relocate()` 在 `relocate()` 返回 `awaiting_confirm` 时继续调用 `confirm_replace()`
- 锁定 `_auto_relocate()` 在 `relocate()` 返回 `archived` 时不会重复调用 `confirm_replace()`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未覆盖真实线程、真实 qB、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：测试通过 fake `shared` / `notification_service` 模块和立即执行线程隔离订阅管理器、归位器与通知侧副作用
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：3 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 当前测试把后台线程改成了同步立即执行，只证明调用顺序，不证明真实并发时序。
- 尚未证明真实 qB / Alist API 返回值在所有边界状态下都能稳定触发这条链。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。下载→归位闭环已从路由层补到 `DownloadManager` 的自动归位衔接层，但仍属于“部分验证”；下一步更值得补的将是 qB / Alist 边界状态与真实线程时序，而不是继续扩本地同步 mock。
```

### 本轮交付检查（2026-04-24：sync_progress 完成触发链测试补强）

```text
【本轮目标】
为 `download_manager.py` 增加隔离测试，锁定 `sync_progress()` 在任务完成瞬间触发归位与订阅回调的当前行为。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 在 `test_download_manager_relocate_flow.py` 中新增 qB 完成态触发测试
- 锁定 qB 任务在 `sync_progress()` 中从 `downloading` 变为 `completed` 时，会先调用 `_relocate_to_save_path()`，再调用 `_notify_subscription_complete()`，最后走 `_save_now()`
- 新增 alist 完成态触发测试
- 锁定非订阅任务在 `sync_progress()` 中完成时会调用 `_relocate_to_save_path()`，但不会调用 `_notify_subscription_complete()`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖真实线程、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：测试通过 monkeypatch 把 `_sync_qb_progress()` / `_sync_alist_progress()` 的结果聚焦到 `sync_progress()` 的分支逻辑，不依赖真实下载器
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：5 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发下 `_auto_relocate()` 的时序表现。
- 仍未证明真实下载器在更长尾的边界状态组合下的表现。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。`sync_progress()` 到归位 / 订阅回调的核心触发链已有隔离证据；“下载→归位闭环基线”仍未完全闭合，但剩余风险已经集中到更少的真实环境项。
```

### 本轮交付检查（2026-04-24：download_manager 下载器边界状态测试补强）

```text
【本轮目标】
为 `download_manager.py` 增加隔离测试，锁定 qB / Alist 若干关键边界状态的当前映射，不修改下载器状态机实现。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 为 `_sync_qb_progress()` 新增 completed / lost 两个边界状态测试
- 锁定 qB `pausedUP` 当前会被判定为 `completed`，并把 `progress` 归 1.0、清空 `speed` / `eta`
- 锁定 qB 查询返回空列表时当前会被判定为 `lost`
- 为 `_sync_alist_progress()` 新增 completed / lost 两个边界状态测试
- 锁定 Alist done 列表命中且本地文件存在时当前会被判定为 `completed`
- 锁定 Alist undone / done 两侧都找不到任务时当前会被判定为 `lost`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖更长尾的下载器状态组合
- 未覆盖真实线程、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试通过 fake qB session / fake requests.post 响应锁定当前状态映射，不依赖真实下载器
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：9 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发下 `_auto_relocate()` 的时序表现。
- 仍未覆盖 qB `missingFiles`、`stalledUP`、Alist 本地同步卡住等更多长尾状态。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。下载器边界状态已有最小隔离基线；“下载→归位闭环基线”还未完全闭合，但未证明风险已进一步收窄到长尾状态和真实并发环境。
```

### 本轮交付检查（2026-04-24：download_manager 长尾状态测试补强）

```text
【本轮目标】
继续为 `download_manager.py` 增加隔离测试，补齐 qB / Alist 若干长尾状态的当前映射，不修改下载器状态机实现。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 为 `_sync_qb_progress()` 新增 `stalledUP` 当前映射测试
- 锁定 qB `stalledUP` 当前同样会被判定为 `completed`
- 为 `_sync_qb_progress()` 新增登录失败测试
- 锁定 qB 登录失败当前会把任务状态置为 `unknown`
- 为 `_sync_alist_progress()` 新增 done 命中但本地文件缺失测试
- 锁定 Alist done 命中且本地文件尚未落地时当前会维持 `local_sync`，并把 `progress` 估算为 `0.8`
- 为 `_sync_alist_progress()` 新增 undone 请求失败测试
- 锁定 Alist undone 列表请求失败当前会把任务状态置为 `unknown`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖 qB `missingFiles`、HTTP 非 200、Alist 本地同步长时间卡住等更长尾状态
- 未覆盖真实线程、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试继续通过 fake qB session / fake requests.post 锁定当前状态映射，不依赖真实下载器
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：13 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发下 `_auto_relocate()` 的时序表现。
- 仍未覆盖 qB `missingFiles`、HTTP 非 200、Alist 本地同步长时间卡住等更长尾状态。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。下载器长尾状态的当前映射又补齐了一小段；“下载→归位闭环基线”仍是部分验证，但现在未证明风险已经主要收敛到少量更长尾的下载器状态与真实并发环境。
```

### 本轮交付检查（2026-04-24：download_manager 补齐 missingFiles / HTTP 非 200 / Alist 未完成态测试）

```text
【本轮目标】
继续为 `download_manager.py` 增加隔离测试，补齐 qB `missingFiles`、qB info 接口非 200，以及 Alist 未完成态的当前映射，不修改下载器状态机实现。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 为 `_sync_qb_progress()` 新增 `missingFiles` 当前映射测试
- 锁定 qB `missingFiles` 当前不会转成 `lost` 或 `failed`，而是维持 `downloading`，并保留进度 / 速度 / ETA 格式化结果
- 为 `_sync_qb_progress()` 新增 info 接口非 200 测试
- 锁定 qB info 接口非 200 当前会把任务状态置为 `unknown`
- 为 `_sync_alist_progress()` 新增未完成态 `state=1` 测试
- 锁定 Alist undone 命中且 `state!=2` 时当前维持 `cloud_download`
- 为 `_sync_alist_progress()` 新增未完成态 `state=2` 测试
- 锁定 Alist undone 命中且 `state=2` 时当前进入 `local_sync`，并把 `progress` 归 1.0

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖真实线程、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试继续通过 fake qB session / fake requests.post 锁定当前状态映射，不依赖真实下载器
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：17 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发下 `_auto_relocate()` 的时序表现。
- 仍未覆盖 qB 其它 HTTP 异常组合、Alist 本地同步长时间卡住、真实 RecycleBin 落盘等真实环境问题。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。下载器状态映射的已知空白又收窄了一步；“下载→归位闭环基线”仍是部分验证，但当前未证明风险已进一步集中到真实线程时序和更少量的真实环境长尾问题。
```

### 本轮交付检查（2026-04-24：download_manager 启动恢复 / 对账测试补强）

```text
【本轮目标】
继续为 `download_manager.py` 增加隔离测试，补齐服务启动恢复与下载器对账规则的当前基线，不修改状态机实现。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 为 `on_startup()` 新增启动恢复测试
- 锁定残留 `pending` 任务当前会在启动时被标记为 `failed`，错误文案为“服务重启时任务未完成推送”
- 锁定 `on_startup()` 会对残留 `downloading` 任务调用 `_reconcile_task()`，并最终触发一次 `_save_now()`
- 为 `_reconcile_task()` 新增 qB 丢 hash 测试
- 锁定启动对账时如果 qB 中缺少该 hash，当前会把任务标记为 `lost`
- 为 `_reconcile_task()` 新增“无 downloader hash”测试
- 锁定缺少 hash 的 downloading 任务当前会被标记为 `lost`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖真实线程、真实回收站、真实文件系统落盘
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试继续通过 monkeypatch 隔离 `_reconcile_task()` / `_get_qb_hashes()`，不依赖真实下载器
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：20 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发下 `_auto_relocate()` 的时序表现。
- 仍未覆盖真实下载器长时间同步卡住、真实 RecycleBin 落盘等真实环境问题。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。下载任务状态机在“启动恢复 / 对账”这一段也有了明确基线；“下载→归位闭环基线”仍未完全闭合，但未证明风险已进一步收敛到真实线程时序和少量真实环境长尾问题。
```

### 本轮交付检查（2026-04-24：download_manager 线程启动与补定位顺序测试补强）

```text
【本轮目标】
继续为 `download_manager.py` 增加隔离测试，补齐 `_auto_relocate()` 的线程启动参数和“先补定位再归位”的当前顺序证据，不修改自动归位实现。

【涉及文件】
backend/test_download_manager_relocate_flow.py
.kiro/docs/optimization-stabilization-todo.md

【改动性质】
测试补强

【已完成】
- 为 `_auto_relocate()` 新增线程创建测试
- 锁定当前会以 `daemon=True`、线程名 `relocate-{task.id}` 启动后台线程
- 为 `_auto_relocate()` 新增“local_file_path 缺失后重新定位”测试
- 锁定当 `local_file_path` 不存在时，当前会先调用 `media_matcher.match()` 尝试重新定位
- 锁定重新定位成功后会调用订阅管理器 `update(..., {"local_file_path": folder})`
- 锁定补定位后仍会继续调用 `relocate()`，且在无冲突归档场景下不会多调 `confirm_replace()`

【未触碰】
- 未修改 `backend/download_manager.py`
- 未修改 `backend/file_relocator.py`
- 未接入真实 qB / Alist 客户端
- 未覆盖真实回收站、真实文件系统落盘、真实线程并发竞争
- 未修改前端代码、UI、样式、design token

【验证结果】
- 静态检查：新增测试通过自定义 `RecordingThread` / `ImmediateThread` 和 fake shared 依赖锁定当前顺序，不依赖真实线程调度
- 搜索检查：本轮不涉及搜索链路行为
- 测试结果：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py -q`：22 passed，1 个既有 `.pytest_cache` 权限 warning
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：15 passed，1 个既有 `.pytest_cache` 权限 warning

【未能证明的风险】
- 仍未证明真实线程并发竞争下 `_auto_relocate()` 的时序表现。
- 仍未覆盖真实下载器长时间同步卡住、真实 RecycleBin 落盘等真实环境问题。
- `.pytest_cache` 权限 warning 仍是既有 Windows 环境噪声，本轮未处理其根因。

【风险检查】
- 是否改业务逻辑：否
- 是否改接口字段：否
- 是否改路由行为：否
- 是否影响主链路：否（仅新增隔离测试）

【结论】
安全。`_auto_relocate()` 的线程启动参数与补定位顺序已有隔离证据；“下载→归位闭环基线”仍未完全闭合，但剩余未证明风险已经进一步集中到真实线程竞争和少量真实环境长尾问题。
```

### 本轮交付检查（2026-04-24：relocate 路由白名单格式修复）

```text
【本轮目标】
在已有基线保护下，修复 `routes/relocate.py` 中 `/organize/archive-both` 与 `/organize/purge-old` 传给 `FileRelocator.relocate()` 的白名单格式，使其与 dry-run / execute 保持一致。

【涉及文件】
backend/routes/relocate.py
backend/test_relocate_routes.py

【改动性质】
业务逻辑修复（小范围）

【已完成】
- 修复 `/organize/archive-both`：qB `get_torrent_files()` 返回的文件对象列表改为先提取 `name` 字段，再传给 `relocate()`
- 修复 `/organize/purge-old`：同样改为传文件路径字符串白名单，而不是原始文件对象列表
- 更新 `test_relocate_routes.py` 对应断言，锁定两条路由当前都会传字符串路径白名单

【未触碰】
- 未修改 `backend/file_relocator.py`
- 未修改下载状态机、自动归位线程、真实 RecycleBin 落盘逻辑
- 未修改前端代码、UI、样式、design token

【验证结果】
- 路由回归：
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py -q`：6 passed，1 个既有 `.pytest_cache` 权限 warning
- 相关基线回归：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：31 passed，1 个既有 `.pytest_cache` 权限 warning

【行为判断】
- 是否行为等价：否，这是一次显式业务修复
- 修复内容：把原本错误的“文件对象列表白名单”改成 `FileRelocator` 预期的“路径字符串白名单”
- 风险范围：仅限 `/organize/archive-both` 和 `/organize/purge-old` 两条路由调用 `relocate()` 的参数格式，不影响 dry-run / execute 已有路径

【未能证明的风险】
- 尚未覆盖真实 qB 返回异常对象结构时的兼容性。
- 尚未覆盖真实 RecycleBin 落盘和真实线程竞争问题。

【结论】
安全可控。这是“下载→归位闭环”上第一处基于现有基线切入的小范围业务修复，回归结果稳定，后续可继续按同样节奏推进。
```

### 本轮交付检查（2026-04-24：relocate dry-run 的 action_plan fallback 修复）

```text
【本轮目标】
修复 `/organize/dry-run` 在 qB 文件列表缺失时的兜底分支，让它能正确从 `action_plan["plan"]` 回推 `new_files_all` / `new_tree`，而不是错误迭代整个 `action_plan` 字典。

【涉及文件】
backend/routes/relocate.py
backend/test_relocate_routes.py

【改动性质】
业务逻辑修复（小范围）

【已完成】
- 修复 `routes/relocate.py` 中 dry-run fallback 分支
- 当 qB 文件列表为空但 `res.action_plan` 存在时，当前会从 `action_plan["plan"]` 提取 `source_path`
- 新增 `test_organize_dry_run_falls_back_to_action_plan_when_qb_file_list_missing`
- 锁定 fallback 场景下：
  - `relocate()` 仍以 `whitelist=None` 执行
  - `new_files_all` 会从 `source_path` 回推出相对路径
  - `new_tree` 会按该相对路径构建目录树

【未触碰】
- 未修改 `backend/file_relocator.py`
- 未修改下载状态机、自动归位线程、真实 RecycleBin 落盘逻辑
- 未修改前端代码、UI、样式、design token

【验证结果】
- 路由回归：
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py -q`：7 passed，1 个既有 `.pytest_cache` 权限 warning
- 相关基线回归：
  - `cd backend && python -X utf8 -m pytest test_download_manager_relocate_flow.py test_file_relocator_conflicts.py test_route_response_snapshot.py test_core_constants.py -q`：31 passed，1 个既有 `.pytest_cache` 权限 warning

【行为判断】
- 是否行为等价：否，这是一次显式业务修复
- 修复内容：把原本会在 fallback 场景出错的 `action_plan` 迭代改成正确读取 `action_plan["plan"]`
- 风险范围：仅限 `/organize/dry-run` 在“qB 文件列表缺失 + action_plan 存在”的兜底路径

【未能证明的风险】
- 尚未覆盖 `action_plan["plan"]` 内部项缺少 `source_path` 字段时的异常兼容性。
- 尚未覆盖真实 RecycleBin 落盘和真实线程竞争问题。

【结论】
安全可控。这是第二处基于既有基线切入的小范围业务修复；当前 dry-run fallback 不再依赖 qB 文件列表才能构建最小预览。
```

### 本轮交付检查（2026-04-24：confirm_replace 的白名单兜底修复）

```text
【本轮目标】
修复 `FileRelocator.confirm_replace()` 在 plan 未携带 `whitelist` 时与 dry-run 阶段行为不一致的问题，使确认替换阶段也能沿用磁盘扫描白名单兜底。

【涉及文件】
backend/file_relocator.py
backend/test_file_relocator_conflicts.py

【改动性质】
业务逻辑修复（小范围）

【已完成】
- 修复 `confirm_replace()`：当 `plan["whitelist"]` 为空时，当前会回退到 `_scan_disk_for_whitelist(task.save_path)`
- 新增 `test_confirm_replace_falls_back_to_disk_scanned_whitelist_when_plan_missing_it`
- 锁定 fallback 场景下：
  - `confirm_replace()` 会先通过磁盘扫描识别新资源白名单
  - 旧资源仍会进入 `_recycle_old_files()`
  - 随后继续调用 `_execute_plan()`

【未触碰】
- 未修改 `backend/routes/relocate.py`
- 未修改下载状态机、自动归位线程、真实 RecycleBin 落盘逻辑
- 未修改前端代码、UI、样式、design token

【验证结果】
- 冲突探测回归：
  - `cd backend && python -X utf8 -m pytest test_file_relocator_conflicts.py -q`：4 passed，1 个既有 `.pytest_cache` 权限 warning
- 相关基线回归：
  - `cd backend && python -X utf8 -m pytest test_relocate_routes.py test_download_manager_relocate_flow.py test_route_response_snapshot.py test_core_constants.py -q`：35 passed，1 个既有 `.pytest_cache` 权限 warning

【行为判断】
- 是否行为等价：否，这是一次显式业务修复
- 修复内容：让 confirm 阶段和 dry-run 阶段使用一致的白名单兜底策略，避免 qB 文件列表缺失时两阶段判定来源不一致
- 风险范围：仅限 `confirm_replace()` 在 plan 缺少 whitelist 的 fallback 路径

【未能证明的风险】
- 尚未覆盖磁盘扫描误判新资源目录的真实环境案例。
- 尚未覆盖真实 RecycleBin 落盘和真实线程竞争问题。

【结论】
安全可控。这是第三处基于既有基线切入的小范围业务修复；当前 confirm 阶段不再强依赖 qB 白名单才能延续 dry-run 的判定结果。
```
