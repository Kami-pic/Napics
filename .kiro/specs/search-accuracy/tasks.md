# 实现计划：搜索匹配准确性提升 (search-accuracy)

## 概述

本计划将搜索匹配准确性提升功能拆分为增量实现步骤，从底层工具函数开始，逐步构建影子名管理、别名解析、增强评分、搜索词构造等核心组件，最后集成到现有刮削和搜索流程中，并在前端添加交互支持。

## 任务

- [x] 1. 实现文本标准化和模糊匹配基础工具
  - [x] 1.1 重构 `backend/tmdb_client.py` 中的 `normalize_text` 函数，提取到新文件 `backend/text_utils.py`
    - 将现有 `normalize_text` 移到 `text_utils.py`，确保全角→半角、去标点空格、小写转换逻辑完整
    - 在 `tmdb_client.py` 中改为 `from text_utils import normalize_text`
    - _需求: 7.1, 7.2, 7.3, 7.4_

  - [x] 1.2 在 `backend/text_utils.py` 中实现 `fuzzy_score(s1, s2)` 模糊匹配函数
    - 基于 Levenshtein 编辑距离，返回 0.0-1.0 的相似度
    - 长度差异超过较长字符串 50% 时返回 0.0
    - 完全相同返回 1.0，空字符串返回 0.0
    - _需求: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 1.3 为 `normalize_text` 编写属性测试
    - **Property 18: 文本标准化输出规范** — 输出不含全角字符、标点、空格、大写字母
    - **Property 19: 文本标准化幂等性** — normalize_text(normalize_text(s)) == normalize_text(s)
    - **验证: 需求 7.1, 7.2, 7.3, 7.4**

  - [ ]* 1.4 为 `fuzzy_score` 编写属性测试
    - **Property 14: 模糊匹配值域约束** — 返回值始终在 [0.0, 1.0]
    - **Property 15: 模糊匹配自身相等性** — fuzzy_score(s, s) == 1.0
    - **Property 16: 模糊匹配长度差异阈值** — 长度差 > 50% 时返回 0.0
    - **Property 17: 模糊匹配对称性** — fuzzy_score(a, b) == fuzzy_score(b, a)
    - **验证: 需求 6.1, 6.2, 6.3, 6.4**

- [x] 2. 检查点 — 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 3. 实现影子名管理器 (ShadowNameManager)
  - [x] 3.1 创建 `backend/shadow_name_manager.py`，实现 `ShadowNameManager` 类
    - 实现 `get(file_path)` — 获取影子名条目
    - 实现 `set(file_path, shadow_name, source, tmdb_id)` — 设置影子名
    - 实现 `auto_fill(file_path, shadow_name, source, tmdb_id)` — 自动填充（不覆盖 manual）
    - 实现 `clear(file_path)` — 清除影子名
    - 实现 `get_search_name(file_path)` — 获取搜索名称（优先影子名）
    - 实现 `batch_generate()` — 批量从已有 NFO/刮削数据生成影子名
    - 读写 `media_library.json` 中的 `shadow_name`、`shadow_name_source`、`shadow_tmdb_id` 字段
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.3_

  - [ ]* 3.2 为 ShadowNameManager 编写属性测试
    - **Property 1: 影子名读写往返一致性** — set 后 get 返回相同值
    - **Property 2: 手动影子名不可被自动覆盖** — manual 来源的 auto_fill 返回 False
    - **Property 3: 自动填充在无手动影子名时成功** — 非 manual 时 auto_fill 返回 True
    - **Property 4: 清除影子名后字段为空** — clear 后 get 返回 None
    - **Property 5: get_search_name 优先返回影子名** — 有影子名时返回影子名
    - **验证: 需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

- [x] 4. 实现别名解析器 (AliasResolver)
  - [x] 4.1 创建 `backend/alias_resolver.py`，实现 `AliasSet` 数据类和 `AliasResolver` 类
    - 实现 `resolve(title, year, media_type)` — 合并多源别名
    - 实现 `_from_douban(title)` — 从豆瓣搜索建议提取 subtitle/别名
    - 实现 `_from_bangumi(title)` — 从 Bangumi 搜索提取 original_title
    - 实现 `_from_nfo(folder_path)` — 从 NFO 提取 originaltitle
    - 内存缓存已解析的别名，避免重复请求
    - 任一数据源失败时跳过，不影响其他数据源
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5, 13.2_

  - [ ]* 4.2 为 AliasResolver 编写属性测试
    - **Property 8: 别名解析完整性** — cn_names 至少包含原始标题
    - **Property 9: 别名解析缓存有效性** — 第二次调用不发起新请求
    - **Property 10: 别名解析数据源降级** — API 异常时仍返回有效 AliasSet
    - **验证: 需求 4.1, 4.4, 4.5**

