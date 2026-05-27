# 发现推荐模块

## 后端数据源

### 豆瓣 (douban_api_v2.py)
- App API v2 签名鉴权，9 个榜单 + 探索 + 搜索 + 详情
- 探索接口 `movie_explore`/`tv_explore`：过滤非影视条目（无标题或无年份且无评分的合集/豆列）
- sort 参数：T=近期热度（默认） U=综合排序 S=高分优先 R=首播时间
- sort=T 数据量不稳定（豆瓣 API 行为），后端自动用 sort=U 补位
- 请求间随机延迟 1-3 秒 + 随机 UA，防封

### Bangumi (bangumi_client.py)
- 所有请求加了代理支持（从 config.json 的 http_proxy 读取）
- calendar API 的 bgm_id 和卡片标题偶尔错位，需要标题校验

### TMDB (tmdb_client.py)
- discover() 支持 count 参数，超过 20 条自动请求多页合并

### 综合推荐 (combined_recommend.py)
- 三源融合排序算法
- 60 条上限 + 排名角标
- Fallback 补位：去重后不足 60 条从 top250 + weekly 补位（`_fallback_fill`）

## 探索筛选配置（对齐 MP 前端 discover-DW2W5EZR.js）

- 豆瓣：排序(T/U/S/R) + 风格(22个) + 地区(15个常用) + 年代(年代段+动态6年) + 评分双滑块
- 豆瓣电影额外排序：TOP250（走 movie_top250 接口，显示排名角标）
- TMDB 电影：排序(6个含升降序) + 风格(19个) + 语言(13个) + 评分双滑块
- TMDB 剧集：排序(6个，日期用 first_air_date) + 风格(16个) + 语言 + 评分双滑块
- Bangumi：类别 cat(其他/TV/OVA/Movie/WEB) + 排序(rank/date) + 年份(最近10年)

## 前端组件

- `ExplorePage.tsx`：探索页主组件（筛选+无限滚动+卡片网格）
- `ExploreFilterBar.tsx`：探索筛选栏
- `RecommendTabContent.tsx`：推荐 tab 渲染组件
- 筛选切换立即清空+骨骼屏+loadIdRef 竞态防护
- 评分过滤后不足 count 条时通用候补机制（用其他排序补位）
- reqSize = colCount * 4 动态计算
- 二级 tab 电影蓝/剧集绿色彩规范

## 详情匹配逻辑

- **三源统一 ID 直拉**：豆瓣/TMDB/Bangumi 列表数据已携带各自 ID，详情页优先用 ID 直接拉取详情，跳过搜索匹配
  - 豆瓣源：`douban_id` → `douban_api_v2.get_detail()`，失败时自动尝试 movie↔tv
  - TMDB 源：`tmdb_id` → `_try_tmdb_detail_by_id()`，失败时自动尝试 movie↔tv（trending mixed 类型可能传错 type）
  - Bangumi 源：`bgm_id`（存在 douban_id 字段中）→ `bangumi_client.get_detail()`
- **ID 传递链路**：后端列表返回 `tmdb_id`/`douban_id` → 前端 `normalizeItem` 统一存入 `douban_id` 字段 → 点击卡片时作为 `id` 参数传给 `/media/info`
- **TMDB 搜索匹配**（无 ID 时的 fallback）：使用 `tmdb_client.best_match` 多维度评分（标题相似度+年份+热度，30 分阈值），不再盲取搜索结果第一条
- 豆瓣 ID 拉取失败时自动尝试 movie↔tv（探索列表的 media_type 可能不准）
- 两种都失败说明是非影视条目，直接返回 found:false，不 fallback 搜索（避免匹配错误）
- 已知案例：豆瓣探索混入合集/豆列（如 "WOWOW 連続ドラマW"），ID 404 后搜索匹配到错误影片

## 本地媒体感知 (local_media_matcher.py)

- 三层匹配 + 内存索引 + 异步 TMDB ID 补全
- 第一层：启动时从 media_library.json 构建内存索引（tmdb_id / title+year / title），save_library 回调自动刷新
- 第二层：`id_mapping_cache.json` 持久化 douban_id → tmdb_id 映射
- 第三层：后台线程异步用 TMDB API 补全未命中的豆瓣条目，每条间隔 1.5s
- height=0 时从文件名解析分辨率兜底（2160p/1080p/720p）
- 前端卡片角标：✓ 已有（emerald）/ ↑ 可升级（amber），有排名角标时下移避免重叠
- 详情面板"查看本地"按钮：点击跳转到媒体库对应目录
- `config_manager.py` 的 `_on_library_save_callbacks` 回调机制自动刷新索引
