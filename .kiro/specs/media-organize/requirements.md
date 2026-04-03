# 需求文档：媒体库整理功能补全 (media-organize)

## 简介

本需求文档定义了 NAS 媒体库整理功能的 P0 需求，涵盖后端任务 1-7（备份/快照修复、season.nfo 刮削、CD 分片合并、散落季合并、刮削候选补 english_title、统一清洗逻辑、刮削搜索词优化）和前端任务 11-16（series_collection 缩略图列表、movie_collection 小卡片网格、tv 季 tab 适配、DetailDrawer folder_type 分发、刮削候选/结果英文名显示）。目标是让一键整理链路的每个环节都能正确执行，前端能根据文件夹类型自动切换到最合适的展示模式。

## 术语表

- **系统 (System)**：NAS 影视媒体库管理工具的后端服务
- **快照管理器 (Snapshot_Manager)**：organize_history.py 中负责操作快照创建、回滚和列表查询的组件
- **分析引擎 (Analyzer)**：analyzer.py 中负责纯读取诊断的组件，产出结构调整计划、命名修正计划、刮削问题等
- **整理执行器 (Organizer)**：organizer.py 中负责文件移动、季目录规整、批量改名等执行操作的组件
- **刮削器 (Scraper)**：scraper.py 中负责 NFO 读写、海报下载、递归刮削的组件
- **TMDB 客户端 (TMDB_Client)**：tmdb_client.py 中负责 TMDB API 搜索、详情获取、英文名获取的组件
- **清洗函数 (Clean_Function)**：analyzer.py 中的 _clean_filename_for_folder 函数，负责去除广告、质量标签、发布组等噪音
- **DetailDrawer**：前端详情面板组件，负责根据 folder_type 分发到对应展示组件
- **SeriesCollectionList**：前端 series_collection 类型的缩略图列表组件
- **MovieCollectionGrid**：前端 movie_collection/variety/misc 类型的小卡片网格组件
- **TvDetail**：前端 tv 类型的季 tab + 集列表展示组件
- **CandidatePicker**：前端刮削候选选择组件
- **ScrapeInfo**：前端刮削信息展示组件
- **season.nfo**：季级别的元数据 XML 文件，包含季号、标题、简介、首播日期等
- **tvshow.nfo**：剧级别的元数据 XML 文件，包含剧名、简介、评分、总季数等
- **folder_type**：文件夹分类标识，取值为 movie / tv / series_collection / movie_collection / variety / misc
- **CD 分片**：同一影片分成多个光盘文件的情况（如 CD1、CD2）
- **散落季**：同一剧集的不同季目录散落在同级目录下，未归入统一父目录的情况
- **english_title**：TMDB 返回的英文标题，用于搜索和显示

## 需求

### 需求 1：快照创建与自动记录

**用户故事：** 作为媒体库用户，我希望每次整理操作都自动创建快照，以便在操作出错时能够回滚到之前的状态。

#### 验收标准

1. WHEN Organizer 执行 organize_folder 且 dry_run 为 False THEN Snapshot_Manager SHALL 自动创建包含所有文件移动操作的快照记录
2. WHEN Snapshot_Manager 创建快照 THEN Snapshot_Manager SHALL 为每条操作记录标注 is_dir 字段以区分文件操作和目录操作
3. WHEN Snapshot_Manager 创建快照 THEN Snapshot_Manager SHALL 记录 label 字段标识操作类型（"organize"、"rename"、"scrape"、"merge_seasons"）
4. WHEN 用户查询快照列表 THEN Snapshot_Manager SHALL 返回按时间倒序排列的快照列表，支持 limit 参数限制返回数量

### 需求 2：快照回滚

**用户故事：** 作为媒体库用户，我希望能够回滚指定快照，以便将文件恢复到操作前的位置。

#### 验收标准

1. WHEN 用户触发回滚指定快照 THEN Snapshot_Manager SHALL 按操作的逆序依次将文件和目录从新路径移回原路径
2. WHEN Snapshot_Manager 回滚完成后发现空目录 THEN Snapshot_Manager SHALL 自动清理由整理操作创建的空目录
3. IF 回滚过程中某个文件已被手动移动导致新路径不存在 THEN Snapshot_Manager SHALL 将该操作标记为 failed 并继续回滚其余操作
4. WHEN 回滚完成 THEN Snapshot_Manager SHALL 返回成功操作数和失败操作列表

### 需求 3：season.nfo 刮削

**用户故事：** 作为媒体库用户，我希望刮削 tv 类型文件夹时自动为每个季目录写入 season.nfo 和季封面，以便媒体服务器能正确识别季级元数据。

#### 验收标准

