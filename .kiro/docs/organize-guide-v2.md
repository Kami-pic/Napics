# 整理操作指南 v2.0

本文档是整理 NAS 媒体库的唯一操作手册。所有整理操作必须严格按照本文档执行。

---

## 一、文件夹分类规则

### 6 种类型

| 类型 | 含义 | 判断条件 | 整理后结构 |
|------|------|----------|-----------|
| movie | 单部电影 | 单视频文件（或CD分片） | `电影名/movie.nfo + poster.jpg + 电影.mkv` |
| tv | 剧集 | 多集视频，文件名有集号 | `剧名/tvshow.nfo + Season 01/season.nfo + S01E01.nfo` |
| series_collection | 系列电影 | 多部相关电影（如三部曲） | `系列名/电影1/movie.nfo + 电影2/movie.nfo` |
| movie_collection | 电影聚合 | 多部无关电影（如"欧美电影"） | 同 series_collection |
| variety | 综艺 | 文件名带日期 | 同 movie_collection |
| mixed | 混合 | 以上都不是 | 同 movie_collection |

### 核心规则

1. **每个末端视频必须有自己的独立文件夹**，NFO/封面/字幕都在文件夹内
2. **散落视频**（直接放在父目录下没有自己文件夹的）必须先包裹进独立文件夹再刮削
3. **聚合文件夹**（movie_collection/series_collection/mixed）不写文件夹级 NFO，每个子视频独立刮削
4. **tv 类型**写文件夹级 tvshow.nfo + 每季 season.nfo + 每集 episode.nfo

### 分类判定函数：`organizer.classify_folder(folder_path, library_data)`

判定流程（按顺序，命中即返回）：

```
1. 有 movie.nfo 且单视频 → movie
2. 有 tvshow.nfo → tv
3. 无子目录 + 单视频 → movie
4. 无子目录 + 多视频 + 多数有独立同名NFO → series_collection 或 movie_collection
5. 无子目录 + 多视频 + 多数有集号 → tv
6. 无子目录 + 多视频 + 平均时长<45min → tv
7. 无子目录 + 多视频 + 平均时长>60min → series_collection 或 movie_collection
8. 有子目录 + 全是季目录 → tv
9. 有子目录 + 部分季目录 → tv 或 mixed
10. 有子目录 + 子目录全是 movie → series_collection 或 movie_collection
11. 其他 → mixed
```

**已知陷阱和解决办法：**

| 陷阱 | 例子 | 解决 |
|------|------|------|
| 旧 tvshow.nfo 导致误判为 tv | 命运之夜有旧的 TV 版 NFO | 整理前先删旧刮削再分析 |
| 方括号数字被当成集号 | 永远之久远 `[04]` | 先检查独立 NFO 数量，有独立 NFO 优先判为 collection |
| 剧场版被当成季目录 | EVA 子目录含"剧场版" | `_is_season_dir` 不匹配"剧场版" |
| 中文数字季号不识别 | "第一季" | `_is_season_dir` 匹配 `第[一二三四五六七八九十]+季` |
| 无子目录的不同作品被判为 tv | 茗记4个不同视频 | **待修**：需要检查视频文件名是否各不相同 |
| 聚合文件夹被写了 tvshow.nfo 后误判 | 动画短片合集 | **待修**：聚合文件夹不应写文件夹级 NFO |

---

## 二、整理 7 步流水线

### 总览

```
第0步：散落视频封装  →  一级分类目录下的独立视频封装进文件夹
第1步：旧刮削备份删除  →  避免旧 NFO 干扰分类
第2步：分析            →  判定类型 + 诊断结构问题
第3步：结构归位        →  散落视频包裹 + CD合并 + 文件移动
第4步：多季规整        →  仅 tv 类型，合并散落季
第5步：刮削            →  TMDB 搜索 + 写 NFO + 下载封面
第6步：标准名生成      →  生成 "中文名 英文名 S01E01" 格式
第7步：影子名写入      →  存到 media_library.json
```

**关键：必须按顺序执行。先封装散落视频，再删旧刮削再分析，先整理结构再刮削，先刮削再生成标准名。**

### 第 0 步：散落视频封装

**目的**：一级分类目录（如 `动画电影/`、`电影/`）下直接散落的视频文件，各自封装进独立文件夹。

