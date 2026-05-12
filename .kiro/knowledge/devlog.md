# 开发日志

> 里程碑归档，记录每个阶段做了什么、为什么这么做、踩了什么坑。只追加，不删除。
> AI 加载项目时读此文件了解版本递进脉络。

---

## 2026-05-09 清洗名手动编辑不生效 + 环绕声筛选误匹配

**变更**:
- **清洗名中文编辑修复（前端）**：`ShadowNameSection.tsx` 的 `handleSaveClean` 在文件夹模式下因 `!video?.file_path` 直接 return，请求根本没发出去。改为用 `video?.file_path || path`，并传 `is_folder` 参数
- **清洗名英文编辑修复（后端）**：`get_library_tree` 的 `finalize` 每次从 `clean_for_folder()` 重新计算文件夹清洗名，完全忽略手动保存的值。新增手动覆盖逻辑：检查视频条目是否有 `clean_name_source == "manual"`，有则用手动值覆盖计算值
- **post_process season 保护**：season 子目录有 manual 来源时跳过 `clean_for_folder` 重新计算
- **垃圾英文名检测豁免**：手动设置的英文名不做垃圾检测（用户明确指定的值应尊重）
- **set_clean_name 增强**：文件夹模式下英文名保存强制设 `clean_name_source = "manual"`（原来只在 source 为空时才设）；中文名保存时同步写入 `clean_name_cn` 字段
- **环绕声筛选修复**：`quality_parser.py` 额外环绕声检测正则从 `[5-9][\s.]?[01]` 改回 `[5-9][\s.][01]`，分隔符必须存在，避免 `51`/`50` 等纯数字（集数/年份）被误判为环绕声

**踩坑**:
- 文件夹没有独立的持久化字段存储手动清洗名，只能通过视频条目的 `clean_name_source` 间接标记。`finalize` 中需要先计算再检查手动覆盖
- `post_process` 对 season 子目录也会重新计算 `clean_name`，必须同时加保护，否则 `finalize` 中设置的手动值会被二次覆盖
- 环绕声正则 `?` 让分隔符可选后，`Episode.51` 中的 `51` 被匹配为 `5.1`，导致大量非环绕声结果被标记为环绕声

---

## 2026-04-30 季集完整性检测（基于 TMDB 的缺失分析）

**变更**:
- **新增 `completeness.py`**：核心业务模块，从 TMDB 获取完整季/集结构，与本地文件做差集比对
- **本地集号提取**：NFO 优先 → 文件名正则回退（S01E02/EP02/第5集/02集/连字符/中文数字/中文字符后数字）
- **前端 `CompletenessBar.tsx`**：进度条 + 季标签（✓完整/⚠️部分缺失/✗整季缺失）+ 缺失集展开 + 搜索联动
- **持久化缓存**：`completeness_cache.json`，API 默认读缓存秒返回，刷新按钮清除 TMDB 缓存重新计算
- **自动刷新**：挂钩 `save_library` 回调（`shared.py`），3 秒防抖，后台线程刷新受影响的 TV 文件夹
- **批量预计算**：`POST /library/completeness/refresh-all` + `_batch_completeness.py` 脚本
- **season 节点单季显示**：传父目录路径 + `seasonFilter` 过滤，只显示当前季的完整度
- **绝对集数重映射**：全集平铺场景（如十二国记 45 集无季目录），自动检测并用 `build_absolute_episode_map` 重映射到各季
- **快速同步进度显示文件名**：`Toolbar.tsx` 进度事件增加文件名展示（截断 30 字符）

**踩坑**:
- CRC32 校验码误匹配：`[E0412FB5]` 中的 `E0412` 被 `[Ee][Pp]?(\d+)` 匹配为集号 412。修复：限制 E/EP 后数字最多 3 位，且 E 前面不能是十六进制字符
- NFO 季号不可信：刮削错误可能导致 NFO 中 `<season>` 值不对（如 S4 的 NFO 写成 season=1）。修复：目录名有明确季号时始终覆盖 NFO 的季号
- 缓存并发安全：10 线程并发写入缓存文件会丢数据。修复：`_cache_lock`（threading.Lock）保护所有缓存读写
- 中文字符后紧跟数字（如 `高清02.rmvb`）：独立数字正则的前置边界不支持中文字符。修复：增加 `[\u4e00-\u9fff](\d{2,3})` 模式

**决策**:
- TMDB 为主数据源（结构化季/集列表），豆瓣暂不做实时 fallback（不返回详细集列表、有限频风险）
- 特别篇（Season 0）默认不计入完整度
- 未播出集标记 `aired=false`，前端灰色不可搜索
- 缓存文件不入 git（加入 .gitignore）

---

## 2026-04-29 清洗名系统多瑕疵修复

