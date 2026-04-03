# 媒体库整理 & 搜索下载 — 完整 TODO

---

## 一、整理功能（后端）— ✅ 已完成

- [x] 1. 修复备份/快照机制（label/is_dir/空目录清理/organize_folder自动创建快照）
- [x] 2. 补 season.nfo 刮削（scrape_folder递归时写season.nfo+季封面）
- [x] 3. CD 分片合并执行验证（关联文件正确归入）
- [x] 4. 跨文件夹散落季合并执行（merge_scattered_seasons + API）
- [x] 5. 刮削候选列表补 english_title
- [x] 6. 统一清洗逻辑（generate_standard_name复用_clean_filename_for_folder）
- [x] 7. 刮削搜索词优化（scrape_candidates用清洗名搜索）

## 二、整理功能（前端）— ✅ 已完成

- [x] 8. CardGrid按folder_type展开（tv=季tab，series_collection=缩略图列表，movie_collection=小卡片网格）
- [x] 9. movie类型不展开，直接显示详情
- [x] 10. 聚合展开小卡片复用外层卡片样式（封面+渐变+标题+分辨率），比父级多2列
- [x] 11. DetailDrawer回归纯详情+操作（移除展开组件）
- [x] 12. 刮削候选/结果显示english_title
- [x] 13. types扩展（OrganizeSnapshot含label/is_dir，ScrapeCandidate含english_title）
- [x] 14. API层补充（analyzeFolder, analyzeLibrary, mergeScatteredSeasons）

## 三、全库数据整理 — ✅ 已完成

### 阶段 0：安全准备 ✅
- [x] 备份当前 media_library.json 和 config.json
- [x] 修复 _diagnose_structure：mixed 类型散落视频用 wrap_in_folder 而非 move_to_subdir

### 阶段 1：分析摸底 ✅
- [x] 跑 analyze_library，产出全库健康报告
- [x] 统计：6个一级目录，结构问题89，改名83，刮削缺失12，文件名问题14

### 阶段 2：分批结构整理 ✅
- [x] 电影目录：53个散落视频包裹进独立文件夹（252个文件移动）
- [x] 动画电影目录：36个散落视频包裹进独立文件夹（166个文件移动）
- [x] 动画番/电视剧：结构已完好，无需整理

### 阶段 3：分批刮削 ✅
- [x] 14个未刮削文件夹尝试自动刮削
- [x] 1个成功（National Geographic Porsche 911），Netflix XX监督子文件夹也成功
- [ ] 剩余 not_found 的需手动选择候选：national geographic 6个、动画电影 5个、电影 1个（白2023）、电视剧 1个

### 阶段 4：批量改名 + 影子名 ✅
- [x] 电影：125项改名，73个影子名
- [x] 动画电影：37项改名，73个影子名
- [x] 动画番：1830项改名，1748个影子名
- [x] 电视剧：776项改名，703个影子名
- [x] national geographic：3项改名，2个影子名

### 阶段 5：验证收尾 ✅
- [x] 再跑 analyze_library：结构问题 89→0，改名 83→0，文件名问题 14→0，影子名问题 4→0
- [ ] 剩余手动处理：13个刮削 not_found 的文件夹需手动匹配

## 四、搜索下载优化（spec: search-download）

### 搜索底层（后端核心）
- [ ] 23. 多关键词搜索回退策略（影子名→clean_name→英文原名→TMDB标题，搜到即停）
- [ ] 24. 搜索结果二次匹配（标题/年份精确比对，剔除误匹配）
- [ ] 25. 全局质量过滤规则（必须包含/严格排除关键词，默认排除TS/CAM/HDTC）
- [ ] 26. 发布组名称提取（Quality_Parser 增加 release_group 字段）

### 搜索展示（前端）
- [ ] 27. 搜索结果结构化展示（分行显示质量标签/标题/大小做种数，中字徽章，升级标识）
- [ ] 28. 搜索结果分组（按发布组/按索引器分组，默认平铺）

### 剧集搜索
- [ ] 29. 整季搜索策略（优先整季包+种子文件解析验证集数，不完整降级）
- [ ] 30. 同源匹配（多集搜索优先同一发布组，覆盖率计算）
- [ ] 31. 逐集搜索与结果汇总（S01E01逐集搜，表格展示，支持逐集切换备选）

### 批量搜索
- [ ] 32. 高匹配批量推荐算法（回退链搜索+二次匹配+过滤+评分）
- [ ] 33. 批量结果确认（一键全选推荐，支持逐个查看备选和修改）
- [ ] 34. 批量一键下载

### 下载管理
- [ ] 35. 下载任务队列（持久化JSON+中断恢复+Hash映射）
- [ ] 36. 下载进度监控（qB进度/Alist双段式：云端离线+本地同步）
- [ ] 37. 整季包解包与集数映射（parse_filename提取集数→标准重命名→字幕配对）
- [ ] 38. 下载完成归位（自动移到正确文件夹，tv归季目录，movie归电影文件夹）
- [ ] 39. 新旧文件共存与确认替换（保留旧文件，确认后旧文件+NFO+海报入回收站，触发刮削更新）
- [ ] 40. 回收站机制（可配置路径，记录原始路径，30天自动清理，支持恢复）
- [ ] 41. 下载方式智能推荐（qB vs Alist，做种数+大小自动推荐）

## 五、后续迭代（Phase 2）

### 搜索下载二期
- [x] 种子排序优先级可配置（用户自定义排序权重）— `config_manager.SortWeightsConfig` + `batch_recommend.BatchRecommendAlgo(custom_weights)` + 设置面板
- [ ] 下载转移多线程作业管理（TransferChain，对接V3整理流水线）— 暂缓，当前单线程归位已满足需求
- [x] 无效种子缓存/黑名单（TTL缓存，24h避免重复提交）— `torrent_blacklist.py` + 下载提交自动检查/加入
- [ ] 发现与订阅模块（TMDB/豆瓣/Bangumi聚合推荐+自动订阅下载）— 大功能，后续迭代

### 整理功能二期
- [x] 一键整理进度反馈（5步串行进度状态）— `/organize/full-stream` SSE + `OrganizeProgress.tsx`
- [x] 全库分析报告页（首页展示）— `/analysis/report` + `AnalysisReport.tsx` 健康分面板
- [x] 分析结果缓存（增量更新）— `analysis_cache.py` 文件缓存+年龄追踪
- [ ] AI分析接入（审查规避文件名猜测）— 需要更多 AI 模型集成
- [x] 整理历史记录（查看和回滚）— `/organize/history` + `OrganizeHistory.tsx` 面板
