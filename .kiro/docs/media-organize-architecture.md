# [当前] 媒体库分类体系与前端展示设计

> 本文档只管分类体系和前端展示规则。
> 整理流水线（含分析层、刮削层）见 `knowledge/organize-pipeline-v3.md`。

## 一、一级分类标签（category_tag）

用户在 UI 上给根目录子文件夹打的标签，只有 2 种：

| 标签 | 中文 | 含义 |
|------|------|------|
| `movie` | 电影 | 电影、动画电影、其他视频 |
| `tv` | 剧集 | 电视剧、动画番、综艺、纪录片 |

- 自动推断：`infer_category_tag()` 用中英文关键词匹配目录名
- 用户可在详情面板修改，持久化到 `config.category_tags`
- 推断不了的默认 `movie`（movie 逻辑更宽松，不会强行改变目录结构）

## 二、文件夹类型（folder_type）

算法自动判定 + 用户可覆盖，共 6 种：

| 类型 | 中文 | 含义 |
|------|------|------|
| `movie` | 电影 | 单部电影封装文件夹 |
| `collection` | 合集 | 多部不相关影片的合集 |
| `series` | 系列 | 同系列影片（如 EVA 新剧场版） |
| `tv` | 剧集 | 剧集/动画/综艺（有季子目录） |
| `season` | 季 | 季文件夹（tv 的子目录） |
| `mixed` | 混合 | 混合内容（多部不同 tv 聚合等） |

### 一级标签下允许的文件夹类型

| 一级标签 | 允许的 folder_type |
|----------|-------------------|
| `movie` | movie, collection, series, mixed |
| `tv` | tv, season, mixed |

## 三、分类算法

### movie 标签下（`_classify_movie_category`）

```
无子目录：
  0个视频 → empty
  1个视频 → movie
  多个视频 → series（同系列）或 collection（不相关）

有子目录 + 有散落视频 → collection

有子目录 + 无散落视频：
  深度 ≥ 3 → mixed
  2层 + 同系列 → series
  2层 + 不相关 → collection
```

### tv 标签下（`_classify_tv_category`）

```
无子目录：
  有视频 → tv（扁平结构，整理时强制季化）

有子目录：
  子目录直接包含视频（两层） → tv
  子目录各自还有子目录（三层，多部不同剧聚合） → mixed
```

- 豁免规则：Season 00/Specials/SP/OVA 等特别篇目录不参与"不同剧"判定

## 四、前端展示规则

### 左侧主内容区（CardGrid）

| folder_type | 点击行为 |
|-------------|----------|
| movie | 不展开，直接右侧 VideoDetail |
| collection | 展开为小卡片网格 |
| series | 展开为缩略图列表 |
| tv | 展开为季小卡片网格，点击卡片切换集列表 |
| season | 不出现在顶层，只在 tv 展开面板中 |
| mixed | 不展开，点击进入（导航到子目录） |

### 右侧详情面板（DetailDrawer）

| folder_type | 封面 | 刮削信息 | 影子名/清洗名 | 操作按钮 |
|-------------|------|----------|--------------|----------|
| movie | 刮削封面 | ✅ | ✅ 视频级 | 刮削/重新匹配/搜索升级/重命名 |
| collection | 独立封面 | ❌ | ❌ | 一键刮削/搜索升级 |
| series | 独立封面 | ❌ | ❌ | 一键刮削/搜索升级 |
| tv | 刮削封面 | ✅ | ✅ 文件夹级 | 刮削/重新匹配/搜索升级/重命名 |
| season | 刮削封面 | ✅ | ✅ 文件夹级 | 刮削/重新匹配/搜索升级/重命名 |
| mixed | 独立封面 | ❌ | ❌ | 一键刮削 |

逻辑：
- movie/tv/season 是"末端刮削单元"（`isScrapeUnit`），有完整刮削信息
- collection/series/mixed 是"聚合容器"（`isAggregate`），只有独立封面
- 纯视频文件复用 movie 面板逻辑

## 五、标准目录结构

```
NAS 根目录/
├── 欧美电影/                          ← collection（一级分类 movie）
│   ├── 盗梦空间 Inception (2010)/     ← movie
│   │   └── *.mkv + movie.nfo + poster.jpg
│   └── 星际穿越 Interstellar (2014)/ ← movie
├── 魔戒三部曲/                        ← series
│   ├── 指环王1 护戒使者 (2001)/       ← movie
│   ├── 指环王2 双塔奇兵 (2002)/
│   └── 指环王3 王者无敌 (2003)/
├── 黑镜 Black Mirror/                 ← tv（一级分类 tv）
│   ├── tvshow.nfo + poster.jpg
│   ├── Season 01/
│   │   ├── season.nfo + poster.jpg
│   │   └── S01E01.mkv + S01E01.nfo
│   └── Season 02/
└── 肖申克的救赎 (1994)/               ← movie
    └── *.mkv + movie.nfo + poster.jpg
```
