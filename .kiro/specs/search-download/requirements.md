# 需求文档：搜索下载优化 (search-download)

## 简介

本需求文档定义了 NAS 影视媒体库管理工具在搜索展示、剧集搜索、批量搜索和下载管理四个维度的功能优化需求。当前系统已具备基础的 Prowlarr 搜索和 qBittorrent/Alist 下载能力，但搜索结果展示信息密度不足、剧集搜索缺乏整季/逐集策略、批量搜索缺少智能推荐、下载后缺乏任务队列和文件归位机制。本功能通过结构化搜索展示、智能剧集搜索策略、高匹配批量推荐、完整下载生命周期管理四个方面进行增强，实现从搜索到下载到归位的完整闭环。

## 术语表

- **系统 (System)**：NAS 影视媒体库管理工具的后端服务
- **搜索弹窗 (Search_Modal)**：前端搜索资源弹窗组件，展示搜索结果并提供下载操作
- **批量升级面板 (Batch_Upgrade_Panel)**：前端批量搜索升级全屏弹窗组件
- **搜索引擎 (Search_Engine)**：后端 searcher.py 中的增强搜索模块，负责多关键词搜索和综合排序
- **质量解析器 (Quality_Parser)**：后端 quality_parser.py 中的 BT 标题质量解析模块
- **下载管理器 (Download_Manager)**：后端负责下载任务队列管理、进度监控和文件归位的新模块
- **下载任务 (Download_Task)**：一条下载记录，包含状态（pending/downloading/seeding/completed/relocating/archived/failed）、来源、目标路径等信息
- **回收站 (Recycle_Bin)**：存放被替换旧文件的临时目录，支持定时清理和手动恢复
- **发布组 (Release_Group)**：BT 资源的制作/发布团队标识，如 CMCT、HDHome、CHD 等
- **整季包 (Season_Pack)**：包含一整季所有集数的单个 BT 资源
- **逐集搜索 (Episode_Search)**：按 S01E01 格式逐集搜索并汇总结果的搜索策略
- **同源匹配 (Same_Source_Match)**：多季/多集搜索时优先选择同一发布组资源的匹配策略
- **影子名 (Shadow_Name)**：存储在 media_library.json 中的标准化搜索名称
- **搜索回退链 (Search_Fallback_Chain)**：多关键词按优先级依次搜索的策略，影子名 → clean_name → 英文原名 → TMDB 原始标题
- **二次匹配 (Secondary_Match)**：对 Prowlarr 返回的原始结果进行标题/年份精确比对，剔除误匹配资源
- **全局过滤规则 (Global_Filter)**：用户可配置的必须包含和严格排除关键词，在二次匹配阶段执行
- **Prowlarr**：BT 索引器聚合搜索服务（localhost:9696）
- **qBittorrent**：BT 下载客户端（localhost:8080）
- **Alist**：网盘离线下载服务（localhost:5244）

## 需求

### 需求 1：搜索结果结构化展示

**用户故事：** 作为媒体库用户，我希望搜索结果以结构化方式分行展示标题、分辨率、编码、字幕、大小、做种数等信息，以便快速评估每条资源的质量。

#### 验收标准

1. WHEN Search_Modal 渲染搜索结果列表 THEN Search_Modal SHALL 为每条结果分行显示：第一行为质量标签（分辨率+来源+编码）和索引器名称，第二行为完整原始标题，第三行为文件大小、做种数和发布时间
2. WHEN 搜索结果包含中文字幕标记 THEN Search_Modal SHALL 在质量标签旁显示"中字"徽章
3. WHEN 搜索结果的分辨率高于当前媒体的分辨率 THEN Search_Modal SHALL 在该结果上显示"↑ 更高"升级标识
4. WHEN Quality_Parser 解析 BT 标题 THEN Quality_Parser SHALL 额外提取发布组名称并包含在 QualityTag 结构中

### 需求 2：搜索结果分组展示

**用户故事：** 作为媒体库用户，我希望搜索结果按发布组或来源自动分组，以便快速对比同一发布组的不同版本。

