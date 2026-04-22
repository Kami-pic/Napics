# [当前] 订阅系统重新设计

> 两个核心需求：
> 1. 剧集追更：订阅一部剧/动画 → 每周自动从指定源搜索新集 → 自动下载
> 2. 洗版蹲守：本地已有的低质量资源 → 持续监控更高质量版本 → 自动替换
>
> 参考：MoviePilot（订阅搜索+洗版+日历）、Sonarr（RSS 监控+质量档案+自动升级）

---

## 一、业界最佳实践总结

### Sonarr/Radarr 模式
- 质量档案（Quality Profile）：定义可接受的质量范围和优先级排序
- Quality Cutoff：达到目标质量后自动停止搜索更好版本
- RSS 监控：定时拉取索引器的 RSS feed，新种子自动匹配
- 自动升级：已有文件低于质量档案上限时，发现更好版本自动替换
- 剧集追踪：从 TVDB/TMDB 获取播出日历，只搜索已播出的集
- 下载失败自动换候选重试

### MoviePilot 模式
- 订阅搜索：定时遍历所有订阅，调用搜索链路匹配资源
- 洗版模式：`best_version=True` 时用更严格的过滤规则，只接受优先级更高的资源
- 站点范围：每个订阅可指定搜索哪些站点
- 自定义关键词：覆盖默认搜索词
- 订阅完成判定：电影下载即完成；剧集所有集齐全后完成

### 我们的差异点
- 我们有 15+ 个直搜源（Prowlarr 索引器 + 直搜爬虫 + 网盘），不是纯 RSS
- 我们的搜索是 SSE 实时流，不是后台静默搜索
- 用户习惯是在发现页/搜索弹窗中操作，不是独立的订阅管理界面

### 我们的架构选择：RSS + 直搜双通道

经过调研，我们现有 BT 源中 **8 个支持 RSS**（Prowlarr/蜜柑/Nyaa/ACG.RIP/Bangumi Moe/YTS + 新增 EZTV/动漫花园），只有磁力熊/XL720/Bitsearch 和网盘源没有 RSS。采用双通道架构：

**RSS 通道（高频·低成本）**— 订阅的主力搜索通道：
- 请求轻量：RSS 端点返回标准 XML，比搜索 API 响应快、负载低
- 限频宽松：站点鼓励使用 RSS，不触发反爬机制
- 匹配灵活：拿到完整标题后在本地做匹配，可以用更宽松的规则，不漏资源
- 注意：大部分 RSS 源仍需按关键词查询（蜜柑/Nyaa/动漫花园/ACG.RIP），请求量是 O(订阅数×RSS源数)，但单次请求成本远低于直搜
- Prowlarr 可做真正的全站 RSS feed 拉取（一次覆盖所有订阅），其他源按关键词
- 轮询频率：每 15-30 分钟

**直搜通道（低频·补充覆盖）**— 兜底和补充：
- 覆盖无 RSS 的源（磁力熊/XL720/Bitsearch/网盘）
- 搜索历史资源（RSS 只有最近发布）
- 轮询频率：每 4-12 小时

**RSS vs 直搜优势总结**：
| 维度 | RSS | 直搜 |
|---|---|---|
| 请求效率 | 单次请求轻量，限频宽松 | N订阅 × M源 次重量级请求 |
| 限频风险 | 极低（站点鼓励使用 RSS） | 高（关键词搜索易触发限频） |
| 资源覆盖 | 最近发布的全部内容 | 只能搜到关键词匹配的 |
| 历史资源 | ❌ 只有最近 | ✅ 可搜历史 |
| 实时性 | 新种子发布后几分钟出现在 feed | 取决于搜索间隔 |
| 源覆盖 | 8 个源有 RSS | 全部 15+ 源 |

### 各源 RSS 支持情况

