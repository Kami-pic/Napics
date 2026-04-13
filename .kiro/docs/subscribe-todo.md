# [TODO] 订阅系统（阶段 3 + 阶段 4）

> 用户在发现页/搜索结果中订阅影片 → 系统定时自动搜索资源 → 通知或自动下载 → 归位到媒体库。
> 阶段 3（A+B+C）+ 阶段 4 核心已完成。剩余低优先级尾巴见底部。

---

## 子阶段 A：订阅数据模型 + CRUD + 前端订阅入口

### A.1 后端：订阅数据模型与管理器

- [x] 新建 `backend/subscriber.py` — 订阅管理器
- [x] 数据持久化：`backend/subscriptions.json`
- [x] 订阅数据结构：
  ```json
  {
    "id": "uuid",
    "title": "流浪地球3",
    "year": "2027",
    "type": "movie",
    "tmdb_id": 12345,
    "douban_id": "36104Mo",
    "poster": "",
    "season": null,
    "total_episode": 0,
    "downloaded_episodes": {
      "1": {
        "info_hash": "abc123",
        "title": "[SubGroup] Title S01E01 1080p",
        "quality_tag": "WEB-DL-1080p-x265-AAC",
        "source": "prowlarr",
        "channel": "qb",
        "task_id": "uuid-xxx",
        "timestamp": "2026-04-13T10:00:00"
      }
    },
    "quality": "1080p",
    "include": "",
    "exclude": "",
    "save_path": "",
    "search_keyword": "",
    "aliases": {
      "cn": ["进击的巨人"],
      "en": ["Attack on Titan"],
      "jp": ["進撃の巨人"]
    },
    "state": "active",
    "mode": "notify",
    "found_resources": [],
    "best_version": false,
    "search_count": 0,
    "first_search": "",
    "last_search": "",
    "last_found": "",
    "created_at": "",
    "note": ""
  }
  ```
- [x] 电影不分集，用 `"0"` 作为 downloaded_episodes 的 key
- [x] 订阅状态机：`active` ↔ `paused`，全部下载完成 → `completed`
- [x] CRUD 方法：add / get / get_all / update / delete
- [x] 新增订阅时调用 `alias_resolver` 预拉别名，存入 `aliases` 字段
- [x] 新增订阅时检查媒体库是否已有（复用 `local_media_matcher`），已有则提示
- [x] 剧集订阅：从 TMDB 获取总集数填入 `total_episode`

### A.2 后端：DownloadTask 扩展

- [x] `DownloadTask` 新增 `subscription_id: Optional[str]` 字段
- [x] `DownloadTask` 新增 `subscription_episode: Optional[int]` 字段
- [ ] 下载完成回调时，通过这两个字段反向更新订阅的 `downloaded_episodes`
- [x] 确保 `download_tasks.json` 序列化/反序列化兼容新字段（旧数据缺失时默认 None）

### A.3 后端：订阅路由

- [x] 新建 `backend/routes/subscribe.py`
- [x] `POST /subscribe` — 新增订阅（传入 title/year/type/tmdb_id/douban_id/season/quality 等）
- [x] `GET /subscribe` — 查询所有订阅列表
- [x] `GET /subscribe/{id}` — 查询单个订阅详情
- [x] `PUT /subscribe/{id}` — 更新订阅（暂停/恢复/修改过滤条件）
- [x] `DELETE /subscribe/{id}` — 删除订阅
- [x] `POST /subscribe/{id}/search` — 手动触发单个订阅搜索（子阶段 B 实现搜索逻辑，此处先预留路由）
- [x] 在 `main.py` 中注册路由

### A.4 前端：订阅按钮与入口

- [x] 发现页详情面板（ExpandDetail）新增"订阅"按钮（搜索资源按钮旁边）
- [ ] 点击订阅弹出配置面板：质量偏好、包含/排除关键词、通知/自动模式、保存路径
- [x] 已订阅的卡片显示 📌 角标（DiscoverCard 组件）
- [x] 前端 `api.ts` 新增订阅相关 API 调用函数
- [x] 订阅状态通过 `/subscribe` 接口查询，前端启动时拉取一次缓存

### A.5 前端：订阅管理面板