**核心规则**：每个末端视频必须有自己的文件夹，NFO/封面/字幕都在文件夹内。

**函数**：`organizer.wrap_loose_videos_in_category(category_path, dry_run=False)`

**操作**：
```python
# 扫描一级分类目录下的散落视频
# 每个视频用 _clean_filename_for_folder 生成文件夹名
# CD 分片合并到同一文件夹
# 关联的字幕/NFO/图片一起移入
```

**注意**：
- 只处理一级分类目录，不递归
- 二级文件夹内的散落视频由第 3 步处理
- 封装后需要同步 media_library.json 的路径

### 第 1 步：旧刮削备份删除

**目的**：删除旧的 NFO/封面文件，避免旧数据干扰第2步的类型判定。

**函数**：无现成函数，需要手动实现（`_organize_pipeline.py` 中的 `archive_old_scrape`）。

**操作**：
```python
# 递归处理：父文件夹 + 所有子文件夹，每个文件夹各自打包
def archive_old_scrape(folder_path, recursive=True, delete_after=True):
    # 识别刮削文件：poster.jpg, fanart.jpg, movie.nfo, tvshow.nfo, season.nfo,
    #              clearlogo.png, folder.jpg, cover.jpg, theme.mp3,
    #              *-poster.jpg, *-fanart.jpg, *.nfo（同名NFO）
    # 打包为 .old_scrape.zip（如果已有则跳过）
    # delete_after=True 时删除原文件
```

**注意**：
- 必须在分析之前执行，否则旧 tvshow.nfo 会导致分类错误
- 打包而非直接删除，方便回滚
- 每个文件夹各自打包，不要把子目录的文件打到父目录的 zip 里

---

### 第 2 步：分析

**目的**：判定文件夹类型 + 诊断结构/命名/刮削问题。

**函数**：`analyzer.analyze_folder(folder_path, library_data)`

**返回值关键字段**：
```python
{
    "folder_type": "tv" | "movie" | "series_collection" | "movie_collection" | "mixed" | ...,
    "structure_ops": [...],    # 结构操作建议（wrap_in_folder / move / move_to_subdir）
    "rename_ops": [...],       # 改名建议
    "scrape_issues": [...],    # 刮削问题
    "filename_issues": [...],  # 文件名问题（广告/乱码）
}
```

**注意**：
- `analyze_folder` 内部调用 `classify_folder` 判定类型
- `structure_ops` 里的 `wrap_in_folder` 操作是第3步要执行的
- 分析是只读操作，不修改任何文件

---

### 第 3 步：结构归位

**目的**：把散落视频包裹进独立文件夹，CD分片合并，孤立刮削文件归位。

**函数**：`organizer.organize_folder(folder_path, tmdb_client, dry_run=False, library_data=library)`

**内部逻辑**：
```
1. 调用 analyzer.analyze_folder 获取 structure_ops
2. 执行 wrap_in_folder：每个散落视频创建独立文件夹，文件夹名由 _clean_filename_for_folder 生成
3. 执行 move：CD分片合并到同一文件夹
4. 孤立刮削文件归位：改名后的 NFO/poster 文件名不匹配新文件夹名时，用模糊匹配归位
```

**关键规则**：
- **聚合文件夹（mixed/movie_collection/series_collection）的散落视频必须各自包裹**，不能移到统一子目录
- CD 分片（阿甘正传CD1 + CD2）合并到同一个文件夹
- 文件夹名由 `_clean_filename_for_folder` 生成，去掉广告/质量标签/CD标记

**`_clean_filename_for_folder` 清洗顺序**：
```
0. + 替换为空格
1. 去方括号内容 []、中文方括号【】、日文引号「」
2. 去圆括号内含域名的广告
3. 去已知广告站名（红旅首发/电影天堂/影视帝国/66影视）
4. 去裸 URL
5. 去质量标签（1080p/720p/BluRay/WEB-DL/x264/x265/AAC/DTS/BD/HD/DVD...）
6. 去语言字幕标签（中英双字/中文字幕/UNCUT/KORSUB...）
7. 去媒体形式标签（劇場版/剧场版/TV版/OVA/SP/特别篇...）
8. 去季号标记（第X季/S01/1-8季）
9. 去分辨率数字（1024X576/1280X720）
10. 去 CD 标记
11. 去尾部发布组标签（-FGT/-SPARKS）
12. 清理分隔符（. _ 转空格）
13. 去尾部纯数字集号
```

