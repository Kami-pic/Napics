# [TODO] 订阅系统（阶段 3）

> 用户在发现页/搜索结果中订阅影片 → 系统定时自动搜索资源 → 通知或自动下载 → 归位到媒体库。
> 分三个子阶段，每阶段可独立交付。

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

## 子阶段 B：定时搜索 + 资源匹配 + 通知/自动下载

### B.1 后端：订阅搜索引擎

- [ ] 新建 `backend/subscribe_searcher.py`
- [ ] 搜索词构造 — Search Group 动态构造：
  - 电影：`[cn_name, en_name + year]`
  - 剧集/动漫：`[cn + 季号, en + 季号, jp + 季号]`（从 aliases 读取）
  - 自定义 `search_keyword` 优先级最高
- [ ] BT 通道：复用 `enhanced_search()`，但改为 Search Group 模式（多词并查、结果按 info_hash 去重、取最优）
- [ ] 网盘通道（可选）：复用 `PanSearchService.search_sync()`，仅搜中文名
- [ ] 质量过滤：`parse_quality()` 解析 → 检查是否满足订阅的 `quality` 最低要求
- [ ] 包含/排除过滤：`include` / `exclude` 关键词匹配
- [ ] 剧集匹配：从种子标题提取集号，对比 `downloaded_episodes`，只保留缺失集
- [ ] 电影匹配：搜到满足质量要求的资源即可
- [ ] 订阅指纹去重：已下载集的 `info_hash` 不再重复推送

### B.2 后端：搜索频率衰减

- [ ] `should_search_now(subscription)` 判断函数：
  - 新订阅前 72h：每 4h 搜一次
  - 3-14 天未命中：每 12h
  - 14-30 天未命中：每 24h
  - 30 天未命中：自动 `state=paused` + `note="长期未找到资源，已自动暂停"`
- [ ] 找到资源后重置 `search_count` 和衰减计时
- [ ] `config.json` 新增 `subscribe_interval_hours`（基础间隔，默认 4）

### B.3 后端：定时任务

- [ ] 后台线程定时遍历活跃订阅（`threading.Timer` 循环）
- [ ] 每个订阅间随机延迟 30-120 秒（防限频）
- [ ] 单源超时/失败不影响其他源，自动降级
- [ ] 搜索结果处理：
  - `mode=notify` → 更新 `found_resources` 列表
  - `mode=auto` → 调用 `DownloadManager.submit()` 下载，传入 `subscription_id` + `subscription_episode`
- [ ] 下载完成回调：更新 `downloaded_episodes`（写入指纹信息）
- [ ] 电影下载完成 → `state=completed`
- [ ] 剧集全部集数下载完成 → `state=completed`
- [ ] 启动时恢复定时任务（`on_startup`）

### B.4 前端：订阅管理增强

- [ ] 订阅管理面板显示搜索状态：上次搜索时间、下次预计搜索时间、累计搜索次数
- [ ] 通知模式：`found_resources` 不为空时显示 🔔 角标 + 资源列表（复用搜索结果 UI）
- [ ] 用户从 found_resources 中选择资源 → 手动触发下载
- [ ] 订阅卡片状态角标：🔔 有新资源 / ✓ 已完成 / ⏸ 已暂停 / 🔍 搜索中
- [ ] 剧集订阅进度条增强：显示每集的下载状态（已下载/缺失）

---

## 子阶段 C：剧集日历 + 媒体库联动 + 洗版对接

### C.1 订阅日历

- [ ] `GET /subscribe/calendar` — 返回订阅影片的更新时间线
- [ ] 剧集用 TMDB 的 episode air_date 构建播出日历
- [ ] 前端日历视图（可选）：时间线展示即将更新的剧集
- [ ] 新集播出当天自动触发一次搜索（不等定时任务）

### C.2 媒体库联动

- [ ] 新增订阅时自动检查媒体库已有集数（复用 `local_media_matcher`）
- [ ] 剧集订阅自动填充 `downloaded_episodes`（已有集标记为 local）
- [ ] 下载完成后可选触发整理流水线归位（`file_relocator`）
- [ ] 归位完成后更新 `media_library.json`

### C.3 洗版对接（依赖阶段 4 质量评分系统）

- [ ] `best_version=true` 时，搜索不受"已下载"限制
- [ ] 新资源 `quality_score` > 已有 `quality_score` + threshold → 触发下载替换
- [ ] 替换流程复用 `file_relocator`（旧版进回收站）
- [ ] 电影洗版：不自动 completed，持续搜索直到用户手动关闭
- [ ] 剧集洗版：按集独立比较分数

---

## 技术要点

- 订阅数据 JSON 持久化，读写加锁（参考 download_manager.py 的 debounce 写入）
- 所有搜索复用现有模块，不重复造轮子
- DownloadTask 的 subscription_id 是订阅→下载→回调的关键纽带
- 别名在订阅创建时预拉取并缓存，避免每次搜索都请求外部 API
- 搜索频率衰减保护 Prowlarr 和站点，新订阅高频、老订阅低频
- 前端订阅状态启动时拉取一次，之后通过操作实时更新本地缓存
