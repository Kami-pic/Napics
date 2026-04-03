# 全库整理操作指南

本文档是给 AI 执行全库整理时的操作手册。必须严格按照此流程执行，不要自己发明逻辑。

## 核心原则

1. 所有诊断用 `analyzer.py`，所有执行用 `organizer.py`，所有刮削用 `scraper.py`
2. 刮削搜索 TMDB 时必须用 `analyzer._clean_filename_for_folder()` 清洗文件名，不要用原始文件名直接搜
3. `scraper.py` 的 `scrape_folder` 和 `scrape_video` 已经内置了清洗名优先搜索逻辑，直接调用即可
4. 不要试图兼容旧刮削数据，旧的 NFO/封面先打包再全新刮削

## 文件夹分类（4+2种）

| 类型 | 判断条件 | 整理后结构 |
|------|----------|-----------|
| movie | 单视频+文件夹 | `电影名/电影.mkv + movie.nfo + poster.jpg` |
| tv | 剧集（单季或多季） | `剧名/Season 01/S01E01.mkv + tvshow.nfo + season.nfo` |
| series_collection | 系列电影（如魔戒三部曲） | `系列名/电影1/movie.nfo + 电影2/movie.nfo` |
| movie_collection | 电影聚合（如"欧美电影"） | `聚合名/电影1/movie.nfo + 电影2/movie.nfo` |
| variety | 综艺（文件名带日期） | 同 movie_collection |
| misc | 杂项（CG/MV/短片） | 同 movie_collection |

核心规则：**每个末端视频必须有自己的文件夹**，NFO/封面/字幕都在文件夹内。

## 整理执行流程（严格按顺序）

### 第 1 步：旧刮削备份（递归，打包并删除）

在分析之前先清理旧刮削，避免旧 NFO 干扰类型判定：

```python
# archive_old_scrape(folder_path, recursive=True, delete_after=True)
# 递归处理父文件夹和所有子文件夹
# 每个文件夹各自打包为 .old_scrape.zip
```

### 第 2 步：分析

```python
import analyzer
report = analyzer.analyze_folder(folder_path, library_data)
# 旧刮削已清理，分析基于纯文件结构判断类型
```

### 第 3 步：文件移动（结构归位）

```python
import organizer
result = organizer.organize_folder(folder_path, tmdb_client, dry_run=False, library_data=library)
# 内部包含孤立刮削文件归位逻辑
```

### 第 4 步：多季规整

```python
result = organizer.reorganize_seasons(folder_path, tmdb_client, dry_run=False)
```

### 第 5 步：刮削

```python
import scraper
result = scraper.scrape_folder(folder_path, tmdb_client, force=True)
# 内部使用渐进式搜索策略（中英文同时搜+副标题拆分+核心名缩短）
```

### 第 6 步：标准名生成（只存标准名，不改原始文件名）

```python
result = organizer.rename_videos_in_folder(folder_path, tmdb_client, dry_run=True, library_data=library)
# dry_run=True 只生成预览，不改文件
# 标准名格式：中文名 + 英文名 (年份)，如 "切尔诺贝利 Chernobyl S01E01"
# 分集标准名用剧名而非分集标题
```

### 第 7 步：影子名填充

```python
from shadow_name_manager import ShadowNameManager
shadow_m = ShadowNameManager()
for r in result:
    shadow_m.auto_fill(r["old_path"], r["shadow_name"], source="parsed")
# 不覆盖手动设置的影子名
```

## 文件名清洗函数

`analyzer._clean_filename_for_folder(filename)` 是核心清洗函数，按固定顺序执行：

