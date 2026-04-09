# 整理流水线 v3 — 三段式解耦架构

## 核心理念

v2 的致命问题：**先猜后做**。用正则从脏文件名猜季号 → 物理挪文件建季目录 → 再刮削。
正则猜错（纯绝对集数、无季号特征）→ 物理结构错 → 后续全崩。

v3 的核心：**先问后做**。物理结构与逻辑确权完全解耦。

```
阶段一（物理隔离）：只做最安全的事 — 散装视频包进文件夹，绝不猜季号
阶段二（确权）    ：问 TMDB 拿官方答案，写进 NFO，NFO 成为唯一真理
阶段三（执行）    ：读 NFO 执行物理操作和影子名生成，不再看原始文件名
```

---

## Pipeline 执行顺序

```
Step 0: 散落视频基础封装（仅限一级分类目录）
Step 1: 旧刮削智能处理（保留有效 NFO，清理无效残余）
Step 2: 分析判定（classify_folder，传递 folder_type + category_hint 上下文）
Step 3: 刮削确权（TMDB 查询 + 绝对集数映射 + 写精准 NFO）  ← 原 Step 5 前移
Step 4: 依据 NFO 深度结构归位（建季目录、挪文件）           ← 原 Step 3+4 后移
Step 5: 影子名生成与写入（严格读 NFO 拼接，不回退到文件名清洗）
```

---

## Step 0: 散落视频基础封装

### 作用域
仅在一级分类目录（如 `电影/`、`动画电影/`）执行。判断方法：path 是 NAS 根目录的直接子目录。

### 规则
- movie 标签下的散落视频：封装进独立文件夹（和现在一样）
- tv 标签下的散落视频：**完全不动**，等 Step 4 根据 NFO 建季目录
- 非一级分类目录：跳过此步

### 代码改动
- `wrap_loose_videos_in_category` 加 `category_tag` 参数
- `category_tag == "tv"` 时直接 return，不封装
- 流水线入口加判断：只有 `_is_top_category(path)` 时才调用

---

## Step 1: 旧刮削智能处理

### 策略：不无脑删，智能保留

读取 NFO，按 `<title>` 是否非空判断有效性：

| 条件 | 处理 |
|------|------|
| `<title>` 非空 | 保留，视为有效历史数据 |
| `<title>` 为空或无法解析 | 打包备份（`.old_scrape.zip`）后删除 |
| 无 NFO 的孤立 poster/fanart | 打包备份后删除 |

### 父级信任锁定
如果保留了有效的 `tvshow.nfo`（含 TMDB ID），Step 3 刮削时直接用这个 TMDB ID 拉取季/集数据，跳过搜索步骤。

### 递归深度
递归遍历所有子目录（不只一层），tv 的季目录下的旧刮削也要处理。

### 代码改动
- `_archive_dir` 改为 `_smart_archive_dir`：先读 NFO，title 非空则跳过
- 遍历改为递归（当前只遍历一层）

---

## Step 2: 分析判定

### 上下文传递（v3 核心修复）

`category_hint` 和 `folder_type` 必须贯穿整个流水线，只判定一次。

```python
# 流水线入口
category_hint = _get_category_from_path(path)
report = analyzer.analyze_folder(path, library, category_hint=category_hint)
folder_type = report["folder_type"]

# 后续所有步骤都接收这两个参数，不再内部重新判定
```

### 代码改动
- `organizer.organize_folder` 加 `category_hint` 参数，传给内部 `analyze_folder`
- `scraper.scrape_folder` 调用时传入 `folder_type`（已支持参数，流水线没传）
- `rename_videos_in_folder` 递归时也传 `category_hint`

---

## Step 3: 刮削确权（核心重构）

### 原则
- 绝不修改原文件名
- 只在内存中提取搜索词
- 所有季/集归属以 TMDB 返回的官方数据为唯一真理
- NFO 是后续步骤的 Single Source of Truth

### 3.1 按 folder_type 分发

```python
def scrape_folder(path, client, force, folder_type, ...):
    if folder_type == "movie":
        _scrape_movie(...)        # 搜 TMDB → 写 movie.nfo + poster
    elif folder_type == "tv":
        _scrape_tv_v3(...)        # 核心重构：确权式刮削
    elif folder_type in ("collection", "series", "mixed"):
        _scrape_collection(...)   # 不写父目录 NFO，递归子目录各自独立刮削
```

### 3.2 TV 确权式刮削（`_scrape_tv_v3`）

#### 第一步：确定 TMDB ID

```
1. 读现有 tvshow.nfo
   - 有效（title 非空 + tmdb_id > 0）→ 父级信任锁定，直接用
   - 无效或不存在 → 搜索 TMDB
2. 搜索 TMDB
   - 用文件夹名清洗后搜索（现有渐进式搜索策略）
   - 搜不到 → 从子目录/视频文件名提取搜索词重试
3. 写 tvshow.nfo + poster（如果是新搜到的）
```

