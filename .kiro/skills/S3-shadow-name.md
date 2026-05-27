---
name: shadow-name
description: >
  影子名生成：从 NFO 严格拼接标准化文件名，不回退到原始文件名。
  Use when modifying shadow name generation, renaming logic, or debugging "shadow name mismatch" issues.
  Depends on clean-name-system (S1) for structured name data, and NFO handler for reading metadata.
---

# S3 影子名生成

> 影子名（shadow_name）是整理流水线的最终产出，用于 Emby/Jellyfin 等媒体服务器识别。
> 核心原则：严格读 NFO 拼接，不回退到文件名清洗。

## 生成规则

| 类型 | 格式 | 示例 |
|------|------|------|
| 电影 | `中文名 英文名 (年份)` | `盗梦空间 Inception (2010)` |
| 剧集 | `剧名 英文名 S01E01` | `进击的巨人 Attack on Titan S03E01` |
| 季文件夹 | `剧名 英文名 Season XX` | `进击的巨人 Attack on Titan Season 03` |
| 聚合容器内子视频 | 按 movie 逻辑各自独立 | — |
| 聚合容器文件夹 | 不生成影子名 | — |

## 数据来源

影子名的各字段严格从 NFO 读取：
- 中文名：`<title>` 标签
- 英文名：`<originaltitle>` 标签（需 detect_language 判断是否为英文）
- 年份：`<year>` 标签
- 季集号：`<season>` + `<episode>` 标签

**不回退到文件名**：如果 NFO 缺少某字段，该部分留空，不从文件名猜测。

## 关键函数

| 函数 | 文件 | 职责 |
|------|------|------|
| `generate_shadow_name_from_nfo` | renamer.py | 从 NFO 拼接视频文件的影子名 |
| `generate_folder_shadow_name` | renamer.py | 文件夹级影子名（tv/movie 有，聚合容器无） |
| `shadow_name_manager.py` | — | 影子名批量管理和写入 |

## shadow_name_source 追踪

和 clean_name_source 类似，shadow_name 也追踪来源：
- `nfo`：从 NFO 生成（最可靠）
- `manual`：用户手动设置
- `auto`：自动生成（旧逻辑，逐步淘汰）

## 注意事项

- shadow_name 可能含中文，构造 enName 搜索词时必须去掉中文字符
- shadow_name 中的英文名可能是日文原名（如"進撃の巨人"），不能直接当英文名用
- 影子名写入时不覆盖 manual 来源的已有值
