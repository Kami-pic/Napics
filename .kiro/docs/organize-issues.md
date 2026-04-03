# 整理问题汇总 — 全部测试+全量审计

## 格式说明

每条问题包含：编号、文件夹、问题描述、修改函数、修改状态（✅已修/❌未修/⚠️修了但全量跑时回退）

---

## 一、分类问题（classify_folder）

| # | 文件夹 | 问题 | 原因 | 修改函数 | 状态 |
|---|--------|------|------|----------|------|
| C1 | 东京食尸鬼 | mixed→应为tv | 子目录"东京喰种第一季"的"第一季"是中文数字，`_is_season_dir`不识别 | `organizer._is_season_dir` 加中文数字季号 | ✅ Day2第11轮 |
| C2 | 永远之久远 | tv→应为series_collection | `[04]`等方括号数字被`_count_episode_files`当成集号 | `classify_folder` 加独立NFO优先检查 | ✅ Day2第2轮 |
| C3 | 命运之夜 | tv→应为series_collection | 旧tvshow.nfo匹配到TV版(tmdb_id=61415) | 流水线改为先删旧刮削再分析 | ✅ Day2第5轮 |
| C4 | 壳中少女/哥斯拉/EVA | movie_aggregate→应为series_collection | `classify_folder`子文件夹都是movie时没调用`_is_series_collection` | `classify_folder` 加 `_is_series_collection` 调用 | ✅ Day2第8轮 |
| C5 | EVA剧场版 | tv→应为series_collection | `_is_season_dir`包含"剧场版"，4个子目录被误判为季 | `_is_season_dir` 移除"剧场版" | ✅ Day2第10轮 |
| C6 | 茗记 | tv→应为series_collection | 无子目录的4个不同作品被判为tv | `classify_folder` 对无子目录多文件的判定逻辑 | ❌ 未修 |
| C7 | 经典电影 | tv→应为mixed | 全量跑时被重新整理，结构变了导致分类变了 | `classify_folder` | ⚠️ Day2测试通过但全量跑时回退 |
| C8 | 动画短片合集 | 刮削匹配到Alarm后被判为tv | 文件夹级NFO错误导致分类错误 | `scrape_folder` 聚合文件夹不应写文件夹级NFO | ❌ 未修 |
| C9 | 21克 | tv→应为movie | 单文件但`scrape_folder`写了tvshow.nfo | `scrape_folder` 单文件不写tvshow.nfo | ✅ Day3 |
| C10 | 来自深渊剧场版 | tv→应为series_collection | 有子目录被判为tv，但子目录是独立电影不是季 | `classify_folder` 子目录判定 | ❌ 未修 |
| C11 | 福音战士剧场版 | 全量跑后变回tv | Day2测试通过(series_collection)，但全量跑时旧刮削被删重新刮削后分类变了 | | ⚠️ 回退 |

## 二、结构问题（organize_folder / analyzer）

| # | 文件夹 | 问题 | 原因 | 修改函数 | 状态 |
|---|--------|------|------|----------|------|
| S1 | mixed类型散落视频 | 用move_to_subdir移到统一子目录 | 应该用wrap_in_folder各自包裹 | `analyzer._diagnose_structure` | ✅ Day2 |
| S2 | 孤立刮削文件 | 结构整理后NFO/poster留在父目录 | 改名后文件名不匹配 | `organizer.organize_folder` 加归位逻辑 | ✅ Day2 |
| S3 | 经典电影CD分片 | CD1+CD2需合并到同一文件夹 | | `organize_folder` 内置CD合并 | ✅ Day2第9轮 |
| S4 | 动画短片合集 | 4个子目录无NFO | 散落视频包裹后子目录刮削失败 | `scrape_folder` 子目录刮削 | ❌ 未修 |
| S5 | 欧美电影/韩国电影等 | 聚合文件夹内散落视频未包裹 | 全量跑时结构整理不彻底 | `organize_folder` | ❌ 未修 |

## 三、刮削问题（scraper / tmdb_client）

