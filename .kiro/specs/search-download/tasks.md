# 实现计划：搜索下载优化 (search-download)

## 概述

本计划将搜索下载优化功能拆分为增量实现步骤。从后端基础模块（质量解析增强、二次匹配、全局过滤）开始，逐步构建剧集搜索策略、批量推荐算法、下载管理器、文件归位器和回收站，最后在前端集成搜索展示改造、下载管理面板和回收站面板。每个任务复用现有模块（V3 流水线、parse_filename、text_utils 等），不重复实现已有逻辑。

## 任务

- [x] 1. QualityParser 增强 — 发布组提取
  - [x] 1.1 在 `backend/quality_parser.py` 的 `QualityTag` 中新增 `release_group` 字段，在 `parse_quality` 中添加发布组提取逻辑
    - 匹配标题末尾的 `-GroupName` 或 `@GroupName`
    - 排除常见非发布组后缀（MP4, MKV, AVI, SRT, ASS）
    - 更新 `display` 字段生成逻辑，不包含发布组（发布组单独展示）
    - _需求: 1.4_

  - [ ]* 1.2 为发布组提取编写属性测试 `backend/test_quality_parser_props.py`
    - **属性 1: 发布组提取正确性** — 含 `-GroupName` 后缀的标题应提取出组名，不含后缀的标题 release_group 为空
    - **验证: 需求 1.4**

- [x] 2. SecondaryMatcher — 二次匹配器
  - [x] 2.1 创建 `backend/secondary_matcher.py`，实现 `SecondaryMatcher` 类
    - 复用 `tmdb_client.parse_filename` 从 BT 标题解析中英文名和年份，不手写正则
    - 实现 `match(result, target_titles, target_year, media_type)` 方法
    - 标题比对：解析出的中英文名与 target_titles（含别名）模糊匹配（阈值 0.8）
    - 年份比对：电影 ±1 年容差，剧集与任一季年份匹配即通过
    - 返回 `MatchVerdict(passed, reason)`
    - _需求: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 2.2 为 SecondaryMatcher 编写属性测试 `backend/test_secondary_matcher_props.py`
    - **属性 4: 二次匹配过滤正确性** — 匹配后结果集仅包含标题匹配通过的结果
    - **属性 5: 年份容差规则** — 电影 |Y-R|<=1 通过，|Y-R|>1 失败；剧集与任一季年份匹配即通过
    - **验证: 需求 4.1, 4.2, 4.3, 4.4**

- [x] 3. GlobalFilter — 全局过滤器
  - [x] 3.1 创建 `backend/global_filter.py`，实现 `GlobalFilter` 类
    - 从配置读取 `must_include` 和 `must_exclude` 关键词列表
    - 默认排除列表：TS, CAM, HDTC, TC, TELECINE, HDTS
    - `apply(results)` 方法：命中排除词丢弃，配置了包含词时未命中丢弃
    - 大小写不敏感匹配
    - _需求: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 3.2 为 GlobalFilter 编写属性测试 `backend/test_global_filter_props.py`
    - **属性 6: 全局过滤规则正确性** — 过滤后无结果含排除词，包含词非空时所有结果至少含一个包含词
    - **验证: 需求 5.2, 5.3**

- [ ] 4. 检查点 — 确保基础模块测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 5. SearchEngine 增强 — 搜索回退链集成
  - [x] 5.1 改造 `backend/searcher.py` 的 `enhanced_search` 函数
    - 新增参数：`shadow_name`, `clean_name`, `global_filter`, `season_info`
    - 实现搜索回退链：shadow_name → clean_name → en_name → title
    - 每个关键词搜索后执行 SecondaryMatcher 二次匹配 + GlobalFilter 全局过滤
    - 有效结果 >= 1 则停止回退
    - 返回 `EnhancedSearchResponse`（含 `hit_keyword`, `total_raw`, `total_filtered`）
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 5.2 为搜索回退链编写属性测试 `backend/test_search_engine_props.py`
    - **属性 3: 搜索回退链优先级与停止** — 按优先级依次尝试，首个有效结果处停止，hit_keyword 正确
    - **验证: 需求 3.1, 3.2, 3.3, 3.5**

- [x] 6. 全局过滤规则配置 API
  - [x] 6.1 在 `backend/config_manager.py` 中扩展配置结构，新增 `search_filter` 字段
    - 包含 `must_include` 和 `must_exclude` 两个关键词列表
    - 新增 `preferred_codec`（默认 "x265"）和 `download_channel_auto`（默认 true）
    - 新增 `recycle_bin_path` 和 `recycle_bin_retention_days`（默认 30）
    - _需求: 5.1, 17.1, 18.1_

  - [x] 6.2 在 `backend/main.py` 中新增 `/config/search-filter` GET/POST API
    - GET 返回当前过滤规则配置
    - POST 保存过滤规则配置
    - _需求: 5.1_