- [x] Header 新增订阅入口图标（📌 或 🔔）
- [x] 订阅管理面板（侧边抽屉或独立区域）：
  - 订阅列表：海报缩略图 + 标题 + 状态标签 + 质量偏好
  - 操作按钮：暂停/恢复、删除、手动搜索、编辑
  - 剧集订阅显示进度（已下载集数 / 总集数）
  - 状态筛选：全部 / 活跃 / 已暂停 / 已完成

---

## 子阶段 B：RSS 订阅框架 + Prowlarr 源接入

> 核心目标：搭建可扩展的 RSS 订阅框架，Prowlarr 作为第一个源跑通全链路。
> 框架设计原则：源和框架解耦，新增源只需实现一个类并注册，不改框架代码。
> 重心放在剧集/番剧的周期性更新，电影订阅作为简化场景支持。

### B.1 后端：RSS 源接口标准化

- [x] 新建 `backend/rss_source_base.py` — RSS 源基类
- [x] `RSSItem` 标准化数据结构：title / download_url / pub_date / size / info_hash / quality_tag / episode / season / source_name
- [x] 源注册机制：`RSSSourceManager` 管理所有源，支持动态启用/禁用
- [x] 集号/季号提取工具：`extract_episode()` / `extract_season()`

### B.2 后端：Prowlarr 源实现（第一个源）

- [x] 新建 `backend/rss_source_prowlarr.py`，实现 `RSSSourceBase`
- [x] `fetch()` 从订阅 aliases 构造 Search Group 搜索（英文+日文+中文+标题，多词并查、info_hash 去重）
- [x] 剧集自动追加季号后缀（S01）
- [x] 自定义 `search_keyword` 优先级最高
- [x] `can_download()` / `get_download_url()` 实现

### B.3 后端：条目匹配引擎

- [x] 新建 `backend/rss_matcher.py` — 匹配 + 过滤逻辑
- [x] 质量过滤：`parse_quality()` → 检查是否满足订阅的 `quality` 最低要求
- [x] 包含/排除过滤：`include` / `exclude` 关键词匹配（排除 OR，包含 AND）
- [x] 剧集匹配：从标题提取集号，对比 `downloaded_episodes`，只保留缺失集
- [x] 电影匹配：搜到满足质量要求的资源即可
- [x] 指纹去重：已下载集的 `info_hash` 不再重复推送
- [x] 整季包识别（无集号但有季号 / 含 Complete/全集/Batch）

### B.4 后端：定时调度器

- [x] 新建 `backend/rss_engine.py` — `SubscriptionScheduler` 后台线程调度
- [x] 搜索频率衰减 `should_search_now()`：前 72h 每 4h，3-14 天每 12h，14-30 天每 24h，30 天无果自动暂停
- [x] 找到资源后重置计数器
- [x] 每个订阅间随机延迟 30-120 秒（防限频）
- [x] 遍历所有启用的 RSS 源，合并结果后匹配
- [x] 结果处理：notify → 存入 found_resources，auto → DownloadManager.submit()
- [x] 自动下载选择最佳条目（电影取最高 seeders，剧集每集取最高 seeders）
- [x] 启动时自动启动调度器（懒加载）
- [ ] `config.json` 新增 `subscribe_interval_hours`（基础间隔，默认 4）

### B.5 后端：RSS 源管理路由

- [x] `GET /subscribe/sources` — 查询所有 RSS 源及状态
- [x] `PUT /subscribe/sources/{name}` — 启用/禁用某个源
- [x] 手动搜索路由 `POST /subscribe/{id}/search` 真正实现（替换 A 阶段占位）

### B.6 前端：订阅管理增强

- [ ] 订阅面板显示搜索状态：上次搜索时间、累计搜索次数
- [x] 通知模式：`found_resources` 不为空时 🔔 角标 + 资源列表，用户手动选择下载
- [x] 手动搜索按钮真正生效
- [x] 订阅卡片状态标签：右下角信息行半透明样式（✓已有 / ↑可升级 / 📌已订阅 / 合并标签）
- [x] 推荐/探索/搜索三个场景统一支持订阅按钮+卡片角标
- [x] 订阅入口移到发现页一级tab（SubscribeInline 内嵌列表）
- [x] 一级tab点击+搜索框聚焦时自动置顶
- [x] 订阅按钮即时反馈（localSubscribed + justSubscribed）

