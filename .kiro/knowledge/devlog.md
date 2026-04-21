# 开发日志

> 里程碑归档，记录每个阶段做了什么、为什么这么做、踩了什么坑。只追加，不删除。
> AI 加载项目时读此文件了解版本递进脉络。

---

## 2026-04-21 搜索资源弹窗 UI 重构 + 排序/过滤修复

**变更**:
- SourceTabs + FilterBar 合并：源 Tab 切换保留，源开关栏改为"直搜源"MultiSelect 下拉（放筛选器最前面）
- 每个单源 Tab 有专属筛选器：Prowlarr 有索引器下拉，磁力熊/xl720 无做种数筛选，acgrip/bangumi_moe 无做种数筛选
- 网盘侧同步改造：加 SourceTabs + 源下拉筛选器，网盘筛选器用绿色（emerald）变体
- SourceTabs 显示 loading/结果条数状态（绿色 ✓+条数 / 蓝色脉冲 / 红色 ✗），去掉搜索词回显
- 搜索词回显改到 input 框内：灰色标签 + 箭头连接回退链，"回退匹配:" 前缀，命中词蓝色排最后
- 排序修复：三档分层（有做种/无做种数信息源 > 死种 > 磁力链接），quality_score 优先于 match_score
- 新增 NO_SEEDER_INFO 集合（cilixiong/xl720/acgrip/bangumi_moe），新增直搜源时在此注册防止排序降权
- 智能过滤修复：后端 compute_junk_flags 移除 acgrip/bangumi_moe 的死种豁免，开启过滤后 0 做种结果被过滤
- 后端 SSE 搜索源启用判断改用 _BT_SOURCE_DEFAULTS 默认值，修复 limetorrents 被错误启用的 bug
- 单源 Tab 搜索 loading 只显示该源名称，不显示全量搜索的各源状态
- BT 结果卡片索引器标签区分：Prowlarr 索引器用两段式（橙色 p + 灰色索引器名），直搜源保留各自品牌色
- 筛选器 UI 统一：MultiSelect/NumberInput/大小输入框高度对齐（py-1.5 text-[11px]），SourceTabs 同高
- SourceTabs + 筛选器区域加分割线与上方搜索区域分开
- 手动改词二次搜索清除单源 Tab 缓存 + sourceKeywordInfo，统一用搜索框的词搜所有源
- 新搜索开始时清除 sourceKeywordInfo，防止上次搜索词残留
- 测试修复：test_smart_filter.py / test_smart_filter_extra.py 导入路径从 routes.search 改为 search_helpers，84 测试全绿
- MultiSelect 组件支持 variant（blue/emerald），网盘筛选器用绿色

**踩坑**:
- 后端 SSE 搜索用 `bt_overrides.get(name, True)` 默认启用所有源，limetorrents（默认 disabled）被错误搜索
- 前端排序只区分"磁力链接"和"其他"，acgrip/bangumi_moe 的 seeders=0 但 size>0 的结果被当作死种排到后面
- sourceKeywordInfo 在新搜索开始时没有清除，导致上次搜索的词残留在回显中
- 搜索词回显收集所有源的搜索词去重，不同源回退链顺序不同导致显示顺序混乱，改为未命中排前+命中排后

**架构决策**:
- FilterBar 统一导出：根据 activeSource 自动选择 AllFilterBar 或 SourceFilterBar，调用方只传 activeSource
- 直搜源下拉交互：选中=显示（默认全选），取消=关闭，比原来的源开关栏更紧凑
- 新增直搜源的防护机制：NO_SEEDER_INFO 集合 + _BT_SOURCE_DEFAULTS 默认值，两处注册即可

---

## 2026-04-21 发现页 TMDB 英文名补全（C+E 方案）
**变更**:
- 新建 `tmdb_enrich_cache.json` 持久化缓存（启动加载、LRU 5000 条、30 天过期、threading.Lock 保护）
- `_inject_clean_names` 改为先查缓存 → 未命中同步并发请求 TMDB（max_workers=5，2 秒超时）→ 超时转交后台
- `_async_enrich_tmdb_ids` 补全结果写入 enrich_cache
- `get_media_info` 返回前回写 enrich_cache（详情页数据自动积累）
- 前端 `DoubanHotItem` 加 `clean_name_cn/en/original`，`normalizeItem` 传递这三个字段
- SearchModal 的 `enName` 回退链加入 `searchModalItem.clean_name_en`
- 修复 `_try_tmdb_detail` 丢弃 `english_title` 的关键 bug（ScrapeResult 有但返回字典没取）
- 修复 `_enrich_ratings` 用 `original_title` 当英文名的错误（日文名被误用），统一字段名为 `english_title`
- 修复 `_writeback_enrich_cache` 用 `original_title` 回写的错误，改为优先取 `english_title`
- 前端 `MediaDetail` 接口正式加 `english_title` 字段，去掉 `(d as any).en_title` hack
- 详情页三语名始终展示（有值显示、无值显示占位符"原始名 —"/"英文名 —"）
- 6 项集成测试全绿（持久化、缓存命中、同步补全、超时降级、回写、LRU 淘汰）

