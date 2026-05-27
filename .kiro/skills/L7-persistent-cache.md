---
name: persistent-cache
description: >
  持久化缓存模式：文件缓存 + 内存字典 + LRU 淘汰 + TTL 过期 + 线程安全。
  Use when implementing new caches, modifying cache eviction/TTL logic,
  or debugging cache miss/stale data issues.
  Do NOT use for in-memory-only caches (ScraperBase._cache is simpler, not this pattern).
---

# L7 持久化缓存

> 比 Redis 轻量，比内存字典持久。适合个人工具的缓存需求。

## 核心模式（以 tmdb_enrich_cache 为例）

```python
# 启动时加载
_cache = {}
_cache_lock = threading.Lock()

def _load_cache():
    if os.path.exists(CACHE_PATH):
        _cache.update(json.load(open(CACHE_PATH)))

def cache_put(key, value):
    with _cache_lock:
        value["updated_at"] = datetime.now().isoformat()
        _cache[key] = value
        # LRU 淘汰
        if len(_cache) > MAX_SIZE:
            oldest = sorted(_cache, key=lambda k: _cache[k].get("updated_at", ""))
            for k in oldest[:len(_cache) - MAX_SIZE]:
                del _cache[k]
        # 异步写文件
        threading.Thread(target=_save_cache, daemon=True).start()

def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        # TTL 检查
        updated = entry.get("updated_at", "")
        if _is_expired(updated, TTL_DAYS):
            return None
        return entry
```

## 设计要点

| 要点 | 说明 |
|------|------|
| 启动加载 | 模块导入时从 JSON 文件加载到内存字典 |
| 线程安全 | `threading.Lock` 保护内存字典的读写 |
| 异步写文件 | 写入操作在 daemon 线程中执行，不阻塞主线程 |
| LRU 淘汰 | 超过上限时按 `updated_at` 排序删除最旧的 |
| TTL 过期 | 读取时检查，过期返回 None（不主动清理） |
| 复合 key | `douban_{id}` > `tmdb_{id}` > `title_{title}_{year}` |

## 项目中的实例

| 缓存 | 文件 | 上限 | TTL | 用途 |
|------|------|------|-----|------|
| tmdb_enrich_cache | `scrape_cache/tmdb_enrich_cache.json` | 5000 条 | 30 天 | TMDB 英文名+评分 |
| id_mapping_cache | `id_mapping_cache.json` | 无上限 | 无过期 | douban_id → tmdb_id 映射 |
| analysis_cache | `analysis_cache.json` | 1 条 | 手动刷新 | 全库分析报告 |
| ScraperBase._cache | 内存 | 无上限 | 600s | 爬虫结果缓存（非持久化） |

## 注意事项

- `_save_cache` 只能在持有 `_cache_lock` 的上下文中调用（当前唯一调用点是 `cache_put` 内部）
- 测试中需 `time.sleep()` 等待异步写入完成
- 缓存文件路径相对于 `backend/` 目录，启动时 cwd 必须是 `backend/`
- LRU 淘汰按 `updated_at` 排序，不是按访问时间（写入时间 LRU）
