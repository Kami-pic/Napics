# [TODO] 发现推荐模块改造

> 参考 MoviePilot v2 的发现/推荐/订阅模块，将其核心功能接入 nas-video-upgrader。
> 分三个阶段，每阶段可独立交付。

## 阶段 1：后端豆瓣 API v2 + 多榜单推荐

### 1.1 后端：接入豆瓣 API v2
- [x] 新建 `backend/douban_api_v2.py`，参考 MoviePilot 的 `apiv2.py` 实现签名鉴权
- [x] 实现以下接口（同步版本，带文件缓存 7 天）：
  - `movie_showing()` — 正在热映
  - `movie_hot_gaia()` — 热门电影
  - `tv_hot()` — 热门剧集
  - `tv_animation()` — 热门动画
  - `movie_top250()` — 电影 TOP250
  - `tv_chinese_best_weekly()` — 国产剧周榜
  - `tv_global_best_weekly()` — 全球剧周榜
  - `movie_recommend(tags, sort)` — 豆瓣电影探索（按标签+排序筛选）
  - `tv_recommend(tags, sort)` — 豆瓣剧集探索
- [x] 实现 `movie_detail(subject_id)` 和 `tv_detail(subject_id)` — 影片详情（结构化数据）
- [x] 实现 `search(keyword)` — 搜索（比网页版 suggest 接口结果更全）
- [x] 保留现有 `douban_client.py` 作为 fallback，新代码优先走 API v2
- [x] 豆瓣 API v2 防封策略：请求间随机延迟 1-3 秒 + 随机 User-Agent 池
- [ ] 豆瓣 ID → TMDB ID 映射：榜单数据获取后用 TMDB 搜索静默补充 tmdb_id，结果缓存到 `scrape_cache/`

### 1.2 后端：刮削模块切换到 API v2
- [x] `routes/scrape.py` 中豆瓣搜索和详情改为优先调用 `douban_api_v2`
- [x] 失败时 fallback 到现有 `douban_client`（爬网页版）
- [x] API v2 返回的海报直链不需要 Referer 头，可以直接下载

### 1.3 后端：扩展 TMDB discover + trending
- [x] 在 `tmdb_client.py` 新增 `discover()` 方法
- [x] 在 `tmdb_client.py` 新增 `trending()` 方法（TMDB /trending/all/week）
- [x] 文件缓存 24 小时

### 1.3 后端：扩展 routes/discover.py 路由
- [x] `/discover/recommend/{source}` — 统一推荐接口（9 个源）
- [x] `/discover/explore` — 探索接口（豆瓣+TMDB）
- [x] `/discover/sources` — 数据源列表
- [x] `/discover/refresh/{source}` — 手动清除缓存
- [x] 返回统一的 JSON 结构

### 1.4 前端：发现页组件重构
- [x] 新建 `frontend/components/media/DiscoverPage.tsx` 替代 `DoubanRecommend.tsx`
- [x] 两层 sticky 头部：一级 tab（发现/探索）+ 二级 tab（8 个推荐源）
- [x] 周榜合并为一个 tab，华语+全球上下排列带排名
- [x] TOP250 和周榜显示排名角标（前 3 金色）
- [x] 响应式列数计算，每次加载精确 4 行
- [x] 内存缓存，切 tab 瞬间切换
- [x] 骨骼屏加载替代转圈 loading
- [x] 手动刷新按钮（清前端+后端缓存）
- [x] 保留"点击卡片展开详情 → 搜索资源"交互模式
- [ ] 搜索框保留（豆瓣搜索）

### 1.5 前端：丝滑无感页面切换
- [x] `page.tsx` 中媒体库内容和发现页使用同一个滚动容器
- [x] 媒体库内容在上，发现页在下，用户滚动到底部自然进入发现区域
- [x] 发现区域有自己的 sticky 标题栏，滚动到该区域时吸顶
- [x] 进入子文件夹时隐藏发现区域，回到根目录时显示
- [x] IntersectionObserver 检测发现区域进入视口时才开始加载数据（懒加载）
- [ ] 磁吸滚动：滚动到发现区域边界时自动吸附（待打磨）
- [ ] 卡片展开面板切换时下方卡片图片闪烁/重载问题（已修复：everLoadedRef 防止重复 spinner）
- [ ] 后端 `/scrape/poster` 接口添加 CORS 头消除 OpaqueResponseBlocking 报错（优化项）

