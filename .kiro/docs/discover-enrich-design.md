# [当前] 发现页 TMDB 数据补全方案设计

> 问题：发现页推荐数据（豆瓣为主）缺少英文名和 TMDB 评分，直接影响搜索效果。
> 目标：在不显著增加等待时间的前提下，让发现页数据尽可能有英文名和 TMDB 评分。

---

## 一、现状分析

### 当前数据流

```
用户打开发现页
  → 后端查文件缓存（hot_*.json / combined_*.json）
    → 命中（7天/1小时内）：直接返回缓存数据
    → 未命中：拉取豆瓣/TMDB/Bangumi 数据
      → _inject_clean_names()：注入 cn/en/original（从 original_title + subtitle 提取）
      → _inject_local_status()：注入本地媒体状态
      → 返回给前端
      → _async_enrich_tmdb_ids()：后台线程补全 tmdb_id + 英文名（结果写在内存，不持久化）
```

### 问题

| 问题 | 原因 | 影响 |
|------|------|------|
| 英文名缺失 | 豆瓣 API v2 无 subtitle，original_title 可能是日/韩/中文 | Prowlarr/Bitsearch 搜不到 |
| TMDB 评分缺失 | 豆瓣数据没有 TMDB 评分，需要额外请求 | 用户看不到国际评分 |
| 异步补全结果丢失 | `_async_enrich_tmdb_ids` 写在内存中的 items 列表，请求结束后丢失 | 每次请求都要重新补全 |
| 缓存中无补全数据 | 文件缓存在 `_async_enrich_tmdb_ids` 之前写入 | 缓存命中时也没有英文名 |

### 当前缓存机制

| 缓存 | 位置 | 有效期 | 内容 |
|------|------|--------|------|
| 热榜文件缓存 | `scrape_cache/hot_*.json` | 7 天 | 豆瓣原始数据 + clean_names（无 TMDB 补全） |
| 综合推荐缓存 | `scrape_cache/combined_*.json` | 1 小时 | 三源合并数据（无 TMDB 补全） |
| TMDB ID 映射缓存 | `local_media_matcher._id_cache` | 内存（重启丢失） | douban_id → tmdb_id |
| 详情页缓存 | 前端 `getCachedDetail` | 会话内 | 完整详情（有英文名+评分） |

---

## 二、方案对比

### 方案 A：定时预补全

**思路**：后台定时任务（如每天一次），对所有缓存的推荐数据批量调用 TMDB 补全英文名+评分，结果写回缓存文件。

**流程**：
```
定时任务（每天凌晨）
  → 读取所有 hot_*.json / combined_*.json
  → 对每个条目：有 douban_id 但无 en_title → TMDB 搜索 → 获取英文名+评分
  → 写回缓存文件
  → 下次用户请求时，缓存已有完整数据
```

| 优点 | 缺点 |
|------|------|
| 用户零等待（数据已预备好） | 需要新增定时任务机制 |
| 一次补全，所有用户受益 | TMDB API 调用量大（每天 50-100 条） |
| 缓存文件自包含，重启不丢 | 新数据要等到下次定时任务才有 |

### 方案 B：详情页按需补全

**思路**：卡片列表不补全，用户点击展开详情页时才请求 TMDB 获取英文名+评分。详情页已有请求机制（`handleCardClick` → `api.fetchMediaDetail`），只需确保返回数据包含英文名。

**流程**：
```
用户点击卡片
  → 前端请求详情页 API（已有机制）
  → 后端从 TMDB 获取完整详情（含 english_title + vote_average）
  → 返回给前端，前端缓存
  → 用户点"搜索升级"时，从详情缓存中取英文名
```

| 优点 | 缺点 |
|------|------|
| 零额外 API 调用（复用已有详情请求） | 用户必须先点击卡片才有英文名 |
| 实现最简单（可能只需调整数据传递） | 卡片列表上看不到 TMDB 评分 |
| 按需加载，不浪费资源 | 直接点"搜索"而不展开详情时，仍然缺英文名 |

