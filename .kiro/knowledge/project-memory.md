# 项目记忆

> 只记录跨模块的业务知识和核心红线。特定领域细节见对应 knowledge 文件。
> 更新原则：直接覆写旧内容，不保留矛盾的历史版本。

## 跨域业务知识

### 搜索匹配过滤排序（通用能力层）
- 4 个基础模块：text_processing.py（L1）、match_scoring.py（L2）、data_filtering.py（L3）、result_sorting.py（L4）
- L1 文本处理：normalize（繁简+全角+标点+小写）、detectLanguage、splitByLanguage（数字/字母紧邻CJK归入中文）、isShortName、extractVariants、cleanKeyword（含 blacklist）、tokenize
- L2 匹配评分：match_chain（快速筛选，0-100 分）、multi_dimension_score（精细排名，多维度+交叉验证+缺失惩罚）
- L3 数据过滤：include_exclude_filter、threshold_filter（磁力链接豁免）、soft_filter（只标记不排除）、deduplicate、filter_pipeline（完整流水线+统计+filtered_reason）
- L4 结果排序：multi_level_sort（默认：magnet_only→season_pack→match_score→quality_score→seeders→size）、weighted_sort
- L2 只算匹配分，质量分（quality_score）是业务逻辑，L4 负责合并
- 短名字保护：中文≤2字符、英文≤5字符只允许精确匹配
- 动态 fuzzy 阈值：长度≤4 禁用，5-10 用 0.7，>10 用 0.8
- 技能文档：`.kiro/skills/L1-text-processing.md` ~ `L4-result-sorting.md`
- **架构决策**：L1-L4 是通用能力 skill（已完成），业务编排（BT搜索匹配、刮削候选、过滤排序的具体参数和流程）不做独立 skill，而是在接入业务代码时边做边总结到对应的 knowledge 文件中

### 名称可信度机制
- **清洗名系统**（`clean_name_system.py`）：统一入口，所有清洗逻辑集中在此
  - `CleanNameResult` 结构化输出：cn（中文）/ en（英文）/ original（日/韩/法等原始语言）/ display（展示名）/ suffix（季集号）
  - 三层清洗：strip_noise（去噪）→ split_names（语言分离）→ compose_display（组装展示名）
  - strip_noise 去噪规则：方括号/广告/URL/质量标签/字幕组 + 季范围尾缀（1-8季/S1-S3）+ 尾部独立季号（S1/16季/S）+ 紧跟中文的TV版
  - split_by_language 季集号保护：S/E+数字（如 s5、S01E03）作为整体 token 归入 en，不被拆分
  - 三个业务入口：`clean_from_filename`（文件名解析）/ `clean_from_scrape`（刮削结果）/ `clean_for_folder`（文件夹）
  - 搜索词构造：`clean_for_season_search` / `clean_for_episode_search`（对接多语言搜索）
- **字段命名**：cn / en / original 三字段。original 放所有非中非英的原始语言名，不单独设 jp 字段
- **全链路接入**：
  - 树构建（get_library_tree）：finalize 从文件名+shadow_name+NFO 生成，post_process 继承父级并尊重高优先级
  - post_process 覆盖 tv/season/movie 三种类型（电影文件夹下的视频也参与清洗名补全）
  - 刮削后（_update_clean_names_after_scrape）：从刮削结果写入结构化字段
  - 发现页（douban_hot/recommend/explore）：统一注入 clean_name_cn/en/original
  - 前端搜索词：FolderDetail/VideoDetail/DiscoverPage 直接用结构化字段传给 SearchModal