| 源 | RSS | RSS 端点 | 说明 |
|---|---|---|---|
| Prowlarr | ✅ | Newznab/Torznab 标准 | 全站 RSS feed（一次拉取覆盖所有订阅）+ 搜索 API（走直搜通道） |
| 蜜柑 | ✅ | `/RSS/Search?searchstr=关键词` | 已实现（`rss_source_mikan.py`） |
| Nyaa | ✅ | `/?page=rss&q=关键词&c=分类&f=过滤` | 按关键词+分类订阅 |
| ACG.RIP | ✅ | `/t/关键词.xml` | 按关键词订阅 |
| Bangumi Moe | ✅ | `/api/v2/torrent/rss` | 按标签订阅 |
| YTS | ✅ | `/rss/` | 全站 RSS |
| **EZTV**（新增） | ✅ | `/ezrss.xml?imdb_id=xxx` | 按 IMDB ID 精准订阅，追美剧首选 |
| **动漫花园**（新增） | ✅ | `/topics/rss/rss.xml?keyword=xxx` | 按关键词/字幕组，中文动漫全覆盖 |
| 磁力熊 | ❌ | — | 纯搜索，走直搜通道 |
| XL720 | ❌ | — | 纯搜索，走直搜通道 |
| Bitsearch | ❌ | — | 纯搜索 API，走直搜通道 |
| 网盘源(6个) | ❌ | — | 纯搜索，走直搜通道 |

### 新增源调研

**EZTV**（`eztv.re`）：
- 定位：专注欧美剧集的 BT 站，RARBG 关站后追美剧的主力公开站
- RSS：按 IMDB ID 精准订阅（`/ezrss.xml?imdb_id=xxx`），追更杀手级功能
- 直搜 API：`/api/get-torrents?imdb_id=xxx` 返回 JSON，也可行
- 网络：需代理（和 Nyaa 同通道）
- 价值：⭐⭐⭐⭐ 追美剧/英剧强烈推荐

**动漫花园 DMHY**（`share.dmhy.org`）：
- 定位：中文动漫资源最大的公开 BT 站，字幕组发布主阵地
- RSS：按关键词 `/topics/rss/rss.xml?keyword=xxx`，按字幕组 `?team_id=xxx`，按分类 `?sort_id=2`
- 直搜：搜索页返回 HTML，需爬虫解析，有轻度 CF 保护
- 网络：需代理
- 价值：⭐⭐⭐⭐ 中文动漫全覆盖，和蜜柑互补（花园覆盖面更广，不限于动画）

---

## 二、两个需求的设计

### 需求 1：剧集追更

**用户故事**：我订阅了"黑袍纠察队 第五季"，每周五更新一集，系统自动帮我搜索并下载新集。

**核心流程**：
```
用户在发现页/搜索结果中点"订阅"
  → 弹出订阅配置（选源、质量、目标质量、保存路径）
  → 后台定时任务（每 N 小时）
    → 对每个活跃订阅：
      → 用多语言搜索词调用 search_service（复用 SSE 的后端逻辑，但不走 SSE）
      → 匹配+过滤+排序（复用 L1-L4）
      → 和已下载集号对比，找出新集
      → 自动下载（qB/Alist）
      → 更新订阅进度
  → 前端订阅列表实时展示进度
```

**关键设计决策**：

1. **双通道搜索**：RSS 通道 + 直搜通道并行
   - RSS 通道（高频）：Prowlarr RSS feed + 蜜柑/Nyaa/ACG.RIP/Bangumi Moe/YTS/EZTV/动漫花园
     - 每 15-30 分钟轮询，请求轻量且限频宽松
     - Prowlarr 全站 feed 一次拉取覆盖所有订阅；其他源按订阅关键词拉取
   - 直搜通道（低频）：Prowlarr 搜索 API + 磁力熊/XL720/Bitsearch/网盘源
     - 每 4-12 小时搜索一次
     - 覆盖无 RSS 的源 + 搜索历史资源 + 全源兜底
   - 用户可在订阅配置中选择启用哪些源（默认全部启用）

2. **搜索源推荐**：订阅时根据内容类型推荐源组合
   - 动画推荐：蜜柑 + Nyaa + 动漫花园 + ACG.RIP（字幕组更新最快）
   - 美剧推荐：EZTV + Prowlarr（EZTV 按 IMDB ID 精准订阅）
   - 国产剧推荐：磁力熊 + XL720 + 网盘源
   - 电影推荐：YTS + Prowlarr + 磁力熊
   - 用户可自定义勾选覆盖推荐

