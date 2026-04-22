---
name: quality-scoring
description: >
  质量评分体系：100 分制综合评分 + 质量等级排名 + 质量对比。
  Use when modifying quality scoring weights, adding new quality dimensions,
  implementing upgrade detection, or debugging quality-based sorting/filtering.
  This is a cross-cutting concern used by search, subscription, and organize modules.
  Do NOT confuse with L2 match-scoring (which scores "how similar", not "how good").
---

# S4 质量评分体系

> 跨搜索/订阅/整理的全局质量基准。
> 和 L2 匹配评分的区别：L2 算"候选和目标有多像"，S4 算"资源本身有多好"。

## 100 分制综合评分

```
quality_score = 分辨率(45) + 来源(20) + 音频(20) + 编码(10) + 字幕(5)
```

| 维度 | 满分 | 分值映射 |
|------|------|---------|
| 分辨率 | 45 | 2160p=45, 1080p=28, 720p=14 |
| 来源 | 20 | Remux=20, Bluray=16, WEB-DL=10, HDTV=5 |
| 音频 | 20 | Atmos=20, TrueHD=17, DTS-HD=14, DDP5.1=10, DD5.1=8, DTS=7, EAC3=6, AC3=5, AAC=3 |
| 编码 | 10 | x265=10, AV1=10, x264=6 |
| 字幕 | 5 | 有中文字幕=5 |

## 质量等级（QualityLevel）

用于排序对比，8 级：

| rank | label | 条件 |
|------|-------|------|
| 8 | 2160p Remux | 2160p + Remux |
| 7 | 2160p Bluray | 2160p + Bluray |
| 6 | 2160p WEB-DL | 2160p + 其他/未知来源 |
| 5 | 1080p Remux | 1080p + Remux |
| 4 | 1080p Bluray | 1080p + Bluray |
| 3 | 1080p WEB-DL | 1080p + 其他/未知来源 |
| 2 | 720p | 720p |
| 1 | 其他 | 无分辨率信息 |

## 质量对比

```python
compare_quality_score(current_score, new_score, threshold=5) -> bool
# 新分数比旧分数高出 threshold 分才返回 True
# 避免微小差异频繁替换（如 AAC→AC3 只差 2 分）
```

## 调用场景

| 场景 | 调用方式 | 用途 |
|------|---------|------|
| BT 搜索结果 | `enrich_result` → `compute_quality_score(tag)` | 结果排序 |
| 媒体库扫描 | `config_manager.save_library()` 自动注入 | 库内质量统计 |
| 订阅匹配 | `rss_matcher._filter_quality` | 最低质量过滤 |
| 洗版判定 | `compare_quality_score(current, new)` | 是否值得替换 |
| Quality Cutoff | `get_quality_level(tag).rank >= target_rank` | 达标后停止搜索 |
| 批量升级 | `BatchUpgradePanel` 的 `is_upgrade` 判定 | 是否有提升 |

## 从本地视频计算质量分

```python
compute_quality_score_from_video(video: dict) -> int
# 用 height/codec/audio_codec 构造 QualityTag 再算分
# height >= 2160 → "2160p"，>= 1080 → "1080p"，>= 720 → "720p"
# 文件名中尝试解析更多信息（来源/编码/字幕）
```

## 判定阈值

- `quality_score >= 35`：判定"有质量"（约等于 1080p WEB-DL + x264）
- 回退：`height >= 720` 也算有质量（quality_score 可能为 0 但分辨率够）
- 洗版阈值：`compare_quality_score(current, new, threshold=5)` → 差 5 分以上才替换