---

### 第 4 步：多季规整

**目的**：仅 tv 类型。如果多季散落在不同位置，合并到统一父目录。

**函数**：`organizer.reorganize_seasons(folder_path, tmdb_client, dry_run=False)`

**注意**：非 tv 类型跳过此步。

---

### 第 5 步：刮削

**目的**：搜索 TMDB 获取元数据，写 NFO 文件，下载封面。

**函数**：`scraper.scrape_folder(folder_path, tmdb_client, force=True)`

**`scrape_folder` 的分支逻辑（这是最复杂的一步）**：

```
输入：folder_path
├── 有子目录？
│   ├── YES → 分支A：有子目录的文件夹
│   │   1. 用父文件夹名搜 TMDB（清洗名 + 英文部分 + 渐进缩短）
│   │   2. 如果搜到 TV 类型 → 写 tvshow.nfo + poster
│   │   3. 递归每个子目录调用 scrape_folder
│   │   4. 为季子目录写 season.nfo + 季封面
│   │   ⚠️ 问题：对聚合文件夹也写了 tvshow.nfo（应该跳过）
│   │
│   └── NO → 分支B：末端文件夹（无子目录）
│       ├── 是分类聚合文件夹？（_is_category_folder）
│       │   ├── YES → 分支B1：每个视频独立刮削
│       │   │   对每个视频调用 scrape_video
│       │   │
│       │   └── NO → 分支B2：统一刮削
│       │       1. 用文件夹名搜 TMDB
│       │       2. 单视频 → 写 movie.nfo
│       │       3. 多视频 → 写 tvshow.nfo + 每个视频写分集 NFO
│       │          ⚠️ 问题：多视频一律当 TV 处理，聚合文件夹也被当 TV
│       │          ⚠️ 问题：分集 NFO 用 get_episode_detail，404 时 fallback 写错误数据
```

**搜索策略（渐进式）**：
```
第1轮：_clean_filename_for_folder 清洗名 + 英文部分，中英文同时搜取最佳
第2轮：去年份集号后再搜
第3轮：拆副标题（冒号分隔，从后往前试）
第4轮：只取前几个中文字
第5轮：从视频文件名提取搜索词（文件夹名搜不到时的 fallback）
```

**已知问题和应该的行为**：

| 场景 | 当前行为（错误） | 应该的行为 |
|------|-----------------|-----------|
| 聚合文件夹（欧美电影/动画短片合集） | 写了文件夹级 tvshow.nfo | 不写文件夹级 NFO，每个子视频独立刮削 |
| 末端多视频聚合（茗记/经典电影） | 当 TV 处理，所有视频共享一个 NFO | 先判断类型，聚合类型每个视频独立刮削 |
| TV 分集 get_episode_detail 返回 404 | 用 _write_movie_nfo_for_video 写文件夹级数据 | 写 episode NFO 只填剧名+季号+集号，不填分集标题 |
| TV 分集 NFO 的 title | 填了分集标题（如"红蛇""女巫瓶"） | 填剧名（如"权力的游戏"） |
| series_collection 有子目录 | 给父目录写 tvshow.nfo | 不写父目录 NFO，递归子目录各自独立刮削 |

---

### 第 6 步：标准名生成

**目的**：为每个视频生成标准化的影子名（不改原始文件名）。

**函数**：`organizer.rename_videos_in_folder(folder_path, tmdb_client, dry_run=True, library_data=library)`

**标准名格式**：
- tv 分集：`中文名 英文名 S01E01`（如 `切尔诺贝利 Chernobyl S01E01`）
- movie：`中文名 英文名 (年份)`（如 `千年女优 Millennium Actress (2002)`）
- collection 子项：各自独立的 `中文名 英文名 (年份)`

**内部逻辑**：
```
1. 判断文件夹类型（classify_folder）
2. is_collection = type in (movie_collection, series_collection, mixed, variety, misc)
3. 读文件夹级 NFO（folder_scrape）
4. 对每个视频：
   a. 读视频同名 NFO → 有则用
   b. 无同名 NFO 且非 collection → 用 folder_scrape
   c. 无同名 NFO 且是 collection → 尝试用 tmdb_client 独立搜索
   d. 调用 generate_standard_name(filename, scrape_data, video_info, folder_title, is_collection)
5. 递归子目录，用父目录剧名+英文名修正子目录视频的标准名
```