3. **搜索频率**：
   - RSS 通道：每 15-30 分钟（全局统一拉取，成本极低）
   - 直搜通道：默认 4 小时一次（可配置）
   - 日历感知：知道播出日的订阅，在播出日当天直搜通道加密搜索（每 1 小时）
   - 全局速率限制：每分钟最多 N 次请求到同一源，避免 20 个订阅同时搜索触发限频

4. **集号匹配**：
   - 从搜索结果的文件名中解析集号（复用 `parse_filename` + `rss_source_base.extract_episode_number`）
   - 和 `downloaded_episodes` 对比，只下载缺失的集
   - 整季包识别：下载完成后扫描文件列表提取所有集号，批量填充 downloaded_episodes

5. **搜索词**：
   - 复用 `search_keyword_mapper` 的多语言搜索词
   - 订阅时可自定义搜索词覆盖

6. **目标质量（Quality Cutoff）**：
   - 追更模式也支持 `target_quality`
   - 达到目标质量后该集不再搜索更好版本
   - 追更+洗版可同时生效：追更负责新集，洗版负责已有集的升级

7. **搜索结果缓存**：
   - RSS 通道：feed 内容缓存（按源，TTL 15 分钟，避免重复拉取）
   - 直搜通道：`search_service` 结果缓存（按源+关键词，TTL 30 分钟）
   - 避免重复请求，缓解源限频问题

8. **下载失败重试**：
   - `DownloadManager` 检测到 failed/lost 状态时，通知订阅系统
   - 从 found_resources 中选下一个候选自动重试

### 需求 2：洗版蹲守

**用户故事**：我本地有一个 1080p WEB-DL 的"沙丘2"，想等 4K Remux 出来后自动替换。

**核心流程**：
```
用户在发现页详情对 local_status=owned_low 的条目点"蹲守升级"
  → 记录当前质量分（quality_score）
  → 后台定时任务
    → 搜索该影片
    → 过滤出 quality_score > 当前分 + 阈值(5分) 的结果
    → 自动下载最高质量的
    → 下载完成后触发归位替换（file_relocator）
    → 旧文件入回收站
```

**关键设计决策**：

1. **触发入口**（先只做发现页，媒体库入口延后）：
   - 发现页详情对 `local_status=owned_low` 的条目显示"蹲守升级"按钮
   - 后续根据使用频率再决定是否加媒体库详情面板入口

2. **质量判定**：
   - 复用 `compare_quality_score(current, candidate)`，阈值 5 分
   - 用户可设置目标质量（如"至少 4K"或"至少 Remux"）

3. **搜索频率**：
   - 比追更低频：每 12-24 小时一次
   - 电影洗版通常在上映后 3-6 个月出高质量版本，不需要太频繁

4. **自动替换**：
   - 下载完成 → 调用 `file_relocator.relocate()` 归位
   - 旧文件移到回收站（不直接删除）
   - 归位替换失败时不标记 completed，保留订阅继续搜索
   - 洗版完成后自动结束该订阅

5. **local_file_path 校验**：
   - 归位时先校验路径是否存在
   - 不存在则尝试通过 `local_media_matcher` 重新定位

---

## 三、统一数据模型

现有的 `Subscription` 模型基本够用，补充几个字段：

```python
class Subscription:
    # 现有字段保持不变
    id, title, year, type, tmdb_id, state, quality, mode, best_version,
    save_path, search_keyword, sources, ...
    
    # 新增字段
    purpose: str = "follow"           # "follow"(追更) | "upgrade"(洗版)
    target_quality: str = ""          # 目标质量（"2160p" 等），达到后停止搜索
    current_quality_score: int = 0    # 洗版用：当前文件的质量分
    local_file_path: str = ""         # 洗版用：本地文件路径（归位替换用）
    search_interval_hours: float = 0  # 搜索间隔（0=用全局默认，追更4h，洗版24h）
    last_results_summary: str = ""    # 上次搜索结果摘要（前端展示用，含错误信息）
    imdb_id: str = ""                 # IMDB ID（EZTV 精准订阅用，创建时从 TMDB 转换并缓存）
```