**变更**:
- **strip_noise 增强**：新增步骤 0a 去除季范围尾缀（`1-8季`/`S1-S3`）和尾部独立季号（`守望尘世S1`→`守望尘世`、`火线16季`→`火线`）；步骤 7 改为也去紧跟中文名的 `TV版`（`方子传TV版`→`方子传`）
- **split_by_language 季集号保护**：token 化正则增加 `S/E+数字` 整体模式（如 `s5`、`S01E03`），避免被拆分成 `s` + `5`
- **纯数字英文名过滤**：`clean_from_filename` 中从文件名解析出的纯数字 en 直接清空（如 `02.mkv` 不再产生 `en=02`）；自愈层2 冒泡时增加垃圾英文名检测，纯数字不冒泡到文件夹级
- **电影文件夹视频清洗名补全**：`post_process` 条件从 `("tv", "season")` 改为 `("tv", "season", "movie")`，电影文件夹下的视频也参与清洗名补全
- **前端搜索词过滤**：`FolderDetail.tsx` 和 `VideoDetail.tsx` 中 cnName 回退时过滤一级分类目录名（"电影"/"电视剧"等），避免搜索词变成"电影白"
- **TV文件夹影子名去集号**：shadow_name 冒泡到 TV/season 文件夹时去掉尾部 S01E01 等季集号；split_names 从 en 中去除尾部季集号
- **英文名可编辑**：ShadowNameSection 清洗名行同行布局（中文名 + 英文名），各自独立编辑热区；后端 `/library/clean-name` 扩展支持 `clean_name_en`
- **整理替换三栏文件类型标签**：plan 栏和 old 栏补上文件类型标签（视频/字幕/扩展名），与 new 栏一致
- **搜索 SSE 竞态保护**：`useSearchState.ts` 增加 `searchIdRef`，每次搜索递增 ID，`onmessage` 中检查 ID 是否匹配当前搜索，不匹配则丢弃；关闭弹窗时递增 ID 确保残留消息被丢弃

**踩坑**:
- `split_by_language` 的 token 化顺序很重要：`S/E+数字` 模式必须在英文字母模式之前匹配，否则 `s` 会被先匹配为独立字母 token
- 电影文件夹下 77 个视频中 19 个完全没有 `clean_name`（连 display 都没有），自愈层1 无法触发（需要有 `clean_name` 才能反向解析），只有 `post_process` 从父文件夹继承才能补全

---

## 2026-04-28 搜索下载修复 + 清洗名自愈机制 + 分季搜索 + 英文名展示

**变更**:
- **Prowlarr 下载链接修复**：`searcher.py` 优先用 `infoHash` 构造磁力链接（覆盖 ~86% 结果），其次用真正的 `magnetUrl`，最后回退到 Prowlarr 代理链接；`download_manager.py` 的 `_push_to_qb` 增加 Prowlarr 代理链接预处理（GET + allow_redirects=False 解析重定向获取磁力链接）
- **搜索弹窗高度固定**：`SearchModal.tsx` 容器从 `max-h-[85vh]` 改为 `h-[85vh]`，不再因内容多少高低变化
- **分季搜索词支持中文数字**：`FolderDetail.tsx` 季号提取增加中文数字解析（一~九十九），支持"第一季"到"第九十九季"
- **移除重启后端组件**：`layout.tsx` 移除 `MaintenanceCenter` 引用和渲染
- **清洗名名称污染修复**：`finalize` 中子节点向上冒泡限制为仅 tv/season 类型（同一部剧），一级分类目录不冒泡；`post_process` 中一级分类目录（`is_top_category`）不向下传播 cn/en/original
- **清洗名自愈机制**（接入 `parse_legacy_clean_name`）：
  - 自愈层1：视频条目缺失 `clean_name_cn`/`clean_name_en` 时，从 `clean_name`（display）反向解析（`parse_legacy_clean_name`），并持久化到 `media_library.json`
  - 自愈层2：从视频条目冒泡补全文件夹节点，如果视频的英文名比文件夹名解析的更长则覆盖
  - 自愈层3：NFO 兜底（文件夹名和视频都解析不出时读 NFO）
  - 自愈层4：子树冒泡（仅 tv/season）
  - 垃圾英文名检测：季号碎片、纯数字、常见非作品名（Season/SPs/EXTRA/menu 等）自动清空，让冒泡补全正确值
- **前端英文名展示**：`ShadowNameSection` 新增 `cleanNameEn` prop，清洗名行追加显示英文名（如果 display 中不包含）；`FolderDetail` 传递 `node.clean_name_en`

**踩坑**:
- Prowlarr API 返回的 `downloadUrl` 是代理链接（`http://127.0.0.1:9696/X/download?apikey=...`），qBittorrent 无法正确处理 301 重定向到 magnet: 的情况；`magnetUrl` 也是代理链接不是真正的磁力链接；只有 `infoHash` 是可靠的
- `clean_name_cn`/`clean_name_en` 在 `media_library.json` 中全部为空（0% 覆盖率），根因是 `parse_legacy_clean_name` 函数已实现但从未被业务代码调用——清洗名系统上线时没有做存量数据迁移
- `finalize` 中子节点向上冒泡没有限制范围，导致一级分类目录（如"欧美剧"）从第一个有 `clean_name_en` 的子节点（如 better call saul）冒泡英文名，然后 `post_process` 向下传播污染所有兄弟节点
- `clean_for_folder` 对含季号范围的文件夹名（如"进击的巨人s1-s5"）解析出垃圾英文名（如 `en='1 s 5'`），阻止了视频冒泡的正确英文名覆盖
- 电影 vs 电视剧清洗名展示差异：电影文件夹名本身含中英文所以 display 有英文，电视剧的 display 由 `compose_display(include_en=False)` 组装只有中文，英文名存在 `clean_name_en` 但前端 ShadowNameSection 没有展示

