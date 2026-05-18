# [TODO] metadata-service-design-todo.md

> 清债阶段第一步：设计 Core MetadataService 兼容层。
> 目标：让 scraper/discover/completeness 等模块不再直接 import TMDBClient/DoubanClient/BangumiClient。

---

## 问题分析

当前 scraper 核心（`scraper.py`/`scraper_tv.py`）深度依赖 `TMDBClient` 实例的以下方法：

| 方法 | 调用场景 | 频率 |
|---|---|---|
| `scrape_by_filename(name)` | 文件名→搜索→匹配→返回 ScrapeResult | 极高（每个文件/文件夹） |
| `search_movie(q)` / `search_tv(q)` | AI fallback 候选搜索 | 中 |
| `get_movie_detail(id)` / `get_tv_detail(id)` | 获取完整详情写 NFO | 高 |
| `get_season_detail(id, season)` | 获取季详情 | 中 |
| `get_episode_detail(id, season, ep)` | 获取集详情 | 高 |
| `best_match(name, results, year)` | 候选匹配评分 | 中 |
| `_get(path)` | 直接调 TMDB API（completeness 用） | 低 |
| `_cache_path()` / `_save_cache()` | 缓存操作（scraper_tv 用） | 低 |
| `proxy` 属性 | 海报下载代理 | 高 |

其他模块：
- `completeness.py`：用 `get_tv_detail` + `get_season_detail` + `_get`
- `discover_enrich.py`：用 `_tmdb_client()` 从 shared 获取，调 `search_movie`/`search_tv`
- `local_media_matcher.py`：用 `_tmdb_client()` 做异步 ID 补全
- `subscriber.py` / `rss_engine.py`：用 TMDB 做订阅匹配验证

## 设计方案

### 方案 A：Core MetadataService（推荐）

新增 `backend/metadata_service.py`，作为 Core 层的元数据统一入口：

```python
class MetadataService:
    """Core 元数据服务。
    内部通过 MetadataProvider registry 获取具体实现，
    对外暴露与旧 TMDBClient 兼容的方法签名。
    """
    
    def scrape_by_filename(self, name: str) -> ScrapeResult: ...
    def search_movie(self, query: str) -> list: ...
    def search_tv(self, query: str) -> list: ...
    def get_movie_detail(self, tmdb_id: int) -> ScrapeResult: ...
    def get_tv_detail(self, tmdb_id: int) -> ScrapeResult: ...
    def get_season_detail(self, tmdb_id: int, season: int) -> ScrapeResult: ...
    def get_episode_detail(self, tmdb_id: int, season: int, ep: int) -> ScrapeResult: ...
    def get_raw(self, path: str) -> dict: ...  # 替代 _get()
    
    @property
    def proxy(self) -> str: ...
```

**优点**：
- scraper 代码改动最小（只换注入的对象类型）
- 保持 `ScrapeResult` 返回类型不变
- 未来可以在 service 层做多源 fallback（TMDB 失败→豆瓣兜底）

**缺点**：
- 初期实现就是 TMDBClient 的薄包装，看起来多余
- `_get` / `_cache_path` 等内部方法暴露到 service 层不优雅

### 方案 B：直接用 MetadataProvider adapter（不推荐）

让 scraper 直接用 `MetadataProvider` 协议。

**问题**：
- `MetadataProvider` 的 `search()` 返回 `MetadataCandidate`，不是 `ScrapeResult`
- `scrape_by_filename` 是 TMDB 特有的复合操作（搜索+匹配+详情），不属于通用 provider 协议
- 需要大量改动 scraper 内部逻辑

### 方案 C：渐进式收口（推荐的执行策略）

不一次性替换所有调用点，而是分步：

1. **第一步**：新增 `MetadataService`，内部直接委托给 `TMDBClient`（薄包装）
2. **第二步**：`shared.py` 的 `_tmdb_client()` 改为返回 `MetadataService` 实例
3. **第三步**：验证所有调用点行为等价
4. **第四步**：后续可以在 `MetadataService` 内部切换为通过 registry 获取 provider

这样改动最小，风险最低，且为未来多源 fallback 留了口子。

---

## 执行计划

### Step 1：新增 MetadataService 薄包装

- [x] 新增 `backend/metadata_service.py`
- [x] `MetadataService.__init__` 接收 TMDBClient 实例
- [x] 暴露与 TMDBClient 兼容的公开方法（不暴露 `_get`/`_cache_path` 等内部方法）
- [x] 对 `completeness.py` 用到的 `_get` 提供 `get_raw(path)` 替代
- [x] 对 `scraper_tv.py` 用到的 `_cache_path`/`_save_cache` 提供 `get_cache_path`/`save_cache` 替代
- [x] 补充 `trending`/`discover` 方法（discover.py/combined_recommend.py 需要）
- [x] 验证：14 个单元测试确认方法签名兼容

### Step 2：shared.py 切换

- [x] `shared._tmdb_client()` 改为返回 `MetadataService` 实例（内部包装 TMDBClient）
- [x] `shared.get_clients()["tmdb"]` 同步改为返回 `MetadataService` 实例
- [x] 验证：57 个后端测试通过（含 metadata route snapshots）
- [x] 验证：前端构建通过

### Step 3：消除直接 import

- [x] `completeness.py` 的 `tmdb_client._get()` 改为 `tmdb_client.get_raw()`
- [x] `scraper_tv.py` 的 `tmdb_client_instance._get()` 改为 `get_raw()`
- [x] `scraper_tv.py` 的 `_cache_path()`/`_save_cache()` 改为 `get_cache_path()`/`save_cache()`
- [x] `shadow_name_manager.py` 的 `_get_english_title()` 改为 `get_english_title()`
- [x] `routes/subscribe.py` 的 `tmdb._get()` 改为 `tmdb.get_raw()`
- [x] `routes/library.py` 的 `_get_english_title()` 改为 `get_english_title()`
- [x] `rss_engine.py` 的 `tmdb._get()` 改为 `tmdb.get_raw()`
- [x] `renamer.py` 的 `_get_english_title()` 改为 `get_english_title()`
- [x] `discover_enrich.py` 的 `_get_english_title()` 改为 `get_english_title()`
- [x] `test_enrich_integration.py` mock 适配（`_get_english_title` → `get_english_title`）
- [x] `parse_filename`/`build_absolute_episode_map` 保留在 tmdb_client.py（纯函数，不构成依赖）

### Step 4：验证与收口

- [x] 59 个后端测试通过（排除 6 个已有失败的 enrich 测试，非本轮引入）
- [x] 前端构建通过

---

## 不做

- 不改 TMDBClient 内部实现
- 不改 ScrapeResult 数据结构
- 不改刮削决策逻辑
- 不改 discover/completeness 的业务逻辑
- 不新增元数据源
- 不做多源 fallback（留口子但不实现）

## 验证命令

```bash
cd backend && python -X utf8 -m pytest test_metadata_provider_adapter.py test_metadata_route_snapshots.py test_metadata_info_route_snapshots.py test_metadata_select_route_snapshots.py
cd backend && python -X utf8 -m pytest test_scraper_tv_dry_run_actions.py
cd frontend && npm run build
```
