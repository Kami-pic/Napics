# 整理流水线 V3 重构 — TODO 清单

参考设计文档：`.kiro/docs/organize-guide-v3.md`

---

## Phase 1：基础设施（数据结构扩展，无破坏性）

### 1.1 tmdb_client.py — parse_filename 升级
- [x] 新增 `absolute_episode` 返回字段，默认 `None`
- [x] 在所有现有匹配逻辑之后，增加绝对集数判定：
  - 条件：`episode is not None` 且 `season == 1` 且文件名无明确季号特征（无 `S\d+`/`第X季`/`Season`）且 `episode > 50`
  - 动作：`absolute_episode = episode`，`season = None`，`episode = None`
- [x] 新增纯数字文件名匹配（如 `060.mkv`，去掉扩展名后整个是数字）
- [x] 验证：`060.mkv` → `{"absolute_episode": 60, "season": None, "episode": None}`
- [x] 验证：`S01E25.mkv` → `{"episode": 25, "season": 1, "absolute_episode": None}`（不误判）
- [x] 验证：`[字幕组] 作品名 [26].mkv` → `{"episode": 26, "season": 1}`（26 < 50，不触发）

### 1.2 tmdb_client.py — ScrapeResult 扩展
- [x] `ScrapeResult` 新增字段 `seasons_info: List[Dict] = []`
- [x] `get_tv_detail` 中从 TMDB 响应提取 seasons 数组，存入 `seasons_info`
- [x] 确认旧缓存兼容（`ScrapeResult(**cached)` 缺少 `seasons_info` 时默认 `[]`）

### 1.3 tmdb_client.py — 绝对集数映射函数
- [x] 新增 `build_absolute_episode_map(seasons_info)` 独立函数
- [x] 逻辑：遍历 `seasons_info`，跳过 `season_number == 0`，累加 `episode_count`
- [x] 返回 `Dict[int, Tuple[int, int]]`：`{1: (1,1), 2: (1,2), ..., 60: (4,1)}`
- [x] 验证：进击的巨人（S1=25集, S2=12集, S3=22集, S4=28集）→ `60 → (4, 1)`

### 1.4 scraper.py — NFO 格式扩展
- [x] `write_episode_nfo` 增加 `showtitle` 参数，写入 `<showtitle>` 标签
- [x] `read_video_nfo` 增加读取 `<showtitle>` 字段

### 1.5 Phase 1 验证
- [x] 语法检查通过（getDiagnostics）
- [x] 验证脚本 `_test_phase1.py` 全部通过（11 个 parse_filename + 2 个 ScrapeResult + 8 个映射表）

---

## Phase 2：核心流水线重构

### 2.1 scraper.py — 确权式 TV 刮削
- [x] 新增 `_scrape_tv_v3` 函数（支持 dry_run + use_ai 参数）
- [x] 第一步：确定 TMDB ID（父级信任锁定 or 搜索）
- [x] 第二步：构建绝对集数映射表
- [x] 第三步：遍历所有视频计算 plan
- [x] 第四步：落盘（仅 dry_run=False）
- [x] 修改 `scrape_folder` 的 tv 分支调用 `_scrape_tv_v3`
- [x] `scrape_folder` 签名新增 `dry_run` 和 `use_ai` 参数

### 2.2 organizer.py — 读 NFO 建季目录
- [x] 新增 `reorganize_seasons_by_nfo(folder_path, dry_run=True)`
- [x] 用 `os.walk` 遍历所有视频，读 NFO 取 season
- [x] 没有 NFO 或没有 season → 完全不动
- [x] 移动视频 + 关联文件（.nfo, poster, 字幕）
- [x] 季目录名标准化（第1季 → Season 01，SP/OVA 不动）

### 2.3 organizer.py — 上下文传递修复
- [x] `organize_folder` 加 `category_hint` 参数，传给内部 `analyze_folder`
- [x] `wrap_loose_videos_in_category` 加 `category_tag` 参数，tv 时跳过
- [x] `rename_videos_in_folder` 递归子文件夹时传 `category_hint`

### 2.4 organizer.py — 影子名生成重写
- [x] 新增 `generate_shadow_name_from_nfo(video_path, folder_path, folder_type)`
- [x] 新增 `generate_folder_shadow_name(folder_path, folder_type)`