1. WHEN Scraper 递归刮削 tv 类型文件夹 THEN Scraper SHALL 识别每个季子目录并从 tvshow.nfo 读取 tmdb_id
2. WHEN Scraper 识别到季子目录且该目录没有 season.nfo THEN Scraper SHALL 调用 TMDB_Client 获取季详情并写入 season.nfo
3. WHEN Scraper 写入 season.nfo THEN Scraper SHALL 包含 seasonnumber、title、plot、aired 字段
4. WHEN Scraper 写入 season.nfo 且 TMDB 返回季封面 URL THEN Scraper SHALL 下载季封面到该季目录的 poster.jpg
5. WHILE 季目录已存在 season.nfo 且 force 参数为 False THEN Scraper SHALL 跳过该季目录的 season.nfo 写入
6. WHEN season.nfo 写入完成 THEN Scraper SHALL 确保 seasonnumber 字段值与目录名中提取的季号一致
7. IF 季详情获取失败（TMDB API 错误或无数据）THEN Scraper SHALL 记录错误日志并继续处理下一个季目录

### 需求 4：CD 分片合并

**用户故事：** 作为媒体库用户，我希望整理时能正确处理 CD 分片文件，将同组 CD 文件及其关联文件归入同一目标文件夹。

#### 验收标准

1. WHEN Organizer 执行 wrap_in_folder 遇到 CD 分片文件 THEN Organizer SHALL 将同组 CD 文件（如 CD1、CD2）移入同一目标文件夹
2. WHEN Organizer 移动 CD 分片文件 THEN Organizer SHALL 同时移动每个 CD 文件的关联文件（同名 .nfo、-poster.jpg、.srt 等）
3. WHEN Organizer 匹配 CD 分片的关联文件 THEN Organizer SHALL 仅匹配以 CD 文件基础名开头的文件，不匹配属于整体的同名文件
4. WHEN CD 分片合并完成 THEN Organizer SHALL 使用 Clean_Function 生成目标文件夹名

### 需求 5：散落季合并

**用户故事：** 作为媒体库用户，我希望系统能将同一剧集散落在同级目录下的多个季目录合并到统一的父目录中，以便目录结构规范化。

#### 验收标准

1. WHEN Analyzer 检测到散落季问题 THEN Organizer SHALL 提供 merge_scattered_seasons 函数接收诊断结果并执行合并
2. WHEN merge_scattered_seasons 以 dry_run=True 调用 THEN Organizer SHALL 返回预览操作列表而不修改文件系统
3. WHEN merge_scattered_seasons 以 dry_run=False 调用 THEN Organizer SHALL 以 core_name 创建父目录（如不存在）并将所有散落季目录移入
4. WHILE 目标父目录下已存在同名季子目录 THEN Organizer SHALL 跳过该季目录的移动并在操作列表中标记为 skip
5. WHEN 散落季合并完成 THEN Organizer SHALL 确保所有季目录位于同一父目录下且原位置不再存在散落目录
6. WHEN 目标父目录已有 tvshow.nfo THEN Organizer SHALL 保留已有的 tvshow.nfo 不覆盖

### 需求 6：刮削候选补 english_title

**用户故事：** 作为媒体库用户，我希望刮削候选列表中每个候选项都包含英文标题，以便在选择匹配时能看到更完整的信息。

#### 验收标准

1. WHEN 系统返回刮削候选列表 THEN 系统 SHALL 为每个候选项包含 english_title 字段
2. WHEN 候选项的 original_title 为拉丁字符 THEN 系统 SHALL 直接使用 original_title 作为 english_title
3. WHEN 候选项的 original_title 非拉丁字符 THEN 系统 SHALL 调用 TMDB_Client 的 _get_english_title 获取英文名
4. IF TMDB API 限流导致 english_title 获取失败 THEN 系统 SHALL 将该候选项的 english_title 设为空字符串，不阻塞其他候选项的处理

### 需求 7：统一清洗逻辑

**用户故事：** 作为媒体库用户，我希望系统在生成标准名和搜索词时使用统一的清洗逻辑，以便消除不同清洗路径导致的不一致问题。

#### 验收标准

1. WHEN Organizer 的 generate_standard_name 在没有刮削数据时需要清洗文件名 THEN Organizer SHALL 调用 Clean_Function 进行清洗
2. WHEN Clean_Function 返回空结果 THEN Organizer SHALL 回退到 parse_filename 的 clean_name 或 folder_title
3. THE Clean_Function SHALL 去除广告标签、质量标签、发布组标签和其他噪音字符

### 需求 8：刮削搜索词优化

**用户故事：** 作为媒体库用户，我希望刮削搜索时使用更彻底的清洗逻辑构造搜索词，以便提高 TMDB 搜索的命中率。

#### 验收标准

1. WHEN 系统构造刮削搜索词 THEN 系统 SHALL 优先使用 Clean_Function 清洗后的结果作为搜索词
2. WHEN Clean_Function 清洗结果为空或长度不足 2 个字符 THEN 系统 SHALL 回退到 parse_filename 的 clean_name
3. WHEN parse_filename 的 clean_name 也为空或长度不足 2 个字符 THEN 系统 SHALL 使用去除扩展名后的原始文件名

