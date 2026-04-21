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
- RSS 监控：定时拉取索引器的 RSS feed，新种子自动匹配
- 自动升级：已有文件低于质量档案上限时，发现更好版本自动替换
- 剧集追踪：从 TVDB/TMDB 获取播出日历，只搜索已播出的集

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
  → 弹出订阅配置（选源、质量、保存路径）
  → 后台定时任务（每 N 小时）
    → 对每个活跃订阅：
      → 用多语言搜索词调用已有的搜索链路（复用 SSE 的后端逻辑，但不走 SSE）
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

3. **集号匹配**：
   - 从搜索结果的文件名中解析集号（复用 `parse_filename`）
   - 和 `downloaded_episodes` 对比，只下载缺失的集
   - 整季包也能识别

4. **搜索词**：
   - 复用 `search_keyword_mapper` 的多语言搜索词
   - 订阅时可自定义搜索词覆盖

### 需求 2：洗版蹲守

**用户故事**：我本地有一个 1080p WEB-DL 的"沙丘2"，想等 4K Remux 出来后自动替换。

**核心流程**：
```
用户在媒体库中对某个文件/文件夹点"蹲守升级"
  → 记录当前质量分（quality_score）
  → 后台定时任务
    → 搜索该影片
    → 过滤出 quality_score > 当前分 + 阈值(5分) 的结果
    → 自动下载最高质量的
    → 下载完成后触发归位替换（file_relocator）
```

**关键设计决策**：

1. **触发入口**：
   - 媒体库详情面板加"蹲守升级"按钮
   - 搜索结果中对已有资源显示"蹲守更好版本"
   - 发现页详情对 `local_status=owned_low` 的条目显示"蹲守升级"

2. **质量判定**：
   - 复用 `compare_quality_score(current, candidate)`，阈值 5 分
   - 用户可设置目标质量（如"至少 4K"或"至少 Remux"）

3. **搜索频率**：
   - 比追更低频：每 12-24 小时一次
   - 电影洗版通常在上映后 3-6 个月出高质量版本，不需要太频繁

4. **自动替换**：
   - 下载完成 → 调用 `file_relocator.relocate()` 归位
   - 旧文件移到回收站（不直接删除）
   - 洗版完成后自动结束该订阅

---

## 三、统一数据模型

现有的 `Subscription` 模型基本够用，补充几个字段：

```python
class Subscription:
    # 现有字段保持不变
    id: str
    title: str
    year: str
    type: str          # "movie" | "tv"
    tmdb_id: int
    state: str         # "active" | "paused" | "completed"
    quality: str       # "2160p" | "1080p" | "720p" | ""
    mode: str          # "notify" | "auto"
    best_version: bool
    save_path: str
    search_keyword: str
    sources: list      # 搜索源列表
    
    # 新增字段
    purpose: str       # "follow"(追更) | "upgrade"(洗版) — 区分两种需求
    current_quality_score: int  # 洗版用：当前文件的质量分
    target_quality: str         # 洗版用：目标质量（"2160p" 等，可选）
    local_file_path: str        # 洗版用：本地文件路径（归位替换用）
    search_interval_hours: float  # 搜索间隔（追更默认4h，洗版默认24h）
    last_results_summary: str   # 上次搜索结果摘要（前端展示用）
```

---

## 四、前端交互改造

### 4.1 订阅入口统一

当前：发现页详情面板的"📌 订阅"按钮 → `SubscribeConfigModal`

改造：
- 保持现有入口不变
- `SubscribeConfigModal` 增加"订阅类型"选择：追更 / 洗版
- 追更模式：显示源选择、质量、搜索词、保存路径
- 洗版模式：显示当前质量、目标质量、搜索频率

### 4.2 媒体库增加"蹲守升级"入口

- 文件夹详情面板 / 视频详情面板加"蹲守升级"按钮
- 点击后弹出简化版配置（目标质量 + 搜索源 + 保存路径）
- 自动填入当前 quality_score

### 4.3 订阅列表改造

