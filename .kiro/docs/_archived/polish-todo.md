# [废弃] 查漏补缺 — 全局打磨与 Bug 修复（原版归档）

> 本次对话主要完成：P0/P1 Bug 修复 + P2 功能完善。
> 关联文档：subscribe-todo.md / discover-recommend-todo.md / search-enhance-todo.md / bt-expand-todo.md / auto-replace-todo.md

---

## 本次对话完成的主要功能

### 新增组件（4 个）
- `SearchSettingsPanel.tsx` — SearchModal 内搜索源开关面板
- `SubscribeConfigModal.tsx` — 订阅配置弹窗（质量/模式/洗版/关键词/路径/源选择）
- `SubscribeSourceSelect.tsx` — 可复用的订阅源选择组件
- `rss_source_nyaa.py` — Nyaa RSS 源（接入订阅框架）

### 新增后端接口（2 个）
- `GET /search/sources` — 搜索源列表（BT + 网盘）
- `PUT /search/sources/{name}` — 搜索源开关切换

### 架构改动
- 探索二级 tab 从 ExplorePage 移到 DiscoverHeader（统一所有 tab 高度）
- 订阅筛选栏从 SubscribeInline 移到 DiscoverHeader（合并一行）
- /search/single 的 skip_filter 模式改为线程池并行调用 5 个直搜源
- 订阅时自动补全 tmdb_id（用 TMDB 搜索）
- 发现页统一使用 SearchModal 作为搜索下载入口

---

## 用户报告的所有 Bug（30 项）

### 第一批：初始报告

| # | Bug | 状态 | 改动 |
|---|-----|------|------|
| 1 | 网盘搜索应优先使用中文 | ✅ | SearchModal 搜索标签顺序：纯中文排最前 |
| 2 | 点击订阅 tab 顶部高度矮 | ✅ | 统一二级 tab 容器 + minHeight:100vh 撑滚动 |
| 3 | 发现页搜索弹窗调用的是旧版 | ✅ | ExpandDetail 改为打开 SearchModal |
| 4 | 综合推荐匹配错误（航海王→跨界电影） | ✅ | _is_same_media 加严：短标题完全包含+长标题70%重叠 |
| 5 | 冰湖重生配图是夜魔侠 | ✅ | _dedup_and_merge 封面合并改为仅 ID 匹配时覆盖 |
| 6 | 订阅 tab 搜索缺少 loading | ✅ | 改为打开 SearchModal |
| 7 | 订阅搜索为什么不调用搜索资源弹窗 | ✅ | 同 #6，通过 onOpenSearch 回调 |
| 8 | 前端看不到订阅日历 | ✅ | SubscribeCalendar + DiscoverHeader 二级 tab 切换 |
| 9 | 前端看不到自动洗版开关 | ✅ | SubscribeConfigModal 中 best_version 开关 |
| 10 | 前端看不到订阅源选择 | ✅ | SubscribeSourceSelect 组件集成到配置面板 |
| 11 | 探索地区折叠后没有"其他" | ✅ | 添加"其他"Pill + 展开冷门地区列表 |
| 12 | 豆瓣电视剧缺少综艺标签 | ✅ | DOUBAN_TV_TAGS 添加"综艺" |
| 13 | 网盘搜索片源标签样式不一致 | ✅ | 来源标签改为统一小标签样式 |
| 14 | 发现页排行角标样式需调整 | ✅ | 改为矩形设计，与评分标签对齐 |

### 第二批：验证后追加

| # | Bug | 状态 | 改动 |
|---|-----|------|------|
| 15 | 订阅列表展开几百条不匹配的结果 | ✅ | 移除 FoundResourcesList 自动展开，改为一行通知 |
| 16 | 订阅 tab 高度还是没改好 | ✅ | 多轮修复，最终统一 flex 容器 |
| 17 | 搜索框聚焦后高度也不对 | ✅ | 搜索模式用 invisible button 撑高度 |
| 18 | 订阅二级 tab 高度不一致 | ✅ | 所有 tab 共用同一个 flex 容器 |
| 19 | 推荐/探索/订阅切换应该置顶 | ✅ | setPrimaryTab 时 scrollToDiscover(true) |
| 20 | 订阅机制不清晰 | — | 理清追更 vs 下载的区别（非代码改动） |
| 21 | 探索二级 tab 高度被改坏了 | ✅ | 探索二级 tab 从 ExplorePage 移到 DiscoverHeader |
| 22 | 订阅二级 tab 和筛选合并一行 | ✅ | 左边视图切换 + flex-1 + 右边筛选（样式区分） |

### 第三批：再次验证

