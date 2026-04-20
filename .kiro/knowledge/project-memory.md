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
  - `CleanNameResult` 结构化输出：cn（中文）/ en（英文）/ original（日文/韩文）/ display（展示名）/ suffix（季集号）
  - 三层清洗：strip_noise（去噪）→ split_names（语言分离）→ compose_display（组装展示名）
  - 三个业务入口：`clean_from_filename`（文件名解析）/ `clean_from_scrape`（刮削结果）/ `clean_for_folder`（文件夹）
  - 搜索词构造：`clean_for_season_search` / `clean_for_episode_search`（对接多语言搜索）
- 持久化字段：`clean_name`（display，向后兼容）+ `clean_name_cn` / `clean_name_en` / `clean_name_original`（结构化）
- 统一优先级表 `NAME_SOURCE_PRIORITY`：manual(4) > nfo(3) > tmdb(3) > douban/bangumi(2) > scrape(2) > parsed(1) > ""(0)
- `safe_update_clean_name()`：多字段版本的优先级保护写入
- 旧的 `_clean_filename_for_folder` / `clean_episode_name` / `clean_season_name`（analyzer.py）待逐步替换为新系统
- 技能文档：`.kiro/skills/clean-name-system.md`
- 设计文档：`docs/name-trust-design.md`

### 搜索架构（BT/磁力 + 网盘 双 Tab）
- BT/磁力：Prowlarr（主力）+ 9 个直搜源（Bitsearch/磁力熊/XL720/Nyaa/蜜柑/YTS/LimeTorrents/ACG.RIP/Bangumi Moe）
- SSE 全源并行搜索（/api/search/stream），as_completed 逐个推送，前端增量追加，max_workers=11
- 去重：同源内 infohash 去重，跨源不去重
- 磁力链接源（磁力熊/XL720）seeders=0 且 size=0，不受做种数筛选影响
- 无做种数信息源（ACG.RIP/Bangumi Moe）seeders=0 但 size>0，不标记为死种
- 直搜源统一输出 SearchResult 格式，routes/search.py 的 SSE 端点合并
- 网盘：6 个源（pansearch/pansou/gogopanso/github/rrdynb/ddys），pan_search_service.py 聚合
- 前端三层分离：results(全量) → displayResults(智能过滤+排序) → filtered(筛选器+源开关)
- 搜索设置在 SearchModal ⚙️ 二级菜单（搜索源/过滤规则/索引器/排序权重），不在总设置页
- 需代理的源（Bitsearch/Nyaa/蜜柑/YTS/LimeTorrents）从 config.http_proxy 读取，和 TMDB 共用
- 直连源（磁力熊/XL720/ACG.RIP/Bangumi Moe/rrdynb）不走代理
- XL720 响应极慢（超时 12s + 1 次重试），搜索质量差需中文子串过滤
- 搜索词传递：用户手动输入时不传 cn_name/en_name（让后端用 query 分词），点击标签时才传辅助参数

### 搜索词构造
- cnName：从 clean_name 提取中文字符，cnParts 用 Set 去重
- enName：shadow_name 去年份再去中文字符 > clean_name 中英文部分
- 搜索框默认词：cnName + enName（cn/en 实质相同时只用 cn）
- 保存路径：优先 searchContext.savePath > currentFolder > NAS 根路径
- discoverUtils.ts 的 normalizeItem 是所有推荐/探索/搜索数据的统一入口，新增字段必须在此传递

### 下载管理
- qB：直接传 save_path，旧沙盒任务完成后自动转移
- Alist 双阶段：cloud_download → local_sync → completed
- 归位替换：file_relocator.py（relocate → confirm_replace / archive_both / cancel_replace）

### 整理流水线
- 三段式架构，详见 knowledge/organize-pipeline-v3.md
- 分类体系：movie/tv/collection/series/season/mixed（一级标签只有 movie/tv）
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
- 新增 BT 直搜源步骤：写爬虫(继承 ScraperBase) → shared.py 加 getter → routes/search.py 的 scrapers 列表加一行 → _BT_SOURCE_DEFAULTS 加配置
- YTS 主域名 yts.mx SSL 不通，用 yts.am 作主域名、movies-api.accel.li 作备用
- LimeTorrents 所有域名 CF 保护严格，默认禁用（enabled=False）
- Bangumi Moe API 端点是 /api/v2/torrent/search（不是 /api/torrent/search），size 字段是字符串格式如 "118.6 GB"
- 搜索匹配通用模块：text_processing.py（L1）→ match_scoring.py（L2）→ data_filtering.py（L3）→ result_sorting.py（L4），业务代码调用这些模块而非自己实现匹配逻辑

## 领域索引

- 整理流水线 → `knowledge/organize-pipeline-v3.md`
- 网盘搜索 → `knowledge/pan-search-pipeline.md`
- BT 搜索 → `knowledge/bt-search-pipeline.md`
- 下载归位替换 → `knowledge/download-replace-pipeline.md`
- 清洗名系统 → `skills/clean-name-system.md`
- 发现推荐 → `knowledge/discover-recommend.md`
- 订阅系统 → `knowledge/subscribe-system.md`
- 滚动交互 → `knowledge/scroll-damping-interaction.md`
- API 清单 → `knowledge/api-reference.md`
- 数据结构 → `knowledge/data-models.md`
- BT 搜索扩展 TODO → `docs/bt-expand-todo.md`
- 搜索匹配过滤调研 → `docs/search-match-filter-research.md`
- 搜索匹配技能建设 TODO → `docs/skill-build-todo.md`
- 通用技能 L1-L4 → `skills/L1-text-processing.md` ~ `skills/L4-result-sorting.md`

## 测试沙盒

- `backend/sandbox_real/`：从真实 NAS 媒体库复制的目录结构（空文件），覆盖各种极端命名场景，用于文件整理、匹配、刮削、搜索等功能的集成测试