当前列表已经不错，补充：
- 显示 `purpose` 标签（追更 🔄 / 洗版 ⬆️）
- 追更类型显示集数进度条
- 洗版类型显示当前质量 → 目标质量
- 每条订阅显示"上次搜索结果摘要"（如"搜到 3 条，最高 4K Remux"）
- 操作按钮：搜索 / 暂停 / 配置 / 删除

### 4.4 日历视图

保持现有实现，但：
- 只对追更类型的订阅显示
- 日历为空时显示友好提示（"订阅剧集后这里会显示播出计划"）

### 4.5 搜索结果关联订阅

在 SearchModal 的搜索结果中：
- 如果当前搜索的影片有活跃订阅，顶部显示订阅状态条
- 手动下载某个结果时，自动更新订阅的已下载记录

---

## 五、后端改造

### 5.1 定时搜索任务（核心）

现有 `SubscriptionScheduler` 需要增强：

```
定时任务循环：
  for sub in active_subscriptions:
    if sub.purpose == "follow":
      → 用 search_keyword_mapper 生成多语言搜索词
      → 调用各源的搜索函数（复用 routes/search.py 的逻辑，但不走 SSE）
      → L2 匹配 + L3 过滤 + L4 排序
      → 解析集号，过滤已下载的集
      → mode=="auto" 时自动下载
      → mode=="notify" 时记录到 found_resources
      → 更新 last_results_summary
    
    elif sub.purpose == "upgrade":
      → 搜索影片
      → 过滤出 quality_score > current_quality_score + 5
      → 取最高质量的结果
      → 自动下载 + 归位替换
      → 替换完成后 state="completed"
```

### 5.2 搜索逻辑复用

不需要重写搜索，而是把 `routes/search.py` 中 SSE `_generate` 函数的核心逻辑抽成可复用的业务函数：

```python
# search_service.py（新建）
def search_all_sources(query, cn_name, en_name, original_name, sources, timeout=30):
    """同步搜索所有指定源，返回合并后的结果列表"""
    # 复用 search_keyword_mapper + 各源搜索函数 + enrich_result
    ...
```

### 5.3 集号解析

复用 `tmdb_client.parse_filename` + `clean_name_system.extract_suffix` 从搜索结果标题中提取季集号。

---

## 六、实施步骤

### Phase 1：后端搜索逻辑抽离（技术债务顺便还）

- [ ] 从 `routes/search.py` 抽出 `search_service.py`（搜索核心逻辑）
- [ ] `SubscriptionScheduler` 调用 `search_service` 而非自己实现搜索
- [ ] 这一步同时解决 search.py 541 行过长的技术债务

### Phase 2：订阅数据模型扩展

- [ ] `Subscription` 新增 purpose / current_quality_score / target_quality / local_file_path / search_interval_hours / last_results_summary
- [ ] 兼容旧数据（purpose 默认 "follow"）

### Phase 3：定时搜索增强

- [ ] 追更模式：多语言搜索 + 集号匹配 + 自动下载
- [ ] 洗版模式：质量对比 + 自动下载 + 归位替换
- [ ] 搜索结果摘要写入 last_results_summary

### Phase 4：前端交互改造

- [ ] `SubscribeConfigModal` 增加 purpose 选择（追更/洗版）
- [ ] 订阅列表区分追更/洗版显示
- [ ] 媒体库详情加"蹲守升级"入口
- [ ] 订阅列表显示上次搜索摘要
- [ ] 日历视图空状态优化

### Phase 5：反馈闭环

- [ ] 订阅搜索日志（前端可查看每次搜索的结果）
- [ ] 下载完成通知（toast 或订阅列表角标）
- [ ] 洗版完成通知 + 自动标记 completed

---

## 七、不做的事

- ❌ 不做独立的订阅管理页面（保持在发现页的订阅 tab 内）
- ❌ 不做 RSS feed 解析（我们的直搜源已经够用，RSS 只是搜索的一种方式）
- ❌ 不做复杂的质量档案系统（Sonarr 那套太重，我们用 quality_score 数值对比就够）
- ❌ 不做订阅分享/导入导出（个人 NAS 工具不需要）
