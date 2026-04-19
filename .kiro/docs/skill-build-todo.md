# [TODO] 搜索匹配过滤排序 — 技能建设与业务验证

> 两个目标：
> 1. ✅ 建立 L1-L4 四个通用技能（`.kiro/skills/`）
> 2. ✅ 用 nas-video-upgrader 的搜索匹配过滤场景验证和强化这些技能
>
> 参考文档：`search-match-filter-research.md`（调研）、`search-matching-todo.md`（业务需求）
> 技能文件：`skills/L1-text-processing.md` ~ `skills/L4-result-sorting.md`
> 测试报告：`stage1-test-report.md`（87 测试）、`l1l4-integration-report.md`（22 集成测试）
> 设计文档：`name-trust-design.md`（名称可信度）、`name-trust-audit.md`（审计报告）

## 架构决策

- L1-L4 是通用能力 skill（已完成，不再新增 skill 文件）
- 业务编排不做独立 skill，直接改业务代码调用 L1-L4，验证后总结到 knowledge 文件

---

## ✅ 已完成

### 阶段 1：通用技能实现（87 个测试全绿）
- [x] L1 text-processing（41 测试）：normalize / splitByLanguage / isShortName / tokenize / cleanKeyword 等
- [x] L2 match-scoring（18 测试）：match_chain / multi_dimension_score / 动态 fuzzy / 短名字保护
- [x] L3 data-filtering（19 测试）：include_exclude / threshold / soft_filter / deduplicate / filter_pipeline
- [x] L4 result-sorting（9 测试）：multi_level_sort / weighted_sort / 磁力排后 / 稳定排序

### 阶段 2.0：名称流转链路治理
- [x] 2.0.1 新增 clean_name_source + NAME_SOURCE_PRIORITY + safe_set_clean_name + auto_fill 分层保护
- [x] 2.0.2 只读审计 media_library.json（3302 条）：零覆盖风险
- [x] 2.0.3 正式拦截：刮削/扫描/手动修改 三个写入点接入保护

### 阶段 2.1：BT 搜索接入
- [x] 2.1.1 后端 _enrich_result 新增 match_score（L2 match_chain + parse_filename）
- [x] 2.1.2 前端 displayResults 排序改用 match_score
- [x] 2.1.4 后端 is_junk 标记 + 前端 smartFilter 切换

### 阶段 2.2：全场景切换（22 个集成测试全绿）
- [x] SecondaryMatcher → L1 split_by_language + L2 match_chain
- [x] local_media_matcher → L1 normalize
- [x] searcher._composite_score → L2 match_chain
- [x] tmdb_client/scraper/enhanced_scorer/combined_recommend/batch_recommend → L1 normalize
- [x] 前端 FolderDetail/VideoDetail cnName → splitByLanguage

---

## 🔲 未完成

### 2.1.3 多语言搜索词构造（暂缓）
- [ ] SSE 搜索时不同源用不同语言搜索词
- 当前回退链够用，等实际搜索质量问题再优化

### 2.2 反馈迭代（需实测）
- [ ] 根据实战反馈修订 skill 文档
- [ ] 用刮削候选、推荐去重等场景进一步验证

### 阶段 3：沉淀和复用
- [ ] 3.1 将验证后的 skill 文档定稿
- [ ] 3.2 提取业务无关的通用代码模板到 skill 的 references/ 目录
- [ ] 3.3 提取各场景的配置模板（维度、权重、策略）为 JSON/YAML

### 已知限制（待后续优化）
- BT 标题含集号时 match_chain 匹配度下降（parse_filename 未识别 `- 01` 为集号）
- 多译名匹配依赖目标标题列表完整性（如 `烙印勇士` vs `剑风传奇`）