### 方案 C：持久化缓存 + 两阶段返回

**思路**：新建独立的 TMDB 补全缓存（`tmdb_enrich_cache.json`），`_async_enrich_tmdb_ids` 补全后写入此缓存。`_inject_clean_names` 先查此缓存，命中则直接用。

**流程**：
```
第一次请求：
  → 查 tmdb_enrich_cache → 未命中 → 返回无英文名的数据
  → 后台 _async_enrich_tmdb_ids → 补全 → 写入 tmdb_enrich_cache

第二次请求（刷新/翻页/下次访问）：
  → 查 tmdb_enrich_cache → 命中 → 返回有英文名+评分的数据
```

| 优点 | 缺点 |
|------|------|
| 渐进式改善（越用越好） | 第一次仍然缺英文名 |
| 不增加同步等待时间 | 需要新建缓存文件和读写逻辑 |
| 缓存持久化，重启不丢 | 缓存过期策略需要设计 |

### 方案 D：混合方案（推荐）

**思路**：结合 B + C 的优点。

1. **卡片列表**：用方案 C（持久化缓存），渐进式补全
2. **详情页展开**：用方案 B（按需请求），确保展开后一定有英文名
3. **搜索时**：优先用详情页缓存的英文名，其次用持久化缓存的，最后回退

**流程**：
```
卡片列表加载：
  → _inject_clean_names 查 tmdb_enrich_cache → 命中的有英文名+评分
  → 后台 _async_enrich_tmdb_ids 补全未命中的 → 写入 tmdb_enrich_cache

用户点击卡片展开：
  → 请求详情 API → 返回完整数据（含英文名+评分）
  → 前端缓存详情

用户点"搜索升级"：
  → 优先用详情缓存的 original_title（已有机制）
  → 其次用卡片的 clean_name_en（来自 tmdb_enrich_cache）
  → 最后回退到 cn
```

| 优点 | 缺点 |
|------|------|
| 展开详情后一定有英文名 | 实现复杂度中等 |
| 卡片列表渐进式改善 | 第一次加载卡片仍可能缺英文名 |
| 不增加同步等待 | 需要新建缓存 |
| 搜索时有多层回退保障 | — |

---

## 三、各方案适用场景

| 场景 | 方案 A | 方案 B | 方案 C | 方案 D |
|------|--------|--------|--------|--------|
| 发现页卡片列表 | ✅ 最优 | ❌ 不适用 | ✅ 渐进式 | ✅ 渐进式 |
| 发现页详情展开 | ✅ 已有 | ✅ 最优 | ⬜ 不涉及 | ✅ 最优 |
| 发现页搜索升级 | ✅ 已有 | ✅ 展开后有 | ✅ 渐进式 | ✅ 多层回退 |
| 媒体库搜索升级 | ⬜ 不涉及 | ⬜ 不涉及 | ⬜ 不涉及 | ⬜ 不涉及 |
| TMDB API 调用量 | 高（批量） | 低（按需） | 中（渐进） | 中（渐进+按需） |
| 实现复杂度 | 高（定时任务） | 低 | 中 | 中 |

---

## 四、媒体库 vs 发现页对比

| 维度 | 媒体库 | 发现页 |
|------|--------|--------|
| 数据来源 | 本地文件 + 刮削 | 豆瓣/TMDB/Bangumi API |
| 英文名获取时机 | 刮削时（TMDB `_get_english_title`） | 需要额外请求 |
| 数据持久化 | media_library.json（永久） | 文件缓存（7天/1小时） |
| 数据量 | 固定（用户的媒体库） | 动态（热榜每周变） |
| 用户期望 | 刮削后应该有完整数据 | 可以接受渐进式加载 |

**结论**：媒体库的模式（刮削时一次性获取完整数据）不适合发现页（数据量大、变化快、不值得全量预请求）。发现页更适合渐进式 + 按需的混合方案。

---

## 五、tmdb_enrich_cache 设计（方案 C/D 的核心）