- [x] 7. 搜索 API 改造
  - [x] 7.1 改造 `backend/main.py` 中的 `/search` API
    - 新增参数：`shadow_name`, `clean_name`, `season`, `total_episodes`
    - 调用增强后的 `enhanced_search`（含回退链 + 二次匹配 + 全局过滤）
    - 返回结构中包含 `hit_keyword`, `total_raw`, `total_filtered`
    - _需求: 3.1, 3.5, 4.1, 5.5_

- [ ] 8. 检查点 — 确保搜索增强模块测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 9. EpisodeSearchStrategy — 剧集搜索策略
  - [x] 9.1 创建 `backend/episode_search.py`，实现 `EpisodeSearchStrategy` 类
    - 实现 `search_season(client, title, season_number, total_episodes, aliases, year, global_filter)` 方法
    - 整季包搜索：使用 "标题 SXX" 格式搜索
    - 整季包验证：通过 HTTP GET 拉取 .torrent 文件，使用 bencodepy 解析 Bencode 结构，从 info.files 提取视频文件并用 parse_filename 解析集数，不依赖 Prowlarr JSON
    - 磁力链接标记为 `is_magnet=True`，无法预先验证
    - 无完整整季包时自动切换逐集搜索（S01E01 格式）
    - 缺失集标记为 "not_found"
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 9.2 在 `EpisodeSearchStrategy` 中实现同源匹配 `_same_source_match` 方法
    - 计算每个发布组覆盖的集数比例
    - 完整覆盖的发布组优先推荐
    - 无完整覆盖时选覆盖率最高的，缺失集从其他发布组补充
    - _需求: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 9.3 为剧集搜索策略编写属性测试 `backend/test_episode_search_props.py`
    - **属性 7: 整季包识别与回退** — 有完整整季包时标记为整季包，无完整包时切换逐集搜索
    - **属性 8: 整季包完整性验证** — 视频文件数 < 总集数时降级为不完整包
    - **属性 9: 同源匹配覆盖率计算与推荐** — 覆盖率计算正确，推荐覆盖率最高的发布组
    - **属性 10: 逐集搜索格式与汇总** — 生成 N 个 S{SS}E{EE} 格式查询，汇总 N 个条目
    - **验证: 需求 6.1, 6.2, 6.3, 6.6, 6.7, 7.1, 7.2, 7.3, 8.1, 8.2**

- [x] 10. BatchRecommendAlgo — 批量推荐算法
  - [x] 10.1 创建 `backend/batch_recommend.py`，实现 `BatchRecommendAlgo` 类
    - 多维度加权评分：标题匹配度(0.30) + 分辨率提升(0.25) + 编码匹配(0.15) + 做种健康度(0.15) + 中字加分(0.10) + 大小合理性(0.05)
    - 置信度标记：score >= 0.7 → high, >= 0.5 → medium, < 0.5 → low
    - 分辨率未提升标记为 `is_upgrade=False`
    - _需求: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 10.2 为批量推荐算法编写属性测试 `backend/test_batch_recommend_props.py`
    - **属性 11: 批量推荐评分范围与置信度标记** — 评分在 [0.0, 1.0]，< 0.5 标记低置信度，无提升标记 is_upgrade=False
    - **验证: 需求 9.2, 9.3, 9.4**