## 2026-04-23 新增直搜源（EZTV/动漫花园/1337x）+ 源级代理配置 + 单源搜索修复
**变更**:
- 新增 3 个 BT 直搜源：EZTV（bt_scraper_eztv.py，默认禁用，不支持关键词搜索）、动漫花园（bt_scraper_dmhy.py，RSS 端点搜索+chrome124 指纹）、1337x（bt_scraper_1337x.py，镜像站 1337xx.to+chrome120 指纹+两步请求取磁力+标题相关性过滤）
- 源级代理配置：BT_SOURCE_DEFAULTS 新增 needs_proxy 字段，get_source_proxy() 统一决定每个源是否走代理；config.bt_search_sources 支持新格式 `{"proxy": false}` 按源覆盖；前端搜索设置页加代理开关按钮
- 单源搜索端点 `/api/search/source` 的 enrich_result 补传 match_names 参数，修复单源 Tab 智能过滤失效的 bug
- 前端单源 Tab 切换优先从 SSE 全量结果中过滤该源结果（`_source` 字段），避免重复请求
- 前端搜索词标签点击改为根据当前 Tab 触发对应搜索 + 同步更新 input 框（之前只对"全部"Tab 生效）
- 直搜源 max_results 从 20 提高到 40（search_direct + search_single_source + merge_bt_extra_sources 三处统一）
- 前端 DIRECT_SOURCES / DIRECT_SOURCE_NAMES 集合补齐新源
- routes/search.py 的 source_getters 字典补齐新源
- ACG.RIP 改为默认禁用（直连超时+走代理 TLS 报错）
- subscribe-redesign.md 标记废弃归档到 _archived/
- ai-integration-test-report.md 移到 _one-off/
- L5/L6 skill 文档全面更新，新增直搜源 Checklist（后端 7 文件 + 前端 4 文件 + 验证 6 项）
- business-skills-plan.md 更新 L5/L6 状态为已沉淀，S2/S3/S4/S12 状态更新
**踩坑**:
- EZTV RSS 端点 `ezrss.xml?search_string=xxx` 完全忽略搜索参数，返回全站最新 20 条
- 动漫花园 chrome131 TLS 报错，chrome120 也不稳定，chrome124 正常（CF 指纹检测动态变化）
- 1337x 主站 1337x.to 所有指纹 403（高级 JS Challenge），镜像站 1337xx.to chrome120 正常
- 1337x 搜索结果包含大量不相关内容（综合站），需加标题相关性过滤
- 单源搜索端点 enrich_result 缺少 match_names 参数，导致 match_score=0 的不相关结果不被标记为 junk，智能过滤失效
- 前端单源 Tab 切换时总是触发新的 API 请求而不复用 SSE 已有结果，导致 1337x 等慢源切 Tab 后显示空
- routes/search.py 的 source_getters 和前端 DIRECT_SOURCES 遗漏新源注册，导致单源搜索返回"未知源"
- 爬虫单例在首次创建时固定代理配置，用户改代理开关后需重启后端
**架构决策**:
- curl_cffi 能绕过中低级 CF 保护（频率触发型、TLS 指纹检测），无法绕过高级 JS Challenge（需执行 JavaScript），用镜像站绕过
- 英文综合站（1337x）必须加标题相关性过滤，否则搜索结果充斥不相关热门内容
- 新增直搜源需注册 11 个位置（后端 7 + 前端 4），建立 Checklist 防遗漏

## 2026-04-22 发现页详情匹配修复（TMDB ID 直拉 + best_match 评分）
**变更**:
- `_try_tmdb_detail` 的 `_pick_best` 从"取第一个+年份匹配"替换为 `tmdb_client.best_match`（多维度评分+30 分阈值），解决搜索返回不相关结果时盲选的问题
- 新增 `_try_tmdb_detail_by_id`：TMDB 路径有 id 时直接拉详情跳过搜索，支持 movie↔tv 自动回退（trending mixed 类型可能传错 type）
- TMDB 路径增加 id 判断：`id` 非空且是数字时优先走 `_try_tmdb_detail_by_id`，失败才 fallback 到搜索
- 三源统一：豆瓣/Bangumi 本来就有 ID 直拉逻辑，现在 TMDB 也补齐了
**溯源**:
- `_pick_best` 是项目初始代码（4/3 初始提交），经两次 refactor（4/9 main.py→scrape.py，4/11 scrape.py→media_info.py）原样搬运从未改过
- 4/13 的"详情匹配算法优化"只升级了豆瓣侧的 `_pick_best_douban_result`，TMDB 侧被遗漏
- `tmdb_client.py` 后来写了成熟的 `best_match` 函数但 `_try_tmdb_detail` 从未使用
**已知案例**: 匹兹堡医护前线→年轻的皮特先生、无敌少侠(Invincible)→同名电影、黑豹纠察队→捉鬼小精灵(The Lost Boys)
**测试**: 22 个单元测试覆盖评分拒绝/接受、movie↔tv 回退、_pick_best 新签名、边界情况