#### 第二步：构建绝对集数映射表

```python
def build_absolute_episode_map(client, tmdb_id):
    """构建绝对集数 → (season, episode) 的映射表
    关键：跳过 Season 0（特别篇）"""
    tv_data = client._get(f"/tv/{tmdb_id}")
    seasons = tv_data.get("seasons", [])
    
    mapping = {}  # {absolute_num: (season_num, episode_num)}
    absolute_counter = 1
    
    for s in sorted(seasons, key=lambda x: x["season_number"]):
        sn = s["season_number"]
        if sn == 0:  # 跳过特别篇
            continue
        ep_count = s["episode_count"]
        for ep in range(1, ep_count + 1):
            mapping[absolute_counter] = (sn, ep)
            absolute_counter += 1
    
    return mapping
```

#### 第三步：遍历所有视频，写 episode.nfo

```
对文件夹下所有视频（含子目录内的）：
1. parse_filename 提取集号信息
   - 返回 season + episode → 直接用
   - 返回 absolute_episode → 查映射表转换为 season + episode
   - 什么都没提取到 → 跳过（不写 NFO，不动文件）
2. 用 (tmdb_id, season, episode) 调 get_episode_detail
3. 写 episode.nfo（视频同名 .nfo）
   - <showtitle>剧名</showtitle>  ← 来自 tvshow.nfo
   - <season>X</season>
   - <episode>Y</episode>
   - <title>分集标题</title>
   - <uniqueid type="tmdb">xxx</uniqueid>
```

#### 降级策略
- 绝对集数查不到映射（超出已知集数范围）→ 不写 NFO，不动文件
- get_episode_detail 返回 404 → 写简化 NFO（只有 showtitle + season + episode，无分集标题）
- 文件名完全无法提取集号 → 不写 NFO，不动文件

### 3.3 parse_filename 升级

新增 `absolute_episode` 返回字段：

```python
def parse_filename(filename):
    result = {
        "clean_name": "",
        "season": None,
        "episode": None,
        "absolute_episode": None,  # 新增
        "year": None,
        "raw": name
    }
    
    # 现有匹配逻辑不变（S01E01、第X集、[02] 等）
    # ...
    
    # 新增：如果 season 被默认设为 1 且没有明确的季号特征，
    # 同时 episode 数值 > 合理单季集数（比如 > 50），
    # 则判定为绝对集数
    if result["episode"] is not None and result["season"] == 1:
        has_explicit_season = bool(re.search(
            r'S\d+|第\d+季|Season\s*\d+', filename, re.I
        ))
        if not has_explicit_season and result["episode"] > 50:
            result["absolute_episode"] = result["episode"]
            result["season"] = None
            result["episode"] = None
```

**阈值说明**：`> 50` 是一个保守阈值。大多数单季剧集不超过 50 集，超过的大概率是绝对集数（如动画番 060、100 等）。如果是 25 集以内的，即使是绝对集数，当作 S01E25 处理也不会错太多（第一季通常就是这些集数）。

### 3.4 ScrapeResult 扩展

`get_tv_detail` 需要保存 seasons 数组信息，用于构建映射表：

```python
# ScrapeResult 新增字段
seasons_info: List[Dict] = []  # [{"season_number": 1, "episode_count": 25}, ...]
```

`get_tv_detail` 中保存：
```python
seasons_info = [
    {"season_number": s["season_number"], "episode_count": s["episode_count"]}
    for s in d.get("seasons", [])
]
r.seasons_info = seasons_info
```

---

## Step 4: 依据 NFO 深度结构归位

### 原则
- 彻底抛弃对原始文件名的依赖
- 完全"听命于 NFO"
- 没有 NFO 的文件完全不动（Leave it alone）

### 4.1 前置：Reload library_data

Step 3 刮削可能写了新文件（NFO、poster），需要重新加载 library 数据：
```python
library = config_m.load_library()  # 重新加载
```

### 4.2 TV 类型：读 NFO 建季目录

新版 `reorganize_seasons_by_nfo`（替代旧的 `reorganize_seasons`）：