- [ ] 11. 检查点 — 确保搜索策略和推荐算法测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 12. DownloadManager — 下载管理器
  - [x] 12.1 创建 `backend/download_manager.py`，实现 `DownloadTask` 数据模型和 `DownloadManager` 类
    - DownloadTask 字段：id, media_name, download_url, save_path, download_dir（隔离沙盒）, channel, downloader_hash, category_hint, status, progress, speed, eta, phase, error, is_season_pack, season_number, created_at, updated_at
    - 状态枚举：pending | downloading | cloud_done | completed | relocating | awaiting_confirm | archived | failed | lost | unknown
    - 持久化到 `download_tasks.json`（JSON 文件读写）
    - _需求: 12.1_

  - [x] 12.2 实现 `DownloadManager` 的任务提交和沙盒隔离
    - `_create_sandbox(task_id)` — 为每个任务创建隔离目录 `downloads/{task_id}/`
    - `submit(task)` — 生成 UUID，创建沙盒，推送下载器（qB/Alist），save_path 指向沙盒
    - 推送成功：pending → downloading，记录 downloader_hash
    - 推送失败：pending → failed，记录错误原因
    - _需求: 12.2, 12.3, 12.5_

  - [x] 12.3 实现 `DownloadManager` 的进度同步
    - `sync_progress()` — 轮询所有 downloading 任务
    - `_sync_qb_progress(task)` — 通过 qBittorrent API 获取进度百分比、速度、ETA
    - `_sync_alist_progress(task)` — 通过 Alist API 区分云端下载/本地同步两阶段
    - qB 下载完成 → completed；Alist 云端完成 → cloud_done，本地同步完成 → completed
    - API 不可达时标记 unknown，恢复后自动重新同步
    - _需求: 13.1, 13.2, 13.3, 13.4, 13.6_

  - [x] 12.4 实现 `DownloadManager` 的启动恢复和查询
    - `on_startup()` — 加载持久化队列，对 downloading 任务通过 downloader_hash 查询实际状态
    - 下载器中已不存在的任务标记为 lost
    - `get_tasks(status)` — 按创建时间倒序返回，支持状态过滤
    - _需求: 12.4, 12.6, 12.7_

  - [x] 12.5 实现下载通道推荐 `recommend_channel(result)` 方法
    - seeders >= 5 且 size_gb <= 50 → 推荐 qb
    - seeders < 5 或 size_gb > 50 → 推荐 alist
    - 仅配置一种通道时直接使用
    - _需求: 18.1, 18.2, 18.3, 18.5_

  - [ ]* 12.6 为 DownloadManager 编写属性测试 `backend/test_download_manager_props.py`
    - **属性 13: 下载任务持久化 round-trip** — 序列化后反序列化，所有字段一致
    - **属性 14: 下载任务状态机** — 初始 pending，推送成功 → downloading，失败 → failed
    - **属性 15: 任务队列排序** — 查询返回按创建时间倒序
    - **属性 17: Alist 双阶段进度状态** — 云端完成 → cloud_done，本地同步完成 → completed
    - **属性 24: 下载通道推荐规则** — seeders>=5 且 size<=50GB → qb，否则 alist
    - **验证: 需求 12.1, 12.2, 12.3, 12.4, 13.2, 13.3, 13.4, 18.2, 18.3, 18.5**

- [x] 13. 下载管理 API
  - [x] 13.1 在 `backend/main.py` 中新增下载管理 API
    - `POST /download-manager/submit` — 提交下载任务
    - `GET /download-manager/tasks` — 查询任务列表（支持 status 过滤）
    - `GET /download-manager/progress` — 获取所有活跃任务进度
    - 服务启动时调用 `download_manager.on_startup()` 恢复队列
    - _需求: 12.2, 12.4, 13.5_

  - [x] 13.2 改造 `backend/main.py` 中的 `/batch-download` API
    - 将批量下载任务提交到 DownloadManager 队列，而非直接调用下载器
    - 返回提交结果摘要（成功数 + 失败数）
    - _需求: 11.1, 11.2, 11.4_

- [ ] 14. 检查点 — 确保下载管理器测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 15. RecycleBin — 回收站
  - [x] 15.1 创建 `backend/recycle_bin.py`，实现 `RecycleBin` 类
    - 使用可配置的回收站目录路径
    - `move_to_bin(file_path, task_id)` — 移入回收站，记录原始路径、移入时间、关联任务 ID、过期时间
    - `restore(entry_id)` — 恢复到原始路径
    - `cleanup_expired()` — 清理超过保留天数的文件
    - `list_entries()` — 列出所有回收站条目
    - 元数据持久化到 `recycle_bin.json`
    - _需求: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [ ]* 15.2 为 RecycleBin 编写属性测试 `backend/test_recycle_bin_props.py`
    - **属性 22: 回收站 round-trip** — 移入后恢复，文件回到原始路径，条目记录正确
    - **属性 23: 回收站过期清理** — 仅删除超过保留天数的条目，未过期的保留
    - **验证: 需求 17.2, 17.4, 17.5**