- 持久化字段：`clean_name`（display，向后兼容）+ `clean_name_cn` / `clean_name_en` / `clean_name_original`（结构化）
- 自愈机制：树构建时自动补全缺失的结构化字段（反向解析 → 视频冒泡 → NFO 兜底 → 子树冒泡），补全后持久化到 media_library.json
- 垃圾英文名检测：季号碎片/纯数字/常见非作品名自动清空，让视频冒泡覆盖正确值
- split_names: 从 en 中去除尾部季集号（S01E01/S01/E03），季集号不是英文名的一部分
- shadow_name 冒泡: TV/season 文件夹从子视频冒泡影子名时去掉尾部季集号，避免 TV 文件夹影子名带 S01E01
- 垃圾英文名检测同时作用于：文件夹级 finalize、自愈层2 冒泡、clean_from_filename 纯数字过滤
- 名称污染防护：finalize 冒泡仅限 tv/season，一级分类目录不冒泡不传播
- 统一优先级表 `NAME_SOURCE_PRIORITY`：manual(4) > nfo(3) > tmdb(3) > douban/bangumi(2) > scrape(2) > parsed(1) > ""(0)
- `safe_update_clean_name()`：多字段版本的优先级保护写入
- 前端 SearchModal props：cnName / enName / originalName（原 jpName 已改名）
- 技能文档：`.kiro/skills/clean-name-system.md`
- 设计文档：`docs/name-trust-design.md`

### 搜索架构（BT/磁力 + 网盘 双 Tab）
- BT/磁力：Prowlarr（主力）+ 12 个直搜源（Bitsearch/磁力熊/XL720/Nyaa/蜜柑/YTS/LimeTorrents/ACG.RIP/Bangumi Moe/EZTV/动漫花园/1337x）
- SSE 全源并行搜索（/api/search/stream），as_completed 逐个推送，前端增量追加，max_workers=14
- 去重：同源内 infohash 去重，跨源不去重
- 磁力链接源（磁力熊/XL720）seeders=0 且 size=0，不受做种数筛选影响
- 无做种数信息源（ACG.RIP/Bangumi Moe）seeders=0 但 size>0，不标记为死种
- 直搜源统一输出 SearchResult 格式，routes/search.py 的 SSE 端点合并
- 网盘：6 个源（pansearch/pansou/gogopanso/github/rrdynb/ddys），pan_search_service.py 聚合
- 前端三层分离：results(全量) → displayResults(智能过滤+排序) → filtered(筛选器+源下拉)
- 前端排序三档分层：有做种/无做种数信息源(tier 0) > 死种(tier 1) > 磁力链接(tier 2)，同层内 quality_score > match_score > seeders > size
- 无做种数信息源集合 NO_SEEDER_INFO：cilixiong/xl720/acgrip/bangumi_moe/dmhy，新增直搜源时在此注册
- 智能过滤（🛡️按钮）：后端 compute_junk_flags 五规则标记 is_junk（枪版+低匹配+死种+跨语言不匹配+标题占比过低），前端过滤
- 智能过滤依赖链：L1（标题清洗+中英分离+tokenize）→ L2（match_chain 评分）→ 业务层（compute_junk_flags 五规则判定）→ L3 模式（软标记+前端开关）
- enrich_result 接受 match_names 参数（cn_name/en_name/original_name），解决跨语言匹配；SSE 搜索和单源搜索端点都必须传 match_names，否则智能过滤对不相关结果失效
- 业务 skill：`skills/smart-filter.md`（五规则详细说明+源特征差异+占比计算逻辑）
- SourceTabs + FilterBar 合并：源 Tab 切换 + 筛选器在同一区域，"全部"tab 用直搜源下拉，单源 tab 用专属筛选器
- 网盘侧同样有 SourceTabs + 筛选器，绿色变体
- BT 结果卡片索引器标签：Prowlarr 两段式（橙色p+灰色名），直搜源保留各自品牌色
- 搜索设置在 SearchModal ⚙️ 二级菜单（搜索源/过滤规则/索引器/排序权重），不在总设置页
- 需代理的源（Bitsearch/Nyaa/蜜柑/YTS/LimeTorrents/EZTV/动漫花园）从 BT_SOURCE_DEFAULTS.needs_proxy 读取默认值，用户可在 config.bt_search_sources 中按源覆盖
- 直连源（磁力熊/XL720/ACG.RIP/Bangumi Moe/rrdynb）默认不走代理
- 代理配置格式：bt_search_sources 支持旧格式 `{"bitsearch": true}` 和新格式 `{"bitsearch": {"enabled": true, "proxy": false}}`
- 代理配置在爬虫首次创建时固定（单例），改配置后需重启后端生效
- XL720 响应极慢（超时 12s + 1 次重试），搜索质量差需中文子串过滤
- 搜索词传递：用户手动输入时不传 cn_name/en_name（让后端用 query 分词），点击标签时才传辅助参数

