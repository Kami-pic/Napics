# [一次性] 阶段 1 测试报告 — L1-L4 通用技能

> 运行日期：2026-04-18
> 环境：Python 3.14.3, pytest 9.0.2, Windows
> 运行命令：`python -m pytest test_text_processing.py test_match_scoring.py test_data_filtering.py test_result_sorting.py -v`

## 总览

| 模块 | 测试文件 | 用例数 | 通过 | 失败 | 耗时 |
|------|----------|--------|------|------|------|
| L1 文本处理 | test_text_processing.py | 41 | 41 | 0 | — |
| L2 匹配评分 | test_match_scoring.py | 18 | 18 | 0 | — |
| L3 数据过滤 | test_data_filtering.py | 19 | 19 | 0 | — |
| L4 结果排序 | test_result_sorting.py | 9 | 9 | 0 | — |
| **合计** | **4 个文件** | **87** | **87** | **0** | **0.44s** |

## L1 text_processing.py — 41 个用例

### normalize（7 个）
| 用例 | 输入 | 预期行为 | 结果 |
|------|------|----------|------|
| 全角→半角 | `Ｓ０４` | → `s04` | ✅ |
| 全角混合 | `進擊的巨人　Ｓ０４` | 繁→简 + 全角→半角 | ✅ |
| 标点移除 | `【YIFY】流浪地球２` | 去方括号 + 全角数字 | ✅ |
| 小写 | `Attack On Titan` | → `attack on titan` | ✅ |
| 空字符串 | `""` | → `""` | ✅ |
| CJK 空格折叠 | 多空格 | 折叠为单空格 | ✅ |
| 繁→简 | `進擊的巨人` | → `进击的巨人` | ✅ |

### detectLanguage（7 个）
| 用例 | 输入 | 预期 | 结果 |
|------|------|------|------|
| 中文 | `进击的巨人` | `"cn"` | ✅ |
| 英文 | `Attack on Titan` | `"en"` | ✅ |
| 日文 | `進撃の巨人` | `"ja"` | ✅ |
| 混合 | `进击的巨人 Attack on Titan` | `"mixed"` | ✅ |
| 纯数字 | `12345` | `"other"` | ✅ |
| 格式串 | `1080p x265` | `"en"` | ✅ |
| 空 | `""` | `"other"` | ✅ |

### splitByLanguage（5 个）
| 用例 | 输入 | 预期 cn / en | 结果 |
|------|------|-------------|------|
| 中英混合 | `[YIFY] 进击的巨人 Attack on Titan S04 (2023) 1080p` | cn=`进击的巨人` / en=`Attack on Titan S04 1080p` | ✅ |
| 英中顺序 | `Attack on Titan 进击的巨人` | cn=`进击的巨人` / en=`Attack on Titan` | ✅ |
| 纯中文 | `进击的巨人` | cn=`进击的巨人` / en=`""` | ✅ |
| 纯英文 | `Shingeki no Kyojin` | cn=`""` / en=`Shingeki no Kyojin` | ✅ |
| BT 标题带标签 | 含字幕组/分辨率标签 | 正确分离 | ✅ |

### isShortName（5 个）
| 用例 | 输入 | 预期 | 结果 |
|------|------|------|------|
| 短中文 | `她` | `true` | ✅ |
| 长中文 | `进击的巨人` | `false` | ✅ |
| 短英文 | `IT` | `true` | ✅ |
| 长英文 | `Attack on Titan` | `false` | ✅ |
| 数字不计 | `007` | 数字不算有效字符 | ✅ |

### extractVariants（4 个）
| 用例 | 输入 | 预期行为 | 结果 |
|------|------|----------|------|
| 含副标题 | `进击的巨人：最终季` | 提取主标题+副标题 | ✅ |
| 含年份 | `流浪地球 (2019)` | 提取名称+年份 | ✅ |
| 含季号 | `进击的巨人 S04` | 提取名称+季号 | ✅ |
| 中英混合 | `进击的巨人 Attack on Titan` | 提取中文+英文 | ✅ |

### cleanKeyword（4 个）
| 用例 | 输入 | 预期输出 | 结果 |
|------|------|----------|------|
| 去年份 | `流浪地球 (2019) [1080p]` | `流浪地球` | ✅ |
| 去方括号 | `[SubsPlease] 进击的巨人` | `进击的巨人` | ✅ |
| 季号标准化 | `第3季` | → `S03` | ✅ |
| blacklist | `x264 10bit` | 去掉编码标签 | ✅ |

### tokenize（3 个）
| 用例 | 输入 | 预期输出 | 结果 |
|------|------|----------|------|
| 英文去停用词 | `Attack on Titan` | `["attack", "titan"]` | ✅ |
| 中文 | `进击的巨人` | 按字符分词 | ✅ |
| 混合 | 中英混合 | 分别处理 | ✅ |