```python
def reorganize_seasons_by_nfo(folder_path, dry_run=True):
    """读取 episode.nfo 确定季号，按季号建目录并移入
    核心规则：没有 NFO 的文件完全不动"""
    ops = []
    video_exts = {".mp4", ".mkv", ...}
    
    # 遍历文件夹下所有视频（含已有季目录内的）
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if os.path.splitext(f)[1].lower() not in video_exts:
                continue
            video_path = os.path.join(root, f)
            nfo = read_video_nfo(video_path)
            if not nfo or not nfo.get("season_number"):
                continue  # 没有 NFO 或没有季号 → 不动
            
            season_num = nfo["season_number"]
            target_dir = os.path.join(folder_path, f"Season {season_num:02d}")
            
            # 如果视频已经在正确的季目录里，跳过
            current_dir = os.path.dirname(video_path)
            if os.path.normpath(current_dir) == os.path.normpath(target_dir):
                continue
            
            # 移动视频 + 关联文件（.nfo, -poster.jpg, 字幕等）
            ops.append({
                "action": "move",
                "old": video_path,
                "new": os.path.join(target_dir, f),
                "mkdir": target_dir
            })
            # 移动关联文件
            base = os.path.splitext(video_path)[0]
            for suffix in [".nfo", "-poster.jpg", "-thumb.jpg", ".srt", ".ass", ".ssa"]:
                assoc = base + suffix
                if os.path.exists(assoc):
                    ops.append({
                        "action": "move",
                        "old": assoc,
                        "new": os.path.join(target_dir, os.path.basename(assoc)),
                        "mkdir": target_dir
                    })
    
    # 执行
    if not dry_run:
        for op in ops:
            if op.get("mkdir"):
                os.makedirs(op["mkdir"], exist_ok=True)
            if os.path.exists(op["old"]):
                shutil.move(op["old"], op["new"])
    
    return {"status": "ok", "ops": ops, "count": len(ops)}
```

### 4.3 Movie/Collection/Series 类型

- movie：已经有文件夹了，不需要结构归位
- collection/series：散装视频在 Step 0 已封装（movie 标签下），不需要额外操作
- 孤立刮削文件归位：保留现有逻辑（模糊匹配归位）

### 4.4 季目录名标准化

在视频归位完成后，标准化已有的季目录名：
- `第1季` → `Season 01`
- `S01` → `Season 01`
- 只对能确定季号的目录做，SP/OVA/特别篇不动

---

## Step 5: 影子名生成与写入

### 原则
- 严格读取 NFO 数据拼接
- 不再使用 `_clean_filename_for_folder` 回退
- NFO 是唯一数据源

### 5.1 生成逻辑

```python
def generate_shadow_name_from_nfo(video_path, folder_path, folder_type):
    """严格从 NFO 生成影子名"""
    
    if folder_type == "movie":
        nfo = read_video_nfo(video_path) or read_nfo(folder_path)
        if not nfo or not nfo.get("title"):
            return None  # 没有 NFO → 不生成，不回退
        title = nfo["title"]
        en = nfo.get("english_title") or ""
        orig = nfo.get("original_title") or ""
        if not en and orig and _is_mostly_latin(orig):
            en = orig
        year = nfo.get("year", "")
        
        shadow = title
        if en and en != title:
            shadow += f" {en}"
        if year:
            shadow += f" ({year})"
        return shadow
    
    elif folder_type in ("tv", "season"):
        # 视频级：读 episode.nfo
        nfo = read_video_nfo(video_path)
        if not nfo:
            return None
        
        # 剧名从 tvshow.nfo 获取（不用分集标题）
        tv_nfo = read_nfo(folder_path, no_fallback=True)
        show_title = (tv_nfo or {}).get("title", "") or nfo.get("title", "")
        show_en = (tv_nfo or {}).get("english_title", "") or ""
        show_orig = (tv_nfo or {}).get("original_title", "") or ""
        if not show_en and show_orig and _is_mostly_latin(show_orig):
            show_en = show_orig
        
        season = nfo.get("season_number", 0)
        episode = nfo.get("episode_number", 0)
        
        shadow = show_title
        if show_en and show_en != show_title:
            shadow += f" {show_en}"
        if season and episode:
            shadow += f" S{season:02d}E{episode:02d}"
        return shadow
    
    elif folder_type in ("collection", "series", "mixed"):
        # 聚合容器内的子视频：各自独立，按 movie 逻辑
        return generate_shadow_name_from_nfo(video_path, 
            os.path.dirname(video_path), "movie")
    
    return None
```

### 5.2 文件夹级影子名

TV 文件夹本身也需要影子名（用于前端显示）：

```python
def generate_folder_shadow_name(folder_path, folder_type):
    """文件夹级影子名"""
    if folder_type in ("tv", "movie"):
        nfo = read_nfo(folder_path, no_fallback=(folder_type == "tv"))
        if not nfo or not nfo.get("title"):
            return None
        title = nfo["title"]
        en = nfo.get("english_title") or ""
        orig = nfo.get("original_title") or ""
        if not en and orig and _is_mostly_latin(orig):
            en = orig
        year = nfo.get("year", "")
        
        shadow = title
        if en and en != title:
            shadow += f" {en}"
        if year:
            shadow += f" ({year})"
        return shadow
    
    return None  # 聚合容器不生成文件夹级影子名
```

---

## 完整流水线伪代码

