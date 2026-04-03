# 文件夹类型体系重构设计

## 一、一级分类标签（category_tag）

用户在 UI 上给根目录子文件夹打的标签，只有 2 种：

| 标签 | 中文 | 含义 |
|------|------|------|
| `movie` | 电影 | 电影、动画电影、其他视频 |
| `tv` | 剧集 | 电视剧、动画番、综艺、纪录片 |

- 自动推断：`infer_category_tag()` 用中英文关键词匹配目录名
- 用户可在详情面板修改，持久化到 `config.category_tags`
- 推断不了的默认 `movie`（movie 的处理逻辑更宽松，不会强行改变目录结构；默认 tv 可能导致流水线试图生成 Season 目录，对散装电影有破坏性）

## 二、文件夹类型（folder_type）

算法自动判定 + 用户可覆盖，共 6 种：

| 类型 | 中文 | 含义 | 前端展示 |
|------|------|------|----------|
| `movie` | 电影 | 单部电影封装文件夹（1个视频） | 不展开，点击直接右侧详情 |
| `collection` | 合集 | 多部不相关影片的合集 | 展开为小卡片网格 |
| `series` | 系列 | 同系列影片（如EVA新剧场版） | 展开为缩略图列表 |
| `tv` | 剧集 | 剧集/动画/综艺（有季子目录） | 展开为季小卡片，点击卡片切换集列表 |
| `season` | 季 | 季文件夹（tv 的子目录） | 有独立详情页（影子名、清洗名、刮削等） |
| `mixed` | 混合 | 混合内容（多部不同tv聚合、深层嵌套等） | 不展开，点击进入（和当前逻辑一致） |

### 一级标签下允许的文件夹类型

| 一级标签 | 允许的 folder_type |
|----------|-------------------|
| `movie` | movie, collection, series, mixed |
| `tv` | tv, season, mixed |

### 中文标签映射表

```
movie → 电影
collection → 合集
series → 系列
tv → 剧集
season → 季
mixed → 混合
```

## 三、分类算法

### movie 标签下的判定

```
无子目录：
  0个视频 → empty
  1个视频 → movie
  多个视频 → series（同系列）或 collection（不相关）

有子目录 + 有散落视频 → collection
  （封装+散装共存，散落视频和封装子目录混在一起 = 多部电影合集）

有子目录 + 无散落视频：
  深度 ≥ 3 → mixed
  2层 + 同系列 → series
  2层 + 不相关 → collection
```

### tv 标签下的判定

```
无子目录：
  有视频 → tv（单季无季目录，扁平结构）

有子目录：
  全部是季目录（含 Season 00/Specials） → tv
  部分是季目录 → tv（非季目录也当作季处理）
  子目录各自是独立的 tv（不同剧） → mixed
  无法判断 → mixed
```

### mixed 的判定（关键优化点）

movie 标签下：
- 深层嵌套（≥3层子目录）
- 无法归类的复杂结构

tv 标签下：
- 多部不同 tv 聚合在一个文件夹里
- 判定方法：子目录各自 classify 为 tv，但文件名前缀不同（不是同一部剧的不同季）
- 例：`其他视频/` 下有 `纪录片A/Season 01/` 和 `纪录片B/Season 01/`
- **豁免规则**：Season 00、Specials、SP、OVA 等特别篇目录不参与"不同剧"的判定，它们始终属于父级 tv

### season 文件夹

- 由整理流水线创建（`reorganize_seasons` 标准化季目录为 `Season XX`）
- 树构建时，tv 类型文件夹的子目录自动标记为 `season`
- 有独立的详情页：影子名、清洗名、刮削信息、文件夹类型
- 和 movie 封装文件夹一样，整理函数可反复调用

### 扁平 tv 目录的强制季化

- 无子目录且有视频的 tv 文件夹 = 扁平结构
- 用户点击"一键整理"或"刮削"时，第一步静默触发 `reorganize_seasons`，自动创建 `Season 01` 并移入视频
- 这样前端只需一套展示逻辑（季卡片 → 选集），不需要为扁平 tv 写额外的展示分支

## 四、前端展示规则

### 左侧主内容区（CardGrid）

| folder_type | CardItem 类型 | 点击行为 |
|-------------|--------------|----------|
| movie | folder | 不展开，直接右侧 VideoDetail |
| collection | collection | 展开为小卡片网格 |
| series | series | 展开为缩略图列表 |
| tv（有子目录） | tv | 展开为季小卡片网格，点击卡片切换集列表 |
| season | — | 不会出现在顶层，只在 tv 展开面板中显示 |
| mixed | folder | 不展开，点击进入（导航到子目录） |

