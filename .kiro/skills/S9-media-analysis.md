---
name: media-analysis
description: >
  媒体目录分析引擎：只读分析目录结构/刮削状态/命名问题/质量问题，输出诊断报告。
  Use when modifying analysis logic, adding new diagnostic dimensions,
  or debugging health report inaccuracies.
---

# S9 媒体目录分析引擎

> 只读分析，不修改任何文件。输出结构化诊断报告和建议操作集。

## 分析维度（6 维度）

| 维度 | 检查内容 | 对应字段 |
|------|---------|---------|
| 结构问题 | 散落视频、错误的季目录结构、混合内容 | structure_issues |
| 命名问题 | 非标准文件名、缺少影子名 | rename_issues |
| 刮削缺失 | 无 NFO、无 TMDB ID | scrape_issues |
| 质量问题 | 低分辨率（<720p）、低质量分（<20） | quality_issues |
| 文件名问题 | 乱码、过长、特殊字符 | filename_issues |
| 影子名问题 | 影子名缺失或不匹配 | shadow_name_issues |

## 健康分计算

```
health_score = max(0, 100 - min(total_issues, 100))
```

- total_issues = 6 个维度的问题数之和
- 80+ 绿色（健康）、50-79 黄色（需关注）、<50 红色（需整理）

## 缓存策略

- `analysis_cache.json` 缓存分析结果
- 手动刷新时 `force=true` 跳过缓存
- 缓存显示"N 小时前"的时间标记

## AI 增强（ai_library_diagnosis）

- 收集统计数据（总数/覆盖率/分布）+ 问题列表（只传文件名不传路径）
- AI 返回 health_score + priorities（最多 5 条建议）+ summary
- AI 关闭时返回 None，前端提示"AI 诊断未启用"
