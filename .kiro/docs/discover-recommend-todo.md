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
- [x] 搜索框保留（豆瓣搜索）

### 1.5 前端：丝滑无感页面切换
- [x] `page.tsx` 中媒体库内容和发现页使用同一个滚动容器
- [x] 媒体库内容在上，发现页在下，用户滚动到底部自然进入发现区域
- [x] 发现区域有自己的 sticky 标题栏，滚动到该区域时吸顶
- [x] 进入子文件夹时隐藏发现区域，回到根目录时显示
- [x] IntersectionObserver 检测发现区域进入视口时才开始加载数据（懒加载）
- [x] 磁吸滚动 + 阻尼吸附：`hooks/useScrollDamping.ts`（下滑距墙<460px吸附到发现页，上滑距墙>260px吸附回顶部）
- [x] 卡片展开面板切换时下方卡片图片闪烁/重载问题（已修复：everLoadedRef 防止重复 spinner）
- [x] 后端 `/scrape/poster` 接口 Cache-Control 优化（public, max-age=3600）
- [x] 后端 `/proxy/image` 接口 Cache-Control 优化（public, max-age=86400）

### 1.6 前端：发现页增强（2026-04-11 新增）
- [x] DiscoverPage.tsx 拆分为 7 个独立文件（313 行主组件 + 6 个子组件）
- [x] 卡片信息增强：类型标签 + 年份·国家·集数 + episodes_info（如"22集全"）
- [x] 评分品牌色：豆瓣黄/TMDB蓝/Bangumi粉，未评分显示"—"
- [x] 混编 tab（TMDB趋势/搜索）显示电影/剧集类型标签
- [x] 裂图处理：img onError fallback 显示 🎬 + 片名 + "图片加载失败"
- [x] Tab 切换 display:none 保持 DOM，图片不重新加载
- [x] 请求竞态防护：loadIdRef + cacheKey 防止旧请求污染新 tab
- [x] 详情多源算法：豆瓣 tab→豆瓣优先，TMDB tab→TMDB优先，Bangumi tab→Bangumi优先
- [x] 详情面板同时显示豆瓣+TMDB 评分（品牌色星星 icon）
- [x] 豆瓣详情封面走代理（防盗链）
- [x] 周榜展开面板（CSS order 定位到点击行下方）
- [x] Tab 文案更新：热门动画/电影总榜/剧集周榜/Bangumi趋势
- [x] 推荐接口 fallback：API v2 失败回退旧版网页接口

### 1.7 刮削候选面板增强（2026-04-11 新增）
- [x] 豆瓣候选：评分 + 类型标签 + 国家 + 导演 + 简介 + 原始名
- [x] TMDB 候选：评分（vote_average）+ 类型标签放前面
- [x] Bangumi 候选：评分（responseGroup=large）+ 类型颜色（动画紫/书籍粉/游戏橙）
- [x] 三源裂图 fallback（onError 显示 🎬 占位）
- [x] 豆瓣搜索过滤非影视条目（音乐/书籍）
- [x] 统一 UI 颜色规范：`lib/mediaColors.ts`

### 1.8 媒体库颜色统一（2026-04-11 新增）
- [x] 电影蓝色、剧集绿色（CardGrid 标签）
- [x] 一级目录标签带透明度蓝/绿
- [x] 系列电影蓝色、剧集绿色

### 1.9 DetailDrawer 拆分（2026-04-11）
- [x] 1339 行→62 行瘦壳 + 11 个独立文件
- [x] 全部零 TS 错误 + 构建通过
- [x] 端到端测试 14 项操作全部通过

### 1.10 发现页详情面板增强（2026-04-12 新增）
- [x] 数据源下拉（豆瓣/TMDB/Bangumi）+ 🔄 刷新按钮（清缓存+用选中源重新请求）
- [x] 三源评分：豆瓣5个tab+TMDB趋势显示双评分，热门动画+Bangumi趋势显示三源评分
- [x] 外部链接补全：豆瓣/TMDB/IMDB/Bangumi，有数据就显示
- [x] 数据来源标签：底部小字 `数据来自 豆瓣/TMDB/Bangumi`
- [x] TMDB 匹配率提升：用豆瓣 original_title 增强 TMDB 搜索
- [x] ID 拉取标题校验：Bangumi/豆瓣 ID 返回标题和请求标题不匹配时自动改走搜索
- [x] 详情加载速度优化：_enrich_ratings 改为并行（豆瓣先跑拿 original_title，TMDB+Bangumi 线程池并行）
- [x] 链接按钮始终可用：有精确 ID 用详情页链接（正常亮度），无 ID 用搜索页链接（变灰区分）
- [x] 卡片封面 genres 标签上限从 2 个改为 3 个
- [ ] 详情匹配错误时的候选选择（类似刮削候选面板，显示多个候选让用户手动选）
- [ ] 匹配算法优化：当前中文搜 TMDB 覆盖率有限，部分冷门片搜不到；Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位z