**踩坑**:
- `_try_tmdb_detail` 构造返回字典时只取了 `original_title`，丢弃了 `english_title`，导致整条链路断裂
- `_enrich_ratings` 中 `result.get("original_title")` 对日本动画拿到的是日文名，不是英文名
- 前端 `en_title` 字段从未正式定义在 `MediaDetail` 接口中，一直用 `(d as any)` 绕过
- `_writeback_enrich_cache` 用 `detail.get("original_title")` 当英文名，日文名被 `detect_language` 过滤后 enrich_cache 里也没有英文名

**架构决策**:
- 选 C+E 而非定时预补全（方案 A）：个人 NAS 工具不需要定时任务复杂度
- 2 秒硬性超时：TMDB 走代理，国内网络波动时自动降级为渐进式补全
- 缓存 key 复合设计：douban_id > tmdb_id > title_year，支持多数据源
- 统一字段名 `english_title`（后端 ScrapeResult + API 返回 + 前端 MediaDetail），不再用 `en_title`

---

## 2026-04-21 清洗名系统重构 + 全链路接入 + 性能优化
**变更**:
- 修复 TV/season 文件夹 clean_name 显示"未设置"的 bug（ShadowNameSection 缺少 folderCleanName prop）
- 新建 `clean_name_system.py`：统一清洗名入口，三层架构（strip_noise→split_names→compose_display）
- 结构化输出 `CleanNameResult`：cn/en/original/display/suffix/year/source/confidence
- 全链路接入：get_library_tree（finalize+post_process）、_update_clean_names_after_scrape、发现页（douban_hot/recommend/explore）
- 前端 FolderDetail/VideoDetail 搜索词直接用 clean_name_cn/en，不再从字符串拆分
- 字段命名统一：jpName → originalName（支持日/韩/法等所有小语种）
- NFO 补全：树构建时从 NFO 读取 en/original，加 exists 预检优化（1854ms→1146ms）
- en 覆盖率 90%，original 108 个（日漫基本全覆盖）
- 49 个单元测试 + 20 个真实用例 + 3 项集成测试全绿
- 新增 skill 文档 `.kiro/skills/clean-name-system.md`

**踩坑**:
- SP 在 Spirited Away 中误匹配为特别篇 → 用词边界保护
- 广告站名粘连 URL → 先把 `.` 转空格再去广告
- NFO 补全对所有文件夹读取导致 SMB IO 过重 → 加 exists 预检跳过无 NFO 的文件夹
- 繁体单字（如"劇"）触发 original 误判 → 已知限制，记录在 skill 文档中

**架构决策**:
- clean_name 不是字符串而是结构（cn/en/original），下游搜索词按源语言映射表直接选字段
- original 统一放所有非中非英的原始语言名（日/韩/法等），不单独设 jp 字段
- 文件夹 clean_name 不持久化，每次树构建动态计算（依赖子节点数据，动态保证一致性）
- post_process 尊重已有的高优先级 clean_name（manual/nfo/tmdb 不被覆盖）

---

## 2026-04-20 智能过滤业务技能 + match_chain 增强
**变更**:
- 智能过滤（smartFilter）从空转升级为三维度判定：枪版检测（TS/CAM/HDTC 等词边界匹配）、匹配度过低（match_score > 0 且 < 30）、死种检测（seeders=0 且非磁力链接源）
- 新增 `_extract_bt_title_for_match`：专为搜索匹配设计的 BT 标题清洗（比 parse_filename 更激进，在第一个技术标签处截断）
- match_chain 增强：新增 contains 子串匹配步骤（70 分，normalize 后子串包含 + 40% 长度比例约束）；修正 token_set 比例方向（候选 tokens 70%+ 出现在目标中，而非反向）
- 新增 `junk_reasons[]` 字段，记录每条结果被标记的具体原因
- 新增业务 skill 文档 `.kiro/skills/smart-filter.md`
- 84 个测试全绿（45 基础 + 39 扩展，覆盖 6 种源格式 × 3 条规则 × 边界情况）
**决策**: match_score=0 不触发低匹配标记（可能是跨语言无法计算而非不相关）；磁力链接源用 seeders=0 && size_gb=0 组合特征判断而非 _source 字段
**已知问题**: MPEG-TS 被误标记为枪版（中低优先级）；单词搜索 vs 长标题 score=0（contains 40% 比例约束 + token_set 单 token 限制）；"西部世界" vs "西部风云" 漏过（中文 2 字公共前缀触发 token_set 60 分）；跨语言完全无法匹配（需别名系统）