- [x] 5. 实现增强匹配评分器 (EnhancedScorer)
  - [x] 5.1 创建 `backend/enhanced_scorer.py`，实现 `MatchResult` 数据类和 `EnhancedScorer` 类
    - 实现 `score_candidate(query, candidate, aliases, year)` — 多维度评分
    - 实现 `best_match(query, candidates, aliases, year)` — 选出最佳匹配
    - 评分维度：精确匹配(100)、模糊匹配、前缀匹配(70)、包含匹配(50)、别名交叉验证(+15~25)、年份(+20/-30)、热度(+10)
    - 置信度：score >= 80 → high, 50-79 → medium, < 50 → low
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 5.2 为 EnhancedScorer 编写属性测试
    - **Property 11: 精确匹配得分最高** — 完全相同时该维度 100 分
    - **Property 12: 年份匹配评分规则** — 相同+20, 差1+10, 差>1减30
    - **Property 13: 置信度与分数的双向映射** — score 与 confidence 一致
    - **验证: 需求 5.2, 5.4, 5.5**

- [x] 6. 实现搜索词构造器 (SearchQueryBuilder)
  - [x] 6.1 创建 `backend/search_query_builder.py`，实现 `SearchQueryBuilder` 类
    - 实现 `build_tmdb_queries(title, aliases, year)` — TMDB 搜索词列表（最多6个，无重复）
    - 实现 `build_bt_queries(title, aliases, year, media_type)` — BT 搜索词列表（英文名+年份优先）
    - 实现 `_simplify_title(title)` — 去除副标题（冒号后内容）
    - 搜索词按成功概率降序排列
    - _需求: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 6.2 为 SearchQueryBuilder 编写属性测试
    - **Property 20: TMDB 搜索词列表约束** — 非空、包含原始标题、长度<=6、无重复
    - **Property 21: 副标题简化搜索词** — 含冒号标题生成简化版本
    - **验证: 需求 8.1, 8.2, 8.4**

- [x] 7. 检查点 — 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 8. 实现索引器优先级管理 (IndexerPriorityManager)
  - [x] 8.1 创建 `backend/indexer_priority_manager.py`，实现 `IndexerConfig` 数据类和 `IndexerPriorityManager` 类
    - 实现 `load()` — 从 config.json 加载索引器优先级
    - 实现 `save(indexers)` — 保存索引器优先级到 config.json
    - 实现 `get_prioritized(media_type)` — 按优先级降序返回，支持按媒体类型过滤
    - 扩展 `config_manager.py` 的 `AppConfig`，新增 `indexer_priorities` 和 `search_confidence_threshold` 字段
    - _需求: 11.1, 11.2, 11.3_

  - [ ]* 8.2 为 IndexerPriorityManager 编写属性测试
    - **Property 23: 索引器优先级排序** — 返回列表按 priority 降序
    - **Property 24: 索引器媒体类型过滤** — 过滤后每个索引器的 preferred_types 包含该类型或为空
    - **验证: 需求 11.2, 11.3**

- [x] 9. 集成增强 TMDB 刮削流程
  - [x] 9.1 修改 `backend/tmdb_client.py`，集成影子名、别名解析、增强评分和搜索词构造
    - 新增 `enhanced_scrape_by_filename(filename, file_path)` 方法
    - 优先使用影子名作为搜索关键词
    - 通过 AliasResolver 收集别名，SearchQueryBuilder 构造搜索词
    - 对每个搜索词执行 TMDB 搜索，按 TMDB ID 去重
    - 使用 EnhancedScorer 评分，选出最佳匹配
    - 刮削成功且置信度 high/medium 时自动回填影子名
    - _需求: 9.1, 9.2, 9.3, 9.4, 9.5, 2.1_

  - [ ]* 9.2 为增强刮削流程编写属性测试
    - **Property 22: TMDB 候选项去重** — 候选列表中无重复 TMDB ID
    - **Property 7: 刮削成功时自动回填影子名** — high/medium 置信度时回填
    - **验证: 需求 9.4, 2.1**

