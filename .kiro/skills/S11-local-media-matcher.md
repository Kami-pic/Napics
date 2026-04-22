---
name: local-media-matcher
description: >
  本地媒体感知：三层匹配 + 内存索引 + 异步 TMDB ID 补全。
  Use when modifying local status injection, debugging "已有/可升级" badge issues,
  or adding new data sources that need local status awareness.
---

# S11 本地媒体感知

> 推荐/探索/搜索三个场景统一注入 local_status + local_folder。
> 让用户在发现页就能看到"这部片我本地有没有、质量够不够"。

## 三层匹配

```
match(item) → (local_status, local_folder)

第一层：tmdb_id 精确匹配（最可靠）
  → 从 media_library.json 的 shadow_tmdb_id 字段查找
  → 覆盖率极低（shadow_tmdb_id 很少有值），片名匹配是主力

第二层：title + year 匹配
  → normalize(title) + year 组合查找
  → 中文匹配用前缀（startswith），避免"你的名字"误匹配"以你的名字呼唤我"

第三层：title 模糊匹配（无年份）
  → 只用 title 匹配，年份不一致时降低置信度
```

## 内存索引

```python
build_index(library):
    _tmdb_index = {tmdb_id: folder_info}      # 第一层
    _title_year_index = {(title, year): info}  # 第二层
    _title_index = {title: [info1, info2]}     # 第三层
```

- 启动时从 media_library.json 构建
- `config_manager.save_library()` 的回调自动刷新索引

## local_status 枚举

| 值 | 含义 | 前端展示 |
|---|---|---|
| `owned` | 本地已有且质量足够 | ✓ 已有（emerald 角标） |
| `owned_low` | 本地已有但质量不足 | ↑ 可升级（amber 角标） |
| `not_owned` | 本地没有 | 无角标 |

质量判定：`quality_score >= 35` 或 `height >= 720`

## 异步 TMDB ID 补全

- 豆瓣/Bangumi 条目没有 tmdb_id → 后台线程用 TMDB API 搜索补全
- 补全结果写入 `id_mapping_cache.json`（douban_id → tmdb_id）
- 每条间隔 1.5s，避免 TMDB API 限频
- 补全后下次请求即可命中第一层精确匹配

## 注入场景

| 端点 | 注入方式 |
|------|---------|
| `/douban/hot` | `_inject_local_status(items)` |
| `/douban/recommend` | `_inject_local_status(items)` |
| `/douban/explore` | `_inject_local_status(items)` |
| 搜索结果 | 前端从 media_library 本地匹配 |
