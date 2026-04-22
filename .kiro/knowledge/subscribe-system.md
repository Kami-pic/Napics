# 订阅系统

## 核心架构：RSS + 直搜双通道

```
SubscriptionScheduler（调度器，后端启动时自动 start）
├── RSS 通道（高频，每 5 分钟检查一轮）
│   ├── RSSSourceManager 管理所有 RSS 源
│   ├── 逐订阅遍历源拉取 feed → rss_matcher 匹配 → 下载
│   └── 源：Prowlarr / 蜜柑 / Nyaa / EZTV（4 个已注册）
│
└── 直搜通道（低频，每 4 小时）
    ├── 调用 search_service.search_all_sources()
    ├── 只搜无 RSS 的源（磁力熊/XL720/Bitsearch）
    └── 和 RSS 通道独立计时，互不阻塞
```

## 数据模型

### Subscription（subscriber.py）
- 基础字段：id / title / year / type / tmdb_id / douban_id / imdb_id / poster / season / total_episode
- 订阅配置：quality / target_quality / include / exclude / save_path / search_keyword / sources / mode / best_version
- 新增字段：purpose（follow/upgrade）/ current_quality_score / local_file_path / search_interval_hours / last_results_summary / imdb_id
- aliases：`{"cn": [], "en": [], "original": []}` — 创建时从发现页清洗名 + alias_resolver 填充
- downloaded_episodes：`Dict[str, EpisodeInfo]` — 每集下载指纹（quality_tag/source/channel/task_id/timestamp）
- 状态机：active ↔ paused → completed

### 订阅创建数据流
```
发现页详情 → 点"订阅" → SubscribeConfigModal（选类型/质量/源）
  → handleSubscribeConfirm 构造数据：
    - type 从 item.media_type 取（卡片级别，不是 tab 级别）
    - season 从标题自动提取（"第二季"→2, "S02"→2）
    - 清洗名从 detail.clean_name_cn/en/original 获取
    - tmdb_id / imdb_id / douban_id 从 detail 获取
  → POST /subscribe → subscriber.add()：
    - aliases 优先用前端清洗名，alias_resolver 补充
    - tmdb_id 中文搜不到时用英文名重试
    - 同作品不同 purpose 允许共存（追更+洗版）
```

## RSS 源

| 源 | 文件 | 特点 |
|---|---|---|
| Prowlarr | rss_source_prowlarr.py | 搜索 API（非真正 RSS），英文名优先 |
| 蜜柑 | rss_source_mikan.py | RSS 搜索，中文/日文优先，curl_cffi |
| Nyaa | rss_source_nyaa.py | RSS 搜索，日文/英文优先，需代理 |
| EZTV | rss_source_eztv.py | RSS 按 IMDB ID 精准订阅，追美剧首选，需代理 |

- 新增源只需：继承 RSSSourceBase → 实现 fetch() → routes/subscribe.py 注册
- search_keyword_mapper.py 的 SOURCE_LANG_PRIORITY 需同步更新

## 搜索服务（search_service.py）

从 routes/search.py 抽离的核心搜索逻辑：
- `build_keywords()` — 构造多语言搜索词
- `search_prowlarr()` / `search_direct()` — 独立搜索函数
- `search_all_sources_iter()` — SSE 迭代器版本
- `search_all_sources()` — 同步版本（订阅调度器用）
- `BT_SOURCE_DEFAULTS` / `PAN_SOURCE_DEFAULTS` — 源配置数据

## RSS 匹配器（rss_matcher.py）

过滤链：标题匹配（L1+L2）→ 质量 → 关键词 → 集数匹配 + Quality Cutoff + 指纹去重
- 标题匹配：用 match_chain 做跨语言匹配，score < 20 过滤
- Quality Cutoff：已下载集质量达到 target_quality 时不再匹配
- 整季包识别：有 S01 但无 E01 → 可能是整季包

## 调度器增强

- `should_search_now()`：支持自定义 search_interval_hours，覆盖默认衰减策略
- `_build_results_summary()`：生成前端展示用的搜索摘要
- `_retry_failed_downloads()`：检测失败任务，从 found_resources 换候选重试
- `_tick_search()`：直搜通道独立循环
- `rss_item_to_search_result()`：RSSItem → SearchResult 格式桥接
- 调度器在 main.py startup 事件中自动启动

## 洗版机制

- purpose="upgrade" 的订阅走洗版逻辑
- `_select_best_version()` 按集比较质量分数
- 下载完成 → `_auto_relocate()` 调用 file_relocator 归位替换
- 归位失败不标记 completed，保留订阅继续搜索
- local_file_path 校验 + media_matcher 自动重新定位
- 电影洗版下载完成自动标记 completed

## 日历

- `GET /subscribe/calendar`：TMDB 优先，Bangumi episodes API fallback
- 过滤已完结（state=completed）和洗版订阅（purpose=upgrade）
- 前端 SubscribeCalendar 按日期分组时间线展示

## 前端

### 组件
- SubscribeConfigModal：订阅类型选择（追更/洗版）+ 目标质量 + 源分组 + 高级设置折叠
- SubscribeSourceSelect：RSS/直搜分组展示 + 内容类型推荐（★标记）
- SubscribeInline：两级展示（折叠态+展开态集详情）+ purpose 标签 + 搜索摘要
- SubscribeCalendar：时间线日历 + Bangumi fallback + 空状态提示

### 类型
- SubscriptionItem（useSubscriptions.ts）：含所有新增字段 + EpisodeInfo 接口
- SubscribeConfig：purpose / target_quality / sources 等

### 保存路径
- `GET /subscribe/save-paths` 返回 config.category_tags 的反向映射
- 前端根据 mediaType 自动填入对应分类路径