| # | Bug | 状态 | 改动 |
|---|-----|------|------|
| 23 | BT 搜索完全不工作 | ✅ | /search/single skip_filter 模式改为线程池并行合并直搜源 |
| 24 | 网盘搜索用中文不是 BT | ✅ | 确认网盘搜索已用中文（query=title） |
| 25 | 新加的 BT 源看不到 | ✅ | 同 #23，直搜源结果现在会合并 |
| 26 | 默认下载路径没有 placeholder 显示 | ✅ | savePath 初始为空，placeholder 显示默认路径 |
| 27 | 探索刷新按钮丢失 | ✅ | 加回刷新按钮 + refreshTrigger 机制 |
| 28 | 切换 tab 回顶部不稳定 | ✅ | 改为 setTimeout 50ms 延迟 |
| 29 | 订阅日历为空 | ✅ | 订阅时自动补全 tmdb_id（search_tv/search_movie + 年份校验） |
| 30 | 发现页 SearchModal 和媒体库不是同一个 | ✅ | 传入 defaultSavePath，统一 SearchModal |

---

## P2 功能完善状态

| # | 功能 | 状态 |
|---|------|------|
| 2.1 | 订阅配置面板 | ✅ |
| 2.2 | 快速同步文件变化检测 | ✅（已有实现） |
| 2.3 | subscribe_interval_hours | ✅ |
| 2.4 | Nyaa RSS 接入 | ✅ |
| 2.5 | 详情匹配候选面板 | ✅ 刮削用 CandidatePicker + 发现页 ExpandDetail 候选选择 |
| 2.6 | 搜索进度条 | ✅ SSE 流式搜索 /api/search/stream + 前端各源实时状态 |
| 2.7 | SearchModal 搜索设置面板 | ✅ |
| 2.8 | 日历视图 | ✅ |
| 2.9 | 综合推荐冷门降权 | ✅ |
| 2.10 | 豆瓣→TMDB ID 映射 | ✅ local_media_matcher 异步补全 + 榜单主动补全 |
| 2.11 | 手动洗版增强 | ✅ |
| 2.12 | dry_run 预览 | ✅ routes/organize.py + routes/relocate.py 全部支持 |
| 2.13 | 订阅源选择组件 | ✅ |

---

## 搁置（不做）

- ❌ 其他网盘转存（7.2~7.5）— 逆向成本高
- ❌ 自动整理开关（3.1~3.4）— 风险高需配套
- ❌ 新旧共存检测（5.2~5.3）— 边界复杂
- ❌ 其他字幕组 RSS — 蜜柑已覆盖

---

## 待新对话校验的项目

> 以下改动已通过后端测试（13/13）和前端构建，但需要用户在浏览器中实际验证。

- [ ] 发现页 SearchModal 搜索是否能返回结果（含直搜源）
- [ ] 订阅/探索/搜索模式的 sticky header 高度是否一致
- [ ] 探索二级 tab 刷新按钮是否正常
- [ ] 切换一级 tab 是否稳定回顶部
- [ ] 订阅日历是否显示播出时间（新订阅的剧集）
- [ ] 保存路径 placeholder 是否显示默认 NAS 路径
- [ ] 订阅配置面板是否正常弹出（质量/模式/洗版/源选择）
- [ ] SearchModal ⚙️ 搜索源设置是否正常

---

## 技术债务

- [ ] `pan_models.py` 的 4 个 `@validator` 迁移到 Pydantic V2 `@field_validator`（Pydantic V3 会移除 V1 风格）
- [ ] `routes/search.py`（507 行）超过 400 行限制，`_merge_bt_extra_sources` 和 SSE `_generate` 应下沉到业务层
- [ ] `routes/discover.py`（700+ 行）超过 400 行限制，`_async_enrich_tmdb_ids`、`douban_hot` 等应下沉到业务层
- [ ] 后端日志从 `print()` 迁移到 `logging` 模块（统一日志级别和格式）

> 以下项目从各旧 TODO 转移到本文档统一跟踪，原文件中已标注"→ 已转移到 polish-todo"。

### 来自 subscribe-todo.md
- A.2 下载完成回调 → ✅ 已确认实现（sync_progress 中调用 _notify_subscription_complete）
- A.4 订阅配置面板 → ✅ SubscribeConfigModal
- B.4 subscribe_interval_hours → ✅ AppConfig 新增字段
- B.7 Nyaa RSS 源 → ✅ rss_source_nyaa.py
- B.7 其他字幕组 RSS → 搁置
- C.2 快速同步文件变化检测 → ✅ 已确认实现（routes/library.py）
- C.3 下载完成触发归位 → ✅ 已在回调链路中（洗版模式自动归位）
- C.4 新集播出自动搜索 → ✅ 日历触发已实现（rss_engine._check_calendar_trigger）
- C.4 前端日历视图 → ✅ SubscribeCalendar + DiscoverHeader 二级 tab
- 4.4 手动洗版增强 → ✅ quality_score 显示 + isHigher 升级

### 来自 discover-recommend-todo.md
- 1.1 豆瓣→TMDB ID 映射 → ✅ local_media_matcher 异步补全 + 榜单主动补全
- 1.10 详情匹配候选面板 → ✅ 刮削 CandidatePicker + 发现页 ExpandDetail 候选选择
- 1.10 匹配算法优化 → ✅ 去重加严 + 封面合并修复
- 2.0.1 冷门降权 → ✅ score × 0.8
- 2.0.1 local_status 综合推荐 → 搁置
- 阶段 4（质量评分+洗版）→ ✅ 在 subscribe-todo 中已完成