**`generate_standard_name` 逻辑**：
```
1. parse_filename 提取集号/季号/年份
2. 有 scrape_data → 用 title + english_title + year
3. 无 scrape_data → 用 _clean_filename_for_folder 清洗文件名
4. 构建名字：
   - is_collection=True → "中文名 英文名 (年份)"，不加集号
   - episode 不为 None → "中文名 英文名 S01E01"
   - 其他 → "中文名 英文名 (年份)"
```

**已知问题和应该的行为**：

| 场景 | 当前行为（错误） | 应该的行为 |
|------|-----------------|-----------|
| collection 类型所有视频用文件夹级 NFO | 影子名全一样 | 每个视频用自己的 NFO 或独立搜索 |
| 分集标准名用了分集标题 | "红蛇 S01E01" | "权力的游戏 Game of Thrones S01E01" |
| 影子名含 hash | "(C46B0638)" | 清洗掉 hash |
| 影子名含方括号 | "[Heaven's Feel]" | 清洗掉方括号 |
| 影子名含广告 | "www.hltm.cc" | 清洗掉 URL |

---

### 第 7 步：影子名写入

**目的**：把标准名存到 media_library.json。

**函数**：`shadow_name_manager.ShadowNameManager.auto_fill(file_path, shadow_name, source, organize_status)`

**注意**：
- `source="parsed"` 表示自动生成
- `organize_status="ok"` 表示整理成功，`"scrape_failed"` 表示刮削失败
- 不覆盖 `source="manual"` 的手动设置
- 每次调用都会全量写 JSON，批量操作时注意性能

---

## 三、集号提取规则

**函数**：`tmdb_client.parse_filename(filename)`

按优先级顺序匹配（命中即停止）：

| 优先级 | 格式 | 例子 | 正则 |
|--------|------|------|------|
| 1 | S01E01 | `Chernobyl.S01E01.mkv` | `S(\d+)\s*E(\d+)` |
| 2 | 第X集/第X话 | `第3集.mp4` | `第(\d+)[集话]` |
| 3 | [02] 方括号纯数字 | `[KTXP][记录的地平线][01].mp4` | `\[(\d{1,3})\]` |
| 4 | [13v2] 方括号+版本号 | `[Sakurato] 86 [13v2].mkv` | `\[(\d{1,3})v\d\]` |
| 5 | (10) 圆括号纯数字 | `加速世界 (10).mp4` | `\((\d{1,3})\)` 排除年份 |
| 6 | - 02 连字符分隔 | `Samurai Champloo - 02 (BD).mkv` | `-\s*(\d{1,3})\s*[-\[\(]` |
| 7 | S1 01 季号+空格+集号 | `Shingeki S1 01 [BD].mkv` | `S(\d+)\s+(\d{1,3})` |
| 8 | 第一集 中文数字 | `斯巴达克斯第一集.rmvb` | `第([一二三...]+)[集话]` |
| 9 | 开头纯数字 | `02.2160p.HD.mkv` | `^(\d{1,3})(?:\.\|[ ])` |
| 10 | 标题后数字+括号 | `Baccano! 01 (1920x).mkv` | `[a-zA-Z!?]\s+(\d{1,3})\s*[\[\(]` |
| 11 | EP01 / E01 | `EP03.mkv` | `EP?(\d{1,3})` |
| 12 | 尾部纯数字 | `权力的游戏02.rmvb` | 去分辨率后 `(\d{1,2})$` |

**预处理**：`+` 替换为空格（字幕组常用 `+` 代替空格）

---

## 四、按文件夹类型的完整处理流程

### 4.1 movie 类型（单部电影）

```
第1步：删旧刮削
第2步：analyze_folder → type=movie
第3步：organize_folder → 无操作（已有独立文件夹）
第4步：跳过
第5步：scrape_folder → 写 movie.nfo + poster.jpg + fanart.jpg
第6步：rename_videos_in_folder → "中文名 英文名 (年份)"
第7步：auto_fill
```

### 4.2 tv 类型（剧集）