- [x] 16. FileRelocator — 文件归位器
  - [x] 16.1 创建 `backend/file_relocator.py`，实现 `FileRelocator` 类
    - 复用 V3 整理流水线 `run_pipeline`，不自己实现解析/重命名逻辑
    - `relocate(task)` — 两段式归位：
      - 第一步：`run_pipeline(path=download_dir, dry_run=True, use_ai=True, category_hint=...)` 获取 Action Plan
      - 解析 Action Plan，检测目标路径是否存在旧文件（冲突检测）
      - 有冲突 → 返回 awaiting_confirm + 冲突对列表
      - 无冲突 → 直接执行第二步
      - 第二步：`run_pipeline(path=download_dir, dry_run=False, action_plan=plan)` 执行落盘
    - _需求: 14.1, 14.2, 14.3, 15.1, 15.2, 15.3, 15.4, 15.5_

  - [x] 16.2 实现 `FileRelocator` 的确认替换和取消替换
    - `confirm_replace(task_id, plan)` — 旧文件 + 同名 NFO + 海报移入回收站，保留 tvshow.nfo 不动，然后执行 V3 落盘
    - `cancel_replace(task_id)` — 新文件（沙盒中的）移入回收站
    - NFO 回收规则：移走 movie.nfo、season.nfo、同名 episode.nfo，绝对不动 tvshow.nfo
    - _需求: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 16.3 为 FileRelocator 编写属性测试 `backend/test_file_relocator_props.py`
    - **属性 18: V3 Action Plan 冲突检测** — 目标路径存在旧文件时返回 awaiting_confirm，无冲突时直接执行
    - **属性 21: 新旧文件共存与替换** — 确认替换时旧文件入回收站但 tvshow.nfo 保留，取消时新文件入回收站
    - **验证: 需求 14.1, 16.1, 16.3, 16.4**

- [x] 17. 归位与回收站 API
  - [x] 17.1 在 `backend/main.py` 中新增归位和回收站 API
    - `POST /download-manager/confirm-replace` — 确认替换
    - `POST /download-manager/cancel-replace` — 取消替换
    - `GET /recycle-bin` — 列出回收站文件
    - `POST /recycle-bin/restore` — 从回收站恢复
    - `POST /recycle-bin/cleanup` — 手动触发过期清理
    - _需求: 16.3, 16.4, 17.3, 17.4, 17.5_

- [ ] 18. 检查点 — 确保归位和回收站测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 19. 前端类型定义扩展
  - [x] 19.1 在 `frontend/types/index.ts` 中扩展和新增类型定义
    - `QualityTag` 新增 `release_group` 字段
    - `EnhancedSearchResult` 新增 `match_verdict`, `publish_date` 字段
    - 新增 `SearchResponse` 类型（含 hit_keyword, total_raw, total_filtered）
    - 新增 `SeasonSearchResponse`, `SeasonPackInfo`, `EpisodeResult`, `SameSourcePlan` 类型
    - 新增 `DownloadTask` 类型（含 id, status, progress, speed, eta, phase, channel, coexist_pairs）
    - 新增 `RecycleBinEntry` 类型
    - _需求: 1.4, 3.5, 6.2, 8.2, 12.1, 17.3_

- [x] 20. 前端 API 封装扩展
  - [x] 20.1 在 `frontend/lib/api.ts` 中新增 API 调用方法
    - `searchEnhanced(query, options)` — 增强搜索（含 shadow_name, clean_name, season, total_episodes）
    - `getSearchFilter()` / `saveSearchFilter(config)` — 全局过滤规则
    - `submitDownload(task)` — 提交下载任务到 DownloadManager
    - `getDownloadTasks(status?)` — 查询下载任务列表
    - `getDownloadProgress()` — 获取活跃任务进度
    - `confirmReplace(taskId)` / `cancelReplace(taskId)` — 确认/取消替换
    - `getRecycleBin()` / `restoreFromBin(entryId)` / `cleanupRecycleBin()` — 回收站操作
    - _需求: 3.5, 5.1, 12.4, 13.5, 16.3, 17.3_

- [x] 21. SearchModal 改造 — 结构化展示与分组
  - [x] 21.1 改造 `frontend/components/search/SearchModal.tsx` 的结果展示布局
    - 每条结果三行结构化布局：第一行质量标签+索引器+中字徽章+↑更高标识，第二行完整原始标题，第三行文件大小+做种数+发布时间
    - 显示命中关键词标注（hit_keyword）
    - 下载按钮标注推荐通道
    - _需求: 1.1, 1.2, 1.3, 3.5, 18.4_

  - [x] 21.2 在 SearchModal 中实现分组模式切换
    - 三种模式：平铺（默认）、按发布组分组、按索引器分组
    - 分组折叠展示，组标题显示分组键和结果数量
    - 无法识别发布组的结果归入"其他"组
    - _需求: 2.1, 2.2, 2.3, 2.4_

  - [x] 21.3 在 SearchModal 中实现逐集搜索汇总表格（tv 模式）
    - 表格形式展示：集号 | 推荐资源质量标签 | 大小 | 做种数
    - 支持逐集切换备选资源
    - 修改选择后重新计算总大小
    - 整季包和逐集方案同时展示，标注各方案总大小
    - _需求: 6.4, 8.3, 8.4_

  - [ ]* 21.4 为 SearchModal 分组逻辑编写属性测试 `frontend/__tests__/SearchModal.prop.test.ts`
    - **属性 2: 搜索结果分组正确性** — 同组内分组键相同，所有结果恰好出现一次，空键归入"其他"
    - **验证: 需求 2.2, 2.3, 2.4**