#### 验收标准

1. WHEN Search_Modal 接收到搜索结果 THEN Search_Modal SHALL 提供"按发布组分组"和"按索引器分组"两种分组模式，默认为不分组的平铺模式
2. WHEN 用户选择"按发布组分组"模式 THEN Search_Modal SHALL 将同一发布组的结果归入同一折叠组，组标题显示发布组名称和该组结果数量
3. WHEN 用户选择"按索引器分组"模式 THEN Search_Modal SHALL 将同一索引器的结果归入同一折叠组
4. WHEN 搜索结果无法识别发布组 THEN Search_Modal SHALL 将该结果归入"其他"分组

### 需求 3：多关键词搜索回退策略

**用户故事：** 作为媒体库用户，我希望系统在搜索资源时能自动尝试多个关键词变体，以便在首选关键词搜不到时仍能找到资源。

#### 验收标准

1. WHEN Search_Engine 执行搜索 THEN Search_Engine SHALL 按以下优先级依次使用关键词搜索 Prowlarr：影子名（shadow_name）→ 清洗名（clean_name）→ 英文原名（TMDB original_title）→ TMDB 中文标题（title）
2. WHEN 当前关键词搜索返回有效结果（经过二次匹配后仍有 >= 1 条结果）THEN Search_Engine SHALL 停止回退，不再尝试后续关键词
3. WHEN 当前关键词搜索返回 0 条有效结果 THEN Search_Engine SHALL 自动使用回退链中的下一个关键词重新搜索
4. WHEN 回退链中所有关键词均搜索完毕仍无有效结果 THEN Search_Engine SHALL 返回空结果并标记该媒体为"未找到资源"
5. WHEN Search_Engine 返回搜索结果 THEN Search_Engine SHALL 在结果中标注实际命中的搜索关键词，供前端展示

### 需求 4：搜索结果二次匹配与过滤

**用户故事：** 作为媒体库用户，我希望系统对 Prowlarr 返回的原始搜索结果进行精确匹配过滤，以便剔除同名不同片、年份不符等误匹配资源。

#### 验收标准

1. WHEN Search_Engine 从 Prowlarr 获取到原始搜索结果 THEN Search_Engine SHALL 对每条结果执行二次匹配：从 BT 标题中解析出中文名、英文名和年份，与目标媒体的标题（含别名/译名）和年份进行比对
2. WHEN 二次匹配比对年份时 THEN Search_Engine SHALL 允许电影年份 ±1 年容差，剧集年份与任一季的年份匹配即通过
3. WHEN 二次匹配的标题比对失败（种子标题中的中英文名均不在目标媒体的标题、原始标题、别名列表中）THEN Search_Engine SHALL 将该结果标记为"不匹配"并从结果列表中剔除
4. WHEN 二次匹配完成后 THEN Search_Engine SHALL 仅将通过匹配的结果传入评分排序环节，未通过的结果不参与后续流程

### 需求 5：全局质量过滤规则

**用户故事：** 作为媒体库用户，我希望能配置全局的质量过滤规则（必须包含和严格排除的关键词），以便自动过滤掉低质量资源。

#### 验收标准

1. THE 系统 SHALL 在设置中提供"搜索过滤规则"配置项，包含"必须包含"和"严格排除"两个关键词列表
2. WHEN 用户配置了"严格排除"关键词（如 TS, CAM, HDTC, TC, TELECINE）THEN Search_Engine SHALL 在二次匹配阶段对每条结果的标题执行排除检查，命中任一排除词的结果直接丢弃
3. WHEN 用户配置了"必须包含"关键词（如 HEVC, x265）THEN Search_Engine SHALL 在二次匹配阶段对每条结果的标题执行包含检查，未命中任一包含词的结果直接丢弃
4. WHEN 用户未配置任何过滤规则 THEN Search_Engine SHALL 使用默认排除列表：TS, CAM, HDTC, TC, TELECINE, HDTS
5. WHEN 过滤规则应用于批量搜索 THEN Batch_Upgrade_Panel SHALL 在搜索前读取全局过滤规则并传递给 Search_Engine