```
第1步：删旧刮削
第2步：analyze_folder → type=tv
第3步：organize_folder → 散落视频移到季目录
第4步：reorganize_seasons → 合并散落季
第5步：scrape_folder →
  - 父目录：tvshow.nfo + poster.jpg
  - 每个季目录：season.nfo + poster.jpg
  - 每个视频：episode.nfo（用 TMDB ID + 集号获取）
第6步：rename_videos_in_folder →
  - 文件夹："中文名 英文名 (年份)"
  - 季目录："中文名 英文名 Season 01"
  - 视频："中文名 英文名 S01E01"
  ⚠️ 分集标准名必须用剧名，不用分集标题
第7步：auto_fill
```

### 4.3 series_collection 类型（系列电影）

```
第1步：删旧刮削
第2步：analyze_folder → type=series_collection
第3步：organize_folder → 散落视频各自包裹进独立文件夹
第4步：跳过
第5步：scrape_folder →
  ⚠️ 不写父目录 NFO
  - 递归每个子目录，各自独立刮削为 movie
  - 每个子目录：movie.nfo + poster.jpg
第6步：rename_videos_in_folder(is_collection=True) →
  - 每个视频用自己的 NFO："中文名 英文名 (年份)"
  ⚠️ 不用父目录名，不加集号
第7步：auto_fill
```

### 4.4 movie_collection / mixed 类型（电影聚合）

```
与 series_collection 完全相同。
唯一区别：series_collection 的子项有共同前缀（如"来自深渊"三部曲），
movie_collection 的子项各不相同（如"欧美电影"下的各种电影）。
处理流程一模一样。
```

**关键**：聚合文件夹的每个子视频必须有独立文件夹 + 独立 NFO + 独立封面。
不能用父目录的 NFO 覆盖所有子视频。

---

## 五、函数调用关系图

```
整理一个文件夹的完整调用链：

_organize_pipeline.run_pipeline(folder_path, execute=True)
│
├── 第0步：organizer.wrap_loose_videos_in_category(category_path)
│   └── 扫描一级分类目录，散落视频封装进独立文件夹
│
├── 第1步：archive_old_scrape(folder_path)
│   └── 递归打包 .old_scrape.zip，删除旧 NFO/poster
│
├── 第2步：analyzer.analyze_folder(folder_path, library)
│   ├── organizer.classify_folder(folder_path, library)
│   │   ├── scraper.read_nfo(folder_path)          # 读标准 NFO
│   │   ├── organizer._is_season_dir(dirname)       # 判断是否季目录
│   │   ├── organizer._count_episode_files(videos)  # 统计集号文件数
│   │   ├── organizer._is_series_collection(videos) # 判断是否系列
│   │   └── organizer._get_durations(...)           # 读时长辅助判断
│   ├── analyzer._diagnose_structure(...)           # 诊断结构问题
│   ├── analyzer._diagnose_scrape(...)              # 诊断刮削问题
│   └── analyzer._diagnose_rename(...)              # 诊断命名问题
│
├── 第3步：organizer.organize_folder(folder_path, client, dry_run=False, library)
│   ├── analyzer.analyze_folder(...)                # 获取 structure_ops
│   ├── 执行 wrap_in_folder                         # 散落视频包裹
│   │   └── analyzer._clean_filename_for_folder()   # 生成文件夹名
│   ├── 执行 move                                   # CD合并 + 文件移动
│   └── 孤立刮削文件归位                              # 模糊匹配归位
│
├── 第4步（仅tv）：organizer.reorganize_seasons(folder_path, client, dry_run=False)
│
├── 第5步：scraper.scrape_folder(folder_path, client, force=True)
│   ├── 有子目录 →
│   │   ├── 搜 TMDB（清洗名 + 英文 + 渐进缩短）
│   │   ├── TV 类型 → scraper.write_tvshow_nfo()
│   │   ├── 递归子目录 → scrape_folder(子目录)
│   │   └── 季目录 → scraper.write_season_nfo()
│   └── 无子目录 →
│       ├── _is_category_folder? → 每个视频 scrape_video()
│       └── 否 → 搜 TMDB → write_movie_nfo 或 write_tvshow_nfo
│           └── 多视频 → 每个视频写分集 NFO
│               ├── get_episode_detail(tmdb_id, season, episode)
│               └── 404 fallback → _write_movie_nfo_for_video
│
├── 第6步：organizer.rename_videos_in_folder(folder_path, client, dry_run=True, library)
│   ├── organizer.classify_folder(...)              # 判断 is_collection
│   ├── scraper.read_nfo(folder_path)               # 读文件夹级 NFO
│   ├── 对每个视频：
│   │   ├── scraper.read_video_nfo(video_path)      # 读视频同名 NFO
│   │   └── organizer.generate_standard_name(...)   # 生成标准名
│   │       └── tmdb_client.parse_filename(...)     # 提取集号
│   └── 递归子目录，用父目录剧名修正标准名
│
└── 第7步：shadow_name_manager.auto_fill(file_path, shadow_name, "parsed", organize_status)
```