```python
def one_click_organize_v3(path, dry_run=True):
    category_hint = _get_category_from_path(path)
    library = config_m.load_library()
    client = _tmdb_client()
    
    # === Step 0: 基础封装 ===
    if _is_top_category(path) and category_hint == "movie":
        wrap_result = organizer.wrap_loose_videos_in_category(path, dry_run=False)
        if wrap_result["ops"]:
            _sync_library_paths(wrap_result["ops"])
    
    # === Step 1: 旧刮削智能处理 ===
    archived = _smart_archive_recursive(path)
    
    # === Step 2: 分析判定 ===
    report = analyzer.analyze_folder(path, library, category_hint=category_hint)
    folder_type = report["folder_type"]
    
    if dry_run:
        return {"steps": {"analyze": report}}
    
    # === Step 3: 刮削确权 ===
    scrape_result = scraper.scrape_folder(
        path, client, force=True, folder_type=folder_type
    )
    
    # === Step 4: 依据 NFO 结构归位 ===
    library = config_m.load_library()  # Reload!
    
    if folder_type == "tv":
        reorg = organizer.reorganize_seasons_by_nfo(path, dry_run=False)
        if reorg["ops"]:
            _sync_library_paths(reorg["ops"])
    
    # 孤立刮削文件归位（所有类型）
    orphan_result = organizer.relocate_orphan_scrape_files(path)
    
    # === Step 5: 影子名生成 ===
    library = config_m.load_library()  # Reload again!
    shadow_filled = _generate_shadows_from_nfo(path, folder_type, library)
    
    return result
```

---

## 各类型完整处理流程

### movie 类型
```
Step 0: 已有文件夹，跳过
Step 1: 智能处理旧刮削
Step 2: classify → movie
Step 3: 搜 TMDB → 写 movie.nfo + poster
Step 4: 无需结构归位
Step 5: 读 movie.nfo → "中文名 英文名 (年份)"
```

### tv 类型
```
Step 0: tv 标签下不封装，跳过
Step 1: 智能处理旧刮削（保留有效 tvshow.nfo）
Step 2: classify → tv
Step 3: 确权式刮削
  - 确定 TMDB ID（优先复用有效 tvshow.nfo）
  - 构建绝对集数映射表
  - 遍历所有视频，写 episode.nfo
  - 没有集号的视频不写 NFO
Step 4: 读 episode.nfo 建季目录
  - 有 NFO 的视频按 <season> 归入 Season XX/
  - 没有 NFO 的视频不动
  - 标准化季目录名
Step 5: 读 NFO → "剧名 英文名 S01E01"
  - 没有 NFO 的视频不生成影子名
```

### collection / series / mixed 类型
```
Step 0: 散装视频封装（仅 movie 标签下的一级分类目录）
Step 1: 智能处理旧刮削
Step 2: classify → collection/series/mixed
Step 3: 不写父目录 NFO，递归子目录各自独立刮削
Step 4: 无需结构归位（子目录已各自独立）
Step 5: 每个子视频读自己的 NFO → 各自独立影子名
```

---

## 代码改动清单

### 1. `tmdb_client.py`

| 改动 | 说明 |
|------|------|
| `parse_filename` 新增 `absolute_episode` 返回 | episode > 50 且无明确季号特征 → 判定为绝对集数 |
| `ScrapeResult` 新增 `seasons_info` 字段 | `List[Dict]`，存每季的 season_number + episode_count |
| `get_tv_detail` 保存 seasons 数组 | 从 TMDB 响应中提取并存入 ScrapeResult |
| 新增 `build_absolute_episode_map(client, tmdb_id)` | 累加每季集数（跳过 Season 0），返回 {abs_num: (s, e)} |

### 2. `scraper.py`

| 改动 | 说明 |
|------|------|
| `_scrape_tv` 重写为 `_scrape_tv_v3` | 三步确权：确定 TMDB ID → 建映射表 → 写 episode.nfo |
| `write_episode_nfo` 增加 `<showtitle>` 标签 | 写入剧名，供 Step 5 读取 |
| `read_video_nfo` 增加读取 `<showtitle>` | 返回 dict 中加 `showtitle` 字段 |

### 3. `organizer.py`

| 改动 | 说明 |
|------|------|
| `organize_folder` 加 `category_hint` 参数 | 传给内部 `analyze_folder` |
| 新增 `reorganize_seasons_by_nfo` | 读 NFO 建季目录，替代旧的正则猜测逻辑 |
| `wrap_loose_videos_in_category` 加 `category_tag` 判断 | tv 标签下不封装 |
| `rename_videos_in_folder` 重写影子名生成 | 严格读 NFO，不回退到 `_clean_filename_for_folder` |
| `rename_videos_in_folder` 递归时传 `category_hint` | 子文件夹类型判定一致 |

### 4. `main.py`