### 搜索词构造（多语言搜索词系统）
- 搜索词映射器：`search_keyword_mapper.py`，为每个搜索源选择最佳语言搜索词 + 回退链
- 三语言字段：cn（中文）/ en（英文）/ original（日/韩/法等原始语言名），来自 clean_name_system
- 源→语言优先级：Prowlarr/Bitsearch/YTS 用 en，磁力熊/XL720 用 cn，Nyaa 用 original，蜜柑/ACG.RIP/萌番组 用 cn
- 回退链：每个源 0 结果时自动换词（最多 3 轮），在 SSE future 内部同步完成，首个有结果的词即为最终结果
- 季号拼接：中文源"第N季"，英文源"S0N"，格式跟源走不跟词的语言走
- SSE source_done 事件返回 search_keywords（搜过的词列表）+ hit_keyword（命中的词）
- 单源搜索端点：`/api/search/source`，JSON 响应，支持 fallback_keywords
- 前端源 Tab 切换：SourceTabs 组件，每个 Tab 独立 keyword/results 状态
- 前端单源 Tab 切换优先从 SSE 全量结果中过滤该源结果（`_source` 字段），避免重复请求；SSE 中无结果时才触发单源搜索端点
- 前端搜索词标签点击根据当前 Tab 触发对应搜索（全部 Tab → SSE 全源，单源 Tab → 单源搜索），并同步更新 input 框
- SSE 竞态保护：activeEsRef 跟踪当前 EventSource，新搜索关闭旧连接
- 英文名获取：TMDB 用 `_get_english_title(language=en-US)` 主动获取；豆瓣从 subtitle 中用 detect_language 提取；Bangumi 无英文名
- 关键红线：original_title 不能直接当英文名（中国电影是中文、日本动画是日文），必须做语言判断
- `_try_tmdb_detail` 返回字典必须包含 `english_title`（来自 ScrapeResult），不能只取 `original_title`
- 详情 API 统一字段名 `english_title`（不是 `en_title`），前端 `MediaDetail` 接口已正式定义
- 旧数据兼容：前端无 clean_name_cn/en 时从 clean_name 字符串正则拆分中英文
- 技能文档：`skills/multilang-search-dispatch.md`、`skills/multilang-name-enrichment.md`
- **已实施**：发现页 TMDB 数据补全（C+E 方案：持久化缓存 + 同步并发补全 + 2 秒超时降级），设计文档 `docs/discover-enrich-design.md`
- 保存路径：优先 searchContext.savePath > currentFolder > NAS 根路径
- tmdb_enrich_cache：`scrape_cache/tmdb_enrich_cache.json`，持久化 TMDB 英文名+评分，30 天过期，5000 条 LRU 上限
- enrich_cache 写入时机：同步并发补全后 + _async_enrich_tmdb_ids 后 + 详情页 get_media_info 返回前
- enrich_cache 同时注入英文名和 TMDB 评分（`tmdb_rating` 字段），卡片列表可直接展示双评分
- enrich_cache 读取时机：_inject_clean_names 中查缓存，命中直接用英文名
- 业务 skill：`skills/discover-enrich-cache.md`
- discoverUtils.ts 的 normalizeItem 是所有推荐/探索/搜索数据的统一入口，新增字段必须在此传递
- 前端详情缓存 key 按数据源（douban/tmdb/bangumi）共享，不按 tab 区分。同一部作品在综合推荐和热门电影 tab 共享缓存

