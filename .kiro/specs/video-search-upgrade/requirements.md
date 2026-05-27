# 需求文档：视频搜索升级与新增影片

## 简介

NAS 影视媒体库管理工具的"搜索升级"与"新增影片"功能。搜索升级允许用户对低质量视频通过 Prowlarr 搜索更高质量的 BT 资源并下载替换；新增影片允许用户通过豆瓣热榜发现或主动搜索新的电影/剧集，搜索资源后下载并自动刮削入库。两个功能共享搜索源、下载通道和筛选体系。

## 术语表

- **Search_Upgrade_System**：搜索升级系统，负责协调搜索、筛选、下载替换的完整流程
- **Prowlarr_Client**：Prowlarr BT 搜索客户端（已有 `backend/searcher.py`），通过 Prowlarr API 搜索 BT 资源
- **Download_Manager**：下载管理器，封装 qBittorrent 和 Alist 两种下载通道（已有 `backend/downloader.py`）
- **Search_Modal**：搜索结果弹窗（已有 `frontend/components/search/SearchModal.tsx`），展示搜索结果并触发下载
- **Quality_Analyzer**：质量分析器，根据视频元数据（分辨率、编码、HDR 等）判断视频质量等级并与搜索结果进行质量对比
- **Batch_Upgrade_Engine**：批量升级引擎，管理多个视频的搜索升级队列、进度追踪和结果汇总
- **Upgrade_Task**：单个搜索升级任务，包含目标视频信息、搜索关键词、匹配结果、下载状态
- **Quality_Tag**：质量标签，从 BT 资源标题中解析出的完整质量信息，包含分辨率、来源、视频编码、音频编码和字幕标记（如 "Bluray-2160p-x265-DTS-中字"）
- **Douban_Discovery**：豆瓣发现模块，通过豆瓣热榜/搜索获取影片信息（已有 `backend/douban_client.py`）
- **Add_Media_Flow**：新增影片流程，从发现影片 → 搜索资源 → 下载 → 自动刮削入库的完整链路

## 需求

### 需求 1：单个视频/文件夹搜索升级

**用户故事：** 作为媒体库用户，我想对单个低质量视频或文件夹搜索更高质量的资源并下载替换，以便提升观影体验。

#### 验收标准

1. WHEN 用户在详情面板点击"搜索升级"按钮, THE Search_Upgrade_System SHALL 使用视频名称或文件夹名称作为关键词调用 Prowlarr_Client 进行搜索，并在 Search_Modal 中展示结果
2. WHEN Prowlarr_Client 返回搜索结果, THE Quality_Analyzer SHALL 为每条结果从标题中解析完整的 Quality_Tag，包含：
   - 分辨率（720p/1080p/2160p）
   - 来源（Bluray/WEB-DL/Remux/HDTV）
   - 视频编码（x264/x265/HEVC/AV1）— 其中 x265/HEVC 为压制版，体积通常比 Remux 小 50-70%
   - 音频编码（AAC/DTS/DTS-HD/TrueHD/Atmos）
   - 字幕标记（CHS/CHT/中字/简繁/内封字幕/外挂字幕）— 从标题中识别中文字幕关键词
3. WHEN 搜索结果展示在 Search_Modal 中, THE Search_Modal SHALL 按做种数降序排列结果，并对每条结果显示标题、Quality_Tag、文件大小（GB）、做种数和索引器名称
4. WHEN 用户在 Search_Modal 中选择一条资源并点击"下载"按钮, THE Download_Manager SHALL 根据配置将下载链接推送到 qBittorrent 或 Alist，并将保存路径设为原视频所在目录
5. IF Prowlarr_Client 搜索超时或返回错误, THEN THE Search_Modal SHALL 显示具体的错误信息并允许用户重试
6. WHEN 用户在 Search_Modal 中查看结果, THE Search_Modal SHALL 允许用户编辑搜索关键词并重新搜索


### 需求 2：质量对比与筛选过滤