| 改动 | 说明 |
|------|------|
| `one_click_organize` 重写为 v3 流水线 | 新的 5 步顺序 |
| 流水线中传递 `folder_type` 和 `category_hint` | 只判定一次，全程传递 |
| Step 4 前 Reload library_data | 刮削后路径可能变化 |
| Step 5 前 Reload library_data | 结构归位后路径可能变化 |
| `_smart_archive_recursive` 替代 `_archive_dir` | 递归 + 智能保留有效 NFO |
| `_is_top_category(path)` 辅助函数 | 判断是否一级分类目录 |

### 5. `analyzer.py`

| 改动 | 说明 |
|------|------|
| `_diagnose_structure` 对 tv 类型不再生成 `split_seasons` 操作 | 季拆分交给 Step 4 根据 NFO 做 |

---

## 不变的部分

- `classify_folder` / `_classify_by_category` / `_classify_tv_category` / `_classify_movie_category`：分类逻辑不变
- `_scrape_movie`：movie 刮削逻辑不变
- `_scrape_collection`：聚合刮削逻辑不变
- `_clean_filename_for_folder`：清洗函数保留，但不再用于影子名生成（只用于 Step 0 封装时的文件夹命名）
- `generate_standard_name`：保留但降级为 fallback，主路径改为 `generate_shadow_name_from_nfo`
- 前端代码：不需要改动（API 接口不变）

---

## 风险点与兜底

| 风险 | 兜底策略 |
|------|----------|
| TMDB 搜不到这部剧 | 不写任何 NFO，不动任何文件，不生成影子名。用户手动处理 |
| 绝对集数超出映射表范围 | 不写 NFO，不动文件。可能是新季还没更新到 TMDB |
| 文件名完全无法提取集号 | 不写 NFO，不动文件 |
| get_episode_detail 404 | 写简化 NFO（只有 showtitle + season + episode） |
| 旧 NFO 的 TMDB ID 对应的剧已被 TMDB 删除/合并 | API 报错时 fallback 到重新搜索 |
| 绝对集数阈值 50 误判 | 保守阈值，50 集以内的即使是绝对集数也不会错太多 |

---

## 测试验证用例

| 文件夹 | 场景 | 期望行为 |
|--------|------|----------|
| 进击的巨人（060.mkv） | 纯绝对集数 | 映射为 S03E10，写 episode.nfo，Step 4 建 Season 03 |
| 切尔诺贝利（S01E01.mkv） | 标准 SxxExx | 直接用，写 episode.nfo |
| 茗记（4个不同视频） | collection | 各自独立刮削为 movie |
| 已有 tvshow.nfo 的剧 | 父级信任锁定 | 跳过搜索，直接用 TMDB ID |
| 文件名无集号（README.mkv） | 无法提取 | 不写 NFO，不动文件，不生成影子名 |
| 混合季目录+散装视频 | tv + 散装 | Step 3 写 NFO，Step 4 按 NFO 归入季目录 |

---

## 六、交互层设计 — 双入口 + 沙盘推演 + AI 旁路

### 6.1 两个独立 API 入口

#### 入口 A：纯结构整理 (`/organize/structure`)

对应前端：单个文件夹上的"标准结构"按钮。

核心原则：**绝对不联网查 TMDB，只做物理收纳**。

```
POST /organize/structure?path=xxx&dry_run=true|false
```

执行逻辑：
```
1. 执行 Step 0（基础封装，仅 movie 标签下的一级分类目录）
2. 跳过 Step 1, 2, 3（不删旧刮削、不分析、不刮削）
3. 直接执行 Step 4（依据本地已有 NFO 结构归位）
   - 有 NFO → 按 NFO 的 <season> 建季目录并移入
   - 没有 NFO → 什么也不做，安全退出
4. 跳过 Step 5（不生成影子名）
```

返回值：
```json
{
  "status": "ok",
  "mode": "structure_only",
  "ops": [
    {"action": "move", "old": "...", "new": "...", "desc": "..."}
  ],
  "count": 5
}
```

使用场景：
- 用户手动刮削完一个文件夹后，想把散装视频按 NFO 归入季目录
- 不想触发 TMDB 搜索，只想整理物理结构
- 网络不通时的离线整理

#### 入口 B：一键完全整理 (`/organize/full`)

对应前端：一级分类目录或乱套文件夹上的"一键整理"按钮。

核心原则：**完整跑通 V3 的 Step 0 到 Step 5**。

```
POST /organize/full?path=xxx&dry_run=true|false&use_ai=false
```

支持两段式提交（沙盘推演）和 AI 旁路开关。

---

### 6.2 沙盘推演机制 (Dry Run Plan)

入口 B 的 `dry_run=true` 不再只返回简单的统计数字，而是返回完整的 Action Plan。

#### 阶段 1：推演模式 (`dry_run=true`)