### 兼容性处理
- 旧数据加载时缺失字段自动取默认值（Pydantic 天然支持）
- `purpose` 默认 `"follow"` — 旧订阅自动归为追更
- `aliases` 字段的 `jp` → `original` 迁移：加载时自动映射
- `sources` 字段语义统一为直搜源名称（如 `["prowlarr", "nyaa", "mikan"]`）
- `SubscriptionManager.update()` 的 `updatable` 白名单需扩展新增字段

---

## 四、前端交互改造

### 4.1 订阅配置弹窗增强

`SubscribeConfigModal` 改造：

**订阅类型选择**：追更 / 洗版（默认追更）

**源选择分组展示**（`SubscribeSourceSelect` 改造）：
```
RSS 源（每 15-30 分钟自动检查）
  [✓蜜柑] [✓Nyaa] [动漫花园] [ACG.RIP]
  [Bangumi Moe] [EZTV] [YTS] [Prowlarr RSS]

直搜源（每 4-12 小时搜索补充）
  [✓Prowlarr] [磁力熊] [XL720] [Bitsearch]

💡 推荐：日本动画优先用蜜柑+Nyaa，美剧用EZTV
```
- 源按 RSS/直搜 分两组展示，用户一眼区分高频和低频
- 根据内容类型自动推荐并预选（动画→蜜柑+Nyaa+动漫花园，美剧→EZTV+Prowlarr，国产剧→磁力熊+XL720，电影→YTS+Prowlarr）
- 用户可自由勾选覆盖推荐

**新增目标质量**（Quality Cutoff）：达到后停止搜索更好版本

**高级设置折叠**：包含/排除关键词、自定义搜索词、保存路径折叠到"高级设置"，减少默认视觉噪音

**洗版模式**：自动填入当前质量信息，只需选目标质量和源

### 4.2 搜索弹窗与订阅的关系

搜索弹窗（SearchModal）和订阅是互补关系，不是替代：
- **搜索弹窗** = 即时需求，手动全源搜索，挑选下载
- **订阅** = 持续监控，后台自动搜索，通知或自动下载

两者交叉使用场景：
- 订阅 notify 模式找到资源后，用户点"查看并下载"打开搜索弹窗手动挑选
- 订阅列表中点"搜索"按钮触发一次全源直搜，在弹窗中看结果
- 不需要追更的内容（如老电影），直接搜索下载，不建订阅
- 订阅 auto 模式是唯一"全自动不用管"的路径

### 4.3 发现页"蹲守升级"入口

- 发现页详情对 `local_status=owned_low` 的条目显示"蹲守升级"按钮
- 点击后弹出简化版配置（目标质量 + 搜索源，自动填入当前 quality_score 和 local_file_path）
- 媒体库详情面板入口延后，根据使用频率再决定

### 4.4 订阅列表改造（两级展示）

**折叠态**（默认，列表中每条订阅）：
```
┌──────────────────────────────────────────────────────┐
│ 🎬 黑袍纠察队 S5            🔄追更  活跃               │
│    2025 · 1080p · 自动 · EZTV+Prowlarr               │
│    ████████░░░░░░░░  5/8 · 下一集 E06 7月11日(3天后)  │
│    上次：搜到 3 条，最高 1080p HEVC · 2h前              │
│    [🔍搜索] [⏸暂停] [⚙配置] [🗑删除]                  │
└──────────────────────────────────────────────────────┘
```

追更剧集折叠态关键信息：
- 标题旁显示季号（S5）
- purpose 标签（🔄追更 / ⬆️洗版）
- 进度条 + 已下载/总集数
- 下一集播出时间（从 calendar 数据计算）
- 搜索源列表（用户选的哪些源）
- `last_results_summary`（上次搜索结果摘要）
- 操作按钮：搜索/暂停/配置/删除

