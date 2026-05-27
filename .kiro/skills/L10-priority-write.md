---
name: priority-write
description: >
  优先级保护写入模式：多数据源写同一字段时的优先级仲裁，低不覆盖高。
  Use when modifying clean_name write logic, adding new data sources that update media metadata,
  or debugging "name was overwritten" issues.
---

# L10 优先级保护写入

> 多个数据源（手动/NFO/TMDB/豆瓣/文件名解析）都可能写入同一个字段。
> 低优先级的数据不能覆盖高优先级的数据。

## 优先级表

```python
NAME_SOURCE_PRIORITY = {
    "manual": 4,    # 用户手动设置，最高
    "nfo": 3,       # NFO 文件
    "tmdb": 3,      # TMDB API
    "douban": 2,    # 豆瓣
    "bangumi": 2,   # Bangumi
    "scrape": 2,    # 刮削结果
    "parsed": 1,    # 文件名解析
    "": 0,          # 未设置
}
```

## 写入函数

```python
def safe_update_clean_name(video, cn="", en="", original="", source=""):
    """多字段版本的优先级保护写入"""
    current_source = video.get("clean_name_source", "")
    current_priority = NAME_SOURCE_PRIORITY.get(current_source, 0)
    new_priority = NAME_SOURCE_PRIORITY.get(source, 0)

    if new_priority < current_priority:
        return  # 低优先级不覆盖高优先级

    # 同优先级或更高：覆盖
    if cn: video["clean_name_cn"] = cn
    if en: video["clean_name_en"] = en
    if original: video["clean_name_original"] = original
    video["clean_name_source"] = source
```

## 写入点

| 写入点 | source | 优先级 | 说明 |
|--------|--------|--------|------|
| 用户手动编辑 | manual | 4 | 最高，不被任何自动流程覆盖 |
| 刮削成功后 | tmdb/nfo | 3 | 覆盖 parsed，不覆盖 manual |
| 树构建 finalize | parsed | 1 | 只填充空字段 |
| 树构建 post_process | 继承父级 | — | 尊重已有的高优先级 |
| 扫描新文件 | parsed | 1 | 初始填充 |

## 适用场景

这个模式不限于 clean_name，任何"多源写同一字段"的场景都适用：
- 封面来源（手动上传 > TMDB > 豆瓣 > 文件夹内图片）
- 评分来源（手动 > 豆瓣 > TMDB > Bangumi）
- 分类标签（手动覆盖 > 自动分类）