---

## 阶段 2：探索筛选（豆瓣 + TMDB + Bangumi）

### 2.1 豆瓣探索筛选
- [ ] 前端筛选面板：类型标签（剧情/喜剧/动作/...）+ 地区（华语/欧美/日本/韩国）+ 排序（热度R/评分S/时间T）
- [ ] 调用 `/discover/explore?provider=douban&type=movie&tags=剧情&sort=S&page=1`
- [ ] 无限滚动分页

### 2.2 TMDB 探索筛选
- [ ] 前端筛选面板：类型（Action/Comedy/...）+ 语言 + 评分范围 + 排序
- [ ] 调用 `/discover/explore?provider=tmdb&type=movie&genres=28&sort_by=popularity.desc&page=1`

### 2.3 Bangumi 探索
- [ ] 扩展 `bangumi_client.py` 新增 `discover(type, sort, year, page)` 方法
- [ ] 前端 Bangumi tab：类型 + 排序 + 年份筛选

---

### 2.4 发现页本地媒体库感知
- [ ] 推荐/探索接口返回的 items 新增 `local_status` 字段：`none`（未拥有）/ `owned_low`（已有低画质）/ `owned_high`（已有高画质）
- [ ] 后端根据 TMDB ID 或片名匹配 `media_library.json`，结合 `quality_score` 判断画质等级
- [ ] 前端海报卡片根据 `local_status` 显示角标：✓ 已有 / ↑ 可升级

## 阶段 3：订阅系统

### 3.1 后端：订阅管理
- [ ] 新建 `backend/subscriber.py` — 订阅业务逻辑
- [ ] 数据持久化：`backend/subscriptions.json`
- [ ] 订阅数据结构：
  ```json
  {
    "id": "uuid",
    "title": "流浪地球3",
    "year": "2027",
    "type": "movie",          // movie / tv
    "tmdb_id": 12345,
    "douban_id": "36104Mo",
    "season": null,            // 剧集才有，电影为 null
    "total_episode": 0,        // 剧集总集数
    "lack_episode": 0,         // 缺失集数（未下载的）
    "downloaded_episodes": [],  // 已下载的集号列表
    "quality": "1080p",        // 质量偏好
    "resolution": "",          // 分辨率偏好
    "include": "",             // 包含关键词（如 "REMUX"）
    "exclude": "",             // 排除关键词（如 "CAM"）
    "save_path": "",           // 下载保存路径
    "state": "active",         // active / paused / completed / new_res_found
    "auto_download": false,    // false=通知模式（默认），true=自动下载
    "found_resources": [],     // 通知模式下暂存的待选资源列表
    "last_search": "",         // 上次搜索时间
    "created_at": "",
    "note": ""                 // 备注/搜索日志
  }
  ```
- [ ] 订阅状态机：`active` ↔ `paused`，下载完成 → `completed`

### 3.2 后端：订阅路由
- [ ] `POST /subscribe` — 新增订阅（传入 title/year/type/tmdb_id/douban_id/season/quality 等）
- [ ] `GET /subscribe` — 查询所有订阅列表
- [ ] `GET /subscribe/{id}` — 查询单个订阅详情
- [ ] `PUT /subscribe/{id}` — 更新订阅（暂停/恢复/修改过滤条件）
- [ ] `DELETE /subscribe/{id}` — 删除订阅
- [ ] `POST /subscribe/{id}/search` — 手动触发单个订阅搜索
- [ ] `GET /subscribe/calendar` — 订阅日历（返回订阅影片的更新时间线，剧集用 TMDB 的播出日期）

### 3.3 后端：定时搜索任务
- [ ] 后台线程定时（可配置间隔，默认 6 小时）遍历活跃订阅
- [ ] 对每个订阅执行搜索（BT + 网盘双通道），匹配到资源后根据模式处理：
  - `auto_download: true` → 自动下载
  - `auto_download: false`（默认）→ 标记状态为 `new_res_found`，存储资源链接，前端角标提醒