**展开态**（点击卡片展开，显示每集详情）：
```
┌──────────────────────────────────────────────────────┐
│ 🎬 黑袍纠察队 S5            🔄追更  活跃               │
│    2025 · 1080p · 自动 · EZTV+Prowlarr               │
│    ████████░░░░░░░░  5/8 · 下一集 E06 7月11日(3天后)  │
│  ┌────────────────────────────────────────────────┐  │
│  │ E01  ✓  1080p WEB-DL    EZTV     6月6日        │  │
│  │ E02  ✓  1080p WEB-DL    EZTV     6月13日       │  │
│  │ E03  ✓  1080p WEB-DL    EZTV     6月20日       │  │
│  │ E04  ✓  1080p HEVC      Prowlarr 6月27日       │  │
│  │ E05  ✓  1080p WEB-DL    EZTV     7月4日        │  │
│  │ E06  ⏳  —              —        7月11日 ← 下集  │  │
│  │ E07  ·  —              —        7月18日        │  │
│  │ E08  ·  —              —        7月25日        │  │
│  └────────────────────────────────────────────────┘  │
│    上次：搜到 3 条，最高 1080p HEVC · 2h前              │
│    [🔍搜索] [⏸暂停] [⚙配置] [🗑删除]                  │
└──────────────────────────────────────────────────────┘
```

每集状态三种：✓ 已下载（显示质量+来源+日期）/ ⏳ 即将播出 / · 未播出

数据来源：
- 每集下载信息：`downloaded_episodes` 中的 `EpisodeInfo`（已有 quality_tag/source/timestamp）
- 播出日期：`/subscribe/calendar` API
- 下一集：calendar 中第一个未下载且 air_date >= today 的集

**洗版订阅卡片**：
```
┌──────────────────────────────────────────────────────┐
│ 🎬 沙丘2                    ⬆️洗版  活跃               │
│    2024 · 电影 · 自动 · YTS+Prowlarr                  │
│    1080p WEB-DL (52分) → 目标 4K                      │
│    上次：已搜索 8 次，暂未找到 · 1天前                    │
│    [🔍搜索] [⏸暂停] [⚙配置] [🗑删除]                  │
└──────────────────────────────────────────────────────┘
```

### 4.5 日历视图

- 只对 `purpose=follow` 的剧集订阅显示
- 日历为空时显示友好提示（"订阅剧集后这里会显示播出计划"）

### 4.6 订阅冲突处理

- 同一影片已有 `purpose=follow` 的订阅，再点"蹲守升级"时提示"已有追更订阅，是否同时开启洗版"
- 追更+洗版可共存：追更负责新集，洗版负责已有集的升级

### 4.7 组件改动清单

| 组件 | 改动 |
|---|---|
| `SubscribeConfigModal` | 加订阅类型选择 + 目标质量 + 高级设置折叠 |
| `SubscribeSourceSelect` | 源按 RSS/直搜分组展示 + 内容类型推荐 |
| `SubscribeInline` | 两级展示（折叠/展开）+ purpose 标签 + 集详情 + 洗版质量 + last_results_summary + 配置按钮 |
| `ExpandDetail`（发现页详情） | owned_low 时显示"蹲守升级"按钮 |
| `SubscribeCalendar` | 只对 purpose=follow 显示（现有逻辑不变） |
| `useSubscriptions` hook | SubscriptionItem 类型扩展新增字段 |

### 4.8 前端类型扩展

`SubscriptionItem`（useSubscriptions.ts）需新增：
```typescript
// 新增字段
purpose: string;              // "follow" | "upgrade"
target_quality: string;
current_quality_score: number;
local_file_path: string;
search_interval_hours: number;
last_results_summary: string;
imdb_id: string;
sources: string[];            // 现有但未在类型中定义
best_version: boolean;        // 现有但未在类型中定义
```

`EpisodeInfo`（后端已有，前端 `downloaded_episodes` 的 value 类型）：
```typescript
interface EpisodeInfo {
  info_hash: string;
  title: string;
  quality_tag: string;    // 展开态显示质量
  source: string;         // 展开态显示来源（"prowlarr"/"eztv"/"mikan" 等）
  channel: string;        // "qb" / "alist"
  task_id: string;
  timestamp: string;      // 展开态显示下载日期
}
```

展开态集详情需要合并两个数据源：
- `downloaded_episodes[ep_key]` → 已下载集的质量/来源/日期
- `/subscribe/calendar` API → 每集的播出日期（air_date）
- 前端在展开时合并：calendar 提供播出日期，downloaded_episodes 提供下载状态

### 延后不做