后端完整执行 Step 0~3 的**计算逻辑**，但严禁任何落盘操作：
- ✅ 可以：读文件、查 TMDB API、计算映射表、生成预览
- ❌ 禁止：写 NFO、移动文件、创建目录、写影子名

返回 Action Plan JSON：

```json
{
  "status": "ok",
  "mode": "full_organize",
  "dry_run": true,
  "folder_type": "tv",
  "category_hint": "tv",
  "tmdb_match": {
    "tmdb_id": 1429,
    "title": "进击的巨人",
    "english_title": "Attack on Titan",
    "total_seasons": 4,
    "match_source": "search"  // "search" | "existing_nfo"（父级信任锁定）
  },
  "absolute_map_built": true,
  "plan": [
    {
      "original_path": "\\\\NAS\\动画番\\进击的巨人\\060.mkv",
      "original_filename": "060.mkv",
      "parsed": {
        "method": "regex",  // "regex" | "ai"
        "absolute_episode": 60,
        "season": null,
        "episode": null
      },
      "mapped": {
        "season": 3,
        "episode": 10
      },
      "scraped_title": "进击的巨人",
      "episode_title": "选择与结果",
      "target_season_dir": "Season 03",
      "target_path": "\\\\NAS\\动画番\\进击的巨人\\Season 03\\060.mkv",
      "target_shadow_name": "进击的巨人 Attack on Titan S03E10",
      "actions": ["write_episode_nfo", "move_to_season", "write_shadow"]
    },
    {
      "original_path": "\\\\NAS\\动画番\\进击的巨人\\README.mkv",
      "original_filename": "README.mkv",
      "parsed": {
        "method": "regex",
        "absolute_episode": null,
        "season": null,
        "episode": null
      },
      "mapped": null,
      "actions": [],
      "skip_reason": "无法提取集号"
    }
  ],
  "summary": {
    "total_videos": 75,
    "will_process": 73,
    "will_skip": 2,
    "seasons_to_create": ["Season 01", "Season 02", "Season 03", "Season 04"],
    "nfo_to_write": 73,
    "files_to_move": 60,
    "shadows_to_fill": 73
  }
}
```

前端拿到这个 Plan 后展示预览面板，用户可以：
- 查看每个视频的映射结果
- 确认季/集归属是否正确
- 看到哪些文件会被跳过及原因
- 点击"确认执行"触发阶段 2

#### 阶段 2：确权执行 (`dry_run=false`)

前端发送确认请求，后端执行 Step 3（写 NFO）→ Step 4（物理归位）→ Step 5（影子名）。

```
POST /organize/full?path=xxx&dry_run=false&use_ai=false
```

返回执行结果：
```json
{
  "status": "ok",
  "mode": "full_organize",
  "dry_run": false,
  "steps": {
    "archive": 12,
    "scrape": {"status": "ok", "nfo_written": 73},
    "structure": {"moved": 60, "seasons_created": 4},
    "shadow": {"filled": 73}
  }
}
```

#### 实现要点

沙盘推演的核心是：Step 3 的刮削逻辑需要拆成"计算"和"落盘"两个阶段。

```python
def _scrape_tv_v3(folder_path, client, force, dry_run=False):
    # 第一步：确定 TMDB ID（读 NFO 或搜索）— 无论 dry_run 都执行
    tmdb_id, tv_detail = _resolve_tmdb_id(folder_path, client, force)
    if not tmdb_id:
        return {"status": "not_found"}
    
    # 第二步：构建映射表 — 无论 dry_run 都执行
    abs_map = build_absolute_episode_map(client, tmdb_id)
    
    # 第三步：遍历视频，计算每个视频的 plan — 无论 dry_run 都执行
    plan = []
    for video_path in _collect_all_videos(folder_path):
        item = _compute_video_plan(video_path, tmdb_id, abs_map, client, tv_detail)
        plan.append(item)
    
    if dry_run:
        return {"status": "ok", "plan": plan, "tmdb_match": {...}}
    
    # 第四步：落盘 — 只在 dry_run=False 时执行
    for item in plan:
        if "write_episode_nfo" in item["actions"]:
            _write_episode_nfo(item)
    if not dry_run:
        write_tvshow_nfo(folder_path, tv_detail)  # 写/更新 tvshow.nfo
    
    return {"status": "ok", "plan": plan}
```

---

### 6.3 AI 旁路开关 (`use_ai=bool`)

在 Step 3 的"提取集号信息"环节，增加 AI 辅助提取能力。

#### 触发条件

```python
def _extract_episode_info(filename, use_ai=False, ai_client=None):
    """提取集号信息，支持 AI 旁路"""
    
    # 第一关：正则提取（默认路径）
    parsed = parse_filename(filename)
    
    if parsed["episode"] is not None or parsed["absolute_episode"] is not None:
        return {**parsed, "method": "regex"}
    
    # 正则失败 + AI 开关关闭 → 放弃
    if not use_ai or not ai_client:
        return {**parsed, "method": "regex"}
    
    # 第二关：AI 语义提取（旁路）
    ai_result = _ai_extract_episode(filename, ai_client)
    if ai_result:
        return {**ai_result, "method": "ai"}
    
    return {**parsed, "method": "regex_failed"}
```

