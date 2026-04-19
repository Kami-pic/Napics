# 给 agent 的优化建议（吸收 Gemini 意见后的版本）

> 目标：在保持 L1 / L2 / L3 / L4 四层边界不变的前提下，增强媒体匹配、过滤、排序的稳定性、可解释性与可配置性。

## 总原则

1. 保持四层职责不变。
   - L1 只做文本预处理。
   - L2 只做匹配评分。
   - L3 只做过滤、去重和标记。
   - L4 只做排序。

2. 所有层都要输出结构化结果。
   - 不要只返回布尔值或单个分数。
   - 尽量保留原因、分项、标记和统计信息，方便调试和 UI 展示。

3. 默认策略要明确。
   - 短名字保护必须默认开启。
   - fuzzy 不能无限放宽。
   - 去重必须先于过滤。
   - 默认排序必须优先相关性。

---

## 一、L1-text-processing.md 的修改建议

### 1. 增加 romanize 能力

请在 L1 中补充一个可选能力：romanize（拼音 / 罗马音转换）。

用途：
- 针对 BT 命名里常见的拼音 / 罗马音标题。
- 例如：Jin Ji De Ju Ren、Shingeki no Kyojin。
- 作为 extractVariants 和 cleanKeyword 的附加候选。

规则：
- 如果源文本包含中日文，可以生成拼音或罗马音变体。
- 这个能力只做“附加候选”，不要替代原始中文名或日文名。
- 不要把 romanize 变成主匹配逻辑。

### 2. 给 cleanKeyword 增加干扰词黑名单

请把干扰词清理做成可配置机制。

需要支持：
- 发片组名
- 编码参数
- 噪声标签
- 其他污染搜索词的特征词

例如可支持：
- YIFY
- RARBG
- SubsPlease
- x264
- 10bit

注意：
- 不要把这些词硬编码死在通用 skill 里。
- 通用 skill 只负责支持 blacklist。
- 具体黑名单由项目层配置。

### 3. 统一输出结构

L1 最好固定输出这些字段：

- original
- normalized
- language
- cn
- en
- isShortName
- variants
- tokens
- cleanKeyword
- romanizedVariants（可选）

这样后面的 L2 / L3 / L4 不需要自己重建文本逻辑。

---

## 二、L2-match-scoring.md 的修改建议

### 1. best_of 里增加动态 fuzzy 阈值

请把 fuzzy 规则改成按文本长度动态变化：

- 长度 ≤ 4：禁用 fuzzy，只允许 exact / contains
- 长度 5~10：Levenshtein ≥ 0.7 才算命中
- 长度 > 10：Levenshtein ≥ 0.8 才算命中

目的：
- 短词防误配。
- 长词保留一定容错。
- 保持短名字保护逻辑不被破坏。

### 2. 给匹配链增加“别名降权”

请把匹配链分数梯度改成下面这样：

1. ID 精确匹配 → 100
2. 主标题精确匹配 → 90
3. 别名 / 译名匹配 → 80
4. 标题拆分匹配 → 60
5. 动态 fuzzy 匹配 → 40
6. 不通过 → 0

要求：
- 主标题必须高于别名。
- 别名不能和主标题同权重。
- 这是为了减少“同名不同剧”的误伤。

### 3. 保留短名字保护

这个规则不要动：

- 中文 / 日文 ≤ 2 字符：只允许 exact
- 英文 ≤ 5 字符：只允许 exact
- 英文停用词不参与匹配

### 4. 把 matchingChain 和 score 分开

请明确：
- matchingChain 用于快速筛选。
- score 用于精细比较 / 排名。
- 不要把 matchingChain 的粗结果直接当最终排序分。

### 5. 输出要保持结构化

L2 的结果至少要带这些字段：

- score
- breakdown
- crossBonuses
- penalties
- passed

---

## 三、L3-data-filtering.md 的修改建议

### 1. 增加 filtered_reason

这是必须加的。

