# 第二天整理优化 — 完整记录

## 一、整理前的问题修复（测试前）

### 1. 操作历史快照
- 需要清空机制 + 操作简介 + 按月保留至少一条
- 修改：`organize_history.py` 增加 `clear_all()`、`_generate_summary()`、`_auto_cleanup()`、`MAX_SNAPSHOTS=100`

### 2. 删除刮削递归 bug
- 问题：点删除刮削会递归删除子文件夹内所有刮削
- 修改：`main.py delete_scrape` 增加 `recursive` 参数，默认 False 只删文件夹级刮削

### 3. 删除刮削后卡片不刷新
- 问题：展开面板子卡片 `cacheKey={0}` 固定不变
- 修改：`CardGrid.tsx` ExpandPanel 传递 `refreshKey`，子卡片用 `cacheKey={refreshKey}`

### 4. _diagnose_structure mixed 类型处理
- 问题：mixed 类型散落视频用 `move_to_subdir` 全部移到一个统一子目录
- 修改：改为 `wrap_in_folder`，每个视频各自包裹进独立文件夹
- 同时增加判断：散落视频大多不是剧集编号时才用 wrap_in_folder

### 5. organize_folder 孤立刮削文件归位
- 问题：结构整理后，改名过的 NFO/poster 文件名不匹配新文件夹名，留在父文件夹
- 修改：增加孤立刮削文件归位逻辑（标准匹配 + 紧凑匹配 + 清洗匹配）

### 6. rename_videos_in_folder mixed 类型处理
- 问题：mixed 类型不在 is_collection 列表里，用文件夹级 NFO 给所有子视频改名
- 修改：mixed/variety/misc 加入 is_collection

### 7. 名字互换
- 决策：shadow_name 变为主显示名（标准名），file_name 变为原始文件名（小字可编辑可覆盖）
- 前端改动：DetailDrawer 标题优先标准名、ShadowNameSection 改为原始文件名编辑区、自动命名只更新标准名、CardGrid/EpisodeList 优先显示标准名、manage 页"影子名"→"标准名"
- 后端不变：数据字段名保持 shadow_name

## 二、清洗函数对比测试结论

### 清洗深度对比
跑了对比测试（_compare_search.py），结论：
- **清洗得越干净越好**——年份、媒体形式、季号等都是辅助匹配信息，不应该放在搜索词里
- TMDB 搜索 API 本身支持年份过滤，搜索词越纯净命中率越高
- 辅助信息（年份、集号、媒体类型）应该在 best_match 打分时使用，不是放在搜索词里

### 中英文对比
跑了中英文搜索对比（_compare_lang.py），结论：
- 英文搜索赢 4 次，中文赢 2 次，平局 3 次
- 文件名自带英文时，应该同时用中文和英文搜，取最佳匹配
- 纯中文文件名刮削后获得英文名，后续搜索升级时用标准名（含英文）更准

### 搜索策略
- 不是"搜不到才缩短"，而是先用最完整的清洗名搜，能匹配就用
- 渐进缩短顺序：完整清洗名 → 英文部分 → 去副标题（冒号拆分）→ 核心中文名
- 中英文同时搜，用 calc_match_score 比较取最佳

## 三、清洗函数增强记录

`analyzer._clean_filename_for_folder` 增加的规则：
1. 中文方括号【】去除
2. 日文引号「」去除
3. WEB-HR、UHD 质量标签
4. 分辨率数字（1024X576 等）
5. 中英字幕、UNCUT、KORSUB
6. 媒体形式标签：劇場版、剧场版、TV版、电视剧版、OVA、OAD、SP、特别篇、番外篇、总集篇、完结篇
7. 季号标记：第X季（含中文数字）、S01
8. H.264/H.265 编码标签

## 四、测试记录（从指派3个文件夹开始）

### 第1轮：经典电影、冰与火之歌、永远之久远（dry_run 分析）

| 文件夹 | 类型 | 结构 | 问题 |
|--------|------|------|------|
| 经典电影 | mixed | 5个wrap_in_folder ✓ | 改名全错（文件夹级NFO污染所有子视频）→ 修了 is_collection |
| 冰与火之歌 | tv ✓ | 0 ops ✓ | 改名有残留（广告没清干净）→ 修了清洗函数 |
| 永远之久远 | series_collection ✓ | 6个wrap_in_folder ✓ | 无问题 |

### 第2轮：永远之久远（execute）
- 执行成功：旧刮削打包18个 → 6个视频包裹 → 刮削全部ok → 标准名正确
- 原始文件名完整保留 ✓

### 第3轮：切尔诺贝利S1、魁拔—殊途、来自深渊（execute）
- 切尔诺贝利：刮削成功，标准名 `切尔诺贝利 Chernobyl S01E01` ✓
- 魁拔：刮削失败（TMDB搜不到），旧刮削被打包后丢失 → 修了旧刮削备份策略
- 来自深渊：完美 ✓