- [x] 22. BatchUpgradePanel 改造 — 智能推荐与确认
  - [x] 22.1 改造 `frontend/components/search/BatchUpgradePanel.tsx` 的确认阶段
    - 每项显示匹配分数和置信度标记
    - 低置信度（< 0.5）以警告色显示
    - 无提升项默认不勾选
    - "全选推荐"仅勾选 score >= 0.5 且有提升的项目
    - 支持"查看备选"展开完整结果列表，切换选中资源
    - 批量下载总大小汇总
    - _需求: 9.3, 9.4, 10.1, 10.2, 10.3, 10.4_

  - [x] 22.2 改造 BatchUpgradePanel 的下载阶段
    - 下载任务提交到 DownloadManager 队列（而非直接调用下载器）
    - 显示提交结果摘要（成功数 + 失败数）
    - _需求: 11.1, 11.2, 11.3_

  - [ ]* 22.3 为 BatchUpgradePanel 全选逻辑编写属性测试 `frontend/__tests__/BatchUpgradePanel.prop.test.ts`
    - **属性 12: 全选推荐逻辑** — 仅勾选 score >= 0.5 且有提升的项目
    - **验证: 需求 10.2**

- [ ] 23. 检查点 — 确保前端搜索组件改造完成
  - 确保所有测试通过，ask the user if questions arise.

- [x] 24. DownloadManagerPanel — 下载管理面板
  - [x] 24.1 创建 `frontend/components/download/DownloadManagerPanel.tsx`
    - 任务列表按创建时间倒序展示
    - 状态筛选：全部 | 下载中 | 已完成 | 待确认 | 失败
    - 每项显示：媒体名 + 状态标签 + 进度条 + 速度 + ETA
    - Alist 通道双阶段显示（"云端下载中" / "同步中"）
    - _需求: 12.4, 13.1, 13.2, 13.5_

  - [x] 24.2 在 DownloadManagerPanel 中实现待确认替换区域
    - 新旧文件对比展示（名称 + 大小）
    - "确认替换"和"取消替换"按钮
    - 确认/取消后刷新任务状态
    - _需求: 16.2, 16.3, 16.4_

- [x] 25. RecycleBinPanel — 回收站面板
  - [x] 25.1 创建 `frontend/components/download/RecycleBinPanel.tsx`
    - 列出回收站所有文件：原始路径、文件大小、移入时间
    - 支持单个文件恢复到原始路径
    - 支持手动触发过期清理
    - 从 DownloadManagerPanel 入口进入
    - _需求: 17.3, 17.4, 17.5_

- [x] 26. 设置页面扩展
  - [x] 26.1 在前端设置页面中新增搜索过滤规则配置区域
    - "必须包含"和"严格排除"关键词列表编辑
    - 回收站路径和保留天数配置
    - 编码偏好选择（x265/x264/AV1）
    - 下载通道自动推荐开关
    - _需求: 5.1, 17.1, 18.1_

- [ ] 27. 最终检查点 — 全部功能集成验证
  - 确保所有测试通过，ask the user if questions arise.

## 备注

- 标记 `*` 的子任务为可选测试任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号，确保需求全覆盖
- 属性测试验证设计文档中定义的正确性属性，确保核心逻辑的形式化正确性
- FileRelocator 复用 V3 整理流水线（run_pipeline），不重复实现文件名解析和重命名逻辑
- SecondaryMatcher 复用 tmdb_client.parse_filename，不手写 BT 标题解析正则
- DownloadManager 为每个任务创建隔离沙盒 downloads/{task_id}/，避免并行任务互相干扰
- 整季包验证使用 Bencode 解析 .torrent 文件，不依赖 Prowlarr JSON
- 回收站 NFO 收尾规则：移走 movie.nfo/season.nfo/同名.nfo，绝对不动 tvshow.nfo