**用户故事：** 作为媒体库用户，我想在搜索结果中直观看到哪些资源比当前视频质量更高，并能按自定义条件（音频编码、文件大小等）筛选结果，以便精准找到符合需求的资源。

#### 验收标准

1. WHEN 搜索结果展示时, THE Quality_Analyzer SHALL 将当前视频的分辨率信息显示在 Search_Modal 顶部，作为对比基准
2. WHEN 搜索结果的分辨率高于当前视频分辨率, THE Search_Modal SHALL 使用绿色高亮标记该结果的 Quality_Tag
3. WHEN 搜索结果的分辨率等于或低于当前视频分辨率, THE Search_Modal SHALL 使用灰色标记该结果的 Quality_Tag
4. THE Quality_Analyzer SHALL 按以下优先级排序质量等级：2160p Remux > 2160p Bluray > 2160p WEB-DL > 1080p Remux > 1080p Bluray > 1080p WEB-DL > 720p > 其他
5. WHEN 搜索结果展示时, THE Search_Modal SHALL 提供筛选条件栏，支持以下可组合的筛选维度：
   - 分辨率下限（720p / 1080p / 2160p）
   - 来源类型（Bluray / WEB-DL / Remux / 不限）
   - 视频编码（x265/HEVC 压制版 / x264 / 不限）— 压制版体积更小，适合存储空间有限的用户
   - 音频编码（DTS / DTS-HD / TrueHD / Atmos / AAC / 不限）
   - 字幕要求（含中文字幕 / 不限）— 筛选标题中包含 CHS/CHT/中字/简繁等中文字幕标记的资源
   - 文件大小上限（用户输入 GB 数值）
   - 最低做种数（用户输入数值，默认 1）
6. WHEN 用户设置筛选条件后, THE Search_Modal SHALL 实时过滤搜索结果列表，仅显示满足所有条件的资源
7. WHEN 用户清除筛选条件, THE Search_Modal SHALL 恢复显示全部搜索结果
8. WHEN 批量搜索升级自动推荐时, THE Batch_Upgrade_Engine SHALL 优先使用用户设置的筛选条件来选择推荐资源，若无匹配则 fallback 到质量等级最高且做种数 > 0 的结果

### 需求 3：下载通道选择

**用户故事：** 作为媒体库用户，我想选择通过 qBittorrent 或 Alist 下载资源，以便灵活使用不同的下载方式。

#### 验收标准

1. WHEN 用户点击下载按钮, THE Search_Modal SHALL 提供 qBittorrent 和 Alist 两个下载通道选项
2. WHEN 用户选择 qBittorrent 通道, THE Download_Manager SHALL 调用 qBittorrent API 添加种子任务，保存路径为原视频所在目录
3. WHEN 用户选择 Alist 通道, THE Download_Manager SHALL 调用 Alist 离线下载 API 推送下载链接，目标路径为原视频所在目录
4. IF qBittorrent 或 Alist 服务不可用, THEN THE Download_Manager SHALL 返回明确的错误信息，包含服务名称和连接地址
5. WHILE 用户未在设置中配置 qBittorrent 或 Alist 地址, THE Search_Modal SHALL 禁用对应的下载通道按钮并显示"未配置"提示

### 需求 4：批量搜索升级

**用户故事：** 作为媒体库用户，我想一键对所有低质量视频进行批量搜索升级，以便高效地提升整个媒体库的质量。

#### 验收标准

