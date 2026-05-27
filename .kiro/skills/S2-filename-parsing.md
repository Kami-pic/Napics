---
name: filename-parsing
description: >
  文件名解析：从 BT 标题和视频文件名中提取 title/year/season/episode/quality/codec/group。
  Use when modifying parse_filename, extract_bt_title_for_match, or episode number extraction logic.
  Depends on L1 text-processing for normalize/splitByLanguage.
  Do NOT confuse with clean-name-system (S1) which is about structured multi-language name output.
---

# S2 文件名解析

> 从 BT 标题和本地视频文件名中提取结构化元数据。
> 和 S1（清洗名系统）的区别：S2 提取所有字段（title+year+season+episode+quality），S1 只关注名称的多语言结构化。

## 两个解析器

### 1. parse_filename（tmdb_client.py）

用于本地视频文件名解析，提取 title/year/season/episode。

```python
parse_filename("进击的巨人 S03E01 1080p.mkv")
→ {"title": "进击的巨人", "year": "", "season": 3, "episode": 1}
```

**已知限制**：
- BT 标题含集号时 clean_name 包含集号导致 fuzzy 匹配度下降
- 纯数字集号（如 `07.mkv`）需要上下文（父文件夹名）才能判断
- 绝对集数（如 `148`）和普通数字难以区分

### 2. extract_bt_title_for_match（search_helpers.py）

专为搜索匹配设计的 BT 标题清洗，比 parse_filename 更激进。

```python
extract_bt_title_for_match("[SubGroup] Attack on Titan S04 1080p x265 AAC")
→ "Attack on Titan S04"
```

**策略**：在第一个技术标签处截断（1080p/x265/BluRay 等），去掉方括号内容、发布组名、年份。

### 3. extract_episode_number（rss_source_base.py）

从 BT 标题中提取集号，用于订阅匹配。

**支持格式**：
- `S01E03` / `s1e3` → season=1, episode=3
- `EP03` / `E03` / `第3集` / `第3话` → episode=3
- `- 05` / `- 05v2`（字幕组格式）→ episode=5
- 整季包识别：有 S01 但无 E01，或含 COMPLETE/全集/BATCH

## 质量解析（quality_parser.py）

从 BT 标题提取完整质量标签：

```python
parse_quality("Movie.2024.2160p.Remux.DTS-HD.MA.7.1.x265-GROUP")
→ QualityTag(resolution="2160p", source="Remux", video_codec="x265",
             audio_codec="DTS-HD", is_surround=True, release_group="GROUP")
```

**解析维度**：
| 维度 | 优先级 | 示例 |
|------|--------|------|
| 分辨率 | 2160p > 1080p > 720p | `4K`, `UHD`, `1080p`, `720p` |
| 来源 | Remux > Bluray > WEB-DL > HDTV | `REMUX`, `BLU-RAY`, `WEB-DL` |
| 视频编码 | AV1 = x265 > x264 | `HEVC`, `H.265`, `AVC` |
| 音频编码 | Atmos > TrueHD > DTS-HD > DDP5.1 > DD5.1 > DTS > AC3 > AAC | |
| 中文字幕 | 有/无 | `CHS`, `中字`, `双语`, `简繁` |
| 发布组 | 末尾 -GroupName | `-CMCT`, `-RARBG` |

## AI 辅助解析（ai_organizer.py）

正则提取失败时的 fallback：
- `ai_extract_episode(filename)` → 单文件 AI 解析
- `ai_extract_episode_batch(filenames)` → 批量（最多 10 个/批，并发 max_workers=3）
- AI 关闭或失败时静默返回 None，跳过该文件

## 踩坑经验

- BT 标题含集号时 match_chain 匹配度下降 → 用 extract_bt_title_for_match 先清洗再匹配
- `_enrich_result` 需要先 parse_filename 提取 clean_name 再匹配（直接传完整 BT 标题噪声太大）
- 日文动画绝对集数（如 `Bocchi the Rock 07`）和普通数字难以区分 → AI 辅助
- SP 在 "Spirited Away" 中误匹配为特别篇 → 用词边界 `(?<![a-zA-Z])` 保护