### 下载管理
- qB：直接传 save_path，旧沙盒任务完成后自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 归位替换：file_relocator.py（relocate → confirm_replace / archive_both / cancel_replace）
- 回收站默认跟随旧文件所属媒体库根落在“同卷同级隐藏目录”（如 `<媒体库根上级>/.recycle_bins/<媒体库名>`），backend 只集中保存 `recycle_bin.json` 元数据；只有显式配置 `recycle_bin_path` 时才使用固定目录
- 整理替换附属文件规则（详见 knowledge/download-replace-pipeline.md）：
  - 字幕文件：扁平化到 Season 目录，通过集号匹配用视频标准名重命名
  - 非字幕文件（字体包/SPs/CDs/OAD）：提升到剧集根目录，不进入 Season
  - 空种子目录壳自动清理
- 季目录检测：save_path 本身是季目录时（如"第三季"），不再嵌套 Season XX
- 电影整理替换：_scrape_movie 支持 dry_run + plan 生成，执行时写 movie.nfo（不是 tvshow.nfo）
- 无冲突但有整理计划时（如纯新下载），也返回 awaiting_confirm + plan 供前端展示
- 分类覆盖：推演阶段 category_hint（movie/tv）优先于 classify_folder 结果，避免种子子目录干扰分类
- 电影分类修复：`_classify_movie_category` 有散落视频时以视频数量为准，忽略子目录（种子文件夹不影响分类）

### 整理流水线
- 三段式架构，详见 knowledge/organize-pipeline-v3.md
- 分类体系：movie/tv/collection/series/season/mixed（一级标签只有 movie/tv）

### 季集完整性检测
- 核心模块：`completeness.py`，从 TMDB 获取完整季/集结构，与本地文件做差集
- 本地集号提取：NFO 优先（目录名季号覆盖 NFO 季号）→ 文件名正则回退
- 正则防误匹配：E/EP 限 3 位数字排除 CRC32 校验码；中文字符后数字（`铳墓02`）
- 绝对集数重映射：全集平铺场景自动检测并用 `build_absolute_episode_map` 重映射
- 持久化缓存：`completeness_cache.json`，API 默认读缓存，刷新按钮清除 TMDB 缓存
- 自动刷新：挂钩 `save_library` 回调（`shared.py`），3 秒防抖，后台线程刷新受影响文件夹
- 前端：`CompletenessBar.tsx`，tv/season 类型自动显示；season 节点用 `seasonFilter` 只显示单季
- 技能文档：`skills/completeness-detection.md`
- 文件夹类型手动覆盖：`backend/folder_types.json`
- 一级分类标签：`config.json` 的 `category_tags`

### 质量评分体系（跨搜索/订阅/整理的全局基准）
- 100 分制（分辨率45+来源20+音频20+编码10+字幕5）
- 搜索/订阅/整理模块统一调用 compare_quality_score()，阈值5分
- quality_score >= 35 判定有质量，回退 height >= 720
- config_manager.save_library() 自动注入 quality_score 字段

### 本地媒体感知（跨推荐/探索/搜索的全局机制）
- local_media_matcher.py：三层匹配（tmdb_id → title+year → title）+ 内存索引
- 推荐/探索/搜索三个接口统一注入 local_status + local_folder
- 中文匹配用前缀（startswith），避免"你的名字"误匹配"以你的名字呼唤我"

