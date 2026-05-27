# 整理流水线 V3 — 三段式解耦架构

## 核心理念

v2 的问题：先猜后做（正则猜季号 → 物理挪文件 → 再刮削，猜错则全崩）。
v3 的核心：先问后做（物理结构与逻辑确权完全解耦，NFO 是唯一真理）。

```
阶段一（物理隔离）：只做最安全的事 — 散装视频包进文件夹，绝不猜季号
阶段二（确权）    ：问 TMDB 拿官方答案，写进 NFO
阶段三（执行）    ：读 NFO 执行物理操作和影子名生成，不再看原始文件名
```

## Pipeline 执行顺序

```
Step 0: 散落视频基础封装（仅 movie 标签下的一级分类目录）
Step 1: 旧刮削智能处理（保留有效 NFO，清理无效残余）
Step 2: 分析判定（classify_folder，传递 folder_type + category_hint）
Step 3: 刮削确权（TMDB 查询 + 绝对集数映射 + 写 NFO）
Step 4: 依据 NFO 结构归位（建季目录、挪文件）
Step 5: 影子名生成与写入（严格读 NFO 拼接）
```

## 各步骤要点

### Step 0: 散落视频基础封装
- 仅在一级分类目录执行（`_is_top_category`）
- movie 标签下：散落视频封装进独立文件夹
- tv 标签下：完全不动，等 Step 4 根据 NFO 建季目录
- 实现：`organizer.wrap_loose_videos_in_category(path, category_tag=...)`

### Step 1: 旧刮削智能处理
- 读 NFO，`<title>` 非空 → 保留；为空或无法解析 → 打包备份后删除
- 有效 tvshow.nfo（含 TMDB ID）→ Step 3 直接用（父级信任锁定）
- 递归遍历所有子目录
- 实现：`organizer.smart_archive_plan()` + `smart_archive_recursive()`

### Step 2: 分析判定
- `category_hint` 和 `folder_type` 只判定一次，全程传递
- 实现：`analyzer.analyze_folder(path, library, category_hint=...)`

### Step 3: 刮削确权
- 按 folder_type 分发：movie → `_scrape_movie`，tv → `_scrape_tv_v3`，聚合 → `_scrape_collection`
- TV 确权三步：确定 TMDB ID → 建绝对集数映射表 → 遍历视频写 episode.nfo
- 绝对集数阈值 > 50 判定为绝对集数（保守阈值）
- 特别篇智能识别：路径中含以下关键词 → 强制 Season 00
  - 关键词列表：sp, sp00~sp03, menu, ova, omake, extra, extras, bonus, trailer, ncop, nced, interview, featurette
- 支持 AI 旁路（`use_ai=true`）和白名单过滤（`whitelist`）
- 支持 dry_run：只计算 plan 不落盘

### Step 4: 依据 NFO 结构归位
- `reorganize_seasons_by_nfo`：读 episode.nfo 的 `<season>` 建季目录并移入
- 没有 NFO 的文件完全不动
- 季目录名标准化为 `Season XX`
- 关联文件（.nfo, poster, 字幕）同步移动

### Step 5: 影子名生成
- `generate_shadow_name_from_nfo`：严格读 NFO 拼接，不回退到文件名清洗
- movie：`中文名 英文名 (年份)`
- tv/season：`剧名 英文名 S01E01`
- 聚合容器内子视频：按 movie 逻辑各自独立
- `generate_folder_shadow_name`：文件夹级影子名（tv/movie 有，聚合容器无）

## 两个 API 入口

### 入口 A：纯结构整理 `/organize/structure`
- 不联网，只按本地已有 NFO 归位
- 执行 Step 0 + Step 4，跳过 1/2/3/5

### 入口 B：一键完全整理 `/organize/full`
- 两段式提交：`dry_run=true` 返回 Action Plan → `dry_run=false` 执行
- 完整跑 Step 0~5
- 支持 `use_ai` 开关和 `whitelist` 白名单

### 沙盘推演（dry_run=true）
- 完整执行 Step 0~3 的计算逻辑，严禁落盘
- 返回 Action Plan JSON：tmdb_match + plan（每个视频的映射结果）+ summary
- 前端展示预览面板，用户确认后触发执行

## 各类型完整处理流程

### movie
Step 0 跳过 → Step 1 智能处理旧刮削 → Step 2 classify=movie → Step 3 搜 TMDB 写 movie.nfo → Step 4 无需归位 → Step 5 读 NFO 生成影子名

### tv
Step 0 不封装 → Step 1 保留有效 tvshow.nfo → Step 2 classify=tv → Step 3 确权式刮削（TMDB ID + 映射表 + episode.nfo） → Step 4 读 NFO 建季目录 → Step 5 读 NFO 生成影子名

### collection / series / mixed
Step 0 散装封装（仅 movie 标签一级目录） → Step 1 智能处理 → Step 2 classify → Step 3 不写父目录 NFO，递归子目录独立刮削 → Step 4 无需归位 → Step 5 各子视频独立影子名

## 降级与兜底

| 风险 | 兜底策略 |
|------|----------|
| TMDB 搜不到 | 不写 NFO，不动文件，不生成影子名 |
| 绝对集数超出映射表 | 跳过该文件 |
| 文件名无法提取集号 | 跳过该文件（AI 开启时尝试 AI 提取） |
| get_episode_detail 404 | 写简化 NFO（只有 showtitle + season + episode） |
| 旧 NFO 的 TMDB ID 失效 | fallback 到重新搜索 |
