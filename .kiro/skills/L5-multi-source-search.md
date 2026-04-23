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
> 本项目中 BT 搜索（13 源 SSE）和网盘搜索（6 源同步）都用此模式。

## 核心架构

```
调用方（SSE 端点 / 订阅调度器 / 单源端点）
  → search_service.search_all_sources_iter() 或 search_all_sources()
    → build_keywords() 构造多语言搜索词
    → _get_enabled_sources() 根据配置过滤启用的源
    → ThreadPoolExecutor(max_workers=14) 并行提交
    → as_completed(timeout=65) 逐个收割
      → 每个 future 内部：
        ├── search_keyword_mapper 选词 + 回退链（最多 3 轮）
        ├── 调用具体源的 search 函数
        ├── enrich_result（quality_score + match_score + junk 标记）
        └── infohash 去重
    → yield source_done 事件（含 search_keywords / hit_keyword）
    → 超时的源 → yield failed 事件
```

## 当前源清单（13 个 BT 源）

| 源 | 类型 | 默认启用 | 代理 | 备注 |
|---|---|---|---|---|
| Prowlarr | 索引器聚合 | ✅ | ❌ | 本地服务 |
| Bitsearch | JSON API | ✅ | ✅ | 欧美片源 |
| 磁力熊 | HTML 爬虫 | ✅ | ❌ | 国内中文 |
| XL720 | HTML 爬虫 | ✅ | ❌ | 国内中文，响应慢 |
| Nyaa | HTML 爬虫 | ✅ | ✅ | 日本动画 |
| 蜜柑 | HTML 爬虫 | ✅ | ✅ | 中文动画字幕组 |
| YTS | JSON API | ✅ | ✅ | 电影专用 |
| ACG.RIP | HTML 爬虫 | ❌ | ✅ | 动画字幕组，默认禁用（TLS 不通） |
| Bangumi Moe | JSON API | ✅ | ❌ | 动画字幕组 |
| 动漫花园 | RSS 端点 | ✅ | ✅ | 中文动漫，chrome124 |
| 1337x | HTML 爬虫 | ✅ | ✅ | 综合站，镜像 1337xx.to，标题过滤 |
| EZTV | RSS 端点 | ❌ | ✅ | 不支持关键词搜索 |
| LimeTorrents | HTML 爬虫 | ❌ | ✅ | TLS 不通 |

## 两种输出模式

| 模式 | 函数 | 用途 |
|------|------|------|
| 迭代器（流式） | `search_all_sources_iter()` | SSE 端点，逐源推送 |
| 同步（批量） | `search_all_sources()` | 订阅直搜通道，等全部完成 |

## 源配置格式

`config.bt_search_sources` 支持两种格式（向后兼容）：

```json
// 旧格式（布尔，只控制启用）
{"bitsearch": true, "limetorrents": false}

// 新格式（字典，独立控制启用和代理）
{"dmhy": {"enabled": true, "proxy": false}}
```

`_get_enabled_sources()` 和 `get_source_proxy()` 自动兼容两种格式。

## 关键设计决策

| 决策 | 理由 |
|------|------|
| as_completed 而非 queue | queue.get 阻塞 SSE generator，as_completed 天然流式 |
| 回退链在 future 内部同步完成 | 不阻塞其他源的并行搜索，共享该源的总超时 |
| infohash 去重只在同源内 | 跨源同一资源可能质量不同（不同 tracker），保留给用户选 |
| max_workers=14 | 12 直搜源 + Prowlarr + 1 余量 |
| 总超时 65s | Prowlarr 本身 60s 超时 + 5s 余量 |
| 源级别代理配置 | 国内源直连更快，海外源走代理 |

## 新增搜索源的接入步骤

> 完整 Checklist 见 `skills/L6-scraping-anti-bot.md`（后端 7 文件 + 前端 4 文件 + 验证 6 项）

简要步骤：
1. 写爬虫 → 2. shared.py getter → 3. search_service.py 注册 → 4. search_helpers.py 注册
5. routes/search.py 单源端点注册 → 6. search_keyword_mapper.py 语言映射
7. 前端 SourceTabs + FilterBar + SearchModal + BtResultCard 四处注册

## 踩坑经验

- `future.result(timeout=20)` 太短，Prowlarr 搜索本身 60s → 改为 65s
- SSE 竞态：用户快速切换搜索时旧 EventSource 结果混入 → 前端 activeEsRef 跟踪并关闭旧连接
- limetorrents 默认 disabled 但 `bt_overrides.get(name, True)` 默认启用 → 改用 `_BT_SOURCE_DEFAULTS`
- bt_search_sources 新格式（字典）需要在 `_get_enabled_sources` 和 `merge_bt_extra_sources` 中兼容判断
- 单源搜索端点 `/api/search/source` 的 enrich_result 必须传 match_names + 用命中词做主匹配，否则智能过滤失效
- 前端单源 Tab 切换应优先从 SSE 全量结果中过滤该源结果，避免重复请求导致慢源显示空