## 2026-04-20 搜索 bug 修复 + 4 个新直搜源
**变更**:
- Bug 修复：搜索框手动输入的搜索词不生效 — doSearch 的 useCallback 依赖数组为空 + 后端优先用 cn_name/en_name 覆盖 query。新增 userEditedRef 跟踪用户编辑，手动输入时不传辅助参数
- Bug 修复：Prowlarr SSE 流中 future.result(timeout=20) 太短，Prowlarr 搜索本身 60s 超时，改为 65s
- Prowlarr 搜索加详细日志（搜索词、耗时、结果数）
- 新增 4 个 BT 直搜源：YTS（电影，JSON API，需代理）、LimeTorrents（综合，HTML 爬虫，需代理但站点不可用默认禁用）、ACG.RIP（动画字幕组，HTML 爬虫，直连）、Bangumi Moe（动画字幕组，JSON API，直连）
- 智能过滤 _compute_junk_flags 增加无做种数信息源豁免（acgrip/bangumi_moe 不标记 dead_seed）
- SSE 线程池 max_workers 从 6 增加到 11
- 前端 FilterBar 新增 4 个源的品牌色标签
**决策**: YTS 用 yts.am 替代 yts.mx（SSL 不通），加 movies-api.accel.li 备用；LimeTorrents 所有域名 CF 保护严格默认禁用；52BT 搜不到公开站点信息暂不接入
**踩坑**: yts.mx SSL 证书/TLS 配置有问题即使走代理也连不上；Bangumi Moe API v1 返回 500，v2 才正确；Bangumi Moe size 字段是字符串不是字节数；ACG.RIP 没有磁力链接只有 .torrent 下载链接且无做种数信息

## 2026-04-19 L1-L4 全场景切换 + 名称流转链路治理（阶段 2 完成）
**变更**:
- L1 splitByLanguage bug 修复：数字/字母紧邻 CJK 时归入中文
- 名称可信度机制：clean_name_source + NAME_SOURCE_PRIORITY + safe_set_clean_name + auto_fill 分层保护
- 只读审计 media_library.json（3302 条）：零覆盖风险
- 正式拦截：_update_clean_names_after_scrape / 扫描 / 手动修改 三个写入点接入保护
- BT 搜索接入：_enrich_result 新增 match_score（L2）+ is_junk（L3），前端排序改用 match_score
- 全场景切换到 L1-L4：SecondaryMatcher → L1+L2、local_media_matcher → L1、searcher._composite_score → L2、tmdb_client/scraper/enhanced_scorer/combined_recommend/batch_recommend → L1 normalize
- 前端 splitByLanguage 工具函数（和后端 L1 一致），FolderDetail/VideoDetail cnName 提取切换
- 22 个集成测试全绿（沙盒 3215 文件 smoke test + SecondaryMatcher + LocalMediaMatcher + 过滤排序端到端）
- sub-agent 审查：切换完整性 100%，参数正确性 100%，逻辑一致性 100%
**决策**: 方案 B 分别追踪 clean_name_source/shadow_name_source；source 细分到 nfo/tmdb/douban/bangumi 粒度；L1-L4 是通用能力 skill，业务编排不做独立 skill；2.1.3 多语言搜索词暂缓
**踩坑**: match_chain 签名是 3 个列表参数不是 2 个字符串；_enrich_result 需要先 parse_filename 提取 clean_name 再匹配（直接传 BT 完整标题会因噪声导致匹配失败）；BT 标题含集号时 clean_name 包含集号导致 fuzzy 匹配度下降