### 数据结构

```json
{
  "douban_12345": {
    "tmdb_id": 550,
    "en_title": "Fight Club",
    "original_title": "Fight Club",
    "tmdb_rating": 8.4,
    "updated_at": "2026-04-21T10:30:00"
  },
  "douban_67890": {
    "tmdb_id": 128,
    "en_title": "Princess Mononoke",
    "original_title": "もののけ姫",
    "tmdb_rating": 8.3,
    "updated_at": "2026-04-21T10:31:00"
  }
}
```

### 缓存策略
- 文件位置：`scrape_cache/tmdb_enrich_cache.json`
- 过期时间：30 天（TMDB 数据不常变）
- 写入时机：`_async_enrich_tmdb_ids` 补全成功后
- 读取时机：`_inject_clean_names` 中，查到 douban_id 对应的缓存则直接用
- 大小控制：最多 5000 条（LRU 淘汰最旧的）

---

## 六、综合分析与推荐方案

### 方案评判总结

| 方案 | 推荐 | 理由 |
|------|------|------|
| A 定时预补全 | ❌ 不推荐 | 个人 NAS 工具不需要定时任务的复杂度；架构侵入大；频率难以和缓存周期对齐 |
| B 详情页按需 | ✅ 作为基础层 | 当前 UI 已经是这个模式（搜索按钮在 ExpandDetail 面板内），零额外开发量 |
| C 持久化缓存 | ✅ 作为增强层 | 解决 `_async_enrich_tmdb_ids` 结果丢失的核心问题，实现简单 |
| D 混合 B+C | ⬜ 方向对但可简化 | B 层已在工作，只需实现 C 层就自动获得 D 的效果 |
| E 同步并发补全 | ✅ 推荐与 C 组合 | 首次加载就有英文名，1-2 秒可接受 |

### 推荐方案：C + E 组合（带超时降级）

**核心思路：**
1. 新建 `tmdb_enrich_cache.json` 持久化缓存（方案 C）
2. 在 `_inject_clean_names` 中，对缺少英文名的条目，先查缓存，未命中则**同步并发**请求 TMDB（方案 E）
3. 补全结果写入缓存，下次直接命中（零等待）
4. 详情页按需补全保持不变（方案 B，已有机制）

**超时降级机制（关键）：**

TMDB API 走代理，国内网络波动可能导致请求超时。必须加硬性超时中断：

```
_inject_clean_names 中的同步并发补全：
  → ThreadPoolExecutor 并发请求 TMDB（max_workers=5）
  → as_completed(timeout=2.0)：最多等 2 秒
  → 2 秒内返回的结果 → 写入缓存 + 注入到当前响应
  → 2 秒内未返回的条目 → 跳过，用 cn/original 回退
  → 超时的条目 → 转交 _async_enrich_tmdb_ids 后台继续补全
```

**效果：**
- 网络好时 → 方案 E 体验（首次加载即完美，1-2 秒内全部补全）
- 网络差时 → 自动降级为方案 C（首屏快速响应，后台渐进补全）
- 永远不会出现前端转圈等待超过 2 秒

**为什么不用方案 D 原版：**
- 方案 D 的"后台异步补全 + 第二次请求才有数据"体验不如"首次同步补全 + 缓存"
- 有了超时降级，同步并发的风险被控制住了
- 缓存命中后零等待，和方案 A 的效果一样

### 关键发现：前端 normalizeItem 丢弃了 clean_name_en

`discoverUtils.ts` 的 `normalizeItem` 没有传递 `clean_name_en` / `clean_name_cn` / `clean_name_original` 字段：
```typescript
export function normalizeItem(item: any): DoubanHotItem {
  return {
    // ... 没有 clean_name_en
    subtitle: item.original_title || item.subtitle || "",
  };
}
```

后端 `_inject_clean_names` 注入的 `clean_name_en` 在前端被丢弃了。需要：
1. `DoubanHotItem` 类型加 `clean_name_en?: string` / `clean_name_cn?: string` / `clean_name_original?: string`
2. `normalizeItem` 传递这三个字段
3. SearchModal 的 enName 回退链加上 `searchModalItem.clean_name_en`

