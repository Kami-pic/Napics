# [废弃] 搜索匹配过滤排序 — 技能建设与业务验证

> 主体工作已完成（阶段 1 + 阶段 2），未完成项已挪到 `search-matching-todo.md`。
> 保留本文件供追溯。
>
> 两个目标：
> 1. 建立 L1-L4 四个通用技能（`.kiro/skills/`）
> 2. 用 nas-video-upgrader 的搜索匹配过滤场景验证和强化这些技能
>
> 参考文档：`search-match-filter-research.md`（调研）、`search-matching-todo.md`（业务需求）
> 技能文件：`skills/L1-text-processing.md` ~ `skills/L4-result-sorting.md`

---

## 执行原则

- 每次只给 agent 一个 skill + 对应的业务数据结构（按层级隔离上下文）
- L1-L4 实现用 TDD 驱动，prompt 中附带具体的输入输出用例
- 名称流转链路用"非破坏性"三步法，不一上来就改覆盖逻辑
- 2.0 是 2.1 的前置条件，2.0 不完成 2.1 不开始
- **架构决策**：L1-L4 是通用能力 skill（已完成，不再新增 skill 文件）。阶段 2 的业务接入不做独立 skill，而是直接改业务代码调用 L1-L4，验证后把编排模式总结到对应的 knowledge 文件

---

## 阶段 1：实现通用技能 + TDD 验证

每个 skill 先写测试，再写实现。

### 1.1 L1 text-processing
- [x] 实现核心函数（normalize / detectLanguage / splitByLanguage / isShortName / extractVariants / cleanKeyword / tokenize / romanize / blacklist）
- [x] 派发时只提供 `L1-text-processing.md`
- [x] 测试用例：
  - `normalize("進擊的巨人　Ｓ０４")` → `"进击的巨人s04"` ✅
  - `normalize("【YIFY】流浪地球２")` → 含 `"yify"` 和 `"流浪地球2"` ✅
  - `splitByLanguage("[YIFY] 进击的巨人 Attack on Titan S04 (2023) 1080p")` → `{cn: "进击的巨人", en: "Attack on Titan S04 1080p"}` ✅
  - `splitByLanguage("Shingeki no Kyojin")` → `{cn: "", en: "Shingeki no Kyojin"}` ✅
  - `isShortName("她")` → `true`；`isShortName("进击的巨人")` → `false` ✅
  - `tokenize("Attack on Titan")` → `["attack", "titan"]`（去掉停用词 on）✅
  - `cleanKeyword("流浪地球 (2019) [1080p]")` → `"流浪地球"` ✅
  - `cleanKeyword("[SubsPlease] 进击的巨人 第3季 x264 10bit")` + blacklist → `"进击的巨人 S03"` ✅
  - `romanize("进击的巨人")` → 暂未实现（需 pypinyin 依赖），标记为可选
  - 输出结构包含所有字段 ✅
- [x] ✅ 完成标准：41 个测试全绿（含 sandbox_real 真实数据集成测试）+ 输出结构完整 + blacklist 可配置
  - [x] 修复 splitByLanguage 数字开头名称 bug（`91天`→cn=`91天`，`JOJO的奇妙冒险`→cn=`JOJO的奇妙冒险`）

### 1.2 L2 match-scoring
- [x] 实现核心函数（多维度评分 / 匹配链 / 交叉验证 / 缺失惩罚 / 动态 fuzzy）
- [x] 派发时只提供 `L2-match-scoring.md` + L1 的输出结构
- [x] 测试用例（全部通过）：精确匹配 / 包含匹配 / 短名字保护 / 年份容差 / 缺失惩罚 / 动态 fuzzy / 别名降权 / 匹配链模式
- [x] ✅ 完成标准：18 个测试全绿，matchingChain 和 score 两种模式都可用

### 1.3 L3 data-filtering
- [x] 实现核心函数（includeExclude / threshold / faceted / softFilter / deduplicate / filtered_reason）
- [x] 派发时只提供 `L3-data-filtering.md`
- [x] 测试用例（全部通过）：exclude / threshold / 磁力链接豁免 / 去重 / softFilter / 流水线顺序
- [x] ✅ 完成标准：19 个测试全绿

### 1.4 L4 result-sorting
- [x] 实现核心函数（multiLevelSort / weightedSort / 特殊项处理 / 缺失值兜底）
- [x] 派发时只提供 `L4-result-sorting.md` + L2 的输出结构
- [x] 测试用例（全部通过）：match_score 优先 / 磁力排后 / 整季包优先 / 稳定排序 / 缺失值兜底
- [x] ✅ 完成标准：9 个测试全绿

### 1.5 集成测试
- [x] L1→L2→L3→L4 完整流水线跑通（87 个测试全绿）

---

## 阶段 2：业务场景验证

### 2.0 前置：名称流转链路治理（非破坏性三步法）

> 设计文档：`docs/name-trust-design.md`

- [x] 2.0.1 **只读/扩展**：clean_name_source + NAME_SOURCE_PRIORITY + safe_set_clean_name + auto_fill 分层保护（36 测试全绿）
- [x] 2.0.2 **旁路运行**：只读审计 media_library.json（3302 条），零覆盖风险（报告：`name-trust-audit.md`）
- [x] 2.0.3 **正式拦截**：刮削/扫描/手动修改 三个写入点接入保护（123 测试全绿）

### 2.1 BT 搜索场景

- [x] 2.1.1 后端 _enrich_result 新增 match_score（L2 match_chain + parse_filename）
- [x] 2.1.2 前端 displayResults 排序改用 match_score
- [x] 2.1.4 后端 is_junk 标记 + 前端 smartFilter 切换

### 2.2 全场景切换到 L1-L4（22 个集成测试全绿）

- [x] SecondaryMatcher → L1 split_by_language + L2 match_chain
- [x] local_media_matcher → L1 normalize
- [x] searcher._composite_score → L2 match_chain
- [x] tmdb_client/scraper/enhanced_scorer/combined_recommend/batch_recommend → L1 normalize
- [x] 前端 FolderDetail/VideoDetail cnName → splitByLanguage
- [x] sub-agent 审查：切换完整性 100%，参数正确性 100%，逻辑一致性 100%

---

## 未完成项（已挪到 search-matching-todo.md）

- 2.1.3 多语言搜索词构造（暂缓）
- 2.2 实战反馈修订 skill 文档
- 2.2 刮削候选、推荐去重等场景验证
- 阶段 3 沉淀复用（skill 定稿 / 代码模板 / 配置模板）
- 已知限制：BT 标题含集号时匹配度下降 / 多译名依赖目标列表完整性
