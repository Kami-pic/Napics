---
name: tv-scrape-mapping
description: >
  TV 刮削确权与分集映射：确定 TMDB 剧集实体 + 绝对集数映射 + 特别篇识别 + NFO 生成。
  Use when modifying TV scraping logic, episode mapping, or debugging "wrong season/episode" issues.
  This is the most complex sub-problem in the organize pipeline.
---

# S10 TV 刮削确权与分集映射

> 整理流水线 Step 3 的核心。"先问后做"的确权理念在这里体现最充分。

## TV 确权三步

```
1. 确定 TMDB ID
   → 搜索 TMDB → best_match 多维度评分（30 分阈值）
   → 有效 tvshow.nfo 的 TMDB ID 直接复用（父级信任锁定）

2. 建绝对集数映射表
   → 从 TMDB 拉所有季的集数信息
   → 绝对集数阈值 > 50 判定为绝对集数编号（保守阈值）
   → 映射表：absolute_episode → (season, episode)

3. 遍历视频写 episode.nfo
   → 从文件名提取集号（正则 → AI fallback）
   → 查映射表确定 season/episode
   → 写 episode.nfo（showtitle + season + episode + title）
```

## 特别篇识别

路径中含以下关键词 → 强制 Season 00：
`sp, sp00~sp03, menu, ova, omake, extra, extras, bonus, trailer, ncop, nced, interview, featurette`

## 降级策略

| 风险 | 兜底 |
|------|------|
| TMDB 搜不到 | 不写 NFO，不动文件，不生成影子名 |
| 绝对集数超出映射表 | 跳过该文件 |
| 文件名无法提取集号 | 跳过（AI 开启时尝试 AI 提取） |
| get_episode_detail 404 | 写简化 NFO（只有 showtitle + season + episode） |
| 旧 NFO 的 TMDB ID 失效 | fallback 到重新搜索 |

## AI 辅助

- `ai_select_scrape_candidate`：TMDB 返回多个候选时 AI 选择最佳匹配
- `ai_extract_episode`：正则提取集号失败时 AI 解析文件名
- 两者都有非 AI fallback，关闭 AI 不影响主流程