### 来自 search-enhance-todo.md
- 7.2~7.5 网盘转存 → 搁置（不做）
- 阶段五 设置页 → ✅ 改为 SearchModal 内搜索设置面板

### 来自 bt-expand-todo.md
- 4.3 Nyaa RSS 源 → ✅ rss_source_nyaa.py
- 6.3 搜索进度条 → ✅ SSE /api/search/stream + 前端各源实时状态
- 6.4 搜索源开关 → ✅ SearchSettingsPanel + /search/sources 接口

### 来自 auto-replace-todo.md
- 1.1~1.3 下载完成刷新 → ✅ "📂 查看"按钮 + navigate-to-folder + 自动局部刷新
- 3.1~3.4 自动整理开关 → 搁置
- 5.2~5.3 新旧共存检测 → 搁置
- 5.5 dry_run 预览 → ✅ routes/organize.py + routes/relocate.py

---

## 2026-04-19 实测发现的问题（从 search-matching-todo 迁入）

### Prowlarr 索引器与爬虫源解耦
- [x] Prowlarr 中的 mikan、nyaa 索引器和爬虫源没有解耦，完全混淆，分不清源。
- [x] 索引器列表不应该混入非 Prowlarr 的源（如 xl720、磁力熊），索引器就是从prowlarr获取的。
- [x] SSE 结果标记 _source 字段区分来源，disabledSources 按 _source 过滤
- [x] Prowlarr 索引器下拉只从 _source=prowlarr 的结果中提取

### FilterBar 筛选无效
- [x] 用户反馈"过滤按钮完全没有用"，需重启服务后复现确认，筛选需要重做重新理逻辑。
- [x] 根因：disabledSources 存 "prowlarr" 但结果的 indexer 是具体索引器名，改为按 _source 过滤
- [x] Prowlarr 索引器筛选只对 _source=prowlarr 的结果生效，直搜源不受影响

### 封面丢失
- [x] 关闭 clash 后推荐卡片封面丢失，详情页却有封面（缓存/代理问题）
- [x] proxyUrl 增加 image.tmdb.org 代理支持
- [x] 后端 proxy_image 对非豆瓣图片不带 Referer

### 非 TMDB 源缺少英文名
- [x] 发现页豆瓣/Bangumi 条目没有英文名，导致 BT 搜索只能用中文
- [x] 需要在 normalizeItem 中补充英文名获取逻辑
- [x] douban_hot enrich_item 和 _async_enrich_tmdb_ids 补全英文名到 original_title
- [x] Bangumi get_hot_anime 补充 original_title 字段
- [ ] 注意：异步补全，首次请求可能无英文名，需清缓存后第二次请求才有

### XL720 标题改进
- [x] xl720 没有 dn 参数时用序号代替哈希区分
- [x] 改为 BeautifulSoup 提取 <a> 标签上下文文字

### 索引器连接状态
- [x] 索引器设置面板显示连接状态（绿/红/黄/灰圆点）
- [x] 从 Prowlarr API 获取真实优先级（prowlarr_priority）
- [x] 每次打开设置面板都从 Prowlarr 同步最新索引器列表和状态

### 磁力熊标题改进
- [x] 用 BeautifulSoup 提取详情页 <a> 标签文字作为文件名
- [x] 中文搜索标题 + 英文文件名拼接

### SSE 超时修复
- [x] as_completed 超时后 catch TimeoutError，推送 failed 状态
- [x] SSE 总超时 65s，前端超时 90s
- [x] Prowlarr 搜索超时恢复 60s

### 多语言搜索词构造
- [x] SSE 接口新增 cn_name/en_name 参数
- [x] Prowlarr/Bitsearch 用英文搜索词
- [x] 磁力熊/XL720 用中文搜索词
- [x] Nyaa/蜜柑 用原名（日文/英文）
- [x] 前端 SearchModal 传递 cnName/enName 到 SSE

### 源开关全选/反选
- [x] BT FilterBar SourceToggleBar 新增全选/反选
- [x] 网盘 PanFilterBar 同步新增全选/反选

### L1-L4 后续迭代（从 skill-build-todo 迁入）
- [x] 多语言搜索词构造（SSE 不同源用不同语言搜索词）— 基础实现完成，完整设计见 multilang-search-todo.md
- [ ] 前端搜索框交互与多语言分配冲突（用户手动输入后所有源用同一个词）→ 新对话解决
- [ ] 媒体库清洗名"未设置"问题（树构建时动态计算可能覆盖）→ 新对话排查
- [ ] 发现页豆瓣信息匹配不上 + 封面丢失（特定条目）→ 新对话排查
- [ ] 媒体库批量 TMDB 搜索补全英文名（665 条只有中文）→ 新对话执行
- [ ] 业务 Skill 建设（S1-S5）→ 见 business-skills-plan.md
- [ ] 根据实战反馈修订 skill 文档
- [ ] 刮削候选、推荐去重等场景验证 L1-L4
- [ ] skill 文档定稿 + 通用代码模板 + 配置模板
- [ ] BT 标题含集号时 match_chain 匹配度下降（parse_filename 集号识别）
- [ ] 多译名匹配依赖目标列表完整性（别名列表补充）