### processText + sandbox（6 个）
| 用例 | 预期行为 | 结果 |
|------|----------|------|
| 输出结构完整 | 包含所有字段 | ✅ |
| 中英提取 | cn/en 正确分离 | ✅ |
| sandbox normalize 不崩溃 | 真实数据全量跑 | ✅ |
| sandbox split 不崩溃 | 真实数据全量跑 | ✅ |
| sandbox processText 不崩溃 | 真实数据全量跑 | ✅ |
| 极端用例 | 空串/超长/纯符号 | ✅ |

## L2 match_scoring.py — 18 个用例

### matchChain（8 个）
| 用例 | 场景 | 预期 score | 结果 |
|------|------|-----------|------|
| 精确匹配 | `进击的巨人` vs `进击的巨人` | ≥ 90 | ✅ |
| 别名匹配 | 主标题不中，别名命中 | ≥ 70 | ✅ |
| 拆分匹配 | 中文部分匹配 | ≥ 50 | ✅ |
| fuzzy 匹配 | 相似但不完全一致 | ≥ 30 | ✅ |
| 无匹配 | 完全不相关 | 0 | ✅ |
| 短名字保护 | `她` vs `她的秘密花园` | 0 | ✅ |
| ID 精确匹配 | tmdb_id 一致 | 100 | ✅ |
| 动态 fuzzy 短词 | 长度≤4 禁用 fuzzy | 0 | ✅ |

### multiDimensionScore（10 个）
| 用例 | 场景 | 预期 | 结果 |
|------|------|------|------|
| 精确名称 | 完全一致 | score ≥ 90 | ✅ |
| 包含匹配 | 部分包含 | score ≥ 40 | ✅ |
| 短名字保护 | 短名字误匹配 | score = 0 | ✅ |
| 年份容差 | 2023 vs 2022 tolerance=1 | 通过 | ✅ |
| 年份不匹配 | 差距超过容差 | score × 0.5 | ✅ |
| 缺失惩罚 | 有年份但不匹配 | 惩罚生效 | ✅ |
| 交叉验证 | 多维度交叉加分 | bonus 生效 | ✅ |
| 季号精确 | 季号一致 | 加分 | ✅ |
| 输出结构 | 包含 score/breakdown/penalties/passed | 完整 | ✅ |
| 动态 fuzzy 阈值 | 不同长度不同阈值 | 正确 | ✅ |

## L3 data_filtering.py — 19 个用例

### includeExclude（5 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| exclude CAM | 标题含 CAM 被排除 | ✅ |
| exclude 带 reason | filtered_reason = "exclude: CAM" | ✅ |
| include 1080p | 只保留含 1080p 的 | ✅ |
| 空过滤器 | 全部保留 | ✅ |
| include + exclude | 同时生效 | ✅ |

### threshold（4 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| min seeders | seeders < 5 被排除 | ✅ |
| 磁力链接豁免 | seeders=0 + size=0 豁免 | ✅ |
| size 范围 | 超出范围被排除 | ✅ |
| 排除带 reason | filtered_reason 正确 | ✅ |

### softFilter（3 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| 标记垃圾 | HDTC → is_junk=true | ✅ |
| 标记带 reason | filtered_reason = "softFilter: HDTC" | ✅ |
| 标记磁力 | magnet_only 标记 | ✅ |

### deduplicate（3 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| infohash 去重 | 同 hash 只保留一条 | ✅ |
| 保留最优 | 保留 seeders 更高的 | ✅ |
| 去重统计 | stats 正确 | ✅ |

### filterPipeline（4 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| 完整流水线 | 去重→include/exclude→threshold→softFilter→faceted | ✅ |
| 流水线顺序 | 去重先于过滤 | ✅ |
| 统计含 reasons | exclude_reasons 字段 | ✅ |
| 空结果 | 返回全部 | ✅ |

## L4 result_sorting.py — 9 个用例

### multiLevelSort（7 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| match_score 优先 | 80 排在 40(quality=100) 前面 | ✅ |
| 磁力链接排后 | magnet_only=true 排最后 | ✅ |
| 整季包优先 | season_pack=true 排前面 | ✅ |
| 稳定排序 | 相同分数保持原序 | ✅ |
| seeders 缺失 | undefined → 0 | ✅ |
| season_pack 缺失 | undefined → false | ✅ |
| 默认排序顺序 | magnet→pack→match→quality→seeders→size | ✅ |

### weightedSort（2 个）
| 用例 | 场景 | 结果 |
|------|------|------|
| 基础加权 | 权重计算正确 | ✅ |
| 权重生效 | 不同权重不同排序 | ✅ |