### AI 集成（一期）
- 统一客户端 `ai_client.py`：AIClient 无状态、每次从 config 构造、chat/chat_json/schema 校验/调用计量
- Prompt 集中管理 `ai_prompts.py`：每个场景独立函数，返回 messages 列表
- 业务编排 `ai_organizer.py`：ai_extract_episode（单/批量）、ai_select_scrape_candidate、ai_library_diagnosis
- 全局总开关 `ai_enabled` + 场景级开关 `ai_features`，关闭时所有 AI 场景静默降级
- 服务商：火山引擎豆包（base_url=ark.cn-beijing.volces.com/api/v3，model 填推理接入点 ID）/ DeepSeek / 任意 OpenAI 兼容
- AI 参与的结果标记 `ai_parsed: true` / `ai_selected: true`，前端显示 🤖 标签
- 性能基准（豆包 lite）：文件名解析 8-11s/400-580 tokens，候选匹配 5-13s/460-800 tokens，诊断 31-36s/2000-2100 tokens
- 设计文档：`docs/ai-integration-design.md`，测试报告：`docs/ai-integration-test-report.md`

## 核心红线

- shadow_name 可能含中文，enName 构造时必须去掉中文字符
- 搜索用 clean_name + 去中文的 shadow_name 拼接，不要直接搜片名
- 豆瓣 API v2 请求间随机延迟 1-3 秒 + 随机 UA，防封
- pansearch.me 连续搜索会被限频，需要间隔
- 网盘转存必须同时提取 share_url + 提取码
- ffprobe 必须设 timeout=15，长队列加 try-except 兜底
- 后台数据和角色快照是独立路径，改一个不要影响另一个
- Bangumi calendar API 的 bgm_id 和卡片标题偶尔错位，需要标题校验
- 发现页 ExpandDetail 的 img 加 key 强制重挂载，解决切换卡片封面残留
- media_library.json 中 shadow_tmdb_id 覆盖率极低，片名匹配是主力
- gogopanso 标题有拼音首字母前缀需清洗（如 "L流浪地球2" → "流浪地球2"）
- normalize_text 会去掉标点和空格，中英混合标题需分别提取中文部分匹配
- 快速同步新增超过 50 个文件时自动切换快速模式（跳过 ffprobe）
- 搜索缓存只缓存有结果的，空结果不缓存
- BT 直搜源统一输出 SearchResult 格式，按 infohash（大写）去重合并到 Prowlarr 结果
- Bitsearch API 有 429 限频，缓存 10 分钟 + 请求间延迟 2-4s
- curl_cffi 是绕 CF 中低级保护的关键，所有有 CF 风险的爬虫必须启用
- rrdynb 多次搜索会触发 CF 限频（临时性，过段时间自动解除），请求间延迟 1.5-3s
- ddys 已升级为 JSON API（POST /api/search-netdisk），link 字段是 base64 编码
- 蜜柑 RSS 同时服务于 BT 搜索（即时）和订阅系统（定时轮询），共用 rss_source_mikan.py
- EZTV 同时有 RSS 源（rss_source_eztv.py）和直搜源（bt_scraper_eztv.py），直搜默认禁用（不支持关键词搜索，只能按 IMDB ID）
- 动漫花园同时有 RSS 源（rss_source_dmhy.py）和直搜源（bt_scraper_dmhy.py），直搜通过 RSS 端点搜索，需代理+chrome124 指纹，无做种数信息
- 1337x（bt_scraper_1337x.py）：综合性公开 BT 站，用镜像站 1337xx.to（主站 CF 严格），需代理+chrome120 指纹，两步请求（列表+详情取磁力），并发获取磁力链接，加标题相关性过滤防止返回不相关热门
- curl_cffi impersonate 兼容性：chrome131 对动漫花园 TLS 报错，chrome124 正常；1337x 主站所有指纹 403，镜像站 chrome120 正常；CF 指纹检测是动态变化的
- ACG.RIP 直连超时（被墙）、走代理所有指纹 TLS 报错，默认禁用
- LimeTorrents 所有域名 TLS 报错，默认禁用
- 新增 BT 直搜源完整 Checklist 见 `skills/L6-scraping-anti-bot.md`（后端 7 文件 + 前端 4 文件 + 验证 6 项），遗漏任何一个注册点都会导致新源在某些场景下不工作
- YTS 主域名 yts.mx SSL 不通，用 yts.am 作主域名、movies-api.accel.li 作备用
- Bangumi Moe API 端点是 /api/v2/torrent/search（不是 /api/torrent/search），size 字段是字符串格式如 "118.6 GB"
- 搜索匹配通用模块：text_processing.py（L1）→ match_scoring.py（L2）→ data_filtering.py（L3）→ result_sorting.py（L4），业务代码调用这些模块而非自己实现匹配逻辑
- 后端日志统一用 `logging` 模块（不用 print），每个文件顶层 `logger = logging.getLogger(__name__)`，shared.py 统一 basicConfig
- pan_models.py 使用 Pydantic V2 语法（`@field_validator` + `@model_validator`），不用已废弃的 `@validator`
- 发现推荐的 enrich 逻辑在 `discover_enrich.py`（业务层），`routes/discover.py` 只放路由端点
- 下载管理已知问题（待修复，详见 `docs/clean-name-fix-todo.md`）：
  - sync_progress 没有后台定时调用，只在前端请求时触发
  - sync_from_qb 会把 qB 中所有种子导入为新任务，用户删除的失败任务重启后会复活
  - 前端"已完成"和"待整理"Tab 从用户角度是重复的