## 2026-04-17 搜索匹配过滤排序 — 通用技能建设（阶段 1 完成）
**变更**:
- 调研文档：从 MoviePilot、xhs-mj-workflow、RapidFuzz 等提炼搜索匹配过滤排序的通用模式
- 4 个通用技能文档：L1 文本处理、L2 匹配评分、L3 数据过滤、L4 结果排序（`.kiro/skills/`）
- 4 个基础模块实现：text_processing.py、match_scoring.py、data_filtering.py、result_sorting.py
- 86 个测试全绿（含 sandbox_real 真实数据集成测试）
- 新增 cleanup-todo.md（遗留清理）、skill-build-todo.md（技能建设 TODO）
- ai-rules 补充测试沙盒路径（`backend/sandbox_real/`）
- project-memory 补充领域索引（技能文档、调研文档、沙盒）
**决策**: 技能分 4 层（L1 文本→L2 评分→L3 过滤→L4 排序），通用能力和业务逻辑分离；匹配度评分只算"有多像"，质量评分是业务逻辑；softFilter 只标记不降分，降分归 L2；名称流转链路用非破坏性三步法治理
**踩坑**: fsWrite 无法写入 `~` 路径（全局 skills 目录），改为放工作区 `.kiro/skills/`；xhs-mj-workflow 被 Kiro 读取时触发 LF→CRLF 行尾符变更，需 git checkout 恢复；normalize 后去空格导致 fuzzy_score 长度差异过大返回 0，token_set 匹配需要短名字保护防止单字符 token 误匹配

**变更**:
- SSE 搜索改为全源并行（Prowlarr + 5 直搜源同时搜索，as_completed 逐个推送，增量追加到前端）
- FilterBar 全面改造：源开关标签（可点击切换）+ MultiSelect 多选筛选器 + Prowlarr 索引器仅开启时显示
- FilterState 从单选 string 改为多选 string[]；网盘 PanFilterBar 同步改造
- 搜索设置从总设置页分离到 SearchModal ⚙️ 二级菜单（4 tab：搜索源/过滤规则/索引器/排序权重）
- 去重逻辑：同源内 infohash 去重，跨源不去重
- 磁力链接源不受做种数筛选影响，显示"磁力"而非"做种 0"
- 排序：匹配准确度 > quality_score > seeders > size_gb
- XL720/磁力熊标题过滤加严（连续中文子串匹配）+ 磁力熊标题从 dn 参数提取
- 全站 select 深色背景；设置页布局调整（分组+分割线+顺序优化）
- 新建 search-matching-todo.md（搜索词构造+匹配算法+过滤策略+排序优化）
**决策**: 源开关和索引器筛选是两个维度；SSE 用 as_completed 而非 queue（queue 阻塞不流式）；XL720 搜索质量差但保留（降低超时 12s + 1 次重试）
**踩坑**: queue.get 阻塞 SSE generator；Pydantic model quality 字段无法 json.dumps 序列化致 SSE 崩溃；XL720 网站响应极慢；弹窗 overflow-hidden 裁剪下拉层；浏览器原生 select option 无法自定义背景色

## 2026-04-15 查漏补缺 — 30 项 Bug 修复 + P2 功能完善
**变更**: 修复 30 个 Bug + 13 项 P2 功能 + 4 个新组件 + 2 个新接口；搜索设置面板、订阅配置弹窗、Nyaa RSS 源等
**决策**: BT 搜索不工作根因是 skip_filter 模式没合并直搜源；综合推荐匹配错误通过加严 _is_same_media 解决
**踩坑**: 订阅 tab 高度反复修 4 轮，根因是多 tab 容器高度不统一

## 2026-04-15 TODO 清理 + 5 项功能补完 + AI 规则升级
**变更**: TODO 状态校验（10 项更正）+ 5 项功能实现（SSE 进度/局部刷新/候选面板/tmdb_id 补全/源统计）+ AI 规则升级（Karpathy 原则）
**决策**: 参考 andrej-karpathy-skills 的 4 原则定制 AI 规则；sub-agent 审查后微调
**踩坑**: test 辅助函数被 pytest 误收集；sys.exit(1) 在收集阶段执行致 INTERNALERROR

## 2026-04-14 搜索源大扩展（网盘修复 + BT 5 源 + 反爬升级）
**变更**: 网盘修复 rrdynb+ddys；BT 新增 5 直搜源；scraper_base 新增 curl_cffi+CF 检测；蜜柑 RSS 接入订阅
**决策**: Bitsearch JSON API 作为欧美片源核心补充；所有 CF 风险爬虫统一 curl_cffi
**踩坑**: rrdynb 多次搜索触发 CF 限频；Bitsearch 有隐藏 JSON API

## 2026-04-14 .kiro 架构重组
**变更**: ai-rules 精简到 35 行，project-memory 精简到 55 行，新增 knowledge 文件
**决策**: memory 定位为"跨域知识+核心红线+领域索引"