### 需求 6：整季搜索策略

**用户故事：** 作为媒体库用户，我希望搜索剧集时系统优先搜索整季包，搜不到再自动切换为逐集搜索，以便用最少的下载任务获取完整一季。

#### 验收标准

1. WHEN 用户对 tv 类型媒体触发季级搜索 THEN Search_Engine SHALL 首先使用"标题 + SXX"格式搜索整季包
2. WHEN 整季包搜索返回的结果中存在包含该季全部集数的资源 THEN Search_Engine SHALL 将整季包结果标记为"整季包"并优先展示
3. WHEN 整季包搜索未找到包含全部集数的资源 THEN Search_Engine SHALL 自动切换为逐集搜索模式，按 S01E01 格式逐集搜索
4. WHEN 整季包和逐集结果同时存在 THEN Search_Engine SHALL 在结果中同时展示两种方案，标注整季包的总大小和逐集方案的总大小供用户选择
5. IF 逐集搜索过程中某一集未找到资源 THEN Search_Engine SHALL 在结果汇总中标记该集为"缺失"并继续搜索其余集数
6. WHEN Search_Engine 判定某资源为"整季包"且准备推荐下载 THEN Search_Engine SHALL 先通过 Prowlarr API 获取该种子的文件列表元数据，解析其中视频文件的集数信息
7. WHEN 种子文件列表解析出的视频文件数量 < 目标季的总集数 THEN Search_Engine SHALL 将该资源降级标记为"不完整包"，不作为整季包推荐
8. WHEN 种子为磁力链接无法预先解析文件列表 THEN Search_Engine SHALL 在结果中标注"磁力链-集数未验证"，由用户自行判断

### 需求 7：同源匹配策略

**用户故事：** 作为媒体库用户，我希望搜索多季或多集时系统优先推荐同一发布组的资源，以便保持整部剧集的画质和编码风格一致。

#### 验收标准

1. WHEN Search_Engine 执行多集搜索且结果中存在多个发布组 THEN Search_Engine SHALL 计算每个发布组覆盖的集数比例
2. WHEN 某个发布组覆盖了全部目标集数 THEN Search_Engine SHALL 将该发布组标记为"完整覆盖"并优先推荐
3. WHEN 没有单一发布组能覆盖全部集数 THEN Search_Engine SHALL 选择覆盖率最高的发布组作为主推荐，缺失集数从其他发布组补充
4. WHEN 同源匹配结果确定后 THEN Search_Engine SHALL 在返回结果中标注每条资源的发布组名称和该发布组的总覆盖率

### 需求 8：逐集搜索与结果汇总

**用户故事：** 作为媒体库用户，我希望系统能自动按集号逐集搜索并将结果汇总展示，以便一次性查看和确认所有集的资源。

#### 验收标准

1. WHEN 用户触发逐集搜索 THEN Search_Engine SHALL 按 S01E01、S01E02 格式依次搜索每一集，每集取评分最高的结果作为推荐
2. WHEN 逐集搜索完成 THEN Search_Engine SHALL 返回汇总结果，包含每集的推荐资源、备选资源列表和搜索状态（found/not_found）
3. WHEN 前端展示逐集搜索汇总 THEN Search_Modal SHALL 以表格形式展示每集的集号、推荐资源质量标签、大小和做种数，支持逐集切换备选资源
4. WHEN 用户在汇总表格中修改某集的选择 THEN Search_Modal SHALL 更新该集的选中资源并重新计算总大小

### 需求 9：高匹配批量推荐算法

**用户故事：** 作为媒体库用户，我希望批量搜索时系统根据影子名、分辨率偏好和编码偏好自动推荐最佳资源，以便减少逐个手动选择的工作量。

#### 验收标准