### tv 展开面板交互（重构）

旧：季 tab 切换 + 集列表
新：
1. 展开后显示季小卡片网格（复用 collection 的小卡片样式）
2. 点击某个季卡片 → 该季高亮 + 下方展开集列表
3. 点击另一个季卡片 → 切换到另一季的集列表
4. 点击季卡片 → 右侧详情面板显示该季的 FolderDetail（有独立刮削/影子名等）

### 右侧详情面板（DetailDrawer）

各文件夹类型的详情面板内容：

| folder_type | 封面 | 刮削信息 | 影子名/清洗名 | 操作按钮 |
|-------------|------|----------|--------------|----------|
| movie | ✅ 刮削封面 | ✅ 显示 | ✅ 视频级别 | 刮削/重新匹配/搜索升级/重命名 |
| collection | ✅ 独立封面（用户上传，和刮削无关） | ❌ 不显示 | ❌ | 一键刮削/搜索升级 |
| series | ✅ 独立封面（用户上传，和刮削无关） | ❌ 不显示 | ❌ | 一键刮削/搜索升级 |
| tv | ✅ 刮削封面 | ✅ 显示 | ✅ 文件夹级别 | 刮削/重新匹配/搜索升级/重命名 |
| season | ✅ 刮削封面 | ✅ 显示 | ✅ 文件夹级别 | 刮削/重新匹配/搜索升级/重命名 |
| mixed | ✅ 独立封面（用户上传，和刮削无关） | ❌ 不显示 | ❌ | 一键刮削 |
| 纯视频文件 | 复用 movie 面板逻辑 | ✅ 同名NFO | ✅ 视频级别 | 刮削/重新匹配/搜索升级/重命名 |

逻辑：
- movie/tv/season 是"末端刮削单元"，有完整的刮削信息和影子名
- collection/series/mixed 是"聚合容器"，只有独立封面（用户可上传），不显示刮削信息
- 聚合容器不显示"重新匹配"按钮，改为"一键刮削"（递归刮削子项）
- 点击纯视频文件（散装/末端视频）时，复用 movie 类型的详情面板逻辑，直接展示同名 NFO 刮削信息及操作按钮

其他：
- 一级分类目录：显示分类标签选择器（movie/tv）
- 所有文件夹：显示 folder_type 选择器（根据一级标签过滤选项，中文显示）

### 文件夹类型选择器

- 非一级分类目录显示 folder_type 下拉
- 下拉选项根据所属一级标签过滤：
  - movie 标签下：movie, collection, series, mixed
  - tv 标签下：tv, season, mixed
- 显示中文标签

## 五、后端改动

### organizer.py

1. `_CATEGORY_KEYWORD_MAP` 简化为只映射 movie/tv
2. `infer_category_tag` 推断不了默认 `movie`
3. `_classify_by_category` 只处理 movie/tv 两种标签
4. `_classify_movie_category` 返回 movie/collection/series/mixed
5. 新增 `_classify_tv_category` 返回 tv/mixed
6. `_classify_by_structure` 中的旧类型名全部更新
7. 所有 `movie_collection` → `collection`，`series_collection` → `series`，`movie_aggregate` → `collection`，`variety`/`other`/`misc` → 根据上下文映射
8. tv 标签下 mixed 判定时，豁免 Season 00/Specials/SP/OVA 等特别篇目录
9. tv 整理/刮削流水线预处理：扁平 tv 目录强制生成 Season 01 并移入视频

### main.py

1. 树构建时 tv 的子目录标记 `folder_type = "season"`
2. `_get_category_from_path` 返回 movie/tv
3. `set_folder_type` API 的可选值更新
4. `set_category_tag` API 的可选值更新为 movie/tv

### config_manager.py

1. `category_tags` 字段已添加（上次改动）

### scraper.py

1. `scrape_folder` 中的 folder_type 参数值更新

### analyzer.py

1. folder_type 引用更新

## 六、前端改动

### types/index.ts

1. `category_tag` 类型更新为 `"movie" | "tv" | ""`
2. `FolderNode` 添加 `is_top_category` 字段

### lib/folderTypes.ts（新文件）

1. 中文标签映射
2. 一级标签下允许的文件夹类型
3. 展示方式判断函数

