# [当前] 搜索·匹配·过滤·排序 — 通用能力调研与技能规划

> 调研日期：2026-04-17
> 数据来源：nas-video-upgrader、MoviePilot、xhs-mj-workflow、GitHub 开源库、Kiro Skills 规范
>
> **两个目标**：
> 1. 建立 L1-L4 四个通用技能（跨项目复用，放 `~/.kiro/skills/`）
> 2. 用 nas-video-upgrader 的搜索匹配过滤场景验证和强化这些技能

---

## 一、业界最佳实践

### 1.1 开源库参考

| 库 | Stars | 语言 | 核心能力 | 值得借鉴的点 |
|---|---|---|---|---|
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | 2.9k | Python/C++ | 模糊字符串匹配 | 提供多种匹配策略（ratio/partial_ratio/token_sort_ratio/token_set_ratio/WRatio），每种适用不同场景；C++ 内核性能极高 |
| [thefuzz](https://github.com/seatgeek/thefuzz) | 9k+ | Python | 模糊字符串匹配 | RapidFuzz 的前身，API 设计简洁；`process.extractBests` 批量匹配+排序一步到位 |
| [fuzzysort](https://github.com/farzher/fuzzysort) | 3.7k | JavaScript | 前端模糊搜索 | 专为 UI 搜索优化，支持高亮匹配位置；SublimeText 风格的非连续字符匹配 |
| [OpenCC](https://github.com/BYVoid/OpenCC) | 8k+ | C++/多语言 | 中文简繁转换 | CJK 文本标准化的参考；繁→简转换对中文匹配很重要 |

### 1.2 RapidFuzz 的匹配策略体系（核心参考）

RapidFuzz 提供的匹配函数体系是业界标准，值得直接借鉴：

| 函数 | 适用场景 | 算法 |
|---|---|---|
| `ratio` | 两个字符串整体相似度 | Levenshtein 归一化 |
| `partial_ratio` | A 是 B 的子串（或反过来） | 最佳子串对齐 |
| `token_sort_ratio` | 词序不同但内容相同 | 排序后再 ratio |
| `token_set_ratio` | 一个字符串包含另一个的所有词 | 集合交集后 ratio |
| `WRatio` | 不确定用哪个时的万金油 | 自动选择最佳策略 |

**关键洞察**：不同场景需要不同的匹配策略，不存在"一个函数解决所有问题"。通用技能应该教会 AI 如何选择策略，而不是只提供一个函数。

### 1.3 Kiro Skills 规范要点

从 [Kiro 官方文档](https://kiro.dev/docs/cli/skills/) 和 [SKILL.md 最佳实践](https://www.mtechzilla.com/guides/how-to-develop-skill-md-production-guide-engineering-teams) 提炼：

- **Skill = 文件夹**：`SKILL.md`（必需）+ `references/`（可选的详细参考）
- **description 是触发器**：写清楚正向触发词 + 反向排除范围 + 产出描述
- **SKILL.md 结构**：Inputs → Steps → Outputs → Gotchas → Escalation Rules
- **Skill 和代码的关系**：Skill 是指导 AI 写代码的指令，不是代码本身。AI 读 Skill 后根据当前项目的语言和框架生成对应代码。同一个 Skill 可以指导生成 Python 代码，也可以指导生成 TypeScript 代码。
- **复用方式**：全局 Skill（`~/.kiro/skills/`）跨项目复用；项目 Skill（`.kiro/skills/`）项目内复用。全局 Skill 描述通用算法和模式，项目 Skill 描述业务特定的配置和约定。

---

## 二、三个项目的能力提炼

### 2.1 文本处理（L1）

**三个项目的共性**：

| 能力 | nas-video-upgrader | MoviePilot | xhs-mj-workflow |
|------|-------------------|------------|-----------------|
| 标准化 | `normalize_text`: 全角→半角、去标点、小写 | `StringUtils.clear`: 正则去特殊字符、去空格 | `normalizeText`: 全角→半角、去标点、小写 |
| 中英文分离 | `_split_cn_en`: 正则提取中文段+剩余英文 | `MetaAnime/MetaVideo`: 完整 BT 标题解析器 | 无（数据源已分好三语名） |
| 语言检测 | `_is_cjk/_is_chinese/_is_english` | `is_chinese/is_japanese/is_korean/is_english_word` | 无 |

**MoviePilot 的额外亮点**：
- `is_english_word`：判断是否为英文单词（非单个字母），防止短英文词误匹配
- `clear_upper`：标准化+大写，用于集合交集匹配（大写比小写更适合集合操作）

**应提炼为 L1 技能的能力**：
1. 文本标准化（全角→半角、去标点、统一大小写）
2. CJK 语言检测（中/日/韩/英/混合）
3. 中英文分离（从混合文本提取纯中文和纯英文部分）
4. 短名字判断（短名字需要更严格的匹配策略）
5. 名称变体提取（去副标题、去年份、去特殊字符）
6. 关键词清洗（搜索词预处理）

### 2.2 匹配评分（L2）

**三个项目的策略对比**：

| 维度 | nas-video-upgrader | MoviePilot | xhs-mj-workflow |
|------|-------------------|------------|-----------------|
| 匹配结果 | 布尔（通过/不通过）| 布尔（通过/不通过）| 连续分数（0-350）|
| 精确匹配 | Levenshtein≥0.8 | 集合交集 | 标准化后相等=满分 |
| 包含匹配 | 无 | 标题拆分后交集 | 包含=半分，短名字保护 |
| 模糊匹配 | Levenshtein | 无 | 无 |
| 多维度 | 单维度（标题） | 多层级（ID→标题→别名→副标题）| 多维度独立打分 |
| 交叉验证 | 无 | 无 | 英文+日文都匹配=+20 |
| 缺失惩罚 | 无 | 无 | 有作品名但没匹配上=×0.3 |

**xhs-mj-workflow 的评分模型最成熟**，核心设计：
- 每个维度独立打分（角色名80分、作品名150分、性别10分、热度20分）
- 短名字保护（英文≤5字符、日文≤2字符只允许精确匹配）
- 交叉验证加分（多维度同时命中=更可信）
- 缺失惩罚（有约束但没匹配上=降分而非排除）

**MoviePilot 的匹配链最实用**，核心设计：
- ID 精确匹配优先（IMDB/TMDB/豆瓣 ID）
- 标题集合交集（标准化后用 set.intersection，简洁高效）
- 逐层放宽（标题→别名→拆分→副标题）
- 英文单词保护（避免 "the" 等短词误匹配）

**RapidFuzz 的策略选择最全面**：
- ratio（整体相似度）、partial_ratio（子串匹配）、token_sort_ratio（词序无关）、token_set_ratio（集合包含）
- 不同场景选不同策略，而非一个函数打天下

**应提炼为 L2 技能的能力**：
1. 匹配策略选择指南（何时用精确/包含/模糊/集合交集）
2. 多维度独立评分模型（维度、权重、策略、阈值可配置）
3. 短名字保护机制
4. 交叉验证加分
5. 缺失惩罚
6. 匹配链（逐层放宽，首个有效结果停止）

### 2.3 过滤（L3）

| 能力 | nas-video-upgrader | MoviePilot | xhs-mj-workflow |
|------|-------------------|------------|-----------------|
| 硬过滤 | GlobalFilter（must_include/must_exclude）| filter_torrent（include/exclude/quality/resolution/size 正则）| 无 |
| 软过滤 | 智能过滤🛡️（排除枪版，用户可开关）| 无 | 评分惩罚（×0.3）|
| 多维筛选 | 前端 FilterBar（分辨率/来源/编码/大小/做种）| 规则组系统（用户可配置多组规则）| 无 |
| 去重 | infohash 去重 | download_url 去重 + 标题+年份+季集控重 | 无 |

**应提炼为 L3 技能的能力**：
1. 包含/排除过滤（正则匹配，AND/OR 组合）
2. 阈值过滤（数值范围）
3. 多维筛选器（多字段同时过滤）
4. 软过滤（标记/降分而非排除）
5. 去重策略（精确字段去重 + 标题相似度去重）

### 2.4 排序（L4）

| 能力 | nas-video-upgrader | MoviePilot | xhs-mj-workflow |
|------|-------------------|------------|-----------------|
| 加权排序 | quality_rank×0.4 + seeders×0.3 + indexer×0.15 + title_match×0.15 | 无 | 无 |
| 多级排序 | 前端：keyword包含 > quality_score > seeders > size_gb | 无 | 无 |
| 可配置优先级 | 无 | 用户可调整 torrent/site/upload/seeder 顺序 | 无 |
| 评分即排序 | 无 | 无 | 综合评分降序 |
| 分组排序 | 无 | sort_group_torrents（按媒体名分组，组内取最优）| 无 |

**应提炼为 L4 技能的能力**：
1. 加权排序（多字段加权综合分）
2. 多级排序（逐级比较，第一级相同比第二级）
3. 可配置优先级排序（用户可调整维度顺序）
4. 分组排序（先分组再组内排序）
5. 评分即排序（L2 评分直接用于排序）

---

## 三、nas-video-upgrader 的业务场景

### 需要搜索匹配过滤排序的 7 个场景

| # | 场景 | 用到的层 | 当前痛点 |
|---|------|---------|---------|
| 0 | **名称流转链路** | L1 | clean_name/shadow_name 的循环依赖：刮削依赖清洗名→清洗名来自原始文件名→原始文件名质量差→刮削失败→名称为空→搜索词差 |
| 1 | BT 搜索结果处理 | L1+L2+L3+L4 | 匹配度评分缺失，排序粗糙，不同源应用不同搜索词 |
| 2 | 网盘搜索结果处理 | L1+L3+L4 | 基本可用 |
| 3 | 订阅 RSS 匹配 | L1+L2+L3 | 已实现 |
| 4 | 刮削候选匹配 | L1+L2 | 基本可用 |
| 5 | 本地媒体匹配 | L1+L2 | 已实现 |
| 6 | 综合推荐去重 | L1+L2+L3 | 已实现 |
| 7 | 搜索词构造 | L1 | 已实现但不够精细 |

### 场景 0（前置）：名称流转链路与循环依赖问题

**这是所有搜索匹配的前置难题**。文件名在不同阶段被不同功能处理，形成了名称依赖链：

```
用户下载的原始文件名（他人命名，质量参差不齐）
  → parse_filename (tmdb_client.py) → clean_name（去标签、去质量标记）
  → generate_standard_name (renamer.py) → shadow_name（标准化影子名）
  → 刮削 (scraper.py) → 从 TMDB/豆瓣获取正式标题
  → _update_clean_names_after_scrape (shared.py) → 用刮削结果更新 clean_name
  → 搜索时用 clean_name + shadow_name 构造搜索词
```

**循环依赖风险**：
- 刮削依赖 clean_name 去搜索 TMDB → 但 clean_name 来自原始文件名的清洗
- 如果原始文件名质量差（如 "YIFY.2024.1080p.mkv"），clean_name 也差 → 刮削搜不到 → shadow_name 为空 → 搜索词差 → 搜索结果差
- 刮削成功后会更新 clean_name → 但如果刮削匹配错了（同名不同片），后续所有操作都基于错误的名称

**当前代码中的名称来源**：
| 名称 | 生成位置 | 来源 | 用途 |
|------|---------|------|------|
| `clean_name` | `tmdb_client.parse_filename` | 原始文件名清洗 | 搜索词构造、显示 |
| `shadow_name` | `renamer.generate_standard_name` | clean_name + 刮削数据 | 搜索词构造、重命名 |
| `shadow_name`（NFO） | `renamer.generate_shadow_name_from_nfo` | NFO 文件中的标题 | 覆盖 shadow_name |
| `clean_name`（刮削后） | `shared._update_clean_names_after_scrape` | 刮削结果的中文标题 | 覆盖 clean_name |

**需要解决的问题**：
1. 名称质量评估：判断 clean_name/shadow_name 是否可靠（是否来自刮削确认 vs 纯文件名猜测）
2. 名称来源追踪：记录每个名称的来源和可信度，搜索时优先用高可信度的名称
   - `user_manual`（最高）：用户手动修正/指定 ID
   - `scrape_exact`：通过唯一 ID 得到的刮削结果
   - `nfo_parsed`：从 NFO 解析出来的标题
   - `filename_parsed`（最低）：从原始文件名猜测出来的名称
3. 低质量名称标记：当 clean_name 质量差（过短、纯数字、纯英文缩写）时，标记为 `pending_review` 提醒用户手动修改
4. 防止错误传播：低可信来源的名称不应覆盖高可信来源的名称；刮削匹配错误时标记为"待确认"而非自动覆盖

### 场景 1（BT 搜索）的 4 个具体改进方向

1. **匹配度评分**：后端计算 `match_score`（0-100），作为 SearchResult 新字段返回前端
2. **排序优化**：匹配度权重最高（不相关的结果再高质量也没用）
3. **多语言搜索词**：不同源用不同语言搜索词（英文站用英文名，中文站用中文名）
4. **垃圾资源处理**：0 做种 0 大小的磁力链接资源统一排到最后

---

## 四、工作流程

> 详细 TODO 已拆分到独立文件：`skill-build-todo.md`
>
> 三个阶段概览：
> 1. **实现通用技能 + TDD 验证**：L1-L4 各自独立实现，附带测试用例
> 2. **业务场景验证**：先治理名称流转链路（非破坏性三步法），再用 BT 搜索主战场验证完整链路
> 3. **沉淀和复用**：提取代码模板和配置模板，实现 skill 和业务代码分离
