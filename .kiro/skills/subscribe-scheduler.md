# 订阅调度器

> 双通道调度器的工作机制。改调度逻辑、频率、源管理时必读。

## 双通道架构

```
main.py startup → _get_scheduler().start()
  → _loop() 每 5 分钟：
    ├── _tick()：RSS 通道
    │   ├── 遍历活跃订阅
    │   ├── should_search_now() 判断是否该搜（支持自定义间隔）
    │   ├── 日历触发：今天有新集播出时强制搜索
    │   ├── 逐源 fetch → match_items → handle_results
    │   └── _retry_failed_downloads() 检测失败任务换候选
    │
    └── _tick_search()：直搜通道（每 4 小时）
        ├── 只搜无 RSS 的源（磁力熊/XL720/Bitsearch）
        ├── search_service.search_all_sources()
        └── 结果转 RSSItem → match_items → handle_results
```

## 频率控制

- `search_interval_hours > 0`：使用自定义间隔（覆盖衰减）
- 默认衰减：前 72h 每 4h → 3-14 天每 12h → 14-30 天每 24h → 30 天无果暂停
- 日历触发：剧集今天有新集播出时强制搜索（不受衰减限制）

## 结果处理

- notify 模式：存入 found_resources，前端展示 🔔 角标
- auto 模式：_select_best（每集取 seeders 最高）或 _select_best_version（洗版质量比较）→ 提交下载
- last_results_summary：每次搜索后写入摘要（"搜到 3 条，最高 1080p HEVC"）

## 新增 RSS 源步骤

1. 新建 `rss_source_xxx.py`，继承 `RSSSourceBase`，实现 `fetch()`
2. `search_keyword_mapper.py` 加 SOURCE_LANG_PRIORITY + 季号集合
3. `routes/subscribe.py` 的 `_get_source_manager()` 中注册
4. 参考 `rss_source_eztv.py`

## 红线

- 调度器必须在 main.py startup 中启动
- 洗版归位失败不能标记 completed
- 下载回调中 source 字段写具体源名，不能硬编码 "prowlarr"
