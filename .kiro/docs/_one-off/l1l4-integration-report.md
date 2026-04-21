# [一次性] L1-L4 全场景集成测试报告

> 运行日期：2026-04-19
> 环境：Python 3.14.3, pytest 9.0.2, Windows
> 沙盒：backend/sandbox_real/（3215 个视频文件，6 个分类）

## 测试总览

| 测试套件 | 用例数 | 通过 | 失败 |
|----------|--------|------|------|
| L1 splitByLanguage 真实数据 | 5 | 5 | 0 |
| L1 normalize 一致性 | 2 | 2 | 0 |
| SecondaryMatcher + L2 | 6 | 6 | 0 |
| LocalMediaMatcher + L1 | 3 | 3 | 0 |
| _enrich_result match_score/is_junk | 2 | 2 | 0 |
| L3+L4 过滤排序端到端 | 1 | 1 | 0 |
| 沙盒全量 smoke test | 3 | 3 | 0 |
| **合计** | **22** | **22** | **0** |

## 切换清单

| 模块 | 旧实现 | 新实现 | 测试覆盖 |
|------|--------|--------|----------|
| SecondaryMatcher._split_cn_en | 手写 CJK 正则 | L1 split_by_language | ✅ test_exact_match 等 6 个 |
| SecondaryMatcher._match_title | text_utils.fuzzy_score | L2 match_chain | ✅ test_sandbox_bt_titles |
| local_media_matcher 索引 | text_utils.normalize_text | L1 normalize | ✅ test_build_index + match |
| searcher._composite_score | text_utils.fuzzy_score | L2 match_chain | ✅ 间接（通过 enhanced_search） |
| routes/search._enrich_result | 无 match_score | L2 match_chain + parse_filename | ✅ test_match_score_calculation |
| routes/search._enrich_result | 无 is_junk | L3 soft_filter 逻辑 | ✅ test_is_junk_detection |
| 前端 displayResults 排序 | keyword.includes() | match_score 排序 | ✅ 前端构建通过 |
| 前端 FolderDetail cnName | 纯 CJK 正则 | splitByLanguage | ✅ 前端构建通过 |
| 前端 VideoDetail cnName | 纯 CJK 正则 | splitByLanguage | ✅ 前端构建通过 |
| tmdb_client | text_utils.normalize_text | L1 normalize (别名导入) | ✅ 间接 |
| scraper | text_utils.normalize_text | L1 normalize (别名导入) | ✅ 间接 |
| enhanced_scorer | text_utils.normalize_text | L1 normalize (别名导入) | ✅ 间接 |
| combined_recommend | text_utils.normalize_text | L1 normalize (别名导入) | ✅ 间接 |
| batch_recommend | text_utils.normalize_text | L1 normalize (别名导入) | ✅ 间接 |

## 已知限制

1. **BT 标题含集号时 match_chain 匹配度下降**：如 `[AnimeRG] Shigurui - 01` 的 clean_name 是 `Shigurui 01`（含集号），和 `Shigurui Death Frenzy` 的 fuzzy 匹配分数不够。根因是 parse_filename 没有把 `- 01` 识别为集号。
2. **多译名匹配依赖目标标题列表完整性**：如 `烙印勇士` vs `剑风传奇`，同一部作品的不同中文译名需要在 target_titles 中都包含才能匹配。
3. **text_utils.py 保留**：`fuzzy_score` 仍被 L2 match_scoring.py 内部使用，`normalize_text` 不再被核心代码直接使用但保留兼容。

## 修复过程中发现的 bug

1. **match_chain 签名不匹配**：调用时传了 2 个字符串，实际需要 3 个列表参数。已修复所有调用点。
2. **_enrich_result 需要 parse_filename 预处理**：直接把 BT 完整标题传给 match_chain 会因为噪声（分辨率、编码等）导致匹配失败。改为先用 parse_filename 提取 clean_name 再匹配。
3. **include_exclude_filter 返回值是 dict 不是 tuple**：测试代码的解构赋值写错了。
