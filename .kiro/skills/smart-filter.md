---
name: smart-filter
description: >
  BT 搜索智能过滤业务技能：基于 L1 文本处理 + L2 匹配评分 + L3 软过滤标记，按源特征差异化判定垃圾结果。
  Use when implementing or modifying the smart filter toggle in search results,
  adjusting junk detection rules, or debugging false positives/negatives in search filtering.
  Depends on L1 text-processing (normalize, splitByLanguage, tokenize),
  L2 match-scoring (match_chain), and L3 data-filtering (soft_filter pattern).
  Do NOT use for FilterBar faceted filtering (that's user-driven, not smart).
---

# 智能过滤（Smart Filter）业务技能

> 搜索资源时，一键过滤不相关/低质量/死种结果。
> 本质是 L1（文本处理）+ L2（匹配评分）+ L3（软过滤标记）的业务编排。

## 设计目标

- 默认关闭：用户看到全量搜索结果，不遗漏
- 开启后：自动隐藏明显不相关和低质量的结果，快速定位目标资源
- 与 FilterBar 互不干扰：智能过滤是"自动判断"，FilterBar 是"手动筛选"

## 架构

```
后端 enrich_result() ← search_helpers.py
  ├── L1 extract_bt_title_for_match() → bt_clean（BT 标题清洗）
  ├── L1 split_by_language() → 中英文分离（搜索词 + BT 标题）
  ├── L2 match_chain(candidates, targets) → match_score (0-100)
  │     candidates = [query, cn, en] + match_names（cn_name/en_name/original_name）
  │     targets = [bt_clean, bt_cn, bt_en]
  ├── quality_parser → quality_score (0-100)
  └── compute_junk_flags() → is_junk + junk_reasons[]
        ├── 规则1: 枪版检测（正则词边界）
        ├── 规则2: 匹配度过低（match_score > 0 且 < 30）
        ├── 规则3: 死种检测（按源特征差异化）
        ├── 规则4: 完全不匹配（match_score=0 + 有多语言候选）
        └── 规则5: 标题占比过低（match_score 40-70 但搜索词只是长标题的一小部分）

前端 displayResults (useMemo)
  └── smartFilter 开启时: filter(r => !r.is_junk)
```

## 数据流

```
搜索结果（全量）
  → enrich_result(r, query, match_names=[cn_name, en_name, original_name])
    → extract_bt_title_for_match → bt_clean
    → match_chain(candidates, targets) → match_score
    → compute_junk_flags(d) → is_junk + junk_reasons
  → 前端 results[] 保存全量（含 is_junk/match_score/junk_reasons）
  → displayResults: smartFilter ? 过滤 is_junk : 全量
  → filtered: applyFilters(displayResults, FilterBar 条件)
  → 渲染
```

## 关键函数（search_helpers.py）

| 函数 | 职责 | 依赖 |
|------|------|------|
| `extract_bt_title_for_match(title)` | BT 标题清洗：去方括号/技术标签/发布组/年份 | L1 正则 |
| `enrich_result(r, query, match_names)` | 结果增强：quality_score + match_score + junk 标记 | L1 + L2 + quality_parser |
| `compute_junk_flags(d)` | 五规则垃圾判定 | L1 normalize/split/tokenize |

## 源特征差异表

| 源 | seeders | size_gb | 特征 | 死种判定 |
|---|---|---|---|---|
| Prowlarr | 真实值 | 真实值 | BT 站聚合，索引器多时返回大量不相关结果 | seeders=0 且 size>0 |
| Bitsearch | 真实值 | 真实值 | 英文为主，中文搜索易误匹配 | seeders=0 且 size>0 |
| Nyaa | 真实值 | 真实值 | 日文动画为主 | seeders=0 且 size>0 |
| 蜜柑 (Mikan) | 真实值 | 真实值 | 日文动画 RSS | seeders=0 且 size>0 |
| YTS | 真实值 | 真实值 | 电影为主，JSON API | seeders=0 且 size>0 |
| ACG.RIP | 恒为 0 | 真实值 | 动画字幕组，无做种数信息 | seeders=0 且 size>0 |
| Bangumi Moe | 恒为 0 | 真实值 | 动画字幕组，无做种数信息 | seeders=0 且 size>0 |
| 磁力熊 (cilixiong) | 恒为 0 | 恒为 0 | 纯磁力链接，无 tracker | 不适用（豁免） |
| XL720 | 恒为 0 | 恒为 0 | 纯磁力链接，无 tracker | 不适用（豁免） |

## 判定规则

### 规则 1：枪版/低质量源检测

**触发条件**：标题中含枪版关键词（词边界匹配，case-insensitive）

**关键词列表**：`TS, CAM, HDTC, TC, TELECINE, HDTS, TELESYNC, HDCAM`

**Gotchas**：
- 必须用 `\b` 词边界，避免 "MONSTERS" 误匹配 "TS"
- "TS" 在日文动画标题中可能是 "Transport Stream"（如 MPEG-TS），已知误伤，后续可用 `(?<!MPEG-)\bTS\b` 豁免

### 规则 2：匹配度过低

**触发条件**：`match_score > 0 且 match_score < 30`

**为什么 match_score=0 不标记**：
- match_score=0 在无多语言候选时表示 match_chain 计算失败或未传入搜索词
- 但如果有多语言候选，match_score=0 就是真的不匹配，见规则 4

**match_chain 评分参考**：
- 90：精确匹配（normalize 后完全一致）
- 80：别名精确匹配
- 70：子串包含匹配（normalize 后 A 是 B 的子串，且长度比例 ≥ 40%）
- 60：token_set 匹配（候选 tokens 70%+ 出现在目标中）
- 40：fuzzy 模糊匹配（动态阈值）
- 0：完全不匹配或跨语言无法计算

### 规则 3：死种检测

**触发条件**：`seeders == 0 且不是磁力链接源`

**磁力链接源判定**：`seeders == 0 AND size_gb == 0`（磁力熊/XL720 自动豁免）

**Gotchas**：
- 不要用 `_source` 字段判断是否磁力源，用 `seeders==0 && size_gb==0` 组合特征
- ACG.RIP/Bangumi Moe 虽然无做种数信息（seeders=0），但 size>0，会被标记为死种

### 规则 4：完全不匹配（跨语言）

**触发条件**：`match_score == 0 且 _has_multilang_candidates == true`

**原理**：
- `enrich_result` 接受 `match_names` 参数（cn_name/en_name/original_name）
- 当有多语言候选时，candidates 包含中文名、英文名、原名等多种变体
- 如果所有变体都无法匹配 BT 标题，说明结果确实不相关
- 典型场景：搜"芙莉莲第二季"（cn="芙莉莲"，en="Frieren"），Prowlarr 返回 Zootopia

**Gotchas**：
- 用户手动输入搜索词时没有 match_names，`_has_multilang_candidates=false`，不触发此规则
- 磁力源也受此规则影响（不相关的磁力链接也应被过滤）
- 前端传 cn_name/en_name 的质量直接影响过滤效果

### 规则 5：标题占比过低（业务层）

**触发条件**：`match_score 在 40-70 且搜索词在 BT 清洗标题中的占比 < 30%`

**原理**：
- match_score 40-70 来自 contains/token_set/fuzzy，不是精确匹配
- 如果搜索词只占 BT 标题很小一部分，说明是"关键词被覆盖"而非"作品名匹配"
- 典型场景：搜"芙莉莲"，标题是"2024年度最佳动画合集 芙莉莲 鬼灭之刃 咒术回战"

**占比计算**：
- 中英文分开算，取最高占比（避免中文搜索词被英文标题部分稀释）
- 中文部分：normalize(搜索词cn) 在 normalize(标题cn) 中的子串长度占比
- 英文部分：normalize(搜索词en) 在 normalize(标题en) 中的子串长度占比
- 如果不是子串关系，用 token 交集占比（交集数 / 标题 token 数）
- 阈值 30%：低于此值标记为 `low_title_ratio`

**Gotchas**：
- match_score ≥ 80（精确/别名匹配）不触发此规则
- match_score < 40 已被规则 2 处理，不重复检查
- "流浪地球" vs "流浪地球2 The Wandering Earth II"：中文部分占比 80%，不误标记
- "西部世界" vs "西部风云"：中文部分 "西部世界" 不是 "西部风云" 的子串，token 交集 2/4=50%... 但 normalize 后 "西部世界" 和 "西部风云" 不是子串关系，token 交集 "西"+"部" = 2 个 / 标题 4 个 = 0.25 < 0.3，被标记

## 前端交互

- 按钮位置：BT 搜索框内右侧（仅 BT 模式显示）
- 开启状态：🛡️ 绿色，tooltip "智能过滤已开启：隐藏不相关/枪版/死种"
- 关闭状态：🔓 灰色，tooltip "智能过滤已关闭：显示全部结果"
- 统计文案：`共 X 条，过滤后 Y 条`（开启时显示）

## 配置项（未来可扩展）

| 配置 | 当前值 | 说明 |
|---|---|---|
| match_score_threshold | 30 | 低于此分数标记为不相关 |
| title_ratio_threshold | 0.3 | 标题占比低于此值标记为覆盖 |
| junk_quality_patterns | [TS,CAM,...] | 枪版关键词列表 |

## 测试文件

| 文件 | 覆盖范围 | 用例数 |
|------|---------|--------|
| `test_smart_filter.py` | 三条基础规则 + match_chain 集成 | 45 |
| `test_smart_filter_extra.py` | 各源格式真实标题 + 端到端场景 | 39 |
| `test_smart_filter_multilang.py` | 跨语言匹配 + unmatched 规则 | 10 |
| `test_smart_filter_ratio.py` | 标题占比检查（规则 5） | 8 |

## 与其他模块的关系

- **L1 text_processing**：normalize/splitByLanguage/tokenize，标题清洗和占比计算的基础
- **L2 match_chain**：提供 match_score，本技能消费并在业务层做二次判断
- **L3 soft_filter**：本技能实现了 L3 的 softFilter 模式（标记+开关）
- **FilterBar (faceted)**：独立于智能过滤，用户手动筛选维度
- **L4 result_sorting**：排序在智能过滤之后执行（displayResults 中先 filter 再 sort）
- **clean_name_system**：提供 cn_name/en_name/original_name，通过 match_names 传入
- **search_keyword_mapper**：决定每个源用什么语言搜索，影响 Prowlarr 返回结果的语言分布

## 已知问题与后续优化

- MPEG-TS 被误标记为枪版（可用 `(?<!MPEG-)\bTS\b` 豁免）
- 单词搜索 vs 长标题 score=0（"Westworld" vs "Westworld.S04E01.The.Auguries..."，contains 40% 比例约束 + token_set 单 token 限制）
- 中文 2 字公共前缀触发 token_set 60 分（"西部世界" vs "西部风云"），已被规则 5 标题占比检查兜底