## 2026-04-22 AI 集成一期（基础设施 + 三场景 + 前端设置页）
**变更**:
- 新建 `ai_client.py`：统一 AI 客户端，封装 OpenAI 兼容 API 调用（chat/chat_json/_extract_json/_validate_schema），内置调用计量（场景级 calls/tokens/errors）
- 新建 `ai_prompts.py`：三个一期场景的 prompt 模板 + schema 定义，集中管理便于调优
- 重构 `ai_organizer.py`：去掉直接 HTTP 调用，改用 ai_client；新增 ai_extract_episode（单/批量）、ai_select_scrape_candidate、ai_library_diagnosis 四个业务函数
- `config_manager.py` 扩展：新增 `ai_enabled`（全局总开关）+ `AIFeaturesConfig`（6 个场景独立开关），旧配置向后兼容
- `routes/tools.py` 新增 3 个端点：`POST /ai/test`（测试连接）、`GET /ai/status`（配置状态+用量）、`POST /ai/diagnosis`（媒体库诊断）
- 前端 `types/index.ts` 新增 AIFeaturesConfig/AIStatus/AIDiagnosisResult 类型
- 前端 `lib/api.ts` 新增 testAIConnection/getAIStatus/aiDiagnosis 三个 API 函数
- 前端 `SettingsModal.tsx` AI 区域升级：master switch 总开关 + 服务商预设（豆包/DeepSeek/自定义）+ API 配置 + 测试连接 + 6 个场景功能开关 + 运行用量统计
- 43 个单元测试（23 ai_client + 20 ai_organizer）全绿
- 3 轮真实 API 测试（基础+独立验证+极端场景）共 16 次调用，约 9767 tokens
**踩坑**:
- 豆包 lite 模型生成结构化 JSON 较慢，诊断场景首次 25s 超时 → 简化 prompt + temperature=0 + 超时调至 60s
- 日文动画长文件名偶发 15s 超时 → 文件名解析超时从 15s 调至 20s
- `_extract_json` 对"多个独立 JSON 对象"的输入返回 None（已知限制，实际 AI 响应不会出现）
**架构决策**:
- AI 是增强不是依赖：所有场景有非 AI fallback，关闭 AI 后系统功能完整
- 不引入 openai SDK，用 requests 直接调 HTTP（项目一贯风格）
- AIClient 无状态，每次从 config 构造（配置可能随时改）
- prompt 集中在 ai_prompts.py 一个文件，方便调优和版本对比
- chat_json 两层保护：_extract_json（格式兼容）+ _validate_schema（结构校验）

## 2026-04-22 订阅系统 Phase 4a/4b（RSS 源扩展 + 反馈闭环）
**变更**:
- Phase 4a：新增 4 个 RSS 源（动漫花园/ACG.RIP/Bangumi Moe/YTS），全部注册到 RSSSourceManager，共 8 个 RSS 源
- Phase 4b：通知系统（notification_service.py）— 搜索日志 + 下载/洗版/发现资源/自动暂停通知，预留 Bark/Server酱/Webhook 外部推送
- Phase 4b：搜索结果缓存（SearchResultCache，同源+同关键词 30 分钟 TTL，500 条 LRU）
- Phase 4b：全局速率限制（RateLimiter，每源每分钟最多 4 次请求）
- subscriber.py 新增 SearchLogEntry/NotificationEntry 模型 + search_logs/notifications 字段
- routes/subscribe.py 新增 4 个 API 端点（/logs, /notifications, /notifications/read, /notifications/unread）
- download_manager.py 下载完成时写入通知（区分追更/洗版）
- rss_engine.py RSS 和直搜通道搜索后自动写入搜索日志
- 前端 useSubscriptions.ts + api.ts 同步更新类型和 API 方法
- 28 个测试全绿（RSS 源解析 14 + 通知服务 4 + 缓存 4 + 速率限制 2 + 模型兼容 4）
**架构决策**: 通知持久化到 subscriptions.json 的 notifications 字段（每订阅最多 100 条），不单独建通知文件；搜索日志同理（每订阅最多 50 条）；外部推送预留接口但不实现，等实际需求再接入

## 2026-04-22 订阅系统重设计 Phase 0-3b + 修复轮（完整交付）
**变更**:
- Phase 0：SubscriptionManager 全局单例
- Phase 1a：数据模型扩展（7 个新字段 + jp→original 迁移）
- Phase 1b：search_service.py 搜索逻辑抽离
- Phase 1c：EZTV RSS 源 + search_keyword_mapper 扩展
- Phase 2a-2d：RSS 调度器增强 + 直搜通道 + 追更完善（Quality Cutoff/自定义间隔/下载失败重试）+ 洗版模式
- Phase 3a-3b：前端核心交互（订阅类型选择/源分组/两级展示/集详情/日历优化）
- 修复轮：订阅创建时传递清洗名和所有平台 ID、type/season 自动提取、保存路径智能填入、调度器自动启动、Bangumi 日历 fallback、订阅冲突提示、RSS 匹配器跨语言增强
**踩坑**: 调度器之前是懒加载（只在手动搜索时启动），导致定时搜索从未运行；订阅创建时 type 取的是 tab 级别而非卡片级别导致剧集被标记为电影；旧订阅 tmdb_id 全部为 None 因为中文标题搜 TMDB 匹配不到
**设计文档**: .kiro/docs/subscribe-redesign.md

