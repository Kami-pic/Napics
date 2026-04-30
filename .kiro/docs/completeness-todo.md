# [完成] 季集完整性检测 — 基于刮削源的缺失分析

> 来源：2026-04-29 用户需求，从 clean-name-fix-todo 拆出
> 核心思路：不靠本地文件名推断季集结构，从 TMDB 获取完整季/集目录，跟本地已有文件做差集
> 状态：2026-04-30 全部完成，已归档到 devlog

---

## 设计思路

### 问题

当前无法知道一部剧"缺了什么"。用户只能肉眼数文件，没有系统级的完整性视图。

### 方案

以 TMDB 为权威数据源，获取一部剧的完整季/集结构，与本地树结构中的实际文件做比对，输出缺失清单。

### 数据流

```
TMDB /tv/{id}                    → seasons_info: [{season_number, episode_count}, ...]
TMDB /tv/{id}/season/{n}         → episodes: [{episode_number, name, air_date}, ...]
本地树结构（media_library.json） → 按路径统计每季下有哪些集号（从文件名/NFO 提取）
差集 = TMDB 全集 - 本地已有集   → 缺失清单
```

### 关键设计决策

1. **TMDB ID 来源**：优先从 NFO/刮削缓存中读取已有的 tmdb_id（`shadow_tmdb_id` 或 tvshow.nfo），没有则需要先刮削
2. **本地集号提取**：从 episode.nfo 的 `<episode>` + `<season>` 读取（最可靠），回退到文件名正则提取
3. **季级别 vs 集级别**：
   - 季级别：TMDB 有 S1-S6，本地只有 S1-S5 → 缺 S6（整季缺失）
   - 集级别：TMDB S3 有 E01-E13，本地有 E01-E06, E08-E13 → 缺 S3E07
4. **特别篇处理**：Season 0（特别篇）默认不计入完整度，可选展示
5. **缓存策略**：TMDB 季集数据复用现有 scrape_cache（`tv{id}_s{n}.json`），已有缓存直接用

---

## 实现步骤

### 后端

- [x] **1. 新增 completeness 业务模块**（`completeness.py`）
  - `collect_local_episodes(folder_path)` — 递归统计本地季/集号（NFO 优先，文件名回退）
  - `get_tmdb_id_from_folder(folder_path)` — 从 NFO 获取 TMDB ID
  - `compute_completeness(tmdb_client, tmdb_id, local_episodes)` — 与 TMDB 做差集
  - 验证：19 个单元测试全部通过

- [x] **2. 本地集号统计函数**（集成在 `completeness.py` 的 `collect_local_episodes` 中）
  - NFO 优先读取 season_number + episode_number
  - 回退：文件名正则提取（S01E02 / EP02 / 第2集 / 纯数字）
  - 季号从目录名推断（Season 1 / S02 / 第3季）

- [x] **3. 新增 API 端点** `GET /library/completeness?path=...&tmdb_id=...`
  - tmdb_id 可选（不传则从 NFO 读取）
  - 返回完整度 JSON（季列表 + 缺失集 + 百分比 + 未播出标记）
  - 无 tmdb_id 返回 `{status: "no_tmdb_id"}`

### 前端

- [x] **4. CompletenessBar 组件**（`components/detail/CompletenessBar.tsx`）
  - 总进度条 + 百分比
  - 季标签列表（✓ 完整 / ⚠️ 部分缺失 / ✗ 整季缺失）
  - 点击部分缺失的季展开集列表
  - 未播出的集显示 📅 标记
  - 缺失集/季可点击触发搜索

- [x] **5. FolderDetail 集成 + 搜索联动**
  - tv/season 类型文件夹自动显示完整度
  - 点击缺失集 → onSearch 传入精确搜索词（如 "Breaking Bad S05E07"）
  - 复用现有 SearchModal 的 cnName/enName/seasonNumber 参数

### 缓存与批量预计算

- [x] **6. 持久化缓存层**（`completeness.py` 内 `completeness_cache.json`）
  - 前端请求优先读缓存秒返回，无缓存时才请求 TMDB
  - 刷新按钮（`refresh=true`）清除 TMDB 缓存 + 重新计算 + 写入缓存
  - scan/sync 完成后自动刷新受影响的 TV 文件夹完整度（后台线程）

- [x] **7. 批量预计算**
  - API：`POST /library/completeness/refresh-all`（后台线程执行）
  - 脚本：`_batch_completeness.py`（一次性跑所有 TV 文件夹）
  - 遍历 NAS 路径下 tv 标签目录，找到有 tmdb_id 的文件夹逐个计算并缓存

---

## 边界情况

- 正在播出的剧：TMDB 可能有未播出的集（air_date 在未来），标记为"未播出"而非"缺失"
- 绝对集数编排（如长篇动画）：需要用 `build_absolute_episode_map` 做映射
- 多版本文件（如同一集有 720p 和 1080p）：按集号去重，不重复计数
- 聚合文件夹（collection/series）：递归子文件夹分别计算
- season 类型节点：只计算该季的完整度，不需要跨季

---

## 不做的事

- 不自动下载缺失集（那是搜索+下载模块的事）
- 不改变现有的刮削流程

---

## 技术债务

- `media_library.json` 中已有的脏数据（如 `clean_name_en: "02"`）需要一次性清洗脚本修复
- `1984` 等纯数字作品名在 strip_noise 步骤 13 中被误删（尾部纯数字集号清理），暂不处理