- ❌ 搜索结果关联订阅 — 增加模块耦合，等核心功能稳定后再加
- ❌ 批量订阅 — 不是 MVP 必须的

---

## 五、后端改造

### 5.1 P0：修复 SubscriptionManager 单例问题

**现有 bug**：`download_manager._notify_subscription_complete()` 每次 `SubscriptionManager(base_path=...)` 新建实例，和 `routes/subscribe.py` 的 `_get_sub_manager()` 单例是两个不同对象，各自持有独立的 subscriptions 列表和 _lock，存在数据竞争。

**修复**：`SubscriptionManager` 改为通过 `shared.py` 提供全局单例，所有调用方统一使用。

### 5.2 搜索逻辑抽离（search_service.py）

从 `routes/search.py` 的 `_generate()` 中抽出核心逻辑：

```python
# search_service.py（新建）
def search_all_sources(
    keywords: MultiLangKeywords,
    sources: List[str] = None,    # 指定源列表，None=全部启用的源
    timeout: int = 30,            # 总超时
    per_source_timeout: int = 15, # 单源超时
    use_cache: bool = True,       # 是否使用结果缓存
) -> List[dict]:
    """同步搜索所有指定源，返回 enrich 后的结果列表"""
    # 复用 search_keyword_mapper + 各源搜索函数 + enrich_result
    # 结果缓存：按源+关键词，TTL 30 分钟
    ...
```

**注意事项**：
- `_search_prowlarr()` 和 `_search_direct()` 从闭包提升为独立函数
- 并行调度逻辑封装为 `search_all_sources()`
- SSE 端点改为调用 `search_service` 的迭代器版本
- 抽离后 SSE 和 `/api/search` 的行为必须和抽离前完全一致（回归测试）

### 5.3 RSS 通道改造（双通道核心）

现有 `rss_engine.py` 框架保留并增强，作为 RSS 通道的调度器：

**架构调整**：
```
SubscriptionScheduler（调度器）
├── RSS 通道（高频，每 15-30 分钟）
│   ├── RSSSourceManager 管理所有 RSS 源
│   ├── 一次拉取 feed → 本地匹配所有活跃订阅
│   ├── 匹配结果走 rss_matcher → 下载
│   └── 源列表：Prowlarr/蜜柑/Nyaa/ACG.RIP/Bangumi Moe/YTS/EZTV/动漫花园
│
└── 直搜通道（低频，每 4-12 小时）
    ├── 调用 search_service.search_all_sources()
    ├── 只搜无 RSS 的源 + 全源兜底
    └── 源列表：磁力熊/XL720/Bitsearch/网盘 + 可选全源
```

**RSS 通道工作流**：
1. Prowlarr 全站 RSS：拉取一次 Newznab/Torznab feed，本地匹配所有订阅
2. 关键词 RSS 源（蜜柑/Nyaa/ACG.RIP/Bangumi Moe/EZTV/动漫花园/YTS）：每个订阅构造搜索词，拉取对应 feed
3. 合并所有 feed 条目，用 `rss_matcher.match_items()` 匹配
4. 匹配到的条目按订阅分组，触发下载

**关键改动**：
- `RSSSourceManager` 新增 `fetch_all_feeds()` 方法：Prowlarr 拉一次全站 feed，其他源按订阅拉取
- `SubscriptionScheduler._tick()` 拆分为 `_tick_rss()` 和 `_tick_search()` 两个独立循环
- RSS 循环和直搜循环各自独立计时，互不阻塞
- `rss_matcher` 增强：引入 L1 normalize + L2 match_chain 做标题匹配（解决跨语言匹配，如"葬送的芙莉莲"匹配 "Sousou no Frieren"）

**新增 RSS 源实现**：

1. `rss_source_nyaa.py`（新建）：
   - RSS 端点：`https://nyaa.si/?page=rss&q=关键词&c=1_0&f=0`
   - 分类过滤：`c=1_0`（动画）、`c=1_2`（英文翻译动画）、`c=3_0`（音乐）等
   - 需代理

