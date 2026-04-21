# [TODO] 下一步工作清单

> 历史 Bug 30 项 + P2 功能 13 项已全部完成（代码层面），已完成的条目归档到 devlog。
> 本文件只保留仍需处理的工作。

---

## 用户实测反馈的新问题

### 前端 UI

- [ ] 发现页排行角标高度/位置没有和右边评分标签对齐
- [ ] 卡片上不需要显示 TMDB 评分（只在详情页显示）
- [ ] 详情页订阅按钮缺少"取消订阅"状态（当前只有 订阅/已订阅，无法取消）
- [ ] 保存路径 placeholder 没有显示默认 NAS 路径

### 订阅系统（需重新规划）

> 以下功能代码已写但用户未看到效果，需要重新验证和完善：

- [ ] 订阅日历（SubscribeCalendar）— 没看到效果
- [ ] 自动洗版开关（SubscribeConfigModal best_version）— 没看到效果
- [ ] 订阅源选择（SubscribeSourceSelect）— 没看到效果
- [ ] 订阅机制整体需重新规划（追更 vs 一次性下载 的区别不清晰）

### 后端 Bug

- [ ] 清洗名回退链算法不完善：如"黑袍纠察队 第五季"没有生成去掉"第五季"的宽泛回退词
  - `extract_variants()` 只处理 `_CN_SEASON_RE`（"第N季"数字），没覆盖中文数字（"第五季"）
  - 也缺少去掉"剧场版"、"2"（系列续作数字）等后缀的回退变体
  - 需要补充：中文数字季号、剧场版/OVA/SP、系列续作数字（如"3"/"III"）的剥离

### 已知但暂不处理

- [ ] 异步补全首次请求可能无英文名（需清缓存后第二次才有）— 已有 C+E 方案缓解

---

## 技术债务

- [ ] `pan_models.py` 的 4 个 `@validator` → Pydantic V2 `@field_validator`
- [ ] `routes/search.py`（541 行）拆分：`_merge_bt_extra_sources` 和 SSE `_generate` 下沉到业务层
- [ ] `routes/discover.py`（729 行）拆分：`_async_enrich_tmdb_ids`、`douban_hot` 等下沉到业务层
- [ ] 后端 1672 处 `print()` → `logging` 模块

---

## 功能迭代（已确认完成，保留记录）

以下项目经代码复查确认已实现：

- [x] 前端搜索框交互与多语言分配：`userEditedRef` 跟踪手动修改，手动输入时不传 cn_name/en_name
- [x] 多语言搜索词构造：`search_keyword_mapper.py` 完整实现源→语言映射 + 回退链 + 季号拼接
- [x] 匹配评分：`match_scoring.py` match_chain + `_enrich_result` match_score
- [x] 智能过滤：`search_helpers.py` compute_junk_flags（枪版/低匹配/死种）
- [x] 前端三层分离：results → displayResults → filtered
- [x] 综合排序：`result_sorting.py` multi_level_sort（match_score → quality_score → seeders → size）

### 待后续对话处理

- [ ] 媒体库清洗名"未设置"问题（树构建时动态计算可能覆盖）
- [ ] 发现页豆瓣信息匹配不上 + 封面丢失（特定条目）
- [ ] 媒体库批量 TMDB 搜索补全英文名（665 条只有中文）
- [ ] 业务 Skill 建设（S1-S5）→ 见 business-skills-plan.md
- [ ] BT 标题含集号时 match_chain 匹配度下降
- [ ] 多译名匹配依赖目标列表完整性（别名列表补充）
