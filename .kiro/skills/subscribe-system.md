# 订阅系统技能

> 订阅系统的核心概念、数据流、扩展点。改订阅相关代码前必读。

## 核心概念

### 双通道架构
- **RSS 通道**（高频）：每 5 分钟检查，RSS 源拉取 feed → 本地匹配 → 下载。请求轻量，不触发限频
- **直搜通道**（低频）：每 4 小时搜索，调用 search_service 搜索无 RSS 的源。覆盖历史资源
- 两个通道独立计时，互不阻塞

### 两种订阅模式
- **追更**（purpose=follow）：订阅剧集，自动搜索新集并下载
- **洗版**（purpose=upgrade）：本地已有低质量版本，等更高质量版本自动替换

### Quality Cutoff
- `target_quality` 字段：达到目标质量后该集不再搜索更好版本
- 在 rss_matcher._filter_episodes 中实现：已下载集质量 >= target_quality 的 rank 时跳过

## 关键数据流

### 订阅创建
```
前端 DiscoverPage.handleSubscribeConfirm
  → 从 item/detail 提取：type(卡片级别) / season(标题解析) / 清洗名(cn/en/original) / 各平台ID
  → POST /subscribe
  → subscriber.add()：aliases 构造(清洗名优先+alias_resolver补充) / tmdb_id 补全(中文→英文回退)
```

### 调度搜索
```
main.py startup → _get_scheduler().start()
  → _loop() 每 5 分钟：
    → _tick()：RSS 通道，逐订阅遍历源 fetch → match_items → handle_results
    → _tick_search()：直搜通道（每 4 小时），search_all_sources → 转 RSSItem → match_items
```

### 匹配过滤链
```
rss_matcher.match_items(items, subscription):
  1. _filter_title_match — L1+L2 跨语言标题匹配（score<20 过滤）
  2. _filter_quality — 最低质量要求
  3. _filter_keywords — 包含/排除关键词
  4. _filter_episodes — 集数匹配 + Quality Cutoff + 指纹去重
```

## 扩展点

### 新增 RSS 源
1. 新建 `rss_source_xxx.py`，继承 `RSSSourceBase`，实现 `fetch(subscription) -> List[RSSItem]`
2. `search_keyword_mapper.py` 的 `SOURCE_LANG_PRIORITY` 加映射
3. `routes/subscribe.py` 的 `_get_source_manager()` 中注册
4. 参考 `rss_source_eztv.py`（最完整的实现）

### 新增直搜源
- 和 RSS 源无关，走 search_service 的 scraper 列表
- 步骤见 project-memory 的"新增 BT 直搜源步骤"

## 红线

- 调度器必须在 main.py startup 中启动，不能只靠懒加载
- 订阅创建时 type 必须从卡片 media_type 取，不能用 tab 级别的 activeTabConfig
- aliases 必须用 `{"cn": [], "en": [], "original": []}`，不能用 `jp`（已迁移）
- tmdb_id 补全必须先中文搜再英文搜，不能只搜中文
- 洗版归位失败时不能标记 completed，必须保留订阅继续搜索
- SubscriptionManager 必须用 shared.py 的全局单例，不能 new 新实例
