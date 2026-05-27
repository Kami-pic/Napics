---
name: text-processing
description: >
  文本标准化、语言检测、分词、中英文分离等文本预处理能力。
  Use when normalizing text for comparison, splitting CJK/English mixed text, detecting language,
  cleaning search keywords, extracting name variants, or tokenizing text for set-based matching.
  Do NOT use for fuzzy matching or scoring (use match-scoring), filtering (use data-filtering),
  or sorting (use result-sorting).
---

# L1 文本处理（Text Processing）

> 所有匹配、搜索、过滤的基石。标准化后的文本才能可靠比较。

## 核心能力

### 1. normalize — 文本标准化

将文本转换为可比较的标准形式。

**步骤**：
1. 全角字符 → 半角（Unicode FF01-FF5E 区间减 FEE0）
2. 繁体中文 → 简体中文（可选，用 OpenCC 或简单映射表；"進擊的巨人" → "进击的巨人"）
3. 去除标点符号和特殊字符（保留字母、数字、CJK 字符）
4. 去除空格（或统一为单空格，取决于场景）
5. 统一小写

**Gotchas**：
- 中文标点和英文标点要同时处理（`：` 和 `:` 都去掉）
- 全角数字也要转半角（`１２３` → `123`）
- CJK 字符之间的空格去掉是正确的（"进击 的 巨人" → "进击的巨人"）
- 繁简转换应在去标点之前做（避免繁体标点干扰）

### 2. detectLanguage — CJK 语言检测

判断文本的主要语言，返回 `"cn" | "en" | "jp" | "ko" | "mixed" | "none"`。

**规则**（按优先级）：
1. 纯数字/符号 → `none`（不参与语言相关匹配）
2. 含日文假名（U+3040-U+30FF）→ `jp`
3. 含韩文（U+AC00-U+D7AF）→ `ko`
4. 含中文汉字（U+4E00-U+9FFF）且无假名 → `cn`
5. 主要是 ASCII 字母 → `en`
6. 混合 → `mixed`

**Gotchas**：
- 日文汉字和中文汉字 Unicode 范围重叠，必须先检测假名
- 短文本（≤3字符）的语言检测不可靠，建议标记为 `unknown`
- "S01E05" 这类纯格式文本应返回 `none`

### 3. splitByLanguage — 中英文分离

从混合文本中提取中文部分和英文部分。

**策略**：按 token 分组判断归属
1. 正则拆分为 token 序列：CJK 字符段、英文单词、数字、其他
2. CJK 字符 → 归入中文
3. 英文单词：紧邻 CJK 时归入中文（如 "JOJO的" 中的 JOJO），独立出现归入英文
4. 数字：紧邻 CJK 时归入中文（如 "91天" 中的 91），独立出现归入英文
5. 其他字符（空格、标点）跳过

**示例**：
- `"西部世界 Westworld"` → `{cn: "西部世界", en: "Westworld"}`
- `"The Last of Us 最后生还者"` → `{cn: "最后生还者", en: "The Last of Us"}`
- `"进击的巨人"` → `{cn: "进击的巨人", en: ""}`
- `"Inception"` → `{cn: "", en: "Inception"}`
- `"91天 91Days"` → `{cn: "91天", en: "91 Days"}`（91 紧邻"天"归入中文）
- `"JOJO的奇妙冒险"` → `{cn: "JOJO的奇妙冒险", en: ""}`（JOJO 紧邻"的"归入中文）
- `"300勇士"` → `{cn: "300勇士", en: ""}`（300 紧邻"勇士"归入中文）

**Gotchas**：
- "紧邻"指 token 序列中相邻位置有 CJK token（中间可能有空格/标点被跳过）
- 纯英文标题中的数字不会被误归入中文（如 "2001 A Space Odyssey" → en 完整保留）
- 这个分离是粗粒度的，用于搜索词构造和短名字判断，不是精确的 NLP 分词

### 4. isShortName — 短名字判断

短名字需要更严格的匹配策略，防止误匹配。

**规则**：
- 中文/日文：≤2 个字符视为短名字（如 "她"、"AI"）
- 英文：≤5 个字符视为短名字（如 "Her"、"Alien"）
- 短名字只允许精确匹配，不允许包含匹配或模糊匹配