## 2026-04-22 技术债务清理（3/4 项）
**变更**:
- `pan_models.py` Pydantic V2 迁移：4 个 `@validator` → `@field_validator` + `@model_validator(mode="before")`，V2 中有默认值的字段不能用 `field_validator(mode="before")` 自动触发，改用 `model_validator` 统一处理 clean_title/resolution/is_complete 的自动填充
- `routes/discover.py` 拆分（809→458 行）：enrich_cache 管理 + 清洗名注入 + 本地状态注入 + TMDB 补全逻辑下沉到 `discover_enrich.py`（333 行，业务层），路由文件只保留端点
- 后端 `print()` → `logging` 模块：38 个核心文件批量替换，`shared.py` 统一 `logging.basicConfig`，每个文件顶层 `logger = logging.getLogger(__name__)`，日志级别按内容自动分类（error/warning/info）
- 同步更新 `code-style.md`（日志规范）、`structure.md`（新增 discover_enrich.py）
**踩坑**: 批量替换脚本把 `logger = logging.getLogger(__name__)` 插到了多行 import 中间或 try 块内部（因为脚本找"最后一个 import 行"时没区分顶层和缩进块），需要二次修复脚本 + 4 个文件手动修正
**未处理**: `routes/search.py` 拆分（标注为订阅重设计 Phase 1b 一并解决）

## 2026-04-21 智能过滤完整实现：五规则判定 + 跨语言匹配 + 标题占比检查
**变更**:
- 智能过滤从空转升级为五规则判定体系（search_helpers.py 的 compute_junk_flags）：
  1. 枪版检测（TS/CAM/HDTC 等词边界匹配）
  2. 匹配度过低（match_score > 0 且 < 30）
  3. 死种检测（seeders=0 且非磁力链接源）
  4. 完全不匹配（match_score=0 + 有多语言候选，解决 Prowlarr 索引器多时返回 Zootopia 等不相关结果）
  5. 标题占比过低（match_score 40-70 但搜索词只是长标题的一小部分，如合集/混剪/长描述）
- enrich_result 新增 match_names 参数，SSE 搜索时传入 cn_name/en_name/original_name 解决跨语言匹配
- 新增 extract_bt_title_for_match：专为搜索匹配设计的 BT 标题清洗（在第一个技术标签处截断）
- match_chain 增强：新增 contains 子串匹配步骤（70分）+ 修正 token_set 比例方向
- 标题占比检查中英文分开算，避免中文搜索词被英文标题部分稀释
- 业务 skill 文档 `.kiro/skills/smart-filter.md`（五规则+源特征差异+占比计算+测试矩阵）
- 102 个测试全绿（基础45 + 扩展39 + 跨语言10 + 占比8）
**决策**: 用 _has_multilang_candidates 区分"有多语言候选但不匹配"和"无候选无法计算"；占比检查中英文分开算取最高值；规则 5 只在 match_score 40-70 区间触发（精确匹配不检查，低分已被规则 2 处理）
**已知问题**: MPEG-TS 误标记枪版；单词搜索 vs 长标题 score=0；中文 2 字公共前缀触发 token_set（已被规则 5 兜底）

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

## 2026-04-21 智能过滤增强：跨语言匹配 + unmatched 规则
**变更**:
- enrich_result 新增 match_names 参数，SSE 搜索时传入 cn_name/en_name/original_name，解决跨语言匹配问题
- 新增规则 4（unmatched）：match_score=0 且有多语言候选时标记为不匹配，过滤 Prowlarr 返回的完全不相关结果
- 用户手动搜索（无 match_names）时不触发 unmatched 规则，避免误伤
- 94 个测试全绿（基础45 + 扩展39 + 跨语言10）
**决策**: 用 _has_multilang_candidates 标记区分"有多语言候选但不匹配"和"无候选无法计算"两种 match_score=0 的含义
**踩坑**: search_helpers.py 已从 routes/search.py 拆出（之前的重构），函数名去掉了下划线前缀

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

## 2026-04-23 设置页 UI 优化 + 产品标题更名
**变更**:
- 添加路径按钮从路径列表下方移到"添加需要扫描的媒体库目录"描述文字最右侧
- 排除文件夹与上方路径模块间距缩小（-mt-2），textarea 从 rows=2 改为 rows=1 + resize-y + min-h-[38px]，和普通 input 等高
- AI 功能开关区域改为折叠展开（▶ 箭头），AI 标题/总开关/服务商预设/API 配置/测试连接始终可见
- 产品标题统一改为 Napics Media Manager（Header 顶栏、layout title、meta description）

## 2026-04-28 下载→归位闭环收口（阶段收口）
**变更**:
- 保留 `optimization-stabilization-todo.md` 作为 `v1` 历史清单，新建 `optimization-stabilization-todo-v2.md` 作为新的收口执行面板
- 收口口径改为“用户主链路可用性”，不再沿用 `v1` 中失真的 `40%`
- 下载→归位闭环主链路正式收口为“已开证，转观察态”
- 已开证范围包括：
  - 下载提交（qB / Alist）
  - 下载进度同步（qB `unknown -> downloading/completed` 恢复映射、AList V3 `task info / done / undone`）
  - 自动归位 / `confirm` / `execute`
  - 前端主入口回归（`archived` tab、查看入口、绝对 NAS 路径命中、首页媒体库树首屏性能回退修复）