#### AI 提取函数

```python
def _ai_extract_episode(filename, ai_client):
    """调用 LLM 从乱码文件名中提取结构化信息
    AI 仅充当"高级提取器"，绝不允许捏造数据"""
    
    prompt = f"""你是一个视频文件名解析器。请从以下文件名中提取信息。
只返回 JSON，不要任何解释。

文件名：{filename}

返回格式（严格遵守）：
{{
  "clean_title": "作品名（中文优先）",
  "year": "年份或null",
  "season": 季号数字或null,
  "episode": 分集号数字或null,
  "absolute_episode": 绝对集数数字或null
}}

规则：
- 如果文件名有明确的 S01E01 格式，填 season 和 episode
- 如果只有一个数字且可能是集数，填 absolute_episode
- 如果无法判断，对应字段填 null
- clean_title 必须是干净的作品名，去掉字幕组、编码、分辨率等标签"""

    try:
        headers = {
            "Authorization": f"Bearer {ai_client.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": ai_client.model,
            "messages": [
                {"role": "system", "content": "你是一个精确的 JSON 生成器，只返回合法的 JSON 对象。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }
        resp = requests.post(
            f"{ai_client.base_url}/chat/completions",
            headers=headers, json=payload, timeout=15
        )
        content = resp.json()["choices"][0]["message"]["content"]
        
        # 解析 JSON
        result = json.loads(content)
        
        # 验证字段合法性（AI 可能返回垃圾）
        clean_title = result.get("clean_title", "")
        if not clean_title or len(clean_title) < 2:
            return None
        
        return {
            "clean_name": clean_title,
            "year": result.get("year"),
            "season": result.get("season"),
            "episode": result.get("episode"),
            "absolute_episode": result.get("absolute_episode"),
        }
    except Exception as e:
        print(f"AI extract error: {e}")
        return None
```

#### 底线规则
- AI 仅提取 `clean_title` / `season` / `episode` / `absolute_episode`
- 提取结果必须经过 TMDB 验证（搜索 + 映射表比对）
- 所有落盘数据（NFO 内容）100% 来自 TMDB 官方 API
- AI 返回的 JSON 必须做字段校验，垃圾数据直接丢弃
- AI 调用失败 → 静默降级为"跳过该文件"，不阻塞流水线

#### 前端交互
- "一键整理"按钮旁边有一个 AI 开关（默认关闭）
- 开启后，沙盘推演的 plan 中每个 item 会标注 `method: "ai"`
- 用户可以在预览中看到哪些文件是 AI 提取的，哪些是正则提取的

---

### 6.4 API 路由汇总

| 路由 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/organize/structure` | POST | `path`, `dry_run` | 纯结构整理（离线，不联网） |
| `/organize/full` | POST | `path`, `dry_run`, `use_ai` | 一键完全整理（两段式） |
| `/organize/classify` | GET | `path` | 分类判定（保留） |
| `/organize/rename` | POST | `path`, `dry_run`, `shadow_only` | 自动命名（保留） |
| `/organize/seasons` | POST | `path`, `dry_run` | 多季规整（保留，但内部改为读 NFO） |

旧路由 `/organize/one-click` 和 `/organize/folder` 标记为 deprecated，
内部重定向到 `/organize/full` 和 `/organize/structure`。

### 6.5 前端 API 封装更新

```typescript
// lib/api.ts 新增
structureOrganize: (path: string, dryRun: boolean = true) =>
  request<StructureResult>(
    `${BASE_URL}/organize/structure?path=${encodeURIComponent(path)}&dry_run=${dryRun}`,
    { method: "POST" }
  ),

fullOrganize: (path: string, dryRun: boolean = true, useAi: boolean = false) =>
  request<FullOrganizeResult>(
    `${BASE_URL}/organize/full?path=${encodeURIComponent(path)}&dry_run=${dryRun}&use_ai=${useAi}`,
    { method: "POST" }
  ),
```

### 6.6 前端 DetailDrawer 按钮改造

当前的"一键整理"按钮拆分为：

```
末端文件夹（movie/tv/season）：
  [标准结构]  → 调 /organize/structure（离线，快速）
  [一键整理]  → 调 /organize/full（两段式，先预览后执行）
  [🤖 AI]    → 一键整理的 use_ai 开关

聚合容器（collection/series/mixed）：
  [一键整理]  → 调 /organize/full（递归子目录）
  [🤖 AI]    → use_ai 开关