1. WHEN Batch_Upgrade_Panel 执行批量搜索 THEN Search_Engine SHALL 为每个媒体项使用搜索回退链（影子名 → clean_name → 英文原名 → TMDB 标题）搜索，结合当前分辨率和用户编码偏好计算匹配分数
2. WHEN Search_Engine 计算批量推荐匹配分数 THEN Search_Engine SHALL 综合考虑以下维度：标题匹配度（权重 0.3）、分辨率提升幅度（权重 0.25）、编码匹配度（权重 0.15）、做种数健康度（权重 0.15）、中文字幕加分（权重 0.1）和文件大小合理性（权重 0.05）
3. WHEN 批量搜索结果中某项的最佳匹配分数低于 0.5 THEN Search_Engine SHALL 将该项标记为"低置信度"，前端以警告色显示
4. WHEN 批量搜索结果中某项的分辨率未提升 THEN Search_Engine SHALL 将该项标记为"无提升"，默认不勾选确认
5. WHEN 批量搜索执行前 THEN Search_Engine SHALL 读取全局过滤规则，对所有搜索结果先执行二次匹配和过滤，再进入评分环节

### 需求 10：批量结果确认与修改

**用户故事：** 作为媒体库用户，我希望批量搜索完成后能一键全选推荐结果，同时支持逐个查看和修改选择，以便在批量操作中保留灵活性。

#### 验收标准

1. WHEN 批量搜索完成进入确认阶段 THEN Batch_Upgrade_Panel SHALL 显示所有搜索结果的汇总列表，每项包含当前分辨率、推荐资源质量标签、匹配分数和确认复选框
2. WHEN 用户点击"全选推荐" THEN Batch_Upgrade_Panel SHALL 勾选所有匹配分数 >= 0.5 且分辨率有提升的项目
3. WHEN 用户点击某项的"查看备选" THEN Batch_Upgrade_Panel SHALL 展开该项的完整搜索结果列表，支持切换选中的资源
4. WHEN 用户修改某项的选中资源 THEN Batch_Upgrade_Panel SHALL 更新该项的显示信息并重新计算批量下载的总大小

### 需求 11：批量一键下载

**用户故事：** 作为媒体库用户，我希望确认批量搜索结果后能一键下载所有选中的资源，以便高效完成批量升级。

#### 验收标准

1. WHEN 用户在 Batch_Upgrade_Panel 点击"全部下载" THEN 系统 SHALL 将所有已确认项目的下载任务提交到 Download_Manager 的任务队列
2. WHEN 批量下载任务提交完成 THEN Batch_Upgrade_Panel SHALL 显示提交结果摘要，包含成功提交数和失败数
3. WHEN 批量下载包含不同下载通道的任务 THEN 系统 SHALL 根据资源类型自动选择 qBittorrent 或 Alist 通道
4. IF 批量下载过程中某个任务提交失败 THEN 系统 SHALL 记录失败原因并继续提交其余任务

### 需求 12：下载任务队列管理

**用户故事：** 作为媒体库用户，我希望系统维护一个下载任务队列，以便追踪所有下载任务的状态。

#### 验收标准

1. THE Download_Manager SHALL 维护一个持久化的下载任务队列（JSON 文件），每个任务包含唯一 ID、媒体名称、下载 URL、保存路径、下载通道、下载器任务 Hash、状态和创建时间
2. WHEN 新下载任务提交到 Download_Manager THEN Download_Manager SHALL 将任务状态设为 "pending" 并加入队列
3. WHEN Download_Manager 处理 pending 任务 THEN Download_Manager SHALL 调用对应下载通道（qBittorrent 或 Alist）推送下载，记录下载器返回的任务 Hash，并将状态更新为 "downloading"
4. WHEN 用户查询任务队列 THEN Download_Manager SHALL 返回按创建时间倒序排列的任务列表，支持按状态过滤
5. IF 下载推送失败 THEN Download_Manager SHALL 将任务状态设为 "failed" 并记录失败原因
6. WHEN 后端服务启动时 THEN Download_Manager SHALL 加载持久化的任务队列，对所有状态为 "downloading" 的任务，通过已记录的下载器任务 Hash 向 qBittorrent/Alist 查询实际状态并同步更新
7. IF 启动时某 "downloading" 任务在下载器中已不存在 THEN Download_Manager SHALL 将该任务标记为 "lost" 状态，等待用户手动处理