### 关键发现：当前 UI 搜索必须先展开详情

代码审查确认：搜索按钮在 `ExpandDetail` 面板内，用户必须先点击卡片展开详情才能搜索。这意味着：
- `searchModalDetail` 在搜索时不会是 null（已有详情数据）
- `enName` 的回退链 `searchModalDetail?.original_title || (searchModalItem as any)._tmdb_original_title || searchModalItem.subtitle` 中，第一个通常有值
- 但如果未来在卡片上加直接搜索按钮，方案 B 就会失效，需要 C+E 兜底

---

## 七、待讨论问题的回答

**1. 方案 D 是否是最优解？**
方案 D 的方向对，但建议用 C+E 组合替代：首次同步并发补全 + 持久化缓存。比 D 更简单，体验更好。

**2. 详情页展开时的 TMDB 请求，返回的英文名是否应该回写到 tmdb_enrich_cache？**
是的，应该回写。在后端 `get_media_info` 返回前顺手写入缓存，前端零改动。

**3. 缓存过期时间 30 天是否合理？**
合理。TMDB 的英文名几乎不变，评分会微调但对搜索无影响。统一 30 天简化实现。

**4. 是否需要前端显示"英文名加载中"的状态？**
不需要。C+E 方案下首次加载时同步补全，返回给前端的数据已经有英文名。

---

## 八、tmdb_enrich_cache 设计细节

### 缓存 key 设计

用复合 key 支持多数据源：
- 有 douban_id：`douban_{douban_id}`
- 有 tmdb_id：`tmdb_{tmdb_id}`
- 都没有：`title_{title}_{year}`（兜底）

### 数据结构

```json
{
  "douban_12345": {
    "tmdb_id": 550,
    "en_title": "Fight Club",
    "original_title": "Fight Club",
    "tmdb_rating": 8.4,
    "updated_at": "2026-04-21T10:30:00"
  }
}
```

### 缓存策略
- 文件位置：`scrape_cache/tmdb_enrich_cache.json`
- 过期时间：30 天
- 写入时机：同步并发补全后 + `_async_enrich_tmdb_ids` 后 + 详情页请求后
- 读取时机：`_inject_clean_names` 中
- 大小控制：最多 5000 条（LRU 淘汰最旧的）
- 并发安全：启动时加载到内存字典，写入时先更新内存再异步写文件，用 `threading.Lock` 保护

---

## 九、实施改动清单（C+E 方案，带超时降级）

### 后端（2 个文件，~100 行）

1. **`backend/routes/discover.py`**（主要改动）
   - 新增 `_load_enrich_cache()` / `_save_enrich_cache()` + `threading.Lock` 保护
   - 修改 `_inject_clean_names()`：
     - 查缓存 → 命中的直接注入 en_title/tmdb_rating
     - 未命中的收集 → `ThreadPoolExecutor(max_workers=5)` 并发请求 TMDB
     - `as_completed(timeout=2.0)` 硬性超时
     - 2 秒内返回的写入缓存 + 注入
     - 超时的条目转交 `_async_enrich_tmdb_ids` 后台继续
   - 修改 `_async_enrich_tmdb_ids()`：补全结果写入持久化缓存
   - 预计新增 ~70 行，修改 ~20 行

2. **`backend/routes/media_info.py`**（小改动）
   - 在 `get_media_info` 返回前，如果有英文名，顺手写入 enrich_cache
   - 预计新增 ~10 行

### 前端（2 个文件，~15 行）

3. **`frontend/types/index.ts`**
   - `DoubanHotItem` 加 `clean_name_cn?` / `clean_name_en?` / `clean_name_original?`

4. **`frontend/components/media/discoverUtils.ts`**
   - `normalizeItem` 传递 `clean_name_cn` / `clean_name_en` / `clean_name_original`

### 总改动量：~115 行，复杂度低