| # | 文件夹 | 问题 | 原因 | 修改函数 | 状态 |
|---|--------|------|------|----------|------|
| D1 | 方子传 | 刮削失败 | "TV版"没去掉 | `_clean_filename_for_folder` 加TV版 | ✅ Day2第5轮 |
| D2 | 命运之夜 | 刮削失败 | 日文引号「」没去掉 | `_clean_filename_for_folder` 加「」 | ✅ Day2第6轮 |
| D3 | 龙之家族 | 匹配到越南电影 | 只搜中文没搜英文 | 中英文同时搜取最佳 | ✅ Day2第7轮 |
| D4 | 经典电影IF ONLY | 匹配到1980版 | 年份权重太低 | `calc_match_score` 年份+40/-50 | ✅ Day2第9轮 |
| D5 | 记录的地平线 | 分集匹配到"WWW"电影 | 文件名全是方括号，独立搜索搜到错误结果 | `scrape_folder` TV类型用TMDB ID+集号 | ✅ Day3 |
| D6 | 新恶魔人 | 文件夹名搜不到 | "新恶魔人"在TMDB搜不到 | `scrape_folder` 从视频文件名提取搜索词 | ✅ Day3 |
| D7 | 动画短片合集 | 文件夹级刮削匹配到Alarm | 聚合文件夹不应该有文件夹级刮削 | `scrape_folder` | ❌ 未修 |
| D8 | 命运之夜天之杯Ⅲ | 匹配到1946年Spring Song | 文件名太复杂，清洗后搜索词不准 | | ❌ 未修 |
| D9 | 欧美电影/其他地区 | 子目录刮削匹配到"指匠情挑" | 聚合文件夹的子目录用了父目录NFO | `scrape_folder` 聚合子目录独立刮削 | ❌ 未修 |
| D10 | 香港电影 | 聚合文件夹有封面但子电影没刮削 | 文件夹级刮削覆盖了子目录 | 同D9 | ❌ 未修 |
| D11 | 冰与火之歌各季 | 分集NFO title是分集标题不是剧名 | `get_episode_detail`返回分集标题 | `scrape_folder` 分集NFO用剧名 | ❌ 未修 |
| D12 | 多个TV文件夹 | 分集NFO匹配错误（"红蛇""女巫瓶"等） | `get_episode_detail`返回404后fallback写了错误NFO | `scrape_folder` fallback逻辑 | ❌ 未修 |
| D13 | 双斩少女/穷神/紫罗兰花园 | 刮削搜不到 | 冷门/文件名特殊 | | ❌ 未修 |
| D14 | 3个国家地理纪录片 | 刮削搜不到 | TMDB无数据 | | ❌ 无法修 |

## 四、命名问题（generate_standard_name / rename_videos_in_folder）

