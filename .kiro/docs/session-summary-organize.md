# 本次对话总结：媒体库整理架构重构

## 做了什么

将原来混乱的 5 种文件夹分类（tv_season/tv_show/movie/movie_collection/series_collection）重构为清晰的 4+2 种（movie/tv/series_collection/movie_collection + variety/misc），并围绕这套分类体系完成了从后端分析层到前端展示的全链路改造。

## 核心架构决策

1. **分析与执行分离**：新建 `analyzer.py` 作为独立诊断层（纯读取），`organizer.py` 消费分析结果执行文件操作。分析层可复用于一键整理、健康报告、AI分析等不同场景。

2. **一键整理链路**：分析 → 文件移动 → 多季规整 → 刮削 → 改名。顺序经过反复讨论确认——先确定结构再动文件，刮削在改名之前（改名需要NFO数据）。

3. **前端展示在左侧主内容区**：tv/series_collection/movie_collection 的展开效果在 CardGrid（左侧），不在 DetailDrawer（右侧）。右侧详情面板只负责详情+操作按钮。

4. **封面绑定锁死**：左侧卡片和右侧详情面板共用同一封面来源，有就都有没有就都没有。

5. **旧刮削策略**：整理时旧NFO/封面打包为 .old_scrape.zip 保留在当前文件夹，全新刮削不兼容旧数据，避免旧数据干扰显示。

## 后端改动

- `analyzer.py`（新建）：7类诊断（结构/命名/刮削/影子名/质量/字幕/文件名），CD分片合并，广告清洗（_clean_filename_for_folder），审查规避检测，跨文件夹散落检测（文本+TMDB ID双轮）
- `organizer.py`：tv_season+tv_show合并为tv，organize_folder消费analyzer输出，新增merge_scattered_seasons，自动创建快照
- `scraper.py`：刮削优先用清洗名搜TMDB，递归时写season.nfo+季封面
- `organize_history.py`：快照增强（label/is_dir/空目录清理）
- `main.py`：新增 /analyze/folder、/analyze/library、/organize/merge-scattered API，scrape_candidates补english_title+清洗搜索词

## 前端改动

- `CardGrid.tsx`：items构建用folder_type识别类型，ExpandPanel按类型分发（tv=季tab+集列表，series_collection=缩略图列表，movie_collection=小卡片网格），movie类型不展开
- `DetailDrawer.tsx`：回归纯详情+操作，聚合文件夹隐藏"重新匹配"改为"一键刮削"，CandidatePicker显示english_title
- 新组件：TvDetail.tsx、SeriesCollectionList.tsx、MovieCollectionGrid.tsx（目前仅在CardGrid展开面板中使用）
- types/index.ts：FolderNode含folder_type，新增ScrapeCandidate类型

## 已知的数据问题（等整理时处理，不是代码问题）

- 黑礁S1嵌套太深（文件夹套文件夹套文件夹）
- 鲁鲁修/进击的巨人缺season.nfo或父级NFO错误
- Fate天之杯有错误的tvshow.nfo（旧刮削匹配到TV版而非剧场版）
- 大量文件名含广告（www.dy2018.com等）、低画质、缺字幕

## 下一步

1. **全库数据整理**（不需要spec）：分批执行分析→文件移动→多季规整→旧刮削打包→新刮削→改名→影子名
2. **搜索下载优化**（需要新spec）：搜索结果结构化展示、同源匹配、下载任务管理、新旧共存+回收站

## 关键文档位置

- 架构设计：`.kiro/docs/media-organize-architecture.md`（含4种交互原型图）
- 完整TODO：`.kiro/docs/organize-todo.md`（已完成项标记✅）
- Spec：`.kiro/specs/media-organize/`（design+requirements+tasks，16任务全部完成）
- 项目记忆：`.kiro/PROJECT_MEMORY.md`