1. WHEN 用户在主页筛选"需升级"视频列表后选择多个视频并点击"批量搜索升级", THE Batch_Upgrade_Engine SHALL 为每个选中的视频创建一个 Upgrade_Task 并加入执行队列
2. WHILE 批量升级任务执行中, THE Batch_Upgrade_Engine SHALL 逐个执行搜索，每个视频搜索间隔至少 2 秒以避免 Prowlarr API 限流
3. WHEN 单个视频搜索完成, THE Batch_Upgrade_Engine SHALL 自动选择质量等级最高且做种数大于 0 的结果作为推荐下载项
4. WHILE 批量升级任务执行中, THE Search_Upgrade_System SHALL 在前端显示实时进度，包含已完成数、总数、当前正在搜索的视频名称
5. WHEN 所有视频搜索完成, THE Batch_Upgrade_Engine SHALL 展示汇总结果面板，列出每个视频的推荐资源（Quality_Tag、大小、做种数），用户可逐个确认或一键全部下载
6. IF 某个视频搜索失败或未找到更高质量资源, THEN THE Batch_Upgrade_Engine SHALL 在汇总结果中标记该视频为"未找到"并跳过，继续处理队列中的下一个视频
7. WHEN 用户在汇总结果面板点击"全部下载", THE Download_Manager SHALL 将所有已确认的资源按队列依次推送到选定的下载通道

### 需求 5：搜索升级后端 API

**用户故事：** 作为前端开发者，我需要后端提供搜索升级相关的 API 端点，以便前端调用完成搜索和下载流程。

#### 验收标准

1. THE Search_Upgrade_System SHALL 提供 `GET /search` 端点，接受 `query` 参数，返回 Prowlarr 搜索结果列表，每条结果包含 title、size_gb、indexer、seeders、leechers、download_url、quality_tag 字段
2. THE Search_Upgrade_System SHALL 提供 `POST /download` 端点，接受 download_url、save_path 和 download_type（"qb" 或 "alist"）参数，将下载任务推送到对应的下载通道并返回操作结果
3. THE Search_Upgrade_System SHALL 提供 `POST /batch-search` 端点，接受视频路径列表，逐个搜索并返回 EventSource 流式进度和结果
4. THE Search_Upgrade_System SHALL 提供 `POST /batch-download` 端点，接受包含 download_url 和 save_path 的任务列表，批量推送下载任务并返回每个任务的成功/失败状态
5. IF 请求中缺少必要的配置（Prowlarr API Key、qBittorrent 地址等）, THEN THE Search_Upgrade_System SHALL 返回 HTTP 400 状态码和具体的缺失配置项说明

### 需求 6：搜索升级状态反馈

**用户故事：** 作为媒体库用户，我想在下载任务提交后获得清晰的状态反馈，以便了解升级进度。

#### 验收标准

1. WHEN 下载任务成功推送到 qBittorrent 或 Alist, THE Search_Modal SHALL 显示"任务已下达"的成功提示并在 3 秒后自动关闭弹窗
2. IF 下载任务推送失败, THEN THE Search_Modal SHALL 显示包含失败原因的错误提示，并保持弹窗打开以便用户重试或选择其他资源
3. WHEN 批量下载全部完成, THE Batch_Upgrade_Engine SHALL 显示汇总通知，包含成功数和失败数

### 需求 7：搜索源管理

**用户故事：** 作为媒体库用户，我想了解并选择不同的搜索源来获取资源，以便根据自己的网络环境和资源偏好获得最佳搜索结果。

#### 搜索源方案对比

| 搜索源 | 原理 | 优势 | 劣势 | 适用场景 |
|--------|------|------|------|----------|
| **Prowlarr（推荐，主力）** | 索引器聚合代理，通过 Torznab/Newznab 协议统一管理多个 BT/Usenet 站点 | 一次配置多站搜索；支持公开+私有 tracker；API 标准化；社区活跃 | 需自建服务；依赖 indexer 站点可用性 | 有 NAS/Docker 环境的用户，长期使用 |
| **Jackett** | 类似 Prowlarr 的老牌索引器代理 | 支持站点多；兼容性好 | 已逐步被 Prowlarr 取代；不支持 Usenet；配置需逐个同步到下游 | 已有 Jackett 的用户可兼容接入 |
| **直接 BT 站爬虫** | 直接爬取 BT 站搜索页面 | 不依赖第三方服务 | 反爬风险高；维护成本大；站点变动频繁 | 不推荐，仅作 fallback |
| **网盘资源搜索** | 聚合阿里云盘/夸克等网盘分享链接 | 国内下载速度快；不需要做种 | 资源质量不稳定；链接易失效；无标准 API | 国内用户补充搜索 |