### B.7 预留：后续源接入清单（不在本阶段实现）

- [ ] `rss_source_mikan.py` — 蜜柑计划（动画字幕组聚合，按番剧 RSS 订阅）
- [ ] `rss_source_nyaa.py` — Nyaa.si（日本动画/日剧 BT 站 RSS）
- [ ] `rss_source_rryingshi.py` — 人人影视（需攻克反爬/登录）
- [ ] 其他字幕组 RSS（ANi、喵萌、恋恋等）

---

## 子阶段 C：收尾完善（前端增强 + 日历 + 媒体库联动 + bug 修复）

> 目标：让订阅系统完整可用。洗版相关（C.3 + 阶段 4）整体后移。

### C.1 前端增强（原 B.6 剩余）

- [x] 订阅面板显示搜索状态：上次搜索时间、累计搜索次数
- [x] 通知模式资源列表：found_resources 展开显示（标题+质量+大小+做种数），用户手动选择下载
- [x] 选择资源后调用 DownloadManager 下载（传入 subscription_id）
- [x] 下载后清除该条 found_resources
- [x] 新建 `FoundResourcesList.tsx` 独立组件

### C.2 质量状态更新 bug 修复（千年女优问题）

- [ ] 手动替换文件后，快速同步应检测文件变化并重新 ffprobe 更新 height/resolution
- [ ] 确认快速同步的文件大小变化检测（差异>5%）是否覆盖了替换场景
- [ ] 如果文件名不变但内容变了（大小变了），也要触发重新扫描

### C.3 媒体库联动

- [x] 新增剧集订阅时自动扫描媒体库已有集数，填充 `downloaded_episodes`（标记 source="local"）
- [ ] 下载完成后可选触发整理流水线归位（`file_relocator`）

### C.4 剧集日历

- [x] `GET /subscribe/calendar` — 从 TMDB 拉剧集播出日期，返回时间线
- [ ] 新集播出当天自动触发一次搜索（不等定时任务）
- [ ] 前端日历视图（可选，优先级低）

### C.5 洗版对接

- [x] `best_version=true` 时，搜索不受"已下载"限制（rss_matcher 已实现）
- [x] 新资源 `quality_score` > 已有 + threshold → 选择下载（rss_engine._select_best_version 已实现）
- [ ] 替换流程复用 `file_relocator`（旧版进回收站）— 需要和归位替换流程打通

---

## 阶段 4：质量评分升级 + 自动洗版

- [x] 4.1 `compute_quality_score()` 100 分制综合评分（分辨率45+来源20+音频20+编码10+字幕5）
- [x] 4.1 `compute_quality_score_from_video()` 从视频条目算分
- [x] 4.1 `compare_quality_score()` 分数比较（阈值 5 分）
- [x] 4.2 `save_library()` 自动注入 quality_score 字段（所有保存路径统一注入）
- [x] 4.2 `local_media_matcher` 质量判断升级（优先用 quality_score，回退到 height）
- [x] 4.3 `rss_matcher._filter_episodes()` 支持 best_version 洗版模式
- [x] 4.3 `rss_engine._select_best_version()` 洗版模式质量比较（按集独立比较分数）
- [ ] 4.4 手动洗版增强：搜索结果按 quality_score 降序，标记比当前更好的

---

## 剩余尾巴（低优先级，按需推进）

- [x] 4.4 手动洗版增强：搜索结果附加 quality_score 字段（100 分制）
- [x] C.4 新集播出当天自动触发搜索（日历触发，绕过频率衰减）
- [x] C.3 下载完成后自动通知订阅管理器更新 downloaded_episodes
- [x] C.4 前端日历视图（SubscribeCalendar 组件，列表/日历切换）
- [ ] C.2 千年女优 bug：手动替换文件后质量状态不更新（需实际复现确认）
- [ ] B.7 新源接入：Mikan / Nyaa / 人人影视 / 字幕组 RSS

---

## 技术要点

- 订阅数据 JSON 持久化，读写加锁
- DownloadTask 的 subscription_id 是订阅→下载→回调的关键纽带
- 搜索频率衰减保护站点，新订阅高频、老订阅低频
- RSS 源框架：新增源只需实现 RSSSourceBase 并注册到 RSSSourceManager
