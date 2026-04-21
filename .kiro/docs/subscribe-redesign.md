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

1. **搜索源选择**：订阅时让用户选择"从哪些源追更"
   - 默认：全部启用的 BT 源
   - 动画推荐：Nyaa + 蜜柑（字幕组更新最快）
   - 国产剧推荐：磁力熊 + XL720 + 网盘源
   - 用户可自定义勾选

2. **搜索频率**：
   - 默认 4 小时一次（可配置）
   - 日历感知：知道播出日的订阅，在播出日当天加密搜索（每 1 小时）
   - 全局速率限制：每分钟最多 N 次请求到同一源，避免 20 个订阅同时搜索触发限频

3. **集号匹配**：
   - 从搜索结果的文件名中解析集号（复用 `parse_filename` + `rss_source_base.extract_episode_number`）
   - 和 `downloaded_episodes` 对比，只下载缺失的集
   - 整季包识别：下载完成后扫描文件列表提取所有集号，批量填充 downloaded_episodes

4. **搜索词**：
   - 复用 `search_keyword_mapper` 的多语言搜索词
   - 订阅时可自定义搜索词覆盖

5. **目标质量（Quality Cutoff）**：
   - 追更模式也支持 `target_quality`
   - 达到目标质量后该集不再搜索更好版本
   - 追更+洗版可同时生效：追更负责新集，洗版负责已有集的升级

6. **搜索结果缓存**：
   - `search_service` 加一层结果缓存（按源+关键词，TTL 30 分钟）
   - 避免重复请求，缓解源限频问题

7. **下载失败重试**：
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

`SubscribeConfigModal` 增加：
- "订阅类型"选择：追更 / 洗版
- 追更模式：源选择、质量、目标质量、搜索词、保存路径
- 洗版模式：当前质量（自动填入）、目标质量、搜索源、搜索频率

### 4.2 发现页"蹲守升级"入口

- 发现页详情对 `local_status=owned_low` 的条目显示"蹲守升级"按钮
- 点击后弹出简化版配置（目标质量 + 搜索源）
- 自动填入当前 quality_score 和 local_file_path
- 媒体库详情面板入口延后，根据使用频率再决定

### 4.3 订阅列表改造

- 显示 `purpose` 标签（追更 🔄 / 洗版 ⬆️）
- 追更类型显示集数进度条
- 洗版类型显示当前质量 → 目标质量
- 每条订阅显示 `last_results_summary`（如"搜到 3 条，最高 4K Remux"或"3/10 源超时"）
- 洗版中但未找到更好版本时显示"已搜索 N 次，暂未找到"
- 操作按钮：搜索 / 暂停 / 配置 / 删除

### 4.4 日历视图

- 只对追更类型的订阅显示
- 日历为空时显示友好提示（"订阅剧集后这里会显示播出计划"）

### 4.5 订阅冲突处理

- 同一影片已有 `purpose=follow` 的订阅，再点"蹲守升级"时提示"已有追更订阅，是否同时开启洗版"
- 追更+洗版可共存：追更负责新集，洗版负责已有集的升级

### 延后不做

- ❌ 搜索结果关联订阅（4.5 原设计）— 增加模块耦合，等核心功能稳定后再加
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

### 5.3 SubscriptionScheduler 增强

让 `SubscriptionScheduler` 直接调用 `search_service.search_all_sources()`，绕过 RSS 框架（因为 `RSSItem` 和 `SearchResult` 是两套数据结构，强行适配增加复杂度）。

`rss_engine.py` 的角色从"RSS 源管理+调度"变成纯"调度器"，源管理由 `search_service` 统一接管。

### 5.4 集号解析增强

BT 标题的格式比本地文件名复杂（如 `[SubGroup] Title - 05 (1080p)`），需要增强解析能力：
- 复用 `rss_source_base.extract_episode_number()` 处理 BT 标题
- 整季包下载完成后扫描文件列表提取所有集号

---

## 六、实施步骤

### Phase 0：修复基础设施（必须最先做）
- [ ] SubscriptionManager 改为 shared.py 全局单例
- [ ] download_manager 和 routes/subscribe.py 统一使用同一实例
- [ ] 验证：并发读写 subscriptions.json 不丢数据

### Phase 1a：数据模型扩展（可和 1b 并行）
- [ ] Subscription 新增 purpose / target_quality / current_quality_score / local_file_path / search_interval_hours / last_results_summary
- [ ] aliases 的 jp → original 迁移（加载时自动映射）
- [ ] updatable 白名单扩展
- [ ] 兼容旧数据验证

### Phase 1b：搜索逻辑抽离（关键路径，最大工作量）
- [ ] 新建 search_service.py
- [ ] _search_prowlarr / _search_direct 从闭包提升为独立函数
- [ ] search_all_sources() 封装并行调度+去重+enrich
- [ ] 结果缓存层（按源+关键词，TTL 30 分钟）
- [ ] SSE 端点改为调用 search_service
- [ ] 回归测试：SSE 和 /api/search 行为不变
- [ ] 同时解决 search.py 541 行过长的技术债务

### Phase 2a：追更模式（用户价值最高，先做）
- [ ] SubscriptionScheduler 调用 search_service 而非 RSS 框架
- [ ] 多语言搜索 + 集号匹配 + 自动下载
- [ ] 目标质量（Quality Cutoff）支持
- [ ] 全局速率限制器
- [ ] 搜索结果摘要写入 last_results_summary（含错误信息）
- [ ] 下载失败自动换候选重试

### Phase 2b：洗版模式（现有代码已有基础）
- [ ] 洗版搜索调用 search_service
- [ ] 质量对比 + 自动下载 + 归位替换
- [ ] 归位失败不标记 completed
- [ ] local_file_path 校验 + 自动重新定位

### Phase 3：前端交互改造
- [ ] SubscribeConfigModal 增加 purpose 选择
- [ ] 发现页"蹲守升级"入口（local_status=owned_low）
- [ ] 订阅列表区分追更/洗版显示 + last_results_summary
- [ ] 日历视图空状态优化
- [ ] 订阅冲突提示

### Phase 4：反馈闭环
- [ ] 订阅搜索日志（前端可查看每次搜索的结果）
- [ ] 下载完成通知（toast 或订阅列表角标）
- [ ] 洗版完成通知 + 自动标记 completed
- [ ] 预留通知接口（后续可接 Bark/Server 酱等推送）

---

## 七、不做的事

- ❌ 不做独立的订阅管理页面（保持在发现页的订阅 tab 内）
- ❌ 不做复杂的质量档案系统（Sonarr 那套太重，我们用 quality_score + target_quality 就够）
- ❌ 不做订阅分享/导入导出（个人 NAS 工具不需要）
- ❌ 不做搜索结果关联订阅（等核心功能稳定后再加）
- ❌ 不做批量订阅（不是 MVP）
- ❌ 不做外部推送通知（预留接口，后续按需接入）