---

## 六、执行注意事项

### 6.1 不要全量跑

分批处理，每批验证后再继续：
```
第1批：电影/（最简单，大部分是 movie）
第2批：电视剧/（tv 类型）
第3批：动画番/（tv 类型，文件名复杂）
第4批：动画电影/（混合类型）
第5批：其他目录
```

### 6.2 跳过已整理好的

检查文件夹是否已有正确的 NFO + 影子名，有则跳过。不要重新整理已经测试通过的文件夹。

### 6.3 dry_run 先预览

每个文件夹先 `dry_run=True` 预览，确认分类/结构/标准名都正确后再 `execute`。

### 6.4 验证清单

每个文件夹整理后必须验证：
- [ ] 分类正确（classify_folder 返回的 type）
- [ ] 结构正确（每个视频有独立文件夹，无散落文件）
- [ ] 刮削正确（NFO 的 title 和文件夹名匹配）
- [ ] 标准名正确（格式对、有集号、用剧名不用分集标题、无广告/hash/方括号）
- [ ] 影子名已写入（media_library.json 中有 shadow_name）

---

## 七、当前代码 vs 应该的行为（待修清单）

以下是对比 guide 流程后，当前代码需要修改的地方：

### 7.1 `scrape_folder` — 聚合文件夹不应写文件夹级 NFO

**当前**：有子目录时一律尝试写 tvshow.nfo。
**应该**：先调用 `classify_folder` 判断类型，如果是 series_collection / movie_collection / mixed，不写文件夹级 NFO，直接递归子目录各自独立刮削。

**修改位置**：`scraper.py` `scrape_folder` 的"有子目录"分支开头。
**修改方案**：
```python
# 在 "if subdirs and depth < max_depth:" 之后加：
from organizer import classify_folder
ft = classify_folder(folder_path, None).get("type", "")
if ft in ("series_collection", "movie_collection", "movie_aggregate", "mixed"):
    # 聚合文件夹：不写父目录 NFO，直接递归子目录
    for sub in subdirs:
        sub_result = scrape_folder(sub_path, tmdb_client_instance, force, depth+1, max_depth)
        results["children"].append(...)
    results["self"] = {"status": "aggregate", "data": None}
    return results
```

### 7.2 `scrape_folder` — 末端多视频聚合不应当 TV 处理

**当前**：末端文件夹多视频时，`is_tv = result.media_type in ("tv", "episode") or len(video_files) > 1`，把所有多视频文件夹都当 TV。
**应该**：先判断类型，聚合类型走 `_is_category_folder` 分支，每个视频独立刮削。

**修改位置**：`scraper.py` `scrape_folder` 末端文件夹的多视频处理。
**修改方案**：
```python
# 在写完文件夹级 NFO 后，多视频处理前：
ft = classify_folder(folder_path, None).get("type", "")
if ft in ("series_collection", "movie_collection", "mixed"):
    # 聚合类型：每个视频独立刮削，不用文件夹级 TMDB ID
    for vf in video_files:
        vr = scrape_video(os.path.join(folder_path, vf), tmdb_client_instance, force)
        results.setdefault("video_results", []).append(...)
else:
    # TV 类型：用 TMDB ID + 集号
    # （现有逻辑）
```

### 7.3 `scrape_folder` — 分集 NFO fallback 不应写错误数据

**当前**：`get_episode_detail` 返回 404 时，用 `_write_movie_nfo_for_video(vf_path, result)` 写了文件夹级数据，导致分集 NFO 的 title 变成文件夹级 title。
**应该**：404 时不写分集 NFO，或者写一个只有剧名+季号+集号的简单 episode NFO。

**修改位置**：`scraper.py` `scrape_folder` 的 `get_episode_detail` fallback。

### 7.4 `generate_standard_name` — 清洗不够干净