#### 验收标准

1. THE Search_Upgrade_System SHALL 以 Prowlarr 作为主要搜索源，通过其 API 聚合所有已配置的 indexer 进行搜索
2. WHEN 用户在设置页配置 Prowlarr 地址和 API Key 后, THE Search_Upgrade_System SHALL 验证连接可用性并显示已配置的 indexer 数量
3. THE Search_Upgrade_System SHALL 支持通过 Jackett 的 Torznab 兼容接口作为备选搜索源，用户可在设置中配置 Jackett 地址和 API Key
4. WHEN 搜索结果返回时, THE Search_Modal SHALL 在每条结果中显示来源 indexer 名称，帮助用户识别资源来源站点
5. IF Prowlarr 和 Jackett 均未配置, THEN THE Search_Upgrade_System SHALL 在搜索界面显示配置引导提示，说明需要至少配置一个搜索源

### 需求 8：豆瓣发现与新增影片

**用户故事：** 作为媒体库用户，我想通过豆瓣热榜发现热门影片或主动搜索想看的电影/剧集，然后搜索资源下载并自动刮削入库，以便快速扩充媒体库。

#### 验收标准

1. THE Add_Media_Flow SHALL 在前端提供"新增影片"入口（主页 Header 区域），打开新增影片面板
2. WHEN 用户打开新增影片面板, THE Douban_Discovery SHALL 默认展示豆瓣热门电影和热门剧集榜单，每个榜单显示影片名称、年份、评分和封面
3. WHEN 用户在新增影片面板输入搜索关键词, THE Douban_Discovery SHALL 调用豆瓣搜索接口返回匹配的影片列表，显示名称、年份、评分和类型
4. WHEN 用户从榜单或搜索结果中选择一部影片, THE Add_Media_Flow SHALL 使用影片名称（优先英文/原名）作为关键词调用 Prowlarr_Client 搜索 BT 资源，并在同一面板中展示搜索结果
5. WHEN 搜索结果展示时, THE Add_Media_Flow SHALL 复用需求 2 的筛选过滤体系（分辨率、编码、字幕、大小等），帮助用户选择合适的资源
6. WHEN 用户选择资源并点击下载, THE Add_Media_Flow SHALL 让用户选择保存目录（默认为 NAS 根路径下按类型分类的目录），然后通过 Download_Manager 推送下载任务
7. WHEN 下载任务推送成功, THE Add_Media_Flow SHALL 使用豆瓣获取的影片信息（名称、年份、评分、简介、封面）自动生成 NFO 文件和下载封面到目标目录，完成预刮削
8. IF 豆瓣搜索无结果或接口不可用, THEN THE Add_Media_Flow SHALL 允许用户直接输入关键词搜索 BT 资源，跳过豆瓣发现步骤

### 需求 9：新增影片后端 API

**用户故事：** 作为前端开发者，我需要后端提供新增影片相关的 API 端点，以便前端调用完成发现、搜索和入库流程。

#### 验收标准

1. THE Add_Media_Flow SHALL 提供 `GET /douban/hot` 端点，接受 `type` 参数（movie/tv），返回豆瓣热门榜单列表，每条包含 title、year、rating、cover_url、douban_id 字段
2. THE Add_Media_Flow SHALL 提供 `GET /douban/search` 端点，接受 `query` 参数，返回豆瓣搜索结果列表
3. THE Add_Media_Flow SHALL 提供 `POST /add-media` 端点，接受影片信息（title、year、douban_id 等）和 save_path 参数，在目标目录创建文件夹并生成预刮削的 NFO 文件和封面
4. THE Add_Media_Flow SHALL 复用 `GET /search` 和 `POST /download` 端点进行资源搜索和下载，不重复实现
5. WHEN 预刮削完成后, THE Add_Media_Flow SHALL 触发媒体库增量同步，使新增影片立即出现在前端媒体库中