### 第4轮：切尔诺贝利（重测）、银翼杀手、哥斯拉（execute）
- 切尔诺贝利：标准名 `凌晨1点23分45秒 p.HD S01E01` ✗ → 修了 generate_standard_name 分集用剧名
- 银翼杀手：标准名 `我们都不是 Blade.Runner.Black.Lotus.S S01E02` ✗ → 同上 + 补充英文名
- 哥斯拉：完美 ✓

### 第5轮：方子传TV版、特别的她、命运之夜（execute）
- 方子传：刮削失败（TV版没去掉）→ 修了清洗函数去TV版
- 特别的她：✓（imdb_id 验证错误不影响功能）→ 修了 imdb_id None 处理
- 命运之夜：类型错误（旧tvshow.nfo）→ 修了流水线顺序（先备份删除旧刮削再分析）

### 第6轮：方子传（重测）、命运之夜（重测）、灵探特莱丝（execute）
- 方子传：✓ `方子传 The Servant S01E01`
- 命运之夜：类型修复为 series_collection ✓，但刮削失败（文件名太复杂）→ 修了日文引号去除 + 媒体形式标签去除
- 灵探特莱丝：✓ `灵探特莱丝 Trese S01E01`

### 第7轮：银翼杀手（重测）、龙之家族、壳中少女（execute）
- 银翼杀手：✓ `银翼杀手：黑莲花 Blade Runner Black Lotus S01E01`（修复成功）
- 龙之家族：刮削匹配到越南电影 → 修了中英文同时搜取最佳匹配
- 壳中少女：✓

### 第8轮：回归测试（12个文件夹）
- 壳中少女、哥斯拉、福音战士被错误判定为 movie_aggregate → 修了 classify_folder 调用 _is_series_collection

### 第9轮：经典电影（execute）
- 结构整理 ✓（7个散落视频包裹，CD分片合并正确）
- 刮削匹配精度差：IF ONLY 匹配到1980版、珍珠港匹配到纪录片、我的野蛮女友2匹配到2024版
- 原因：年份匹配权重太低 → 修了 calc_match_score 年份权重（+20→+40，-30→-50）
- 我的野蛮女友 1 搜不到 → 修了渐进搜索长度阈值（10→4）

## 五、第10轮修正：EVA 剧场版

问题：`_is_season_dir` 正则包含 `剧场版`，导致 EVA 的4个子文件夹（名字含"剧场版"）被误判为季目录 → 整个文件夹被判为 tv
修正：从 `_is_season_dir` 移除 `剧场版`（剧场版是独立电影不是季）
结果：EVA 正确判定为 series_collection ✓

## 六、回归测试最终结果：13/13 全部通过

| 文件夹 | 类型 | 刮削 | 标准名 |
|--------|------|------|--------|
| 切尔诺贝利S1 | tv ✓ | ✓ | `切尔诺贝利 Chernobyl S01E01` ✓ |
| 方子传TV版 | tv ✓ | ✓ | `方子传 The Servant S01E01` ✓ |
| 龙之家族第一季 | tv ✓ | ✓ | `龙之家族 House of the Dragon S01E01` ✓ |
| 灵探特莱丝 | tv ✓ | ✓ | `灵探特莱丝 Trese S01E01` ✓ |
| 银翼杀手：黑莲花 | tv ✓ | ✓ | `银翼杀手：黑莲花 Blade Runner Black Lotus S01E01` ✓ |
| 特别的她 | tv ✓ | ✓ | `特别的她 FLCL S01E01` ✓ |
| 来自深渊剧场版三部曲 | series_collection ✓ | ✓ | ✓ |
| 壳中少女 | series_collection ✓ | ✓ | ✓ |
| 哥斯拉动画电影 | series_collection ✓ | ✓ | ✓ |
| better call saul s5 | tv ✓ | ✓ | `风骚律师 Better Call Saul S05E01` ✓ |
| 指环王：力量之戒 | tv ✓ | ✓ | `指环王：力量之戒 Rings of Power S01E01` ✓ |
| 福音战士新剧场版 | series_collection ✓ | ✓ | ✓ |
| 经典电影之新世代诠释 | mixed ✓ | ✓ | ✓ |

## 七、待修问题（下次继续）

1. **东京食尸鬼类型错误**：应该是 tv 不是 mixed。子文件夹名"东京喰种第一季"和"东京食尸鬼 Season 01"没有被 _is_season_dir 识别（可能是因为"东京喰种第一季"里的"第一季"被清洗函数去掉了？需要检查）
2. **东京食尸鬼标准名错误**：第一季标准名用了"东京喰种"而非"东京食尸鬼"（TMDB 中文名）。原因是子文件夹名"东京喰种 Tokyo Ghoul"被当作独立搜索词，匹配到了 TMDB 的"东京喰种"而非父目录的"东京食尸鬼"
3. **冰与火之歌回归测试**：标准名检查需要包含子文件夹的结果
4. **茗记类型错误**：应该是 series_collection 不是 tv

