---
name: result-sorting
description: >
  结果排序模式：加权排序、多级排序、可配置优先级、分组排序。
  Use when implementing weighted multi-field sorting, configurable priority sorting,
  group-then-sort patterns, or score-based ranking for search results or ranked lists.
  Do NOT use for scoring (use match-scoring) or filtering (use data-filtering).
  本技能负责将 L2 的匹配分和业务质量分合并为最终排序分。
---

# L4 结果排序（Result Sorting）

> 对过滤后的结果集进行排序，让最相关/最优质的结果排在最前面。
> 本技能负责"最终排序分 = L2 匹配分 + 业务质量分"的加权合并。

## 核心能力

### 1. weightedSort — 加权排序

多字段加权计算综合分，按分数排序。

**公式**：`finalScore = sum(normalize(field_value) * weight for each field)`

**归一化**（不同字段值域不同，需先归一化到 0-1）：
- 数值字段：`min(value / max_value, 1.0)`，max_value 用业务定义的合理上限（如 seeders 用 1000），不用数据集中的最大值
- 布尔字段：`1.0 if true else 0.0`
- 枚举字段：预定义映射（如 2160p=1.0, 1080p=0.7, 720p=0.3, SD=0.1）
- L2 匹配分：`match_score / max_possible_score`

**示例（BT 搜索）**：
```
finalScore =
  normalize(match_score, max=130) * 0.40    // 匹配度最重要
+ normalize(quality_score, max=100) * 0.30  // 质量次之
+ normalize(seeders, max=1000) * 0.20       // 做种数
+ normalize(size_gb, max=50) * 0.10         // 文件大小
```

### 2. multiLevelSort — 多级排序

逐级比较，第一级相同时比第二级。比加权排序更直观。

**示例**：
```
sort by:
  1. match_score DESC     (匹配度最重要)
  2. quality_score DESC   (质量次之)
  3. seeders DESC         (做种数)
  4. size_gb DESC         (文件大小)
```

**默认排序推荐**：用 multiLevelSort，特殊项作为最高优先级，不混进普通权重：

```
默认排序链（完整）：
  1. is_magnet_only ASC      (0=正常资源优先, 1=磁力链接排后)
  2. is_season_pack DESC     (1=整季包优先, 0=单集排后)
  3. match_score DESC        (匹配度最重要)
  4. quality_score DESC      (质量次之)
  5. seeders DESC            (做种数)
  6. size_gb DESC            (文件大小)
```

**注意**：is_magnet_only 和 is_season_pack 是特殊优先级，独立于普通排序维度，不要混进 weightedSort 的权重计算中。

**Gotchas**：
- 第一级差异很大时，后续级别几乎不影响结果
- 适合维度之间有明确优先级的场景

### 3. configurableSort — 可配置优先级排序

用户可调整排序维度的优先级顺序。

**设计**：
- 排序规则存储为有序列表：`["match", "quality", "seeders"]`
- 用户可在 UI 中调整顺序
- 每个维度支持 ASC/DESC 切换
- 用户偏好持久化到配置中（localStorage 或后端 config），下次打开时恢复

### 4. groupSort — 分组排序

先按某个维度分组，再在组内排序。

**适用场景**：
- 按来源分组，组内按质量排序
- 按媒体名分组，组内取最优（去重）
- 按匹配度分组（高/中/低），组内按质量排序

### 5. scoreBasedSort — 评分即排序

当 L2 匹配分 + 业务质量分已经通过 weightedSort 合并为 finalScore 时，排序就是 finalScore 降序。

## 特殊处理

### 缺失值兜底
信息不完整的条目，在相同匹配度下必须排在信息完整条目后面：
- 数值字段缺失（seeders、quality_score、size）：按 0 处理
- 布尔字段缺失（is_season_pack）：按 false 处理
- 实现：排序 key 中加入 `has_complete_info`（0=不完整, 1=完整）

### 磁力链接资源排序
seeders=0 且 size=0 的磁力链接资源（L3 标记为 `magnet_only`）：
- 排在有完整信息的资源之后
- 同类磁力链接内部按 match_score 排序
- 实现：排序 key 中加入 `is_magnet_only` 作为第一级（0=正常, 1=磁力链接）

### 整季包优先
无集号但有季号的资源（整季包）应排在单集资源之前。
- 实现：排序 key 中加入 `is_season_pack` 作为高优先级（1=整季包, 0=单集）

## 排序流水线

```
过滤后的数据（含 L2 match_score + L3 标记）
  → 计算 finalScore（L2 匹配分 + 业务质量分加权合并）
  → 分组（可选）
  → 组内排序（multiLevelSort 或 weightedSort）
  → 特殊项处理（磁力链接排后、整季包排前）
  → 输出
```

## Gotchas

- 排序应该是稳定排序（相同分数的项保持原始顺序）
  - Python: `key=lambda x: (-x.score, x.original_index)`
  - JavaScript: `Array.sort` 本身是稳定的（ES2019+）
- 前端排序和后端排序的职责划分：后端算 match_score 和 quality_score，前端做最终排序（用户可交互调整）
- 排序规则变化时不需要重新请求后端（前端本地重排）
