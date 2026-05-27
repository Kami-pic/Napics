---
name: match-scoring
description: >
  多维度匹配评分，用于实体对齐、搜索结果排名、数据去重。
  Use when calculating similarity between candidates and targets, scoring search results against
  a query, deduplicating records across data sources, or aligning entities from different systems.
  Depends on L1 text-processing for normalization and tokenization.
  Do NOT use for filtering (use data-filtering) or sorting (use result-sorting).
  质量评分（分辨率/编码/音频等）不属于本技能，属于项目业务逻辑。
---

# L2 匹配评分（Match Scoring）

> 给定候选项和目标，计算匹配度分数。核心原则：不同场景用不同策略，没有万能函数。
> 本技能只负责"匹配度"（候选和目标有多像），不负责"质量评分"（资源本身有多好）。

## 前置依赖

使用本技能前，确保文本已经过 L1 text-processing 的 normalize 处理。
token_set 策略需要 L1 的 tokenize 能力。

## 核心能力

### 1. 匹配策略选择

不同场景需要不同的匹配策略（参考 RapidFuzz 的策略体系）：

| 策略 | 适用场景 | 算法 | 示例 |
|------|---------|------|------|
| exact | 标准化后完全相等 | normalize(a) === normalize(b) | ID 匹配、精确标题匹配 |
| contains | A 是 B 的子串 | includes / indexOf | "西部世界" in "西部世界 第二季" |
| token_set | 关键词集合包含 | tokenize 后集合交集比率 | "Attack on Titan" vs "Titan Attack" |
| fuzzy | 整体相似度 | Levenshtein 归一化（0-1） | 拼写变体、OCR 错误 |
| partial | 部分子串最佳对齐 | 滑动窗口 Levenshtein | 长标题中找短标题 |

**选择指南**：
- 有唯一 ID（TMDB ID、IMDB ID）→ exact
- 标题可能有前后缀差异 → contains
- 词序可能不同 → token_set
- 可能有拼写错误 → fuzzy
- 不确定 → 用匹配链（见下文第 4 节）

### 2. 短名字保护

短名字（中文≤2字符，英文≤5字符）只允许 exact 策略，防止误匹配。
英文常见词（the, a, an, of, in, on）不参与匹配。

### 3. 多维度独立评分模型

适合需要精细排序的场景（如搜索结果排名）。

**输入示例（BT 搜索场景）**：
```
candidate: {
  names: ["Attack on Titan S04", "進撃の巨人"],
  year: "2023",
  season: 4,
  source: "prowlarr"
}
target: {
  names: ["进击的巨人", "Attack on Titan", "進撃の巨人"],
  year: "2022",
  season: 4
}
dimensions: [
  { field: "name", maxScore: 80, strategy: "best_of", shortProtect: true },
  { field: "year", maxScore: 30, strategy: "tolerance", tolerance: 1 },
  { field: "season", maxScore: 20, strategy: "exact" },
]
crossValidation: [
  { fields: ["name", "year"], bonus: 15 }
]
```

**输出**：
```
{
  score: 125,           // 80(name) + 30(year) + 15(交叉验证)
  breakdown: { name: 80, year: 30, season: 20 },
  crossBonuses: ["name+year: +15"],
  penalties: [],
  passed: true          // score >= threshold
}
```

**每个维度的评分规则**：
- `best_of`：遍历 candidate.names × target.names 的所有组合，取最高分
  - exact 匹配 = maxScore
  - contains 匹配 = maxScore × 0.5
  - fuzzy 匹配 = maxScore × fuzzyScore（动态阈值，见下文）
  - 短名字只允许 exact
- `tolerance`：数值容差匹配
  - 精确相等 = maxScore
  - 差值在容差内 = maxScore × 0.7
  - 超出容差 = 0
- `exact`：精确匹配，命中 = maxScore，不命中 = 0

**动态 fuzzy 阈值**（按文本长度调整，短词更严格）：
- 长度 ≤ 4：禁用 fuzzy，只允许 exact / contains
- 长度 5-10：Levenshtein ≥ 0.7 才算命中
- 长度 > 10：Levenshtein ≥ 0.8 才算命中

### 4. 匹配链（逐层放宽）

适合需要快速判断"是否匹配"的场景（如刮削候选筛选、订阅匹配）。

```
匹配链（短路返回，首个通过即停止）：
1. ID 精确匹配（TMDB/IMDB/豆瓣 ID）→ 100分
2. 主标题精确匹配（normalize 后集合交集）→ 90分
3. 别名/译名匹配（normalize 后集合交集）→ 80分（别名低于主标题，减少"同名不同剧"误伤）
4. 标题拆分匹配（按分隔符拆分，取非停用词，交集）→ 60分
5. 动态 fuzzy 匹配（按文本长度调整阈值）→ 40分
6. 全部不通过 → 0分
```

**何时用匹配链 vs 多维度评分**：
- 匹配链：只需要"是/否"判断 + 粗略分数，性能优先（如过滤几百条结果）
- 多维度评分：需要精细排序，每条结果都要可比较的分数（如搜索结果排名）
- 可以组合：先用匹配链快速过滤，再对通过的结果用多维度评分精排

### 5. 交叉验证

多维度同时命中 = 更可信，额外加分。

**触发条件**：该维度的得分 ≥ 该维度满分的 50%。

**常见规则**：
- 英文名 + 日文名都匹配 → +20
- 标题 + 年份都匹配 → +15
- 标题 + 年份 + 季号都匹配 → +25

### 6. 缺失惩罚

有约束但没匹配上 → 降分而非排除（乘法惩罚）：
- 有年份但不匹配 → 总分 ×0.5
- 有作品名但不匹配 → 总分 ×0.3
- 有类型但不匹配（电影 vs 剧集）→ 总分 ×0.4

**Gotchas**：
- 惩罚用乘法（×0.3）不用减法（-30），高分项被惩罚后仍比低分项高
- 缺失惩罚比直接排除更合理，数据可能不全
- 目标没有该字段时不惩罚（只有"有约束但没匹配上"才惩罚）

## 与 L4 排序的边界

- **L2 只算匹配分**（候选和目标有多像）
- **质量分**（分辨率/编码/做种数等）是项目业务逻辑，不属于 L2
- **L4 负责将匹配分和质量分加权合并为最终排序分**

## 常见配置模板

### BT 搜索结果匹配
- name: 80分, best_of, shortProtect
- year: 30分, tolerance(±1)
- season: 20分, exact
- 交叉验证: [name, year] +15
- 缺失惩罚: year ×0.5

### 角色实体对齐
- character_name: 80分, best_of, shortProtect
- series_name: 150分, best_of, missingPenalty ×0.3
- gender: 10分, exact
- 交叉验证: [name_en, name_ja] +20

### 推荐去重
- id: 100分, exact (tmdb_id/douban_id)
- title: 60分, exact + contains
- year: 20分, tolerance(±1)