- [ ] 后续可扩展外部推送通知（Telegram/PushDeer/Bark 等）
- [ ] 剧集订阅：追踪缺失集数，搜到新集自动下载，更新 `downloaded_episodes` 和 `lack_episode`
- [ ] 电影订阅：搜到匹配资源即下载，下载完成后自动标记 `completed`
- [ ] 下载任务纳入现有 DownloadManager 管理
- [ ] 搜索间隔随机化（避免同时请求多个源被限频）

### 3.4 后端：订阅与媒体库联动
- [ ] 新增订阅时检查媒体库是否已有该影片（避免重复订阅已有资源）
- [ ] 剧集订阅：扫描媒体库已有集数，自动计算缺失集
- [ ] 下载完成后可选触发整理流水线（归位到媒体库对应目录）

### 3.5 前端：订阅交互
- [ ] 发现页卡片详情面板新增"订阅"按钮（搜索资源旁边）
- [ ] 点击订阅弹出配置面板：质量/分辨率偏好、包含/排除关键词、保存路径
- [ ] 已订阅的卡片显示订阅状态标记（角标或图标）
- [ ] Header 或 Sidebar 新增"我的订阅"入口
- [ ] 订阅管理面板：列表展示所有订阅，支持暂停/恢复/删除/手动搜索
- [ ] 剧集订阅显示进度条（已下载集数 / 总集数）
- [ ] 订阅日历视图（可选）：时间线展示即将更新的剧集

---

## 阶段 4：质量评分升级 + 自动洗版

### 4.1 升级质量评分系统
- [ ] 在 `quality_parser.py` 新增 `compute_quality_score(tag: QualityTag) -> int` 综合评分函数（100 分制）
- [ ] 评分维度及权重（参考值，可调）：
  - 分辨率（40 分）：2160p=40, 1080p=25, 720p=12, SD=0
  - 来源（25 分）：Remux=25, Bluray=20, WEB-DL=12, HDTV=6
  - 音频编码（20 分）：Atmos=20, TrueHD=17, DTS-HD=14, DDP5.1=10, DD5.1=8, DTS=7, AAC=3
  - 视频编码（10 分）：x265/HEVC=10, AV1=10, x264=6
  - 中文字幕（5 分）：有=5, 无=0
- [ ] 保留现有 `get_quality_level()` 不动（搜索结果排序仍用它），新函数用于洗版比较
- [ ] 新增 `compare_quality_score(current_score: int, new_score: int, threshold: int = 5) -> bool`
  - 新分数比旧分数高出 threshold 分才返回 True（避免微小差异频繁替换）

### 4.2 媒体库已有资源评分
- [ ] 扫描/同步时，对每个视频文件用 `parse_quality()` + `compute_quality_score()` 算分
- [ ] 分数存入 `media_library.json` 的视频条目中（新增 `quality_score` 字段）
- [ ] 前端详情面板展示质量分数（可选）

### 4.3 订阅自动洗版
- [ ] 订阅数据结构新增 `best_version: bool`（是否开启洗版）和 `current_score: int`（已下载最高分）
- [ ] 订阅搜索时：
  1. 搜索到资源 → `parse_quality()` 解析 → `compute_quality_score()` 打分
  2. 比较 `新分数 > current_score + threshold`？
  3. 是 → 下载 → `file_relocator` 归位替换 → 更新 `current_score`
  4. 否 → 跳过
- [ ] 电影洗版：下载完成后不自动标记 completed，继续搜索直到用户手动关闭洗版
- [ ] 剧集洗版：按集追踪，每集独立比较分数

### 4.4 手动洗版（批量升级增强）
- [ ] 现有"批量搜索升级"功能对接新评分系统
- [ ] 搜索结果按 `quality_score` 降序排列
- [ ] 自动标记哪些结果比当前版本更好（高亮显示）
- [ ] 一键选择最高分资源下载替换

---

## 技术要点
- 豆瓣 API v2 签名：HMAC-SHA1，参考 MoviePilot `apiv2.py` 的 `__sign()` 方法
- 所有外部 API 调用带 timeout=8，失败不中断
- 文件缓存统一放 `backend/scrape_cache/`，key 用 md5 哈希
- 前端新组件放 `frontend/components/media/`，不新建子目录
- 路由不加 `/api/v1/` 前缀，直接挂根路径
