# [TODO] 业务 Skill 规划

> L1-L4 是通用能力层（文本处理/匹配评分/数据过滤/结果排序），已完成。
> 本文档规划业务层 skill——特定于本项目的编排模式和领域知识。

---

## 已识别的业务 Skill

### S1. 多语言搜索词构造
- 输入：媒体名称（可能是中文/英文/混合）
- 输出：{ cn_name, en_name, original_name } 三维搜索词
- 核心逻辑：L1 split_by_language + shadow_name 提取 + TMDB/豆瓣别名扩展
- 应用场景：SSE 搜索、订阅匹配、批量升级
- 详细设计：`docs/multilang-search-todo.md`

### S2. 媒体信息补全（TMDB 英文名 + 评分）
- 输入：中文标题 + 年份 + media_type
- 输出：{ tmdb_id, en_name, original_name, rating, poster_url }
- 核心逻辑：TMDB search → 年份校验 → 最佳匹配 → 缓存
- 应用场景：发现页详情、媒体库补全、订阅 tmdb_id 补全
- 限频策略：40 req/10s，批量操作间隔 0.5s，失败重试 1 次

### S3. 搜索结果匹配排序
- 输入：搜索词 + 搜索结果列表
- 输出：排序后的结果列表（含 match_score + quality_score + is_junk）
- 核心逻辑：L2 match_chain + quality_parser + L4 multi_level_sort
- 应用场景：SSE 搜索结果排序、订阅匹配、批量升级推荐
- 已实现：_enrich_result（但可以抽象为独立模块）

### S4. 本地媒体感知
- 输入：推荐/探索条目列表
- 输出：注入 local_status + local_folder
- 核心逻辑：三层匹配（tmdb_id → title+year → title）+ 内存索引
- 应用场景：发现页推荐/探索、搜索结果本地状态标注
- 已实现：local_media_matcher.py

### S5. 质量评分与升级判断
- 输入：当前文件质量 + 候选资源质量
- 输出：是否升级 + 升级幅度
- 核心逻辑：100 分制评分 + 阈值 5 分 + 分辨率/编码/音频权重
- 应用场景：搜索结果"↑更高"标签、订阅洗版、批量升级
- 已实现：quality_parser.compute_quality_score

---

## 待讨论

1. 这 5 个 skill 的优先级排序？
2. 每个 skill 的文档格式——是写成 `.kiro/skills/S1-xxx.md` 还是直接写在 knowledge 里？
3. S1 和 S2 是否需要在本次对话中开始实现，还是单独开对话？
4. 是否还有其他业务编排模式需要抽象为 skill？

---

## 和 L1-L4 的关系

```
L1 文本处理 ─┐
L2 匹配评分 ─┤── 通用能力层（已完成）
L3 数据过滤 ─┤
L4 结果排序 ─┘
              ↓ 调用
S1 多语言搜索词 ─┐
S2 媒体信息补全 ─┤── 业务 Skill 层（待建设）
S3 搜索结果排序 ─┤
S4 本地媒体感知 ─┤
S5 质量评分升级 ─┘
              ↓ 编排
路由层（routes/*）── 接口层（组合调用 skill）
```