### 需求 9：DetailDrawer folder_type 分发

**用户故事：** 作为媒体库用户，我希望详情面板能根据文件夹类型自动切换到最合适的展示布局，以便不同类型的媒体内容有最佳的浏览体验。

#### 验收标准

1. WHEN DetailDrawer 接收到 folder_type 为 "movie" 的节点 THEN DetailDrawer SHALL 渲染 MovieDetail 组件
2. WHEN DetailDrawer 接收到 folder_type 为 "tv" 的节点 THEN DetailDrawer SHALL 渲染 TvDetail 组件
3. WHEN DetailDrawer 接收到 folder_type 为 "series_collection" 的节点 THEN DetailDrawer SHALL 渲染 SeriesCollectionList 组件
4. WHEN DetailDrawer 接收到 folder_type 为 "movie_collection"、"variety" 或 "misc" 的节点 THEN DetailDrawer SHALL 渲染 MovieCollectionGrid 组件
5. IF DetailDrawer 接收到 folder_type 为空或未知值 THEN DetailDrawer SHALL 回退到默认的 FolderDetail 布局

### 需求 10：series_collection 缩略图列表

**用户故事：** 作为媒体库用户，我希望系列电影（如魔戒三部曲）以缩略图列表形式展示，以便快速浏览系列中的每部作品并切换详情。

#### 验收标准

1. WHEN SeriesCollectionList 渲染 THEN SeriesCollectionList SHALL 为每个子项显示小封面（60px 宽）、标题、年份和时长
2. WHEN 用户点击 SeriesCollectionList 中的某个子项 THEN SeriesCollectionList SHALL 触发 onSelectItem 回调并高亮选中项
3. WHEN 用户选中 SeriesCollectionList 中的子项 THEN 父组件 SHALL 将封面更新为选中子项的封面（封面跟随）
4. WHEN SeriesCollectionList 首次渲染 THEN SeriesCollectionList SHALL 默认不选中任何子项，显示聚合文件夹的封面

### 需求 11：movie_collection 小卡片网格

**用户故事：** 作为媒体库用户，我希望电影聚合文件夹（如"欧美电影"）以小卡片网格形式展示，以便直观浏览所有子项。

#### 验收标准

1. WHEN MovieCollectionGrid 渲染 THEN MovieCollectionGrid SHALL 以 2 列网格排列子项，每个卡片显示独立封面和标题
2. WHEN 用户点击 MovieCollectionGrid 中的某个卡片 THEN MovieCollectionGrid SHALL 触发 onSelectItem 回调进入子项详情
3. WHEN 用户在 MovieCollectionGrid 中选中子项 THEN 父组件 SHALL 保持聚合文件夹的封面不变（封面固定）

### 需求 12：tv 季 tab 适配

**用户故事：** 作为媒体库用户，我希望 tv 类型文件夹能正确显示季 tab 和集列表，以便在合并后的 tv 类型下正常浏览剧集内容。

#### 验收标准

1. WHEN TvDetail 接收到包含季子目录的节点 THEN TvDetail SHALL 显示季 tab 切换界面和对应季的集列表
2. WHEN TvDetail 接收到没有季子目录但有视频文件的节点 THEN TvDetail SHALL 以单季模式直接显示集列表，不显示 tab
3. WHEN 用户切换季 tab THEN TvDetail SHALL 更新集列表和封面为当前季的内容（封面跟随当前季）
4. WHEN TvDetail 加载季封面 THEN TvDetail SHALL 从季目录的 poster.jpg 加载

### 需求 13：刮削候选英文名显示

**用户故事：** 作为媒体库用户，我希望在选择刮削候选时能看到英文标题，以便更准确地识别和选择正确的匹配项。

#### 验收标准

1. WHEN CandidatePicker 渲染候选列表 THEN CandidatePicker SHALL 为每个候选项显示标题、年份和媒体类型
2. WHEN 候选项的 english_title 存在且不等于 title THEN CandidatePicker SHALL 在标题下方额外显示 english_title
3. WHEN 候选项的 english_title 为空或等于 title THEN CandidatePicker SHALL 不显示额外的英文名行

### 需求 14：刮削结果英文名显示

**用户故事：** 作为媒体库用户，我希望刮削结果信息中统一显示英文标题，以便在所有入口看到一致的信息。

#### 验收标准

1. WHEN ScrapeInfo 渲染刮削结果 THEN ScrapeInfo SHALL 在标题信息中包含 english_title 字段的显示
2. WHEN english_title 存在且不等于 title THEN ScrapeInfo SHALL 显示 english_title
3. WHEN english_title 为空或等于 title THEN ScrapeInfo SHALL 不显示额外的英文名
4. THE ScrapeInfo 的 english_title 显示逻辑 SHALL 与 CandidatePicker 的 english_title 显示逻辑保持一致