**当前**：影子名可能包含 hash `(C46B0638)`、方括号 `[Heaven's Feel]`、广告 URL。
**应该**：`generate_standard_name` 的最终输出必须再过一遍清洗。

**修改位置**：`organizer.py` `generate_standard_name` 末尾。
**修改方案**：
```python
# 在 return 之前加最终清洗
name = re.sub(r'\([A-Fa-f0-9]{6,}\)', '', name)  # 去 hash
name = re.sub(r'\[.*?\]', '', name)                # 去方括号
name = re.sub(r'www\.\S+', '', name, flags=re.I)   # 去 URL
name = re.sub(r'\s+', ' ', name).strip()
```

### 7.5 `classify_folder` — 无子目录多文件聚合判定

**当前**：无子目录 + 多视频 + 无独立 NFO + 集号不够 + 无时长数据 → 默认 movie_collection。但如果文件名有集号模式（如圆括号数字），会被误判为 tv。
**应该**：检查视频文件名是否各不相同（不是同一部剧的不同集），如果各不相同则判为 collection。

**修改位置**：`organizer.py` `classify_folder` 的末端文件夹多文件分支。

### 7.6 `rename_videos_in_folder` — collection 类型不应 fallback 到 folder_scrape

**当前**：代码里已经有 `if is_collection` 的判断，但 `folder_scrape` 仍然会被用于没有独立 NFO 的视频。
**应该**：collection 类型的视频如果没有独立 NFO，用 `_clean_filename_for_folder` 清洗文件名作为影子名，不用 folder_scrape。

**修改位置**：`organizer.py` `rename_videos_in_folder` 的视频循环内。

---

## 八、测试用例（验证修复后的行为）

修复代码后，必须用以下文件夹验证：

| 文件夹 | 期望类型 | 期望刮削 | 期望标准名 |
|--------|----------|----------|-----------|
| 经典电影之新世代诠释 | mixed | 每个子视频独立 movie.nfo | 各自独立名字 |
| 福音战士新剧场版 | series_collection | 每个子目录独立 movie.nfo | 各自独立名字 |
| 茗记 | series_collection | 每个视频独立 movie.nfo | 各自独立名字 |
| 动画短片合集 | series_collection | 每个子目录独立 movie.nfo | 各自独立名字 |
| 来自深渊剧场版三部曲 | series_collection | 每个子目录独立 movie.nfo | 各自独立名字 |
| 壳中少女 | series_collection | 每个子目录独立 movie.nfo | 各自独立名字 |
| 永远之久远 | series_collection | 每个子目录独立 movie.nfo | 各自独立名字 |
| 切尔诺贝利S1 | tv | tvshow.nfo + 分集 episode.nfo | `切尔诺贝利 Chernobyl S01E01` |
| 冰与火之歌 | tv | tvshow.nfo + 分集 episode.nfo | `权力的游戏 Game of Thrones S01E01` |
| 欧美电影（聚合子目录） | movie_collection | 每个子视频独立 movie.nfo | 各自独立名字 |


---

## 九、架构重构：类型驱动的刮削

### 问题

当前 `scrape_folder` 内部自己判断类型（有子目录？多视频？`_is_category_folder`？），和 `classify_folder` 的判断逻辑不一致，导致：
- 聚合文件夹被当 TV 刮削
- 末端多视频聚合被写 tvshow.nfo
- 分支逻辑复杂难维护

### 解决方案

**类型先行，刮削跟随**：

```
第2步 classify_folder → folder_type
第5步 根据 folder_type 调用不同刮削逻辑：

if folder_type == "movie":
    scrape_single_movie(folder_path)
elif folder_type == "tv":
    scrape_tv_show(folder_path)
elif folder_type in ("series_collection", "movie_collection", "mixed"):
    scrape_collection(folder_path)
```

三个刮削函数各自职责清晰：

- `scrape_single_movie`：搜 TMDB → 写 movie.nfo + poster
- `scrape_tv_show`：搜 TMDB → 写 tvshow.nfo + 递归季目录写 season.nfo + 每集 episode.nfo
- `scrape_collection`：不写父目录 NFO → 递归每个子目录/子视频各自独立刮削

`scrape_folder` 变成一个简单的分发器，不再有复杂的分支逻辑。


### 重构方案：folder_type 作为流水线上下文

