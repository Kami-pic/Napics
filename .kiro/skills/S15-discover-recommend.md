---
name: discover-recommend
description: >
  多源推荐聚合：豆瓣/TMDB/Bangumi 三源融合排序 + 本地状态注入 + 清洗名注入。
  Use when modifying discover page data flow, recommendation algorithm,
  or debugging "wrong poster/title/rating" issues.
---

# S15 多源推荐聚合

> 发现页的数据来自三个源，需要统一格式、融合排序、注入本地状态和清洗名。

## 数据流

```
三个数据源并行拉取：
  ├── 豆瓣 API v2（douban_api_v2.py）：9 个榜单 + 探索 + 搜索
  ├── TMDB（tmdb_client.py）：discover + trending + popular
  └── Bangumi（bangumi_client.py）：calendar + hot

→ combined_recommend.py：三源融合排序
  ├── 60 条上限 + 排名角标
  ├── Fallback 补位：去重后不足 60 条从 top250 + weekly 补位
  └── _is_same_media 去重（短标题完全包含 + 长标题 70% 重叠）

→ discover_enrich.py：注入增强
  ├── _inject_clean_names()：查 enrich_cache → 同步并发补全 → 注入 cn/en/original
  ├── _inject_local_status()：注入 local_status + local_folder
  └── 返回给前端
```

## normalizeItem（前端统一入口）

`discoverUtils.ts` 的 `normalizeItem` 是所有推荐/探索/搜索数据的统一入口：
- 新增字段必须在此传递
- 传递 clean_name_cn/en/original
- 传递 local_status/local_folder
- 传递 douban_id/tmdb_id/bangumi_id

## 详情匹配逻辑

- 有 TMDB ID → `_try_tmdb_detail_by_id`（直接拉详情，支持 movie↔tv 回退）
- 无 TMDB ID → `_try_tmdb_detail`（搜索 + `best_match` 多维度评分，30 分阈值）
- 豆瓣 ID 拉取失败 → 自动尝试 movie↔tv
- 两种都失败 → 返回 found:false，不 fallback 搜索（避免匹配错误）

## 前端详情缓存

- key 按数据源（douban/tmdb/bangumi）共享，不按 tab 区分
- 同一部作品在综合推荐和热门电影 tab 共享缓存

## 踩坑经验

- 豆瓣探索混入合集/豆列（无标题或无年份），ID 404 后搜索匹配到错误影片
- `_pick_best` 旧逻辑盲选第一个 → 替换为 `best_match` 多维度评分
- Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位 → 需要标题校验
- 发现页 ExpandDetail 的 img 加 key 强制重挂载，解决切换卡片封面残留