- `85499bc0 / 5xvyCPXpAe5J9_HTL7Kxb` 样本完成最终只读复测后，已从“阻塞样本”降级为“上游观察样本”
**决策**:
- 后续不再围绕同一个 AList `429` 冷却样本重复复测
- 轻量影子副本默认不重建，仅在后续再次出现 `execute / dry-run` 回归且不适合直接碰真实 NAS 时再启用
- 自动推进策略改为“每 30 分钟继续推进当前最高价值小闭环”，不再锁死在单一样本复测
**踩坑**:
- 真实 AList 离线任务即使仍存在于 `done/info`，也可能因为上游 Prowlarr indexer 长时间冷却而持续返回 `429`，这种情况不应再被当作 DownloadManager 同步链 bug
- 本地 `download_tasks.json` 与 AList 真实任务列表可能出现“本地任务已清理，但远端 tid 仍保留”的时间差，验证时必须同时看本地状态和远端 `tid`

## 2026-04-28 搜索 / 命名 / 刮削基线快照（小闭环）
**变更**:
- 新增 `backend/test_searcher.py`，固定 Prowlarr 下载链接归一化优先级（`infoHash` 构造磁链 > 真实 `magnetUrl`）
- 新增 `backend/test_search_route_snapshots.py`，固定 `/api/search/source` 返回结构与 SSE `/api/search/stream` 的 `source_done` 事件结构
- 扩充 `backend/test_scraper_tv_dry_run_actions.py`，把 `existing_nfo -> tmdb_match -> episode NFO 字段 -> dry-run summary` 固定成代表性 TV 样本
- 更新 `search-naming-scrape-baseline-snapshot.md` 与 `optimization-stabilization-todo-v2.md`，把三条基线从“缺快照”推进到“已有入口快照，可转观察”
**决策**:
- 本轮只补验证入口和证据文档，不扩搜索 / 命名 / 刮削业务逻辑
- 搜索链路的“快照”口径以接口结构稳定性为主，不把外站可用性波动混入当前收口标准
**踩坑**:
- `StreamingResponse.body_iterator` 在测试里是 async generator，SSE 快照要异步收集，不能直接 `list(...)`
- 当前 `DownloadManager` 对 Prowlarr 代理链接的预解析实际走的是 `requests.get(..., allow_redirects=False, stream=True)`，不是 `HEAD`
- 当前完整验证仍有两组既有噪声：
  - 前端 `vitest` 失败集中在 `split-components` / `subscribe-*` 老测试
  - 后端完整 `pytest .` 会被多份历史脚本式测试文件在导入阶段 `sys.exit(...)` 打断

## 2026-04-28 媒体库首页性能专项入口（基线）
**变更**:
- 新增 `library-home-performance-baseline.md`，把首页性能从观察项拉成专项入口
- 复核当前首页首屏链路：
  - `/library/tree` 继续保持“不实时读 NAS NFO”
  - 前端 `useLibrary` 初始化和刷新仍是 `/library + /library/tree` 双请求并行
- 新增 `backend/test_library_route_snapshot.py`，固定 `/library/tree` 返回形状
- 本机 `8000` 粗测：
  - `/library/tree` 约 `910ms`
  - `/library` 约 `305ms`
**决策**:
- 当前先停在“基线 + 下一步候选”，不直接扩成首页重构
- 下一轮若仍要压首页体感，优先看 `useLibrary.refreshLibrary()` 的双请求刷新成本

## 2026-04-29 媒体库首页性能专项（树刷新收窄）
**变更**:
- `frontend/hooks/useLibrary.ts` 新增 `refreshTree()`，把树刷新从全量刷新里拆出来
- `frontend/components/detail/FolderDetail.tsx` 的 `分类标签 / folder_type` 保存后改成只刷新 `/library/tree`
- `frontend/components/detail/ShadowNameSection.tsx` 在 `tv/season` 文件夹模式下保存标准名后也改成只刷新 `/library/tree`
- 新增 `frontend/__tests__/use-library-refresh.test.tsx`，固定“树刷新不会重复拉全量 `/library`”
- 新增 `frontend/__tests__/shadow-name-section.test.tsx`，固定“文件夹模式保存标准名只触发树刷新”
- `frontend/components/detail/FolderDetail.tsx` 在文件夹封面上传 / 删除后也改成只刷新 `/library/tree`
- 新增 `frontend/__tests__/folder-detail-tree-refresh.test.tsx`，固定“文件夹封面上传回调只触发树刷新”
- 同一测试文件继续补“文件夹手动候选确认只触发树刷新”
- 同一测试文件继续补“分类标签 / folder_type 修改只触发树刷新”
- 更新 `library-home-performance-baseline.md`、`optimization-stabilization-todo.md`、`optimization-stabilization-todo-v2.md`
**决策**:
- 本轮只压掉“纯树元数据改动”这一类不必要的双请求刷新
- 重命名、批量管理、刮削、结构整理等仍保留全量刷新，避免过早把刷新策略改复杂
**踩坑**:
- 首页详情侧很多动作都会同时影响目录树和视频列表，不能把 `onRefresh` 一把全替成树刷新；必须按入口逐个收窄