一级分类目录：
  [一键整理]  → 调 /organize/full（全量）
  [🤖 AI]    → use_ai 开关
```

预览面板交互：
```
点击 [一键整理] 
  → 显示 loading
  → 收到 Action Plan
  → 展示预览面板：
    - 顶部：TMDB 匹配结果（剧名、海报、总季数）
    - 中间：视频列表（每行：原文件名 → 映射结果 → 目标路径）
    - 标注 method（正则/AI）
    - 高亮跳过的文件（红色，显示跳过原因）
    - 底部统计：X 个视频将处理，Y 个跳过，Z 个季目录将创建
  → 用户点击 [确认执行]
  → 发送 dry_run=false
  → 显示执行结果
```

---

## 七、完整代码改动清单（含交互层）

### 第 1 批：基础设施（无破坏性）

| 文件 | 改动 | 说明 |
|------|------|------|
| `tmdb_client.py` | `parse_filename` 新增 `absolute_episode` | 正则升级 |
| `tmdb_client.py` | `ScrapeResult` 新增 `seasons_info` 字段 | 数据结构扩展 |
| `tmdb_client.py` | `get_tv_detail` 保存 seasons 数组 | 映射表数据源 |
| `tmdb_client.py` | 新增 `build_absolute_episode_map()` | 绝对集数映射 |
| `scraper.py` | `write_episode_nfo` 增加 `<showtitle>` | NFO 格式扩展 |
| `scraper.py` | `read_video_nfo` 增加读取 `<showtitle>` | NFO 读取扩展 |

### 第 2 批：核心流水线重构

| 文件 | 改动 | 说明 |
|------|------|------|
| `scraper.py` | 新增 `_scrape_tv_v3()` | 确权式 TV 刮削（支持 dry_run） |
| `organizer.py` | 新增 `reorganize_seasons_by_nfo()` | 读 NFO 建季目录 |
| `organizer.py` | `organize_folder` 加 `category_hint` 参数 | 上下文传递 |
| `organizer.py` | `wrap_loose_videos_in_category` 加 `category_tag` | tv 标签不封装 |
| `organizer.py` | 新增 `generate_shadow_name_from_nfo()` | 严格读 NFO 生成影子名 |
| `organizer.py` | 新增 `generate_folder_shadow_name()` | 文件夹级影子名 |
| `analyzer.py` | `_diagnose_structure` 移除 tv 的 `split_seasons` | 季拆分交给 Step 4 |

### 第 3 批：API 入口 + 沙盘推演

| 文件 | 改动 | 说明 |
|------|------|------|
| `main.py` | 新增 `/organize/structure` 路由 | 入口 A：纯结构整理 |
| `main.py` | 新增 `/organize/full` 路由 | 入口 B：一键完全整理 |
| `main.py` | `one_click_organize` 重写为 v3 流水线 | 两段式（dry_run 返回 Plan） |
| `main.py` | 新增 `_smart_archive_recursive()` | 递归 + 智能保留有效 NFO |
| `main.py` | 新增 `_is_top_category()` | 判断一级分类目录 |
| `main.py` | 旧路由 deprecated 重定向 | 兼容旧前端 |

### 第 4 批：AI 旁路

| 文件 | 改动 | 说明 |
|------|------|------|
| `ai_organizer.py` | 新增 `ai_extract_episode()` | LLM 文件名提取 |
| `scraper.py` | `_scrape_tv_v3` 集成 AI 旁路 | `use_ai` 参数控制 |

### 第 5 批：前端适配

| 文件 | 改动 | 说明 |
|------|------|------|
| `lib/api.ts` | 新增 `structureOrganize` / `fullOrganize` | 新 API 封装 |
| `DetailDrawer.tsx` | 按钮拆分 + 预览面板 | 两段式交互 |
| `DetailDrawer.tsx` | AI 开关 | use_ai toggle |

---

## 八、实施顺序

```
Phase 1: 第 1 批（基础设施）
  → 跑现有测试确认无破坏
  → 手动测试 parse_filename 的绝对集数识别

Phase 2: 第 2 批（核心流水线）
  → 用 5 个样本文件夹测试 _scrape_tv_v3
  → 用 5 个样本测试 reorganize_seasons_by_nfo
  → 用 5 个样本测试 generate_shadow_name_from_nfo

Phase 3: 第 3 批（API 入口）
  → 用 curl 测试 /organize/structure 和 /organize/full?dry_run=true
  → 确认 Action Plan JSON 格式正确
  → 测试 dry_run=false 执行

Phase 4: 第 4 批（AI 旁路）
  → 用几个乱码文件名测试 AI 提取
  → 确认 AI 结果能正确注入映射流程

Phase 5: 第 5 批（前端适配）
  → 按钮拆分 + 预览面板
  → npx next build 确认编译通过
```

每个 Phase 完成后等用户确认再进入下一个。
