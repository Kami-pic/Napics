# 开发日志

> 里程碑归档，记录每个阶段做了什么、为什么这么做、踩了什么坑。只追加，不删除。
> AI 加载项目时读此文件了解版本递进脉络。

---

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