### 需求 13：下载进度监控

**用户故事：** 作为媒体库用户，我希望实时查看每个下载任务的进度，以便了解下载状态。

#### 验收标准

1. WHEN 任务状态为 "downloading" 且下载通道为 qBittorrent THEN Download_Manager SHALL 通过 qBittorrent API 轮询获取下载进度百分比、下载速度和预计剩余时间
2. WHEN 任务状态为 "downloading" 且下载通道为 Alist THEN Download_Manager SHALL 通过 Alist API 查询离线下载任务状态，区分两个阶段：云端离线下载阶段（显示"云端下载中"）和 NAS 本地同步阶段（显示"同步中"及进度）
3. WHEN qBittorrent 报告某任务下载完成 THEN Download_Manager SHALL 将该任务状态更新为 "completed"
4. WHEN Alist 报告云端离线下载完成但本地同步未开始 THEN Download_Manager SHALL 将任务状态更新为 "cloud_done"，待本地同步完成后再更新为 "completed"
5. WHEN 前端请求下载进度 THEN 系统 SHALL 返回所有活跃任务的当前进度信息，包含进度百分比、下载速度、状态和阶段描述
6. IF qBittorrent 或 Alist API 不可达 THEN Download_Manager SHALL 将受影响任务标记为 "unknown" 状态并在 API 恢复后自动重新同步

### 需求 14：整季包解包与集数映射

**用户故事：** 作为媒体库用户，我希望下载的整季包在归位前能自动将文件与标准集号（S01E01）精准匹配并重命名，以便媒体服务器能正确识别。

#### 验收标准

1. WHEN Download_Manager 检测到已完成的下载任务为整季包类型 THEN Download_Manager SHALL 扫描下载目录中的所有视频文件，使用 parse_filename 从文件名中提取集数信息
2. WHEN 视频文件的集数信息提取成功 THEN Download_Manager SHALL 按照目标季目录的命名规则（如"剧名 S01E01.扩展名"）生成标准文件名映射表
3. WHEN 集数映射表生成完成 THEN Download_Manager SHALL 在归位前将视频文件重命名为标准格式，同时保留原始文件名到任务日志中
4. IF 某视频文件无法提取集数信息 THEN Download_Manager SHALL 将该文件标记为"未识别"，归位时保留原始文件名并在前端提示用户手动处理
5. WHEN 整季包中包含字幕文件（.srt/.ass/.ssa）THEN Download_Manager SHALL 将字幕文件与同集数的视频文件配对，一并重命名和归位

### 需求 15：下载完成文件归位

**用户故事：** 作为媒体库用户，我希望下载完成后系统自动将文件移动到正确的媒体库文件夹，以便新文件自动归入媒体库目录结构。

#### 验收标准

1. WHEN Download_Manager 检测到任务状态变为 "completed" THEN Download_Manager SHALL 将下载的文件从 qBittorrent/Alist 的下载目录移动到任务指定的目标路径
2. WHEN 目标路径为 tv 类型的季目录 THEN Download_Manager SHALL 将文件移入对应的季子目录（如 Season 01/）
3. WHEN 目标路径为 movie 类型的文件夹 THEN Download_Manager SHALL 将文件移入该电影文件夹
4. WHEN 文件归位完成 THEN Download_Manager SHALL 将任务状态更新为 "archived" 并记录归位后的最终路径
5. IF 文件归位过程中目标路径不存在 THEN Download_Manager SHALL 自动创建目标目录后再移动文件

### 需求 16：新旧文件共存与确认替换

**用户故事：** 作为媒体库用户，我希望下载完成归位后新旧文件同时存在，确认新文件无误后再删除旧文件，以便避免误删导致数据丢失。

#### 验收标准

