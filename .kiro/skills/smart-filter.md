---
name: smart-filter
description: >
  BT 搜索智能过滤业务技能：基于 L2 匹配评分 + L3 软过滤标记，按源特征差异化判定垃圾结果。
  Use when implementing or modifying the smart filter toggle in search results,
  adjusting junk detection rules, or debugging false positives/negatives in search filtering.
  Depends on L2 match-scoring (match_chain) and L3 data-filtering (soft_filter pattern).
  Do NOT use for FilterBar faceted filtering (that's user-driven, not smart).
---

# 智能过滤（Smart Filter）业务技能

> 搜索资源时，一键过滤不相关/低质量/死种结果。
> 本质是 L2（匹配评分）+ L3（软过滤标记）的业务编排。

## 设计目标

- 默认关闭：用户看到全量搜索结果，不遗漏
- 开启后：自动隐藏明显不相关和低质量的结果，快速定位目标资源
- 与 FilterBar 互不干扰：智能过滤是"自动判断"，FilterBar 是"手动筛选"

## 架构

```
后端 _enrich_result()
  ├── L2 match_chain() → match_score (0-100)
  ├── quality_parser → quality_score (0-100)
  └── _compute_junk_flags() → is_junk + junk_reasons[]
      ├── 规则1: 枪版检测（正则词边界）
      ├── 规则2: 匹配度过低（match_score > 0 且 < 阈值）
      └── 规则3: 死种检测（按源特征差异化）
          
前端 displayResults (useMemo)
  └── smartFilter 开启时: filter(r => !r.is_junk)
```

## 数据流

```
搜索结果（全量）
  → _enrich_result 逐条标记
  → 前端 results[] 保存全量（含 is_junk 标记）
  → displayResults: smartFilter ? 过滤 is_junk : 全量
  → filtered: applyFilters(displayResults, FilterBar 条件)
  → 渲染
```

## 源特征差异表

| 源 | seeders | size_gb | 特征 | 死种判定 |
|---|---|---|---|---|
| Prowlarr | 真实值 | 真实值 | BT 站聚合，质量最高 | seeders=0 且 size>0 |
| Bitsearch | 真实值 | 真实值 | 英文为主，中文搜索易误匹配 | seeders=0 且 size>0 |
| Nyaa | 真实值 | 真实值 | 日文动画为主 | seeders=0 且 size>0 |
| 蜜柑 (Mikan) | 真实值 | 真实值 | 日文动画 RSS | seeders=0 且 size>0 |
| 磁力熊 (cilixiong) | 恒为 0 | 恒为 0 | 纯磁力链接，无 tracker | 不适用（豁免） |
| XL720 | 恒为 0 | 恒为 0 | 纯磁力链接，无 tracker | 不适用（豁免） |

## 判定规则

### 规则 1：枪版/低质量源检测

**触发条件**：标题中含枪版关键词（词边界匹配，case-insensitive）

**关键词列表**：
```
TS, CAM, HDTC, TC, TELECINE, HDTS, TELESYNC, HDCAM
```

**Gotchas**：
- 必须用 `\b` 词边界，避免 "MONSTERS" 误匹配 "TS"
- "TS" 在日文动画标题中可能是 "Transport Stream"（如 MPEG-TS），但 BT 搜索场景中极少见，暂不处理

### 规则 2：匹配度过低

**触发条件**：`match_score > 0 且 match_score < THRESHOLD`

**阈值**：30 分（可配置）

**为什么 match_score=0 不标记**：
- match_score=0 在无多语言候选时表示 match_chain 计算失败或未传入搜索词，不代表不相关
- 只有"算了但分数低"才是不相关的信号
- 但如果有多语言候选（cn_name + en_name 都传了），match_score=0 就是真的不匹配，见规则 4

**match_chain 评分参考**：
- 90-100：精确匹配（标题完全一致）
- 70：子串包含匹配（normalize 后 A 是 B 的子串，且长度比例 ≥ 40%）
- 60：token_set 匹配（候选 tokens 70%+ 出现在目标中）
- 40：fuzzy 模糊匹配
- 0：完全不匹配或跨语言无法计算

**已知问题**：
- Bitsearch 中文搜索返回大量标题含搜索词子串但实际不相关的结果（如搜"流浪地球"返回"流浪猫"）
- 当前 match_chain 的 contains 策略（0.5 分）可能让这些结果得到 40 分，刚好在阈值之上
- 后续优化方向：对中文短名字的 contains 匹配加更严格的长度比例约束

### 规则 3：死种检测

**触发条件**：`seeders == 0 且不是磁力链接源`

**磁力链接源判定**：`seeders == 0 AND size_gb == 0`
- 磁力熊和 XL720 的结果恒为此特征，自动豁免
- Prowlarr/Bitsearch/Nyaa 的结果如果 seeders=0 但 size>0，说明有 tracker 信息但无人做种

**Gotchas**：
- 不要用 `_source` 字段判断是否磁力源（前端可能没传）
- 用 `seeders==0 && size_gb==0` 的组合特征判断更可靠
- 某些 Prowlarr 索引器可能返回 seeders=0 但实际有种（API 延迟），这是可接受的误伤

### 规则 4：完全不匹配（跨语言）

**触发条件**：`match_score == 0 且 _has_multilang_candidates == true`

**原理**：
- `enrich_result` 接受 `match_names` 参数（cn_name/en_name/original_name）
- 当有多语言候选时，candidates 包含中文名、英文名、原名等多种变体
- 如果所有变体都无法匹配 BT 标题，说明结果确实不相关
- 典型场景：搜"芙莉莲第二季"（cn_name="芙莉莲"，en_name="Frieren"），Prowlarr 返回 Zootopia

**Gotchas**：
- 用户手动输入搜索词时没有 match_names，`_has_multilang_candidates=false`，不触发此规则
- 磁力源也受此规则影响（不相关的磁力链接也应被过滤）
- 前端传 cn_name/en_name 的质量直接影响过滤效果，如果名称不准确可能误伤

## 前端交互

- 按钮位置：BT 搜索框内右侧（仅 BT 模式显示）
- 开启状态：🛡️ 绿色，tooltip "智能过滤已开启：隐藏不相关/枪版/死种"
- 关闭状态：🔓 灰色，tooltip "智能过滤已关闭：显示全部结果"
- 统计文案：`共 X 条，过滤后 Y 条`（开启时显示）

## 配置项（未来可扩展）

| 配置 | 当前值 | 说明 |
|---|---|---|
| match_score_threshold | 30 | 低于此分数标记为不相关 |
| junk_quality_patterns | [TS,CAM,...] | 枪版关键词列表 |
| dead_seed_enabled | true | 是否启用死种检测 |

## 测试验证维度

1. **正确过滤**：枪版、完全不相关标题、死种应被标记
2. **不误伤**：
   - 磁力链接源（seeders=0, size=0）不应被标记为死种
   - match_score=0（未计算）不应被标记
   - 正常资源（高匹配+有种）不应被标记
3. **边界情况**：
   - match_score 恰好等于阈值（30）→ 不标记
   - 标题含 "TS" 子串但不是词边界（如 "MONSTERS"）→ 不标记
   - 多个垃圾原因同时命中 → 全部记录到 junk_reasons

## 与其他模块的关系

- **L2 match_chain**：提供 match_score，本技能消费
- **L3 soft_filter**：本技能实现了 L3 的 softFilter 模式（标记+开关）
- **FilterBar (faceted)**：独立于智能过滤，用户手动筛选维度
- **L4 result_sorting**：排序在智能过滤之后执行（displayResults 中先 filter 再 sort）