## 八、测试文件清单（不要删除）

- `backend/test_clean_and_search.py`：清洗函数 + CD分组 + 搜索策略单元测试（25个用例）
- `backend/test_organize_pipeline.py`：整理流水线集成测试（18个真实文件夹）
- `backend/_organize_pipeline.py`：完整整理流水线入口
- `backend/_test_series.py`：series_collection 判定测试
- `backend/_show_got_names.py`：冰与火之歌标准名详细输出
- `backend/_test_ep.py`：集号提取测试
- `backend/_debug_gen.py`：generate_standard_name 调试
- `backend/_random_test.py`：随机文件夹测试
- `backend/_check_eva2.py`：EVA 类型判定调试
- `backend/_test_got_search.py`：冰与火之歌搜索词测试
- `backend/_test_got2.py`：TMDB 搜索词对比测试


## 七、最新修正（第11轮）

1. classify_folder 非季目录内容检查：检查非季目录的视频是否有剧集编号，有则也当作季目录（修复东京食尸鬼 mixed → tv）
2. scrape_folder 父目录优先搜 TV：有子目录时如果搜不到或搜到电影版，直接用 search_tv
3. parse_filename 尾部集号提取：增加尾部纯数字集号，先去分辨率标签再提取
4. parse_filename splitext bug：不再对 name 调用 splitext（避免 .com 被当扩展名）
5. 清洗函数增加 1024高清
6. rename_videos_in_folder 递归修正：用父目录剧名+英文名修正子文件夹标准名
7. 文件夹 shadow_name 格式：改为 中文名 英文名 (年份)
8. 英文提取从清洗后名字：所有搜索逻辑的英文提取改为从清洗后的名字

## 八、待继续（下次对话）

- 连续3组随机测试（每组3个）验证所有7步无错误
- 所有改进已在正式代码里（analyzer.py, organizer.py, scraper.py, tmdb_client.py, main.py）
- 测试文件在 backend/ 下，不要删除


## 九、第3天 — 随机测试（3组8个文件夹）

### 修复（测试前）

1. **parse_filename + 替换**：`+` 替换为空格（字幕组常用 `+` 代替空格），增加连字符分隔集号匹配（`- 01` 格式）
2. **_clean_filename_for_folder + 替换**：同上 + 去尾部纯数字集号（`Devilman Crybaby 01` → `Devilman Crybaby`）
3. **scrape_folder TV分集刮削**：末端文件夹多视频时，TV类型用 TMDB ID + 集号获取分集详情（`get_episode_detail`），不再用文件名独立搜索（修复记录的地平线分集匹配到"WWW"电影的问题）
4. **scrape_folder 文件名fallback**：末端文件夹搜不到时，从视频文件名提取英文/中文搜索词（修复新恶魔人搜不到的问题）

### 第1组

| 文件夹 | 类型 | 刮削 | 标准名 | 状态 |
|--------|------|------|--------|------|
| 人渣的本愿 Scum's Wish | tv ✓ | ✓ | `人渣的本愿 Scum's Wish S01E01` ✓ | 首次通过 |
| 新恶魔人 | tv ✓ | ✓ | `恶魔人：哭泣之子 DEVILMAN crybaby S01E01` ✓ | 修复后通过 |
| 记录的地平线 | tv ✓ | ✓ | `记录的地平线 Log Horizon S01E01` ✓ | 修复后通过 |

### 第2组

| 文件夹 | 类型 | 刮削 | 标准名 | 状态 |
|--------|------|------|--------|------|
| 赛博朋克：边缘行者 | tv ✓ | ✓ | `赛博朋克：边缘行者 Cyberpunk Edgerunners S01E01` ✓ | 首次通过 |
| 毒枭第一季 | tv ✓ | ✓ | `毒枭 Narcos S01E01` ✓ | 首次通过（结构整理14个移动） |
| 交响情人梦 Nodame Cantabile | tv ✓ | ✓ | `交响情人梦 Nodame Cantabile S01E02` ✓ | 首次通过 |

### 第3组

| 文件夹 | 类型 | 刮削 | 标准名 | 状态 |
|--------|------|------|--------|------|
| 地球队长 | tv ✓ | ✓ | `地球队长 Captain Earth S01E01` ✓ | 首次通过 |
| 守望尘世S1 | tv ✓ | ✓ | `守望尘世 The Leftovers S01E01` ✓ | 首次通过 |
| 茗记：2nd Life (2007) | tv ✗ | ✓ | 全部变成文件夹级名字 ✗ | 待修（应为 series_collection） |

### 待修问题

1. **茗记类型错误**：应该是 series_collection 不是 tv。4个视频是不同作品（茗记1、茗记2两个版本、DIY生肉版），不应该按剧集命名
2. **毒枭文件夹混入黑镜**：原始数据问题，毒枭第一季文件夹里有黑镜的文件，被整理到了"毒枭 第2季"子目录