---

## 阶段 2：探索筛选 + 综合推荐（豆瓣 + TMDB + Bangumi）

> 参考 MoviePilot v2 的探索页设计 + Gemini 综合排序算法建议。
> 一级 tab 切换"推荐/探索"，推荐新增"综合推荐"tab，探索内二级 tab 5 个源。

### 2.0 推荐 tab 调整
- [x] 一级 tab 文案："发现" → "推荐"
- [x] 推荐 tab 调整为 8 个：
  1. **综合推荐**（新增）— 三源融合排序，混合电影+剧集+动画
  2. 热门电影（豆瓣 movie_hot_gaia）
  3. 热门剧集（豆瓣 tv_hot）
  4. 热门动画（豆瓣 tv_animation）
  5. 正在热映（豆瓣 movie_showing）
  6. 剧集周榜（豆瓣 weekly 合并）
  7. TMDB放送（TMDB trending/week，混合电影+剧集）
  8. Bangumi放送（Bangumi calendar，当季动画按评分排序）
- [x] 电影总榜(TOP250) 移到探索-豆瓣电影的排序选项中（预设标签"TOP250"）

### 2.0.1 综合推荐算法（后端 `/discover/recommend/combined`）

**数据获取（并发，timeout=5s）：**
- [x] 豆瓣：movie_hot(10条) + tv_hot(10条)
- [x] TMDB：trending/week(20条)
- [x] Bangumi：calendar 热门(10条)

**多维去重（优先级从高到低）：**
- [x] 1. tmdb_id / douban_id 关联映射（如果有）
- [x] 2. original_title 精确匹配
- [x] 3. 中文标题 + 年份匹配（年份允许 ±1 误差）

**评分归一化（10 分制基准）：**
- [x] 豆瓣：base = 原始评分 × 1.0
- [x] TMDB：base = (原始评分 + 0.5) × 0.9（补偿 TMDB 评分偏低）
- [x] Bangumi：base = 原始评分 + 0.2（补偿动漫评分严苛）

**加权计算 final_score：**
- [x] 豆瓣来源加成：source == "douban" → +0.5
- [x] 动漫爱好者加成：genres 含"动画/Animation/Anime" → +0.8
- [x] 当季新番加成：源自 Bangumi 且首播当年 → +0.8
- [x] 多源共振：2 源命中 → +1.0，3 源命中 → +2.0
- [ ] 冷门降权：单源且评价人数极少 → score × 0.8

**产出逻辑（40 条）：**
- [x] 动漫保底：至少 12 条(30%) 动画类资源，不足从 Bangumi 桶补位
- [x] 影剧交叉：每 3 条中至少 1 条电影 + 1 条剧集/番剧
- [x] Fallback：去重后不足 40 条，从 top250 或 weekly 补位
- [x] 容错：单源超时/失败不影响其他源，自动降级为双源/单源模式

**返回字段：**
- [x] `reason`: "全网热门" / "高分番剧" / "豆瓣热榜" / "当季新番" 等
- [x] `is_new_anime`: true/false（180 天内新番，前端高亮）
- [ ] `local_status`: 暂不实现，留到 2.7

### 2.1 豆瓣电影探索
- [x] 后端路由 `/discover/explore?provider=douban&type=movie&sort=T&tags=&page=1`
- [x] 调用 `douban_api_v2.movie_explore(sort, tags, start, count)`
- [x] 筛选项对照 MP 前端完整修正：排序(T/U/S/R/TOP250) + 风格(22个) + 地区(15个常用) + 年代(年代段+动态6年) + 评分双滑块
- [x] 豆瓣默认排序 T（近期热度），TOP250 作为豆瓣电影专属排序标签
- [x] 无限滚动分页
- [x] 过滤非影视条目（合集/豆列：无年份且无评分）
- [x] sort=T 数据不足时自动用 sort=U 补位
- [x] 评分过滤后不足 count 条时通用候补机制