## 2026-04-29 整理替换附属文件处理修复

**变更**:
- `backend/routes/organize.py`：`_apply_action_plan_moves` 白名单处理阶段新增三类文件分流逻辑
  - 字幕文件（Subs/ 子目录中）：扁平化到 Season 目录，通过集号匹配用视频标准名重命名
  - 非字幕文件（字体包/SPs/CDs/OAD 等）：提升到剧集根目录（base_path），不跟随视频进入 Season
  - 新增 `_cleanup_empty_dirs`：移动完成后自底向上清理空的种子目录壳
- `backend/routes/relocate.py`：`_build_plan_tree` 预览逻辑与执行逻辑对齐，字幕展示在 Season 下，附属文件展示在根级
- `backend/scraper.py`：`_scrape_tv_v3` 新增季目录检测，当 save_path 本身是季目录（如"第三季"）时不再嵌套 Season XX
- 新增测试：`test_subtitle_flatten.py`（8 个）、`test_plan_tree_preview.py`（3 个）、`test_season_dir_no_nest.py`（2 个）
- 更新 `knowledge/download-replace-pipeline.md`：补充附属文件规则和季目录检测说明
**决策**:
- 字幕扁平化时先剥离多重扩展名（.chs.ass）再用 parse_filename 解析集号，因为 parse_filename 不认识语言标签
- 非字幕文件统一提升到根目录，不区分文件类型（视频/音频/压缩包），避免规则过于复杂
- 季目录检测复用已有的 `_is_season_dir`，支持 Season XX / 第X季 / SXX 等格式
**踩坑**:
- Windows 上 `os.path.normcase` 会把路径转小写，导致 plan_tree 合并时 "Season 01" 和 "season 01" 不匹配，需要大小写不敏感比较
- `_resolve_extra_target_path` 对同目录文件和子目录文件的处理路径不同：同目录文件直接映射到 Season 下，子目录文件保留相对路径。两种情况都需要处理

## 2026-04-29 电影类型整理替换支持

**变更**:
- `backend/scraper.py`：`_scrape_movie` 新增 `dry_run` 参数和 plan 生成逻辑，电影 plan 包含视频重命名为标准名
- `backend/routes/organize.py`：执行模式根据 `folder_type` 区分 movie（写 movie.nfo）和 tv（写 tvshow.nfo + episode.nfo）
**根因**:
- `_scrape_movie` 完全不支持 `dry_run`，不生成 `plan`，导致整理替换链路拿到空 plan 后报告"无需归档"
**踩坑**:
- 执行模式中原来无条件走 TV 逻辑（`get_tv_detail` + `write_tvshow_nfo`），电影会被错误地写成 tvshow.nfo

## 2026-04-29 电影整理替换链路修复 + 无冲突场景支持

**变更**:
- `backend/routes/organize.py`：推演阶段 category_hint 优先覆盖 classify_folder 结果，避免种子子目录干扰分类
- `backend/routes/relocate.py`：无冲突但有整理计划时也返回 awaiting_confirm + plan/tree 数据
- `backend/routes/organize.py`：执行模式根据 folder_type 区分 movie（write_movie_nfo）和 tv（write_tvshow_nfo + write_episode_nfo）
**根因**:
- 电影目录被 classify_folder 误判为 collection（种子子目录干扰）
- _scrape_movie 不支持 dry_run/plan → 空 plan → "无需归档"
- 无冲突时 dry-run 端点不返回 plan → 前端无法展示预览

## 2026-04-29 下载管理面板 UI 改进

**变更**:
- 去掉"待整理" tab（awaiting_confirm 不再作为独立筛选项）
- 名称过长截断：media_name 限制 320px，save_path 限制 240px，hover 显示全名
- 已完成任务增加"归档"按钮，直接将 completed 转为 archived
- 后端新增 `/download-manager/archive` 端点
- 按钮区域 shrink-0 + whitespace-nowrap 防止被名称挤压变形

## 2026-04-29 搜索竞态 + 电影分类误判 + 种子目录清理

**变更**:
- `frontend/components/search/useSearchState.ts`：SSE 竞态保护加强，所有 setState 调用前检查 searchIdRef，防止旧搜索结果混入新搜索
- `backend/organizer.py`：`_classify_movie_category` 修复——有散落视频时以视频数量为准判定类型，忽略子目录（种子文件夹不影响分类）
- `backend/routes/organize.py`：`_cleanup_empty_dirs` 增强——不仅清理空目录，也清理只剩垃圾文件（txt/nfo/jpg）的种子目录壳
**根因**:
- 搜索竞态：旧 SSE 的 onmessage 回调在新搜索启动后仍可能写入 state
- 电影分类：种子子目录（正在下载或已下载）导致 `_classify_movie_category` 把 movie 误判为 collection，影响媒体库树展示和整理替换
- 种子目录残留：整理后种子目录里可能还有 txt/nfo/jpg 等垃圾文件，旧的 `_cleanup_empty_dirs` 只清理空目录

