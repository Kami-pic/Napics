# 季集完整性检测

## 概述

以 TMDB 为权威数据源，获取剧集的完整季/集结构，与本地 NAS 文件做差集比对，输出缺失清单。支持持久化缓存、自动刷新、批量预计算。

## 核心数据流

```
TMDB /tv/{id}              → seasons_info（每季集数）
TMDB /tv/{id}/season/{n}   → episodes（每集编号+名称+播出日期）
本地文件系统               → collect_local_episodes（NFO 优先，文件名回退）
差集                       → missing_episodes + completeness_pct
```

## 后端架构

### 核心模块：`completeness.py`

| 函数 | 职责 |
|------|------|
| `collect_local_episodes(folder_path)` | 递归统计本地季/集号，返回 `{season: [episodes]}` |
| `get_tmdb_id_from_folder(folder_path)` | 从文件夹 NFO 获取 TMDB ID（当前目录 → 父目录） |
| `compute_completeness(tmdb_client, tmdb_id, local_episodes, include_specials=False)` | 与 TMDB 做差集，返回完整度数据 |
| `get_cached_completeness(path)` | 读缓存（线程安全） |
| `save_completeness_to_cache(path, data)` | 写缓存（线程安全） |
| `remove_from_cache(path)` | 从缓存中移除指定路径（线程安全） |
| `refresh_completeness_for_path(tmdb_client, path, clear_tmdb_cache=False)` | 刷新单个文件夹并写缓存 |
| `batch_refresh_all(tmdb_client, nas_paths, category_tags)` | 批量预计算所有 TV 文件夹 |
| `refresh_affected_folders(tmdb_client, changed_paths)` | 从变更文件向上找 TV 根目录并刷新 |

### 本地集号提取优先级

1. **NFO 读取**（最可靠）：`read_video_nfo` → `season_number` + `episode_number`
2. **文件名正则**（回退）：
   - `S01E02` / `S1E10` / `Season 1 Episode 2`
   - `第3季第7集` / `第1季E02` / `第2季02集`
   - `E02` / `EP12` / `第5集` / `02集`
   - `Unnatural-02`（连字符分隔）
   - `03.mkv`（独立数字）
   - 中文数字：`第一集` ~ `第九十九集`
3. **季号推断**：文件名无季号时从目录名提取（`Season 1` / `S02` / `第二季`）

### 缓存机制

- 文件：`backend/completeness_cache.json`
- 结构：`{folder_path: {status, tmdb_id, seasons, completeness_pct, _cached_at}}`
- API 默认读缓存秒返回，`refresh=true` 时清除 TMDB 缓存后重新计算
- 刷新按钮同时清除 `scrape_cache/tv_{id}.json` 和 `tv{id}_s_*.json`

### 自动刷新触发机制

挂钩点：`config_m.save_library()` 的回调（`shared.py`）

```
任何改变媒体库的操作
  → save_library()
    → 回调对比新旧路径集合
      → 找出变更的文件路径
        → 3 秒防抖 Timer
          → 后台线程 refresh_affected_folders
            → 从变更文件向上找 tvshow.nfo 定位 TV 根目录
              → 重新计算完整度 → 写入缓存
```

覆盖的场景（不需要穷举，因为都走 save_library）：
- 快速同步（新增/删除文件）
- 全量扫描
- 下载完成后局部刷新
- 整理流水线（重命名、结构归位、刮削）
- 批量管理（移动、删除、移除）
- 手动修改清洗名/影子名

### API 端点

| 端点 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/library/completeness` | GET | `path`, `tmdb_id?`, `refresh?` | 获取完整度（默认读缓存） |
| `/library/completeness/refresh-all` | POST | 无 | 批量预计算所有 TV 文件夹（后台线程） |

### 批量预计算

- 脚本：`_batch_completeness.py`（`cd backend && python _batch_completeness.py`）
- API：`POST /library/completeness/refresh-all`
- 逻辑：遍历 NAS 路径下 tv 标签目录 → 找有 tmdb_id 的文件夹 → 逐个计算并缓存

## 前端架构

### 组件：`CompletenessBar.tsx`

位置：`frontend/components/detail/CompletenessBar.tsx`
集成点：`FolderDetail.tsx`，tv/season 类型文件夹自动显示

### 显示状态

| 状态 | 显示 |
|------|------|
| 加载中 | 旋转图标 + "检查完整度..." |
| 无 TMDB ID | 不显示（组件返回 null） |
| 全部完整 | 绿色进度条 + "✓ 完整" |
| 部分缺失 | 蓝色/琥珀色进度条 + "X/Y 集 (Z%)" + 季标签列表 |
| 本地无数据 | "TMDB X 集 · 本地数据待同步" |

### 季标签交互

- **完整季**（绿色 ✓）：不可点击
- **部分缺失季**（琥珀色 X/Y）：点击展开集列表
- **整季缺失**（红色 ✗）：点击直接触发搜索

### 集列表交互

- **已播出缺失集**（红色）：点击触发搜索（如 "Breaking Bad S05E07"）
- **未播出集**（灰色 📅）：不可搜索，显示播出日期

### 刷新按钮

进度条右侧小图标，点击后 `refresh=true` 清除 TMDB 缓存重新请求，用于检测新季。

## 类型定义

```typescript
interface SeasonCompleteness {
  season_number: number;
  episode_count: number;      // TMDB 总集数
  local_count: number;         // 本地已有
  missing_episodes: { episode: number; title: string; air_date: string; aired: boolean }[];
  status: "complete" | "partial" | "missing";
}

interface CompletenessResult {
  tmdb_id?: number;
  title?: string;
  english_title?: string;
  total_seasons?: number;
  seasons?: SeasonCompleteness[];
  total_episodes?: number;
  local_total?: number;
  completeness_pct?: number;
  status: "ok" | "no_tmdb_id" | "no_tmdb_client" | "tmdb_error";
  message?: string;
}
```

## 边界情况

| 场景 | 处理 |
|------|------|
| 特别篇（Season 0） | 默认不计入完整度 |
| 未播出的集 | `aired: false`，前端显示 📅，不可搜索 |
| 超过 100%（如 OVA 额外集） | 进度条 cap 在 100%，数字如实显示 |
| NAS 路径不可达 | `collect_local_episodes` 返回空，前端显示"本地数据待同步" |
| 无 TMDB ID | 返回 `{status: "no_tmdb_id"}`，前端不显示组件 |
| TMDB 请求失败 | 降级：只知道缺多少集，不知道具体缺哪些 |
| 中文数字季/集号 | 支持 零~九十九 |
| 连字符分隔集号 | 支持 `Name-02.mp4` 格式 |
| 多版本同一集 | 按集号去重，不重复计数 |

## 文件清单

| 文件 | 职责 |
|------|------|
| `backend/completeness.py` | 核心逻辑 + 缓存层 |
| `backend/completeness_cache.json` | 持久化缓存（自动生成） |
| `backend/_batch_completeness.py` | 批量预计算脚本 |
| `backend/test_completeness.py` | 19 个单元测试 |
| `backend/routes/library.py` | API 端点（`/library/completeness`） |
| `backend/shared.py` | save_library 回调注册 |
| `frontend/components/detail/CompletenessBar.tsx` | 前端展示组件 |
| `frontend/components/detail/FolderDetail.tsx` | 集成点 |
| `frontend/types/index.ts` | 类型定义 |
| `frontend/lib/api/system.ts` | API 调用（getCompleteness） |