2. `rss_source_eztv.py`（新建）：
   - RSS 端点：`https://eztv.re/ezrss.xml?imdb_id=xxx`
   - 按 IMDB ID 精准订阅（需要 tmdb_id → imdb_id 转换，复用 TMDB API）
   - 也支持关键词搜索：`https://eztv.re/ezrss.xml?search_string=xxx`
   - 需代理
   - 同时实现直搜 API（`/api/get-torrents?imdb_id=xxx`），作为 BT 搜索源补充

3. `rss_source_dmhy.py`（新建）：
   - RSS 端点：`https://share.dmhy.org/topics/rss/rss.xml?keyword=xxx`
   - 支持按字幕组 `?team_id=xxx`、按分类 `?sort_id=2`
   - 需代理

4. `rss_source_acgrip.py`（新建）：
   - RSS 端点：`https://acg.rip/t/关键词.xml`
   - 全站 RSS：`https://acg.rip/.xml`

5. `rss_source_bangumi_moe.py`（新建）：
   - RSS 端点：`https://bangumi.moe/api/v2/torrent/rss`
   - 按标签订阅

6. `rss_source_yts.py`（新建）：
   - RSS 端点：`https://yts.mx/rss/` 或 `https://yts.am/rss/`
   - 全站 RSS，主要用于电影洗版发现新版本

**RSSItem → SearchResult 桥接**：
- RSS 通道产出 `RSSItem`，直搜通道产出 `SearchResult`（dict）
- 下载和展示需要统一格式
- 方案：`rss_matcher` 匹配后，将 RSSItem 转换为 SearchResult 格式再进入下载流程
- 转换函数：`rss_item_to_search_result(item: RSSItem) -> dict`

### 5.4 直搜通道改造

`SubscriptionScheduler` 的直搜通道直接调用 `search_service.search_all_sources()`：
- 只搜无 RSS 的源（磁力熊/XL720/Bitsearch）+ 网盘源
- 可选全源兜底搜索（RSS 漏掉的历史资源）
- 复用 5.2 抽离的 search_service，不重复实现

### 5.5 集号解析增强

BT 标题的格式比本地文件名复杂（如 `[SubGroup] Title - 05 (1080p)`），需要增强解析能力：
- 复用 `rss_source_base.extract_episode()` 处理 BT 标题
- 整季包下载完成后扫描文件列表提取所有集号

---

## 六、实施步骤

> 原则：先跑通最小链路，再逐步扩展。RSS 源分批上线，前端先折叠态再展开态。

### Phase 0：修复基础设施（必须最先做）✅
- [x] SubscriptionManager 改为 shared.py 全局单例
- [x] download_manager 和 routes/subscribe.py 统一使用同一实例
- [x] 验证：并发读写 subscriptions.json 不丢数据

### Phase 1a：数据模型扩展（可和 1b 并行）✅
- [x] Subscription 新增 purpose / target_quality / current_quality_score / local_file_path / search_interval_hours / last_results_summary / imdb_id
- [x] aliases 的 jp → original 迁移（加载时自动映射）
- [x] updatable 白名单扩展
- [x] 兼容旧数据验证

### Phase 1b：搜索逻辑抽离（关键路径，最大工作量）✅
- [x] 新建 search_service.py
- [x] _search_prowlarr / _search_direct 从闭包提升为独立函数
- [x] search_all_sources() 封装并行调度+去重+enrich
- [ ] 结果缓存层（按源+关键词，TTL 30 分钟）— 延后，先跑通链路
- [x] SSE 端点改为调用 search_service
- [x] 回归测试：SSE 和 /api/search 行为不变
- [ ] 同时解决 search.py 541 行过长的技术债务 — 延后

### Phase 1c：核心 RSS 源实现（先上最关键的 3 个，跑通链路）✅
- [x] rss_source_eztv.py — EZTV RSS 源（含 IMDB ID 订阅）
- [x] search_keyword_mapper.py 补充 eztv/dmhy 的 SOURCE_LANG_PRIORITY
- [x] 蜜柑（已有）+ Prowlarr（已有）+ Nyaa（已有）+ EZTV（新增）注册到 RSSSourceManager
- [x] 每个源独立测试：拉取 feed + 解析 + 匹配验证

