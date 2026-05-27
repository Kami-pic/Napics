---
name: discover-enrich-cache
description: >
  发现页 TMDB 英文名补全与持久化缓存（C+E 方案）。
  Use when modifying discover page data flow, enrich_cache read/write,
  TMDB enrichment logic, or debugging missing English names on discover page.
  Depends on multilang-name-enrichment for English name acquisition strategies,
  clean-name-system for structured name storage.
  Do NOT use for media library scraping (use clean-name-system directly).
---

# 发现页 TMDB 英文名补全与持久化缓存

> 发现页推荐数据（豆瓣为主）缺少英文名，直接影响 Prowlarr/Bitsearch 等英文 BT 站搜索效果。
> C+E 方案：持久化缓存 + 同步并发补全 + 2 秒超时降级，首次加载即有英文名。

## 一、核心架构

```
用户打开发现页
  → 后端查文件缓存（hot_*.json / combined_*.json）
  → _inject_clean_names()：
      1. 查 tmdb_enrich_cache → 命中 → 直接用英文名
      2. 未命中 → 收集到 need_enrich 列表
      3. _sync_enrich_english_names(need_enrich, timeout=2.0)
         → ThreadPoolExecutor(max_workers=5) 并发请求 TMDB
         → as_completed(timeout=2.0) 硬性超时
         → 2 秒内返回的 → 写入缓存 + 注入当前响应
         → 超时的 → 转交 _async_enrich_tmdb_ids 后台继续
  → _inject_local_status()：注入本地媒体状态
  → 返回给前端

详情页展开：
  → get_media_info() → 返回前 _writeback_enrich_cache() → 回写缓存
```

## 二、tmdb_enrich_cache 设计

### 数据结构
```json
{
  "douban_12345": {
    "tmdb_id": 550,
    "en_title": "Fight Club",
    "original_title": "Fight Club",   // TMDB 原始语言标题（备用，当前读取时未使用）
    "tmdb_rating": 8.4,
    "updated_at": "2026-04-21T10:30:00"
  }
}
```

### 缓存策略
| 属性 | 值 |
|------|-----|
| 文件位置 | `scrape_cache/tmdb_enrich_cache.json` |
| 过期时间 | 30 天（`_ENRICH_CACHE_TTL`） |
| 大小上限 | 5000 条（`_ENRICH_CACHE_MAX`，LRU 淘汰最旧的） |
| 并发安全 | `threading.Lock` 保护内存字典，写文件异步线程 |
| 启动加载 | `_load_enrich_cache()` 在模块导入时执行 |

### 缓存 key 规则
- 有 douban_id → `douban_{douban_id}`（优先）
- 有 tmdb_id → `tmdb_{tmdb_id}`
- 都没有 → `title_{title}_{year}`（兜底）

### 写入时机（三个入口）
1. `_sync_enrich_english_names`：同步并发补全成功后
2. `_async_enrich_tmdb_ids`：后台线程补全成功后
3. `_writeback_enrich_cache`（media_info.py）：详情页请求返回前

### 读取时机
- `_inject_clean_names` 中，对每个条目查缓存，命中且未过期则直接用 en_title

## 三、超时降级机制

```
_inject_clean_names 中的同步并发补全：
  → ThreadPoolExecutor(max_workers=5) 并发请求 TMDB
  → as_completed(timeout=2.0)：最多等 2 秒
  → 2 秒内返回的 → 写入缓存 + 注入到当前响应
  → 2 秒内未返回的 → 跳过，用 cn/original 回退
  → 超时的条目 → 转交 _async_enrich_tmdb_ids 后台继续补全
```

效果：
- 网络好 → 首次加载即完美（1-2 秒内全部补全）
- 网络差 → 自动降级为渐进式（后台补全，下次请求命中缓存）
- 永远不会出现前端转圈等待超过 2 秒

## 四、前端数据流

```
后端返回 items（含 clean_name_cn/en/original）
  → normalizeItem()（discoverUtils.ts）传递三个字段
  → DoubanHotItem 类型包含 clean_name_cn/en/original
  → SearchModal enName 回退链：
      searchModalDetail?.original_title
      → searchModalItem.clean_name_en    ← 新增
      → (searchModalItem as any)._tmdb_original_title
      → searchModalItem.subtitle
      → ""
```

## 五、关键函数

| 函数 | 文件 | 职责 |
|------|------|------|
| `_load_enrich_cache` | discover.py | 启动时从 JSON 文件加载到内存 |
| `_save_enrich_cache` | discover.py | 异步线程写入 JSON 文件（必须在 `_enrich_cache_lock` 内调用） |
| `_enrich_cache_key` | discover.py | 生成复合缓存 key |
| `enrich_cache_put` | discover.py | 线程安全写入一条记录 + LRU 淘汰 |
| `_inject_clean_names` | discover.py | 查缓存 → 同步补全 → 注入字段 |
| `_sync_enrich_english_names` | discover.py | 同步并发请求 TMDB，2 秒超时 |
| `_async_enrich_tmdb_ids` | discover.py | 后台线程补全 tmdb_id + 英文名 + 写入 enrich_cache + 更新 `media_matcher._id_cache`，每次请求间隔 0.5 秒 |
| `_writeback_enrich_cache` | media_info.py | `get_media_info` 内部闭包，详情页返回前回写缓存（优先取 `english_title`，手动构造 cache_key） |
| `normalizeItem` | discoverUtils.ts | 传递 clean_name_cn/en/original |

## 六、修改注意事项

- `enrich_cache_put` 是公开函数（media_info.py 跨模块调用），改签名需同步
- `_enrich_cache` 是模块级全局变量，测试时需保存/恢复原始状态
- `_ENRICH_CACHE_PATH` 相对于 backend/ 目录，启动时 cwd 必须是 backend/
- 缓存过期检查在 `_inject_clean_names` 中做，`enrich_cache_put` 不检查
- LRU 淘汰按 `updated_at` 排序删除最旧的，不是按访问时间
- `_save_enrich_cache` 是异步写入，测试中需 `time.sleep()` 等待完成；且只能在持有 `_enrich_cache_lock` 的上下文中调用（当前唯一调用点是 `enrich_cache_put` 内部）
- `_writeback_enrich_cache` 是 `get_media_info` 的内部闭包，依赖外层变量 `title`/`year`/`id`/`source`，不能独立调用或测试
- ⚠️ `_writeback_enrich_cache` 手动构造 cache_key（`f"douban_{id}"` 等）而非调用 `_enrich_cache_key()`，两处 key 生成逻辑重复。修改 key 规则时必须同步两处（或重构为统一调用 `_enrich_cache_key`）
- `_async_enrich_tmdb_ids` 除了写 enrich_cache，还会更新 `media_matcher._id_cache`（douban_id → tmdb_id 映射）并调用 `_save_id_cache()` 持久化
- 缓存数据结构中 `original_title` 字段存的是 TMDB 原始语言标题（备用），当前 `_inject_clean_names` 读取缓存时只用 `en_title`，未使用 `original_title`
- 缓存策略的关键数值（TTL/MAX）同步记录在 `project-memory.md` 的搜索词构造小节，修改时需两处同步