1. 去方括号内容 `[]`、中文方括号 `【】`、日文引号 `「」`（广告标签、字幕组、原始标题重复）
2. 去圆括号内含域名的广告
3. 去已知广告站名（红旅首发、电影天堂、影视帝国、66影视、更多X请去）
4. 去裸 URL
5. 去质量标签（BD/HD/DVD/SD/UHD/1080p/720p/BluRay/WEB-DL/WEB-HR/WEBRip/BDRip/x264/x265/H.264/H.265/HEVC/AVC/AAC/DTS/FLAC/10bit 等）
6. 去语言字幕标签（中英双字/中英字幕/中文字幕/中字/英字/UNCUT/KORSUB/未删减版）
7. 去媒体形式标签（劇場版/剧场版/TV版/电视剧版/OVA/OAD/SP/特别篇/番外篇/总集篇/完结篇）
8. 去季号标记（第X季含中文数字/S01）
9. 去分辨率数字（1024X576/1280X720/1920x1080）
10. 去 CD 标记
11. 去发布组标签（尾部 -FGT/-SPARKS 等）
12. 清理分隔符（`.` `_` 转空格）

**核心原则：清洗得越干净越好。年份、媒体形式、季号等辅助信息不放在搜索词里，而是在 best_match 打分时使用。**

示例：
```
黑客帝国.1080p.BD中英双字无水印[66影视www.66Ys.Co].mkv → 黑客帝国
星球大战前传1幽灵的威胁BD双语双字修复版[电影天堂www.dy2018.com].mkv → 星球大战前传1幽灵的威胁
影视帝国(bbs.cnxp.com).触不到的恋人.cd1.rmvb → 触不到的恋人
阿甘正传CD1.rmvb → 阿甘正传
【更多美剧请去www.dy131.com】冰与火之歌：权力的游戏第一季HD中英双字1280高清01.rmvb → 冰与火之歌：权力的游戏01
命运之夜 天之杯Ⅰ：恶兆之花 劇場版「Fatestay night [Heaven's Feel] Ⅰ. presage flower」(2017) 1080p.mkv → 命运之夜 天之杯Ⅰ：恶兆之花 (2017)
The.Matrix.1999.1080p.BluRay.x264-SPARKS.mkv → The Matrix 1999
Inception.2010.2160p.UHD.BluRay.x265-TERMINAL.mkv → Inception 2010
```

## 刮削搜索策略

`scrape_folder` 和 `scrape_video` 使用渐进式搜索：

1. **第一轮**：清洗名搜索 + 英文部分搜索，取最佳匹配（用 calc_match_score 比较）
2. **第二轮**（搜不到时）：去掉年份和集号后再搜
3. **第三轮**：拆副标题（冒号分隔，从后往前试）
4. **第四轮**：只取前几个中文字

**中英文同时搜**：文件名自带英文时，中文和英文都搜 TMDB，用 calc_match_score 比较取最佳。英文搜索通常更准（TMDB 英文数据更完整）。

**年份匹配权重**：calc_match_score 中年份精确匹配 +40 分，相差1年 +20 分，差距大 -50 分。年份是决定性因素。

**不要自己写搜索逻辑，直接调用 scrape_folder/scrape_video。**

## CD 分片处理

`analyzer._extract_cd_group_key(filename)` 检测 CD 分片，返回分组 key。同组 CD 文件应该放入同一个文件夹。

`organize_folder` 已经内置了 CD 分片合并逻辑，不需要手动处理。

## 跨文件夹散落季合并

```python
# 分析全库
report = analyzer.analyze_library(base_path, library_data)
# 检查 cross_folder_issues
for issue in report['cross_folder_issues']:
    if issue['type'] == 'scattered_seasons':
        result = organizer.merge_scattered_seasons(issue, dry_run=False)
```

## 分批处理建议

按一级目录分批，每批处理完验证再继续：

```
第1批：电影/（最简单，大部分是 movie 类型）
第2批：电视剧/（tv 类型，可能有散落季）
第3批：动画番/（tv 类型，文件名可能有广告）
第4批：动画电影/（混合类型：movie + series_collection + movie_collection）
第5批：其他目录
```

## 注意事项

- `organize_folder` 执行后会自动创建快照（organize_snapshots/），可以回滚
- TMDB API 有限流（约 40 次/10 秒），批量刮削时注意间隔
- 刮削失败的文件夹不要跳过，用清洗后的名字重试
- 不要手动拼接文件路径，用 `os.path.join`
- NAS 路径是 `\\DS218play\share\视频\`


## 验证测试用例

在处理全库之前，先用这 3 个典型文件夹验证整理链路是否正确。

