---
name: data-filtering
description: >
  数据过滤模式：包含/排除、阈值、多维筛选、软过滤标记、去重。
  Use when implementing include/exclude filters, threshold filters, multi-dimension faceted filters,
  soft filters (mark instead of remove), or deduplication logic.
  Do NOT use for text normalization (use text-processing), scoring (use match-scoring),
  or sorting (use result-sorting).
  分数修改（降分惩罚）属于 L2 match-scoring，本技能的软过滤只用标记模式。
---

# L3 数据过滤（Data Filtering）

> 从结果集中排除不需要的项，或标记低质量项。
> 本技能只做"过滤"（保留/排除/标记），不修改分数（降分逻辑归 L2）。

## 核心能力

### 1. includeExclude — 包含/排除过滤

最通用的过滤模式。

**规则**：
- include：正则匹配，所有条件都满足才通过（AND）
- exclude：正则匹配，任一条件命中即排除（OR）
- 匹配范围：每个字段独立匹配，任一字段命中即算命中（不拼接字段，避免跨字段误匹配）
- 执行顺序：先 include 再 exclude

**Gotchas**：
- 正则用 case-insensitive 模式
- 空的 include/exclude 表示不过滤（不是过滤全部）
- include 为空 = 全部通过；exclude 为空 = 不排除任何项
- 如果支持用户输入正则，必须加执行超时或使用安全正则库，防止 ReDoS

### 2. threshold — 阈值过滤

数值字段的范围过滤。

**支持格式**：
- 区间：`"10-50"` → min=10, max=50
- 大于：`">10"` → min=10
- 小于：`"<50"` → max=50
- 精确值：直接传 min=max

**特殊处理**：
- 值为 0 且大小也为 0 的项可能是特殊类型（如磁力链接），不应被阈值过滤排除
- 建议为特殊类型提供 `exempt` 条件（如 `seeders=0 AND size=0 → 豁免`）

### 3. faceted — 多维筛选器

多个维度同时过滤，适合用户交互场景。

**设计模式**：
- 每个维度独立：分辨率、来源、编码、大小、做种数...
- 维度内多选：OR 逻辑（选了 1080p 和 2160p = 显示两者）
- 维度间：AND 逻辑（选了 1080p + Bluray = 同时满足）
- 全部为空 = 不过滤（返回全量数据）
- 维度列表可以从数据集中动态提取（遍历结果，收集每个字段的唯一值作为筛选选项）

### 4. softFilter — 软过滤（仅标记模式）

不直接排除，而是给结果添加标记，UI 层决定是否显示。

**实现**：给结果添加标记字段（如 `is_junk: true`、`is_cam: true`），UI 提供开关控制显示/隐藏。

**适用场景**：
- 枪版资源（TS/CAM/HDTC）— 用户可手动开启显示
- 不确定是否相关的结果 — 标记为"低置信度"
- 0 做种 0 大小的磁力链接 — 标记为 `magnet_only`

**注意**：降分逻辑（如"不相关结果分数 ×0.3"）属于 L2 match-scoring 的缺失惩罚，不在本技能范围内。

### 5. deduplicate — 去重

**三种策略**：
- 精确字段去重：按唯一字段（infohash、ID、URL）去重
- 标题相似度去重：normalize 后标题相同 → 合并（保留信息最全的那条）
- 跨源 vs 同源：同源内去重（避免重复），跨源不去重（不同源的同一资源可能质量不同）

**Gotchas**：
- 去重应该在过滤之前做 — 原因：去重时保留信息最全的那条，如果先过滤，可能把信息最全的那条过滤掉了
- 合并时保留信息最全的那条，不是随机保留

### 6. filtered_reason — 过滤原因追踪

每条被排除或被标记的数据都应记录原因，方便调试和 UI 展示。

**字段**：
- `filtered_reason`: 排除/标记的具体原因（如 "exclude: 匹配排除词 CAM"、"threshold: seeders < 5"）
- `filtered_stage`: 在哪个阶段被排除（"deduplicate" / "exclude" / "threshold" / "softFilter"）

## 过滤流水线

```
原始数据
  → 去重（精确字段）— 必须第一步
  → 硬过滤（include/exclude）
  → 阈值过滤
  → 软过滤（标记，不排除）
  → 多维筛选（用户交互，前端执行）
  → 输出（附带统计）
```

**过滤结果统计**（每步过滤后记录）：
```
{
  total: number,              // 原始总数
  after_dedup: number,        // 去重后
  after_include_exclude: number,
  after_threshold: number,
  flagged: number,            // 软过滤标记数
  final: number,              // 最终通过数
  exclude_reasons: { [reason]: count }  // 各排除原因的计数
}
```

## Gotchas

- 过滤后为空时，考虑回退（放宽条件或返回全量 + 提示"无匹配筛选条件的结果"）
- 磁力链接源（seeders=0 且 size=0）是特殊类型，不应被做种数/大小阈值排除
- 前端筛选器状态变化时不需要重新请求后端（本地过滤）