**Gotchas**：
- 英文常见词（the, a, an, of, in, on, at, to, for, is, it）不应参与匹配
- 数字不算名字长度（"2001" 不是短名字，但 "AI" 是）

### 5. extractVariants — 名称变体提取

从标题中提取所有可能的搜索/匹配变体。

**步骤和规则**：
1. 原始标题（原样保留）
2. 去副标题 — 分隔符：`：`、`:`、` - `（两侧有空格的短横线）、`～`、`~`
   - `"盗梦空间：终极版"` → `"盗梦空间"`
   - `"Spider-Man: No Way Home"` → `"Spider-Man"`
3. 去年份后缀 — 正则 `\s*[\(\[（]?(19|20)\d{2}[\)\]）]?\s*$`
   - `"流浪地球 (2019)"` → `"流浪地球"`
4. 去特殊字符后的纯净版（normalize 处理）
5. 中英文分离后的各部分（splitByLanguage）
6. 提取季集号 — `"第3季"` → `"S03"`，`"第12集"` → `"E12"`

**输出**：去重后的变体列表，按从精确到宽泛排序。

### 6. cleanKeyword — 关键词清洗

搜索前对关键词进行预处理。

**步骤**：
1. 去年份后缀（部分搜索引擎含年份会 0 结果）
2. 去括号及其内容（`[1080p]`、`(2019)` 等）
3. 标准化季集号：中文 `"第N季"` → `"S0N"`，`"第N集"` → `"E0N"`
4. 去特殊字符（保留字母、数字、CJK、空格）
5. 合并多余空格

### 7. tokenize — 分词

将文本拆分为词元列表，供 L2 的 token_set 匹配策略使用。

**规则**：
- 英文：按空格分词，过滤停用词（the, a, an, of, in, on, at, to, for, is, it, and, or）
- 中文：按字符拆分（不依赖分词库），每个汉字作为一个 token
- 混合文本：先 splitByLanguage，再分别处理，合并结果
- 数字保留为独立 token

**示例**：
- `"Attack on Titan"` → `["attack", "titan"]`（去掉停用词 on）
- `"进击的巨人"` → `["进", "击", "的", "巨", "人"]`
- `"西部世界 Westworld"` → `["西", "部", "世", "界", "westworld"]`

### 8. romanize — 拼音/罗马音转换（可选）

为中日文文本生成拼音或罗马音变体，作为匹配的附加候选。

**用途**：BT 标题中常见拼音/罗马音命名（如 "Jin Ji De Ju Ren"、"Shingeki no Kyojin"）。

**规则**：
- 中文 → 拼音（无声调，空格分隔）
- 日文 → 罗马音
- 只作为 extractVariants 的附加候选，不替代原始中文名/日文名
- 不要把 romanize 变成主匹配逻辑

**Gotchas**：
- Python 可用 pypinyin 库，前端可用 pinyin-pro
- 多音字取最常见读音即可，不需要完美

### 9. blacklist — 干扰词清理

从文本中去除已知的干扰词（发片组名、编码参数、噪声标签）。

**机制**：
- 通用 skill 只提供 blacklist 过滤机制
- 具体黑名单由项目层配置（如 YIFY、RARBG、SubsPlease、x264、10bit）
- 黑名单词用正则匹配，支持词边界（`\b`）

**用途**：cleanKeyword 的前置步骤，去掉污染搜索词的特征词。

## 统一输出结构

L1 处理后建议输出标准化的结构，供 L2/L3/L4 直接使用：

```
{
  original: string,           // 原始文本
  normalized: string,         // 标准化后
  language: "cn"|"en"|"jp"|"ko"|"mixed"|"none",
  cn: string,                 // 中文部分
  en: string,                 // 英文部分
  isShortName: boolean,
  variants: string[],         // 名称变体列表
  tokens: string[],           // 分词结果
  cleanKeyword: string,       // 清洗后的搜索词
  romanizedVariants: string[] // 拼音/罗马音变体（可选）
}
```

## 选择指南

| 场景 | 使用的能力 |
|------|-----------|
| 两个标题比较前 | normalize |
| 构造搜索词 | cleanKeyword + blacklist + extractVariants |
| BT 标题解析 | splitByLanguage + extractVariants |
| 判断是否需要严格匹配 | isShortName |
| 选择搜索语言 | detectLanguage |
| 集合交集匹配前 | tokenize |
| 拼音命名的 BT 资源 | romanize |
