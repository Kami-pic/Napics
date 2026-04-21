# [一次性] 名称可信度审计报告

> 运行日期：2026-04-18
> 数据源：backend/media_library.json（只读，未修改）
> 记录总数：3302

## 1. 字段覆盖率

| 字段 | 有值 | 占比 |
|------|------|------|
| clean_name | 3301 | 99% |
| shadow_name | 2 | 0% |
| clean_name_source | 0 | 0% |

## 2. shadow_name_source 分布

| source | 数量 | 占比 |
|--------|------|------|
| (空) | 3300 | 99% |
| parsed | 1 | 0% |
| nfo | 1 | 0% |

## 3. clean_name 来源推断（启发式）

| 推断来源 | 数量 | 说明 |
|----------|------|------|
| likely_scrape | 0 | 和 shadow_name 中文部分一致，可能来自刮削 |
| likely_parsed | 3301 | 和 shadow_name 不一致，可能来自文件名清洗 |
| empty | 1 | clean_name 为空 |

## 4. clean_name 质量问题（386 个）

| # | 文件夹 | 文件名 | clean_name | 问题 |
|---|--------|--------|------------|------|
| 1 | 动画电影\交响诗篇 超进化Eureka.Seven.Hi-Evolution.A | 交响诗篇 超进化2 Anemone Eureka Seven Hi-Evolution (2018) | Eureka Seven Hi Evolution Anemone AAC | 残留技术标签: 'aac' |
| 2 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 02.rmvb | 02 | 纯数字: '02' |
| 3 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 03.rmvb | 03 | 纯数字: '03' |
| 4 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 04.rmvb | 04 | 纯数字: '04' |
| 5 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 05.rmvb | 05 | 纯数字: '05' |
| 6 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 06.rmvb | 06 | 纯数字: '06' |
| 7 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 07.rmvb | 07 | 纯数字: '07' |
| 8 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 08.rmvb | 08 | 纯数字: '08' |
| 9 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 09.rmvb | 09 | 纯数字: '09' |
| 10 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 10.rmvb | 10 | 纯数字: '10' |
| 11 | 动画番\东京地震8.0 Tokyo Magnitude 8.0 | 11.rmvb | 11 | 纯数字: '11' |
| 12 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][02][GB_CN][720p][MP | S01E02 | 纯格式串: 'S01E02' |
| 13 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][03][GB_CN][720p][MP | S01E03 | 纯格式串: 'S01E03' |
| 14 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][04][GB_CN][720p][MP | S01E04 | 纯格式串: 'S01E04' |
| 15 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][05][GB_CN][720p][MP | S01E05 | 纯格式串: 'S01E05' |
| 16 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][06][GB_CN][720p][MP | S01E06 | 纯格式串: 'S01E06' |
| 17 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][07][GB_CN][720p][MP | S01E07 | 纯格式串: 'S01E07' |
| 18 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][08][GB_CN][720p][MP | S01E08 | 纯格式串: 'S01E08' |
| 19 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][djsfg][09][GB_CN][720p][MP | S01E09 | 纯格式串: 'S01E09' |
| 20 | 动画番\东京食尸鬼 Tokyo Ghoul\东京食尸鬼 Season 01 | [红旅首发www.hltm.cc][KTXP][东京喰种][01][GB_CN][720p][MP4 | S01E01 | 纯格式串: 'S01E01' |
| 21 | 动画番\交响情人梦 Nodame Cantabile | 02.mp4 | 02 | 纯数字: '02' |
| 22 | 动画番\交响情人梦 Nodame Cantabile | 03.mp4 | 03 | 纯数字: '03' |
| 23 | 动画番\交响情人梦 Nodame Cantabile | 04.mp4 | 04 | 纯数字: '04' |
| 24 | 动画番\交响情人梦 Nodame Cantabile | 05.mp4 | 05 | 纯数字: '05' |
| 25 | 动画番\交响情人梦 Nodame Cantabile | 06.mp4 | 06 | 纯数字: '06' |
| 26 | 动画番\交响情人梦 Nodame Cantabile | 07.mp4 | 07 | 纯数字: '07' |
| 27 | 动画番\交响情人梦 Nodame Cantabile | 08.mp4 | 08 | 纯数字: '08' |
| 28 | 动画番\交响情人梦 Nodame Cantabile | 09.mp4 | 09 | 纯数字: '09' |
| 29 | 动画番\交响情人梦 Nodame Cantabile | 10.mp4 | 10 | 纯数字: '10' |
| 30 | 动画番\交响情人梦 Nodame Cantabile | 11.mp4 | 11 | 纯数字: '11' |

... 还有 356 个问题


## 5. shadow_name 质量问题（0 个）

无质量问题 ✅


## 6. 覆盖风险（0 个）

无覆盖风险 ✅