## 领域索引

- 整理流水线 → `knowledge/organize-pipeline-v3.md`
- 网盘搜索 → `knowledge/pan-search-pipeline.md`
- BT 搜索 → `knowledge/bt-search-pipeline.md`
- 下载归位替换 → `knowledge/download-replace-pipeline.md`
- 清洗名系统 → `skills/clean-name-system.md`
- 清洗名修复 TODO → `docs/clean-name-fix-todo.md`（含下载管理 3 个 bug）
- 发现推荐 → `knowledge/discover-recommend.md`
- 订阅系统 → `knowledge/subscribe-system.md`
- 订阅系统重设计 → `docs/_archived/subscribe-redesign.md`（已完成归档）
- 订阅数据流 → `skills/subscribe-data-flow.md`
- 订阅调度器 → `skills/subscribe-scheduler.md`
- RSS 匹配器 → `skills/subscribe-rss-matcher.md`
- 滚动交互 → `knowledge/scroll-damping-interaction.md`
- API 清单 → `knowledge/api-reference.md`
- 数据结构 → `knowledge/data-models.md`
- BT 搜索扩展 TODO → `docs/bt-expand-todo.md`
- 搜索匹配过滤调研 → `docs/search-match-filter-research.md`
- 搜索匹配技能建设 TODO → `docs/skill-build-todo.md`
- 多源聚合搜索 → `skills/L5-multi-source-search.md`
- 爬虫与反爬 → `skills/L6-scraping-anti-bot.md`
- 通用技能 L1-L4 → `skills/L1-text-processing.md` ~ `skills/L4-result-sorting.md`
- 智能过滤业务技能 → `skills/smart-filter.md`
- 多语言搜索词分发 → `skills/multilang-search-dispatch.md`
- 多源英文名补全 → `skills/multilang-name-enrichment.md`
- 发现页英文名缓存 → `skills/discover-enrich-cache.md`
- 季集完整性检测 → `skills/completeness-detection.md`
- AI 集成设计 → `docs/ai-integration-design.md`
- AI 集成测试报告 → `docs/_one-off/ai-integration-test-report.md`
- AI 客户端基础设施 → `skills/ai-client-infra.md`
- AI 业务场景编排 → `skills/ai-business-scenes.md`
- 多语言搜索词 TODO → `docs/multilang-search-todo.md`
- 发现页 TMDB 补全设计 → `docs/discover-enrich-design.md`（已实施）

## 测试沙盒

- `backend/sandbox_real/`：从真实 NAS 媒体库复制的目录结构（空文件），覆盖各种极端命名场景，用于文件整理、匹配、刮削、搜索等功能的集成测试