### Phase 2a：RSS 通道调度器（先只做 RSS，不做直搜）✅
- [x] rss_item_to_search_result() 格式桥接
- [x] 搜索结果摘要写入 last_results_summary（含错误信息）
- [x] _build_results_summary() 生成前端展示用摘要
- [ ] Prowlarr 全站 RSS feed 拉取（区分于搜索 API）— 延后
- [ ] rss_matcher 增强：引入 L1/L2 做标题匹配 — 延后

### Phase 2b：追更模式完善 ✅
- [x] 目标质量（Quality Cutoff）支持
- [x] should_search_now 支持自定义 search_interval_hours
- [x] 下载失败自动换候选重试（_retry_failed_downloads）
- [ ] 全局速率限制器 — 延后

### Phase 2c：直搜通道补充 ✅
- [x] SubscriptionScheduler 新增 _tick_search() 循环
- [x] 直搜通道调用 search_service.search_all_sources()
- [x] 只搜无 RSS 的源（磁力熊/XL720/Bitsearch）+ 可选全源兜底
- [x] RSS 和直搜双循环各自独立计时，互不阻塞

### Phase 2d：洗版模式（现有代码已有基础）✅
- [x] 洗版搜索走双通道（RSS + 直搜都支持 best_version）
- [x] 质量对比 + 自动下载 + 归位替换
- [x] 归位失败不标记 completed，保留订阅继续搜索
- [x] local_file_path 校验 + 自动重新定位（media_matcher）
- [x] 洗版订阅（purpose=upgrade）电影下载完成自动标记 completed

### Phase 3a：前端核心交互（先做折叠态，保证可用）
- [ ] SubscribeConfigModal 增加 purpose 选择 + 目标质量 + 高级设置折叠
- [ ] SubscribeSourceSelect 源按 RSS/直搜分组展示 + 内容类型推荐
- [ ] SubscribeInline 折叠态改造：purpose 标签 + 季号 + 进度 + 下一集 + 搜索摘要 + 配置按钮
- [ ] 洗版卡片：当前质量 → 目标质量
- [ ] SubscriptionItem 类型扩展新增字段
- [ ] 发现页"蹲守升级"入口（local_status=owned_low）

### Phase 3b：前端增强（展开态 + 日历优化）✅
- [x] SubscribeInline 展开态：点击卡片展开每集详情（质量+来源+日期+播出状态）
- [x] 展开态合并 downloaded_episodes + calendar 数据（一次性拉取缓存）
- [x] 折叠态显示"下一集"信息（从 calendar 计算）
- [x] 日历视图空状态优化（友好提示文案）
- [ ] 订阅冲突提示 — 延后

### Phase 4a：扩展 RSS 源（核心链路稳定后再铺开）
- [ ] rss_source_dmhy.py — 动漫花园 RSS 源
- [ ] rss_source_nyaa.py — Nyaa RSS 源
- [ ] rss_source_acgrip.py — ACG.RIP RSS 源
- [ ] rss_source_bangumi_moe.py — Bangumi Moe RSS 源
- [ ] rss_source_yts.py — YTS RSS 源
- [ ] 每个源独立测试 + 注册到 RSSSourceManager

### Phase 4b：反馈闭环和其他补充
- [ ] 订阅搜索日志（前端可查看每次搜索的结果）
- [ ] 下载完成通知（toast 或订阅列表角标）
- [ ] 洗版完成通知 + 自动标记 completed
- [ ] 预留通知接口（后续可接 Bark/Server 酱等推送）
- [ ] 搜索结果缓存（同一个源+同一个关键词 30 分钟内不重复请求）
- [ ] 全局速率限制（避免 20 个订阅同时搜索把源站搞限频）
- [ ] `routes/search.py` 剩余端点清理

---

## 七、不做的事

- ❌ 不做独立的订阅管理页面（保持在发现页的订阅 tab 内）
- ❌ 不做复杂的质量档案系统（Sonarr 那套太重，我们用 quality_score + target_quality 就够）
- ❌ 不做订阅分享/导入导出（个人 NAS 工具不需要）
- ❌ 不做搜索结果关联订阅（等核心功能稳定后再加）
- ❌ 不做批量订阅（不是 MVP）
- ❌ 不做外部推送通知（预留接口，后续按需接入）


### 延后

