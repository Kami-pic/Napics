---
name: multi-source-search
description: >
  多源聚合搜索模式：N 个异构源并行搜索 + 超时降级 + 结果合并去重 + SSE 流式推送。
  Use when adding new search sources, modifying parallel dispatch logic, debugging SSE timeouts,
  or implementing search for new business scenarios (e.g. subscription direct-search channel).
  Do NOT use for individual scraper implementation (use L6 scraping-anti-bot).
---

# L5 多源聚合搜索

> 通用模式：N 个异构数据源并行查询，逐个返回结果，超时自动降级。
> 本项目中 BT 搜索（15+ 源 SSE）和网盘搜索（6 源同步）都用此模式。

## 核心架构

```
调用方（SSE 端点 / 订阅调度器 / 单源端点）
  → search_service.search_all_sources_iter() 或 search_all_sources()
    → build_keywords() 构造多语言搜索词
    → ThreadPoolExecutor(max_workers=11) 并行提交
    → as_completed(timeout=65) 逐个收割
      → 每个 future 内部：
        ├── search_keyword_mapper 选词 + 回退链（最多 3 轮）
        ├── 调用具体源的 search 函数
        ├── enrich_result（quality_score + match_score + junk 标记）
        └── infohash 去重
    → yield source_done 事件（含 search_keywords / hit_keyword）
    → 超时的源 → yield failed 事件
```

## 两种输出模式

| 模式 | 函数 | 用途 |
|------|------|------|
| 迭代器（流式） | `search_all_sources_iter()` | SSE 端点，逐源推送 |
| 同步（批量） | `search_all_sources()` | 订阅直搜通道，等全部完成 |

迭代器模式 yield 的事件类型：
- `source_done`：某源搜索完成，附带结果列表 + 搜索词信息
- `source_failed`：某源超时或异常
- `all_done`：全部源完成

## 关键设计决策

| 决策 | 理由 |
|------|------|
| as_completed 而非 queue | queue.get 阻塞 SSE generator，as_completed 天然流式 |
| 回退链在 future 内部同步完成 | 不阻塞其他源的并行搜索，共享该源的总超时 |
| infohash 去重只在同源内 | 跨源同一资源可能质量不同（不同 tracker），保留给用户选 |
| max_workers=11 | 9 直搜源 + Prowlarr + 1 余量 |
| 总超时 65s | Prowlarr 本身 60s 超时 + 5s 余量 |

## 新增搜索源的接入步骤

1. 写爬虫（继承 ScraperBase），实现 `search()` 返回 `List[SearchResult]`
2. `shared.py` 加 getter 函数（`_get_xxx_scraper`）
3. `search_service.py` 的 `_get_scraper_list()` 加一行
4. `search_keyword_mapper.py` 的 `SOURCE_LANG_PRIORITY` 加映射
5. `_BT_SOURCE_DEFAULTS` 加默认启用/禁用配置
6. 前端 `NO_SEEDER_INFO` 集合按需注册（无做种数信息的源）
7. 前端 FilterBar 加品牌色标签

## 踩坑经验

- `future.result(timeout=20)` 太短，Prowlarr 搜索本身 60s → 改为 65s
- SSE 竞态：用户快速切换搜索时旧 EventSource 结果混入 → 前端 activeEsRef 跟踪并关闭旧连接
- limetorrents 默认 disabled 但 `bt_overrides.get(name, True)` 默认启用 → 改用 `_BT_SOURCE_DEFAULTS`