| # | 文件夹 | 问题 | 原因 | 修改函数 | 状态 |
|---|--------|------|------|----------|------|
| N1 | 切尔诺贝利 | 标准名用分集标题不用剧名 | `generate_standard_name`用了episode_title | `generate_standard_name` 分集用folder_title | ✅ Day2第4轮 |
| N2 | 银翼杀手 | 标准名缺英文名 | 分集NFO没有english_title | `rename_videos_in_folder` 从folder_scrape补english_title | ✅ Day2第4轮 |
| N3 | mixed类型 | 所有视频用文件夹级NFO改名 | mixed不在is_collection列表 | `rename_videos_in_folder` mixed加入is_collection | ✅ Day2第1轮 |
| N4 | 子文件夹视频 | 标准名用子目录刮削名不用父目录剧名 | 递归时没修正 | `rename_videos_in_folder` 递归用父目录剧名修正 | ✅ Day2第11轮 |
| N5 | 福音战士剧场版 | 4部影子名完全一样 | 被判为tv，所有视频用文件夹级NFO | 根因是C11分类回退 | ❌ 未修 |
| N6 | 茗记 | 4个影子名完全一样 | 被判为tv | 根因是C6分类错误 | ❌ 未修 |
| N7 | 经典电影 | 视频用文件夹名+错误集号 | 被判为tv | 根因是C7分类回退 | ❌ 未修 |
| N8 | 紫罗兰花园 | 影子名含hash(C46B0638) | 文件名中的hash没被清洗 | `_clean_filename_for_folder` 或 `generate_standard_name` | ❌ 未修 |
| N9 | 命运之夜 | 影子名含方括号[Heaven's Feel] | 文件名中的方括号没被清洗干净 | `generate_standard_name` | ❌ 未修 |
| N10 | 剑风传奇剧场版 | 3部影子名完全一样 | 被判为mixed但没独立刮削 | | ❌ 未修 |
| N11 | 永远之久远 | 6个视频用了父文件夹名 | series_collection但影子名没用子目录NFO | | ❌ 未修 |

## 五、集号提取问题（parse_filename）

| # | 文件名格式 | 问题 | 修改 | 状态 |
|---|-----------|------|------|------|
| E1 | `[HorribleSubs]+Devilman+Crybaby+-+01+[720p]` | +不识别为空格 | `parse_filename` +替换为空格 | ✅ Day3 |
| E2 | `- 01` 连字符分隔 | 不识别 | `parse_filename` 加连字符匹配 | ✅ Day3 |
| E3 | `加速世界 (10).mp4` 圆括号数字 | 不识别 | `parse_filename` 加圆括号匹配 | ✅ Day3 |
| E4 | `[13v2]` 方括号+版本号 | 不识别 | `parse_filename` 加v版本号匹配 | ✅ Day3 |
| E5 | `Shingeki No Kyojin S1 01` S+空格+数字 | 不识别 | `parse_filename` 加S空格匹配 | ✅ Day3 |
| E6 | `第一集` 中文数字集号 | 不识别 | `parse_filename` 加中文数字映射 | ✅ Day3 |
| E7 | `02.2160p.HD...` 开头纯数字 | 不识别 | `parse_filename` 加开头数字匹配 | ✅ Day3 |
| E8 | `Baccano! 01 (` 标题+空格+数字+括号 | 不识别 | `parse_filename` 加标题后数字匹配 | ✅ Day3 |

## 六、清洗函数问题（_clean_filename_for_folder）

| # | 文件名 | 问题 | 修改 | 状态 |
|---|--------|------|------|------|
| F1 | `[电影天堂www.dy2018.com]` | 广告没清干净 | 重写清洗函数 | ✅ Day2 |
| F2 | `[66影视www.66Ys.Co]` | 同上 | 同上 | ✅ Day2 |
| F3 | `影视帝国(bbs.cnxp.com)` | 站名没清 | 加已知站名列表 | ✅ Day2 |
| F4 | BD紧跟中文 | `\b`不匹配中文边界 | 改用`(?<![a-zA-Z])` | ✅ Day2 |
| F5 | 中文方括号【】 | 没去除 | 加规则 | ✅ Day2 |
| F6 | 日文引号「」 | 没去除 | 加规则 | ✅ Day2 |
| F7 | TV版/剧场版等 | 没去除 | 加媒体形式标签 | ✅ Day2 |
| F8 | `+`代替空格 | 没替换 | 加+替换 | ✅ Day3 |
| F9 | 尾部纯数字集号 | 没去除 | 加尾部数字去除 | ✅ Day3 |

## 七、全量执行暴露的新问题（Day3）

这些是全量跑时新发现的，之前测试没覆盖到：

| # | 问题 | 影响范围 | 根因 | 修改函数 |
|---|------|----------|------|----------|
| B1 | 聚合文件夹(mixed/collection)内散落视频未包裹就直接刮削 | 欧美电影、韩国电影、其他地区、香港电影 | `_batch_organize.py`的`run_pipeline`没有对聚合子目录递归执行结构整理 | `run_pipeline` + `organize_folder` |
| B2 | 聚合文件夹被写了文件夹级NFO | 动画短片合集、经典电影 | `scrape_folder`对聚合文件夹也写了tvshow.nfo/movie.nfo | `scrape_folder` |
| B3 | TV类型分集NFO用了分集标题而非剧名 | 冰与火之歌、斯巴达克斯、多个动画番 | `get_episode_detail`返回的title是分集标题，写入NFO后`rename_videos_in_folder`读到了分集标题 | `scrape_folder`分集NFO写入逻辑 |
| B4 | `get_episode_detail`返回404后fallback写了错误NFO | 大量动画番 | TMDB很多动画没有分集数据，fallback用`_write_movie_nfo_for_video`写了文件夹级数据 | `scrape_folder` fallback逻辑 |
| B5 | 已测试通过的文件夹被全量跑覆盖 | EVA、命运之夜、经典电影等 | 全量脚本没有跳过已整理好的文件夹 | `_batch_organize.py` |
| B6 | media_library.json频繁写入导致损坏 | 影子名填充步骤 | 每填一个影子名就全量写一次JSON | `shadow_name_manager` 批量写入 |
| B7 | 影子名含hash/广告/方括号 | 紫罗兰花园、命运之夜等 | `generate_standard_name`清洗不够 | `generate_standard_name` |

---

## 统计

- 总问题数：C11 + S5 + D14 + N11 + E8 + F9 + B7 = 65
- 已修复：C5 + S3 + D6 + N4 + E8 + F9 = 35 (54%)
- 未修复：30 (46%)
- 其中全量跑回退的：3 (C7/C11/N5/N7)