### 2.5 analyzer.py — 移除 tv 的 split_seasons
- [x] `_diagnose_structure` 中 tv 类型的 `split_seasons` 操作已移除

### 2.6 Phase 2 验证
- [x] 语法检查通过（getDiagnostics 四个文件全部无错误）
- [ ] 样本测试（需要实际 NAS 数据，等 Phase 3 API 入口完成后一起测）

---

## Phase 3：API 入口 + 沙盘推演

### 3.1 main.py — 入口 A：纯结构整理
- [x] 新增路由 `POST /organize/structure`
- [x] 参数：`path: str`, `dry_run: bool = True`
- [x] 逻辑：判断一级分类 → 封装 → `reorganize_seasons_by_nfo`
- [x] 不联网、不查 TMDB、不写 NFO、不生成影子名

### 3.2 main.py — 入口 B：一键完全整理
- [x] 新增路由 `POST /organize/full`
- [x] 参数：`path`, `dry_run`, `use_ai`, `request_body`（含 action_plan）
- [x] dry_run=True：推演模式，严禁文件系统写操作，返回 Action Plan
- [x] dry_run=False + action_plan：所见即所得执行，不重跑 AI/TMDB
- [x] dry_run=False 无 plan：兼容旧调用，完整跑一遍

### 3.3 main.py — 辅助函数
- [x] `_is_top_category(path)` — 判断一级分类目录
- [x] `_smart_archive_plan(path)` — 推演模式扫描旧刮削
- [x] `_smart_archive_recursive(path)` — 执行模式递归清理
- [x] `_execute_archive_plan(plan)` — 执行旧刮削清理 plan

### 3.4 main.py — 旧路由兼容
- [x] `/organize/one-click` 重定向到 `organize_full`
- [x] `/organize/folder` 加 `category_hint` 传递

### 3.5 Phase 3 验证
- [x] 语法检查通过
- [x] `import main` 正常

---

## Phase 4：AI 旁路

### 4.1 ai_organizer.py — AI 文件名提取
- [x] 新增 `ai_extract_episode(filename, config)` 函数
- [x] Prompt 设计：要求 LLM 返回严格 JSON
- [x] 字段校验 + 异常处理 + markdown 代码块提取
- [x] temperature=0

### 4.2 scraper.py — AI 旁路集成
- [x] `_scrape_tv_v3` 中集成 AI 旁路
- [x] 正则失败定义：season/episode/absolute_episode 三个全为 None
- [x] AI 成功 → method: "ai"，AI 失败 → method: "ai_failed"
- [x] plan 中每个 item 标注 `parsed.method`

### 4.3 Phase 4 验证
- [x] 语法检查通过

---

## Phase 5：前端适配

### 5.1 lib/api.ts — 新 API 封装
- [x] 新增 `structureOrganize(path, dryRun)` → `/organize/structure`
- [x] 新增 `fullOrganize(path, dryRun, useAi)` → `/organize/full`
- [x] 新增 `fullOrganizeExecute(path, actionPlan, useAi)` → 回传 Plan 执行

### 5.2 DetailDrawer.tsx — 按钮拆分
- [x] 原"一键整理"按钮拆为 [标准结构] + [一键整理]
- [x] [标准结构] 调 `structureOrganize`（快速，离线）
- [x] [一键整理] 调 `fullOrganize(path, true)`（先预览）
- [x] AI 开关：🤖 toggle 按钮，控制 `useAi` 参数

### 5.3 DetailDrawer.tsx — 预览面板
- [x] 收到 Action Plan 后展示预览信息
- [x] 显示 TMDB 匹配结果、视频列表、映射结果
- [x] 标注 method（regex/ai）
- [x] 显示跳过的文件及原因
- [x] [确认执行] 按钮回传 Plan 执行

### 5.4 Phase 5 验证
- [x] `npx next build` 编译通过
- [x] 修复已有的类型错误（VideoInfo import、DoubanHotItem 字段）

---

## 完成后收尾

- [ ] 更新 `.kiro/PROJECT_MEMORY.md`（流水线架构描述更新为 v3）
- [ ] 更新 `.kiro/docs/organize-todo.md`（标记 v3 重构完成）
- [ ] v2 guide 标记为 deprecated