## 2026-04-30 大文件拆分 P1-P5（纯重构）

**变更**:
- **P1 SearchModal.tsx** (849→163行)：提取 `useSearchState.ts`(602行) 搜索状态+SSE+缓存+排序，`SearchHeader.tsx`(242行) 顶栏 UI
- **P2 api.ts** (484→10个子模块)：按领域拆分到 `lib/api/` 目录（search/scrape/organize/download/discover/subscribe/config/system/ai），`index.ts` 聚合导出，调用方零改动
- **P3 routes/organize.py** (1238→602行)：下沉 `organize_executor.py`(399行) Action Plan 执行器，独立 `routes/rename.py`(159行) 手动重命名路由，独立 `routes/organize_stream.py`(122行) SSE 流式整理路由
- **P4 DiscoverPage.tsx** (597→195行)：提取 `useDiscoverState.ts`(366行) Tab+搜索+展开面板，`useDiscoverSubscribe.ts`(132行) 订阅逻辑
- **P5 scraper.py** (1124→472行)：提取 `scraper_tv.py`(688行) TV 刮削逻辑（_scrape_tv_v3/_scrape_tv/_scrape_collection/_search_tmdb/_episode_nfo_matches_target）
- **附带**：ai-rules 补充文件写入防 aborted 规则（fsWrite 失败禁止同参数重试），structure.md 同步新文件
- **验证**：前端构建通过，后端 208 项测试全绿，零循环依赖，拆分导致的新问题 0 个
- **拆分计划文档**：`.kiro/docs/code-split-todo.md`，含 32 个文件的完整审计（5 拆/7 观望/20 不拆）

**踩坑**:
- fsWrite 新建大文件（>50行）会触发 aborted，必须用 fsWrite 建头部 + fsAppend 分段追加
- scraper_tv.py 中 _scrape_collection 和 _scrape_tv 调用了 scraper.py 的 scrape_folder/scrape_video，通过延迟导入（函数内 `from scraper import ...`）解决循环依赖
- api.ts 拆分后 Next.js 自动解析 `api/index.ts`，所有 `import { api } from "@/lib/api"` 无需改动

## 2026-05-08 Alist → OpenList 迁移

**变更**:
- 全项目从 Alist 切换到 OpenList（Alist 社区兼容分支），指向 NAS 上持续运行的实例
- `config_manager.py`：默认端口保持 5244（OpenList 标准端口）
- `config.json`：实际地址改为 `http://192.168.100.135:5244`（NAS 上的 OpenList）
- `downloader.py`：所有日志和 docstring 中 "Alist" → "OpenList"
- `download_manager.py`：注释和错误信息更新
- `routes/search.py`：路由端点注释和错误提示更新
- `pan_search_service.py`：注释更新
- `quark_transfer.py`：注释和日志更新（从 OpenList 提取夸克 Cookie）
- 前端 `SettingsModal.tsx`：标签 "Alist 地址/Token" → "OpenList 地址/Token"
- 前端 `SearchModal.tsx`：错误提示 "Alist 服务不可达" → "OpenList 服务不可达"
- 前端 `AddMediaPanel.tsx` / `BatchUpgradePanel.tsx`：按钮文字 "Alist" → "OpenList"
- 前端 `lib/api/system.ts`：注释更新
- `tech.md`：外部服务描述更新
- `project-memory.md`：下载管理描述更新

**保持不变**:
- 内部字段名 `alist_url`/`alist_token`/`channel: "alist"` 不改（避免破坏已有数据和 API 路径）
- API 路径 `/alist/transfer`、`/alist/mounts` 不改（前后端对齐，改了没有实际收益）
- 类名 `AlistManager` 不改（OpenList API 完全兼容 Alist）

**验证**: OpenList v4.2.1 在 NAS 正常响应，前端构建通过，后端模块导入正常

## 2026-05-12 Provider 契约与 Registry Phase 2

**变更**:
- 新增 `provider_models.py`、`provider_context.py`、`provider_contracts.py`、`provider_registry.py`，建立 Provider DTO、依赖注入上下文、协议和注册表
- 新增 `providers.py` 并接入 `main.py`，提供 `/api/providers` 只读 Provider catalog
- 新增 `provider_builtin_metadata.py`，将现有 BT、网盘、RSS 源清单投影为 provider metadata，不初始化具体 provider
- `/api/providers` 读取现有搜索/网盘源配置覆盖项，保持 enabled/proxy 与旧源管理开关一致
- 新增 `test_provider_api.py`、`test_provider_contracts.py`、`test_provider_registry.py`

**保持不变**:
- 未迁移 `bt_scraper_*`、`pan_scraper_*`、`rss_source_*`
- 未修改搜索评分、过滤、排序、订阅匹配和下载状态机
- 默认 `ProviderRegistry` 不注册具体 provider，静态 metadata 仅在 API 兼容输出层聚合

**验证**:
- `python -X utf8 -m pytest test_provider_api.py test_provider_contracts.py test_provider_registry.py`
- `python -X utf8 -m pytest test_code_split.py::test_main_app_routes`