## 2026-04-13 订阅系统（阶段 3+4 完成）
**变更**: 订阅 CRUD + RSS 框架 + 匹配引擎 + 定时调度 + 100 分制质量评分 + 洗版 + 前端 UI + 日历
**决策**: 频率衰减策略（前 72h 每 4h → 3-14 天每 12h → 14-30 天每 24h → 30 天无果暂停）

## 2026-04-13 本地媒体感知
**变更**: local_media_matcher.py 三层匹配 + 内存索引 + 异步 TMDB ID 补全
**决策**: 中文匹配用前缀（startswith）避免误匹配

## 2026-04-12 发现页阶段2 + 代码拆分
**变更**: 探索筛选 + 滚动阻尼 + 后端 4 文件 + 前端 2 组件拆分
**决策**: 滚动交互用自定义 hook 而非 CSS scroll-snap；拆分通过 re-export 保持兼容

## 2026-04-10 发现页重构 + 网盘搜索扩展
**变更**: 多源推荐（豆瓣 v2+TMDB+Bangumi）+ 网盘 4 源
**决策**: 豆瓣用 App API v2 签名鉴权

## 2026-04-09 后端模块化拆分
**变更**: main.py 4163 行拆分为 67 行入口 + 9 路由模块 + shared.py
**决策**: shared.py 作为唯一单例源

## 2026-04-03 初始版本
**变更**: 项目初始化

## 2026-04-20 多语言搜索词设计文档
**变更**:
- 新增 `.kiro/docs/multilang-search-todo.md`：多语言搜索词 + 源 Tab 切换完整设计
- 穷举 BT 6 源 + 网盘 9 源的最佳搜索词映射和回退链
- 设计源 Tab 切换 UI（从筛选开关改为 Tab 切换，每个 Tab 独立搜索词）
- 回退链设计：每个源独立回退，在 future 内部同步完成，不阻塞其他源
- sub-agent 审查发现 8 个问题（P0-P2），已补充决策到文档
**决策**: 先跑通再总结 skill（业务编排层经验需实践验证）；网盘搜索词中文优先但不绝对（纯英文片用英文名）；回退链在 _search_direct 内部循环完成共享 20s 超时；单源端点返回普通 JSON 不走 SSE；jpName 预留参数位但获取交给 L1 业务接入

## 2026-04-21 多语言搜索词实现（Phase 1-3 完成）
**变更**:
- 新建 `search_keyword_mapper.py`：源→语言优先级映射 + 回退链词表 + 季号拼接（cn/en/original/query 四字段）
- 新建 `search_helpers.py`：从 routes/search.py 拆出 enrich_result/compute_junk_flags/extract_bt_title_for_match/merge_bt_extra_sources
- 新建 `SourceTabs.tsx`：源 Tab 切换组件（BT/网盘共用）
- SSE 端点改造：接入 mapper + 回退链（0 结果换词最多 3 轮）+ source_done 新增 search_keywords/hit_keyword
- 新增 `/api/search/source` 单源搜索端点（JSON 响应，支持 fallback_keywords）
- 前端 SearchModal 接入源 Tab：每个 Tab 独立 keyword/results 状态，切换自动填入最佳搜索词
- FolderDetail/VideoDetail/page.tsx 补齐 originalName 传递链路
- jp_name/jpName 统一改为 original_name/originalName（与 clean_name_system 对齐）
- 83 个后端测试全绿（25 mapper + 58 综合），前端构建通过
**决策**: original 字段放所有非中非英的原始语言名（日/韩/法等），不单独设 jp 字段；回退链在 future 内部同步完成共享超时；季号格式跟源走不跟词的语言走

## 2026-04-21 英文名缺失修复 + 全场景接入验证
**变更**:
- discover.py `_inject_clean_names` 增强：用 `detect_language` 判断 original_title 语言，正确分配到 en/original；从 subtitle 中提取英文名（豆瓣格式 "Inception / 盗梦空间"）
- library.py scan 切换到 `clean_from_filename`，生成结构化 cn/en/original 三字段（替代旧的 `_clean_filename_for_folder`）
- 128 个测试全绿（25 mapper + 58 综合 + 45 英文名修复），覆盖 discover 注入/文件名解析/搜索词映射/语言检测/端到端链路
**决策**: original_title 不能直接当英文名用（中国电影是中文、日本动画是日文），必须做语言判断后分配；subtitle 中的英文名用 detect_language 提取而非正则猜测
**踩坑**: 豆瓣 original_title 对中国电影返回中文（和 title 相同），TMDB original_title 对中国电影也返回中文；Bangumi 完全没有英文名字段