要求：
- 被排除的数据行，要写 filtered_reason。
- 被软过滤标记的数据行，也要写 filtered_reason。
- 方便 Agent 调试，也方便 UI 展示原因。

建议同时加：
- filtered_stage：比如 exclude / threshold / softFilter / deduplicate

### 2. 增加正则安全边界

includeExclude 里请加一条硬规则：

- 如果支持用户输入正则，必须加执行超时。
- 或使用安全正则库。
- 防止 ReDoS。

### 3. 去重必须先于过滤

请把流程固定成：

deduplicate → include/exclude → threshold → softFilter → faceted

不要反过来。

原因：
- 去重时要保留信息最完整的条目。
- 如果先过滤，可能把最完整的那条删掉。

### 4. softFilter 只做标记，不做降分

请明确：
- softFilter 只能标记。
- 不要修改分数。
- 降分逻辑归 L2，不归 L3。

### 5. 过滤后要返回统计

建议返回：
- total
- deduplicated
- included
- excluded
- flagged
- exclude reasons

这样更容易排查“为什么没搜到”。

---

## 四、L4-result-sorting.md 的修改建议

### 1. 增加缺失值兜底规则

请补充一个强制规则：

- 数值字段缺失：按 0 或最低档处理。
- 布尔字段缺失：按 false 处理。
- 信息不完整的条目，在相同匹配度下必须排在信息完整条目后面。

适用字段：
- seeders
- quality_score
- size
- is_season_pack

### 2. 默认排序优先 multiLevelSort

建议默认排序顺序写死成：

1. is_magnet_only
2. is_season_pack
3. match_score
4. quality_score
5. seeders
6. size

说明：
- 相关性优先。
- 特殊项先处理。
- 排序要可解释。

### 3. weightedSort 只作为显式模式

不要把 weightedSort 设成默认主路径。  
默认应该是 multiLevelSort。

### 4. 排序必须稳定

请明确：
- 相同分数时保留原始顺序。
- 排序规则变化时，前端可以本地重排。
- 不要引入随机性。

---

## 五、主业务流里要加的额外规则

这部分不要放进通用 skill，放在项目主流程里更合适。

### 名称来源可信度优先级

构造 clean_name 或做目标比对时，名称来源要按可信度排序：

1. user_manual：用户手动修正 / 指定 ID
2. scrape_exact：通过唯一 ID 得到的刮削结果
3. nfo_parsed：从 NFO 解析出来的标题
4. filename_parsed：从原始文件名猜测出来的名称

### 行为约束

- 如果当前最高可信来源低于阈值，就不要放宽 fuzzy。
- 低可信名称要标记为 pending_review。
- 不要让低质量名称覆盖高质量名称。

这个规则主要是为了解决“名称流转链路”的循环依赖问题。

---

## 六、推荐修改优先级

### P0
- L3 加 filtered_reason
- L3 去重先于过滤
- L4 缺失值兜底
- L2 短名字保护不变

### P1
- L1 加 romanize
- L1 加 blacklist 支持
- L2 动态 fuzzy 阈值
- L2 别名降权

### P2
- 主流程 trust chain
- pending_review
- 项目级黑名单配置
- 项目级阈值配置

---

## 七、改完后要达到的结果

改完以后，应该达到这些效果：

- 搜索词更干净，拼音 / 罗马音命中率更高。
- 短名字误配更少。
- 过滤原因可以回溯。
- 正则不会轻易卡死。
- 排序对缺失值更稳。
- 名称来源更可信，不容易把错名传播到后续流程。

---

## 八、给 agent 的一句话总结

请保持 L1 / L2 / L3 / L4 的分层不变，只做增强：L1 增加 romanize 和黑名单擦除能力，L2 增加动态 fuzzy 阈值与别名降权，L3 增加 filtered_reason 和正则安全边界并固定去重先于过滤，L4 增加缺失值兜底与稳定排序；名称来源可信度与 pending_review 规则放到主业务流，不要写进通用 skill。