- [x] 10. 集成增强 Prowlarr 搜索
  - [x] 10.1 修改 `backend/searcher.py`，新增 `enhanced_search` 方法
    - 使用 SearchQueryBuilder 构造搜索词列表（最多3个）
    - 按 download_url 去重
    - 综合排序：质量等级×0.4 + 做种数×0.3 + 索引器权重×0.15 + 标题匹配度×0.15
    - 部分索引器失败时跳过，使用其余结果
    - _需求: 12.1, 12.2, 12.3, 12.4_

  - [ ]* 10.2 为增强 Prowlarr 搜索编写属性测试
    - **Property 25: Prowlarr 搜索结果去重** — 无重复 download_url
    - **Property 26: Prowlarr 搜索结果综合排序** — 按综合评分降序
    - **Property 27: 索引器部分失败时结果完整性** — 部分失败不抛异常
    - **验证: 需求 12.2, 12.3, 12.4**

- [x] 11. 检查点 — 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 12. 添加后端 API 端点
  - [x] 12.1 在 `backend/main.py` 中添加影子名管理 API
    - `POST /media/shadow-name` — 设置影子名
    - `DELETE /media/shadow-name` — 清除影子名
    - `POST /media/shadow-name/batch` — 批量生成影子名
    - 修改 `/scrape` 端点，集成增强刮削流程，返回置信度信息
    - 修改 `/search` 端点，集成增强 Prowlarr 搜索
    - 修改 `/scan` 和 `/sync` 端点，扫描时从 NFO 自动填充影子名
    - _需求: 1.1, 1.5, 2.2, 2.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 12.1, 13.1, 13.3_

  - [x] 12.2 在 `backend/main.py` 中添加索引器优先级管理 API
    - `GET /config/indexers` — 获取索引器优先级列表
    - `POST /config/indexers` — 保存索引器优先级配置
    - _需求: 11.1_

- [x] 13. 前端类型定义和 API 封装
  - [x] 13.1 扩展 `frontend/types/index.ts`，新增类型定义
    - 新增 `ShadowName`、`MatchConfidence`、`EnhancedScrapeResult`、`IndexerPriority` 接口
    - 扩展 `AppConfig` 接口，添加 `indexer_priorities` 和 `search_confidence_threshold` 字段
    - _需求: 3.1, 10.1, 10.2, 10.3, 11.1_

  - [x] 13.2 扩展 `frontend/lib/api.ts`，添加新 API 调用
    - 添加 `setShadowName`、`clearShadowName`、`batchGenerateShadowNames` 方法
    - 添加 `getIndexerPriorities`、`saveIndexerPriorities` 方法
    - _需求: 3.2, 11.1_

- [x] 14. 前端影子名交互
  - [x] 14.1 修改 `frontend/components/detail/DetailDrawer.tsx`，添加影子名编辑入口
    - 在详情面板中显示影子名文本和来源标签（TMDB/手动/NFO 等）
    - 支持编辑和保存影子名（来源标记为 manual）
    - 支持清除影子名
    - _需求: 3.1, 3.2_

  - [x] 14.2 修改 `frontend/components/search/SearchModal.tsx`，影子名作为默认搜索词
    - 打开搜索升级弹窗时，如果媒体项有影子名，搜索框默认填入影子名
    - _需求: 3.3_

- [x] 15. 前端匹配置信度展示
  - [x] 15.1 修改刮削相关组件，根据置信度展示不同交互
    - 置信度 "high" — 自动采用匹配结果
    - 置信度 "medium" — 显示匹配结果和确认按钮，附带评分依据
    - 置信度 "low" — 显示候选列表供用户手动选择
    - _需求: 10.1, 10.2, 10.3_

- [x] 16. 前端索引器优先级设置
  - [x] 16.1 修改 `frontend/components/settings/SettingsModal.tsx`，添加索引器优先级配置区域
    - 显示索引器列表，支持设置优先级(0-100)、启用/禁用、偏好类型
    - 保存时调用后端 API 持久化
    - _需求: 11.1_

- [x] 17. 错误处理与降级集成
  - [x] 17.1 确保所有外部 API 调用有降级处理
    - TMDB 不可用时降级使用豆瓣/Bangumi 和缓存
    - 豆瓣别名解析失败时跳过，使用 Bangumi 和 NFO
    - 所有搜索词无结果时返回 confidence="low" 的空结果
    - _需求: 13.1, 13.2, 13.3_

- [x] 18. 最终检查点 — 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

## 备注

- 标记 `*` 的任务为可选测试任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号，确保需求全覆盖
- 检查点任务用于阶段性验证，确保增量开发的稳定性
- 属性测试使用 Python hypothesis 库验证正确性属性
- 单元测试和属性测试是互补的，属性测试验证通用规律，单元测试验证具体场景