1. WHEN Download_Manager 将新文件归位到已有同名媒体的目录 THEN Download_Manager SHALL 保留旧文件不删除，新旧文件同时存在于目标目录
2. WHEN 新旧文件共存时 THEN 系统 SHALL 在前端该媒体项上显示"待确认替换"标识，列出新文件和旧文件的名称及大小
3. WHEN 用户确认替换 THEN 系统 SHALL 将旧视频文件及其同名 .nfo 和海报图片一并移入 Recycle_Bin，保留旧的 tvshow.nfo（剧级元数据）不动，新视频文件沿用旧文件的命名规则
4. WHEN 用户取消替换 THEN 系统 SHALL 将新文件移入 Recycle_Bin 并保留旧文件
5. WHEN 确认替换完成且新文件已就位 THEN 系统 SHALL 触发一次针对该文件夹的刮削更新，确保 episode.nfo 中的质量信息（分辨率/编码）与新文件一致

### 需求 17：回收站机制

**用户故事：** 作为媒体库用户，我希望被替换的旧文件进入回收站而非直接删除，以便在发现问题时能够找回。

#### 验收标准

1. THE Recycle_Bin SHALL 使用 NAS 上的指定目录（可在设置中配置路径）存放被删除的文件
2. WHEN 文件移入 Recycle_Bin THEN Recycle_Bin SHALL 记录原始路径、移入时间和关联的下载任务 ID
3. WHEN 用户查看回收站 THEN 系统 SHALL 返回回收站中所有文件的列表，包含原始路径、文件大小和移入时间
4. WHEN 用户从回收站恢复文件 THEN Recycle_Bin SHALL 将文件移回原始路径
5. WHEN 回收站中的文件超过配置的保留天数（默认 30 天）THEN Recycle_Bin SHALL 自动永久删除过期文件并释放空间

### 需求 18：下载方式智能推荐

**用户故事：** 作为媒体库用户，我希望系统根据资源特征自动推荐最合适的下载方式（qBittorrent 或 Alist），以便选择最高效的下载通道。

#### 验收标准

1. WHEN 用户触发下载且 qBittorrent 和 Alist 均已配置 THEN 系统 SHALL 根据资源特征自动推荐下载通道
2. WHEN 资源的做种数 >= 5 且文件大小 <= 50GB THEN 系统 SHALL 推荐使用 qBittorrent 下载
3. WHEN 资源的做种数 < 5 或文件大小 > 50GB THEN 系统 SHALL 推荐使用 Alist 网盘离线下载
4. WHEN 系统推荐下载通道后 THEN 系统 SHALL 在下载按钮上标注推荐通道，用户仍可手动切换
5. WHILE 仅配置了一种下载通道 THEN 系统 SHALL 直接使用已配置的通道，不显示推荐标识

## 未来迭代规划 (Phase 2)

以下功能在当前版本暂不实现，归档至二期规划：

### P2-1：种子排序优先级可配置

未来支持用户在设置中自定义搜索结果的排序权重维度和顺序，如：资源优先级 → 做种数 → 文件体积 → 站点上传量。当前版本使用固定的评分算法排序。

### P2-2：下载转移多线程作业管理（TransferChain）

未来将简单的文件移动升级为多线程作业管理系统，支持：
- 按媒体分组的作业视图（JobManager），一个媒体的多个文件归为一个作业
- 多线程并行整理，提升大批量文件的处理速度
- 在归位环节对接已有的 V3 整理流水线（散装封装 + 结构归位 + NFO 季归位 + 影子名生成）

### P2-3：无效种子缓存/黑名单

未来引入 TTL 缓存机制，记录下载失败的种子 URL 和死种 Hash：
- 24 小时内避免重复提交同一个失败种子
- 批量搜索时自动跳过已知无效种子
- 支持手动清除黑名单

### P2-4：发现与订阅模块

参考 MoviePilot 的发现+订阅架构，未来新增：
- 发现页面：聚合 TMDB 热门/趋势、豆瓣热映/TOP250/周榜、Bangumi 每日放送
- 订阅管理：添加订阅 → 定时搜索 → 自动匹配下载 → 完成后删除订阅
- 剧集订阅追踪缺失集数（total_episode / lack_episode）
- 质量过滤规则（分辨率/编码/包含/排除）