### 2.2 豆瓣剧集探索
- [x] 后端路由 `/discover/explore?provider=douban&type=tv&sort=T&tags=&page=1`
- [x] 同 2.1，筛选项已修正（无 TOP250）

### 2.3 TMDB 电影探索
- [x] 后端路由 `/discover/explore?provider=tmdb&type=movie&sort_by=popularity.desc&...`
- [x] 排序 6 个：热度降序/升序 + 上映日期降序/升序 + 评分降序/升序
- [x] 电影用 release_date，剧集用 first_air_date
- [x] 筛选：风格(19个) + 语言(13个) + 评分双滑块
- [x] count 参数生效：超过 20 条自动请求多页合并

### 2.4 TMDB 剧集探索
- [x] 同 2.3，`type=tv`
- [x] 排序和风格已修正（剧集风格 16 个）

### 2.5 Bangumi 探索
- [x] `bangumi_client.py` discover() 方法 + 代理支持（从 config.json 读取 http_proxy）
- [x] 类别筛选 cat 参数：其他(0)/TV(1)/OVA(2)/Movie(3)/WEB(5)，type 固定为 2
- [x] 排序(rank/date) + 年份(最近10年)

### 2.6 前端探索页
- [x] 一级 tab 切换：推荐 / 探索
- [x] 探索内二级 tab：豆瓣电影 / 豆瓣剧集 / TMDB电影 / TMDB剧集 / Bangumi
- [x] 二级 tab 电影蓝/剧集绿色彩规范
- [x] 筛选栏对照 MP 前端源码完整修正
- [x] 评分双滑块（豆瓣+TMDB）
- [x] 无限滚动分页，复用 DiscoverCard 卡片组件
- [x] 点击卡片展开详情（复用 ExpandDetail）
- [x] 探索二级 tab sticky 吸附
- [x] 展示逻辑和推荐一致（colCount * 4 行，响应式列数，reqSize 动态计算）
- [x] 筛选切换时立即清空+骨骼屏，loadIdRef 竞态防护
- [x] 缓存命中时确保 loading 状态重置（防宕机）
- [x] TOP250 排名角标（前 3 金色）
- [x] 详情匹配修复：豆瓣 ID 拉取失败时自动尝试 movie↔tv，彻底失败不 fallback 搜索（避免匹配错误）
- [x] 滚动自动加载：前 4 批 IntersectionObserver 自动触发（400ms 延时+骨骼行），之后手动点击
- [x] 数据截断到 colCount 整数倍，避免最后一行不满
- [x] 综合推荐 60 条上限 + 排名角标 + "今天就推荐这么多吧"
- [x] 磁吸滚动 + 阻尼吸附（`useScrollDamping` hook）

### 2.7 本地媒体库感知（已完成）
- [x] 推荐/探索接口返回的 items 新增 `local_status` 字段：`none`（未拥有）/ `owned_low`（已有低画质）/ `owned_high`（已有高画质）
- [x] 后端 `local_media_matcher.py`：三层匹配（TMDB ID 精确 + 片名+年份 + 中文子串/模糊）+ 内存索引 + 异步 TMDB ID 补全
- [x] 内存索引启动时构建，save_library 后自动刷新
- [x] ID 映射缓存持久化到 `id_mapping_cache.json`（douban_id → tmdb_id）
- [x] 异步补全：未匹配的豆瓣条目后台用 TMDB API 搜索补全，下次请求精确匹配
- [x] 前端海报卡片根据 `local_status` 显示角标：✓ 已有（绿色）/ ↑ 可升级（琥珀色）

## 阶段 3：订阅系统

> 已独立为 `subscribe-todo.md`，详见该文档。
> 包含三个子阶段：A（CRUD+前端入口）→ B（定时搜索+自动下载）→ C（日历+媒体库联动+洗版）。

---

## 阶段 4：质量评分升级 + 自动洗版

> 核心已完成（100分制评分+save_library注入+洗版匹配），详见 `subscribe-todo.md`。
> 剩余：4.4 手动洗版增强（搜索结果按 quality_score 排序标记）。

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