### CardGrid.tsx

1. CardItem 类型重构：去掉 `multiseason`/`series_collection`/`movie_collection`，改为 `tv`/`series`/`collection`
2. items 分类逻辑更新
3. tv 展开面板：季 tab → 季小卡片 + 集列表
4. category_tag 角标显示中文

### DetailDrawer.tsx

1. 末端刮削单元（movie/tv/season）：显示刮削信息 + 影子名/清洗名 + 重新匹配
2. 聚合容器（collection/series/mixed）：只显示独立封面 + 一键刮削
3. 纯视频文件：复用 movie 面板逻辑
4. 一级分类目录：分类标签选择器（movie/tv）
5. folder_type 选择器：根据一级标签过滤选项，显示中文

### TvDetail.tsx / SeriesCollectionList.tsx / MovieCollectionGrid.tsx

1. 可能需要更新或合并

---

## TODO 清单

### 第1步：后端类型重命名（基础） ✅
- [x] organizer.py: `_CATEGORY_KEYWORD_MAP` 简化为 movie/tv
- [x] organizer.py: `infer_category_tag` 推断不了默认 `movie`
- [x] organizer.py: `_classify_by_category` 只处理 movie/tv
- [x] organizer.py: `_classify_movie_category` 返回值 movie/collection/series/mixed
- [x] organizer.py: 新增 `_classify_tv_category` 处理 tv 标签下的判定
- [x] organizer.py: `_classify_by_structure` 所有旧类型名更新
- [x] organizer.py: `rename_videos_in_folder` 中的 `is_collection` 判断更新
- [x] organizer.py: `reorganize_seasons` 确保可反复调用
- [x] main.py: 树构建 `finalize` 中 tv 子目录标记 `season`
- [x] main.py: `_get_category_from_path` 返回 movie/tv
- [x] main.py: `set_folder_type` 可选值更新
- [x] main.py: `set_category_tag` 可选值更新为 movie/tv
- [x] analyzer.py: folder_type 引用更新
- [x] scraper.py: folder_type 参数值更新

### 第2步：后端 mixed 判定优化 ✅
- [x] organizer.py: tv 标签下 mixed 判定 — 子目录各自是独立 tv 但不同剧
- [x] organizer.py: 判定方法 — 子目录 classify 为 tv 后检查文件名前缀是否相同
- [x] organizer.py: 豁免 Season 00/Specials/SP/OVA 等特别篇目录，不参与"不同剧"判定

### 第3步：后端 season 整理集成 ✅
- [x] organizer.py: reorganize_seasons 扁平 tv 强制生成 Season 01 并移入视频
- [x] organizer.py: reorganize_seasons 有子目录+散落视频时按季号归入
- [x] main.py: 刮削 API 对 tv 类型预处理（先季化再刮削）
- [ ] organizer.py: season 文件夹有独立的刮削/影子名/清洗名（已有，通过树构建标记 season + FolderDetail 支持）

### 第4步：前端类型定义 & 工具函数 ✅
- [x] types/index.ts: category_tag 类型更新
- [x] types/index.ts: FolderNode 添加 is_top_category
- [x] lib/folderTypes.ts: 中文标签映射、允许类型、展示判断函数

### 第5步：前端 CardGrid 重构 ✅
- [x] CardItem 类型重构
- [x] items 分类逻辑更新
- [x] tv 展开面板：季小卡片 + 集列表（替换旧的季 tab）
- [x] collection 展开面板保持小卡片网格
- [x] series 展开面板保持缩略图列表
- [x] mixed 类型点击进入（不展开）
- [x] category_tag 角标显示中文

### 第6步：前端 DetailDrawer 重构 ✅
- [x] 末端刮削单元（movie/tv/season）：显示刮削信息 + 影子名/清洗名 + 重新匹配
- [x] 聚合容器（collection/series/mixed）：只显示独立封面 + 一键刮削，不显示刮削信息
- [x] 纯视频文件（散装/末端视频）：已有 VideoDetail 复用 movie 面板逻辑
- [x] 一级分类目录：分类标签选择器（movie/tv）
- [x] folder_type 选择器根据一级标签过滤 + 中文显示
- [x] isAggregate 判断更新为 collection/series/mixed

### 第7步：清理 & 兼容
- [ ] folder_types.json 中的旧类型值迁移
- [ ] 删除不再使用的组件（TvDetail.tsx 如果被替换）
- [x] 更新 PROJECT_MEMORY.md