```python
# 流水线入口：一次判定，全程传递
def run_pipeline(folder_path, execute=False):
    # 第1步：删旧刮削
    archive_old_scrape(folder_path)
    
    # 第2步：分析（判定类型）
    report = analyzer.analyze_folder(folder_path, library)
    folder_type = report["folder_type"]  # 唯一的类型判定点
    
    # 第3步：结构归位（接收 folder_type）
    organizer.organize_folder(folder_path, folder_type=folder_type, ...)
    
    # 第4步：多季规整（仅 tv）
    if folder_type == "tv":
        organizer.reorganize_seasons(folder_path, ...)
    
    # 第5步：刮削（接收 folder_type）
    scraper.scrape_folder(folder_path, folder_type=folder_type, ...)
    
    # 第6步：标准名（接收 folder_type）
    organizer.rename_videos_in_folder(folder_path, folder_type=folder_type, ...)
    
    # 第7步：影子名写入
    ...
```

每个函数签名改为：
```python
def scrape_folder(folder_path, tmdb_client, force=False, folder_type=None, ...):
    if folder_type is None:
        folder_type = classify_folder(folder_path).get("type", "")  # 保底
    # 后续逻辑直接用 folder_type，不再自己判断
    
def rename_videos_in_folder(folder_path, tmdb_client=None, dry_run=True, folder_type=None, ...):
    if folder_type is None:
        folder_type = classify_folder(folder_path).get("type", "")  # 保底
    is_collection = folder_type in ("movie_collection", "series_collection", "mixed", ...)
    # 不再内部调 classify_folder
```

**好处**：
1. 类型只判定一次，全程一致
2. 每个函数逻辑简单——收到类型，按类型做事
3. 单独调用时有保底，不会报错
4. 调试时一眼就能看到类型是什么，不用猜每个函数内部判断的结果


---

## 十、讨论确认的设计决策（v2.1 更新）

### 10.1 旧刮削处理策略

**不无脑删旧刮削**。旧 NFO 大概率是正确的（用户手动做的/tinyMediaManager 做的）。

判断旧刮削是否可用：
- **title 非空** → 有效，复用（不管有没有 TMDB ID）
- **title 为空** → 无效，当没有处理

有效的旧刮削：
- 分类时：media_type 作为参考，和文件结构交叉验证
- 刮削时：已有 NFO 就跳过（force=False）
- 标准名：直接用 NFO 的 title + english_title 生成
- 缺字段（poster/english_title）：用 title+year 搜 TMDB 补充

删旧刮削只在"全量整理测试"场景下使用，模拟从零开始。

### 10.2 显示名优先级

所有需要用"名字"做判断的地方，统一用：

```python
display_name = shadow_name or file_name  # 永远不为空
```

- 已整理的文件：shadow_name 是干净的标准名
- 新入库的文件：shadow_name 为空，fallback 到原始文件名
- 清洗函数只在 shadow_name 为空时才被调用（fallback 路径）

### 10.3 流程顺序

保持现有顺序不变：**分类 → 结构归位 → 刮削 → 标准名 → 影子名**

原因：刮削依赖分类（需要知道搜 TV 还是 movie），所以分类必须在刮削之前。

### 10.4 分类信号优先级

```
文件结构（子目录、视频数量）  → 最高
旧 NFO media_type（交叉验证） → 高
文件名集号特征               → 中
文件名内容/共同前缀          → 低
视频时长                     → 最低
```

NFO 的 media_type 不直接信任，必须和文件结构交叉验证。

### 10.5 mixed 类型处理

mixed = 同一父目录下既有剧集季目录，又有独立视频/子目录。

处理策略：拆开来，每个部分按自己的类型处理：
- 季目录 → 按 tv 刮削
- 独立视频 → 先包裹，再按 movie 刮削
- 独立子目录 → 递归判断自己的类型

### 10.6 清洗函数修复（v2.1）

已修复的 bug：
1. 全是方括号的文件名清洗后为空 → 新增 `_extract_core_from_brackets`，从方括号内容提取作品名（优先中文、过滤广告/字幕组/编码标签）
2. 圆括号内的编码信息没清 → 新增 `(xxx x264 xxx)` 格式清洗
3. 圆括号内的 hash 没清 → 新增 `([A-Fa-f0-9]{6,})` 格式清洗
