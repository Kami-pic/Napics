# 开发日志

> 里程碑归档，记录每个阶段做了什么、为什么这么做、踩了什么坑。只追加，不删除。
> AI 加载项目时读此文件了解版本递进脉络。

---

## 2026-04-15 查漏补缺 — 30 项 Bug 修复 + P2 功能完善
**变更**: 修复用户报告的 30 个 Bug（订阅 tab 高度/BT 搜索不工作/综合推荐匹配错误/封面错位等）；完成 13 项 P2 功能（订阅配置面板/Nyaa RSS/搜索设置面板/日历视图/冷门降权/手动洗版增强等）；新增 4 个前端组件（SearchSettingsPanel/SubscribeConfigModal/SubscribeSourceSelect/rss_source_nyaa）；新增 2 个后端接口（/search/sources GET+PUT）
**架构改动**: 探索二级 tab 从 ExplorePage 移到 DiscoverHeader 统一高度；订阅筛选栏合并到 DiscoverHeader 一行；/search/single 的 skip_filter 模式改为线程池并行调用 5 个直搜源；发现页统一使用 SearchModal 作为搜索下载入口
**决策**: BT 搜索不工作的根因是 /search/single skip_filter 模式只返回 Prowlarr 结果没合并直搜源，改为 ThreadPoolExecutor 并行调用 5 源；综合推荐匹配错误（航海王→跨界电影）通过加严 _is_same_media 解决（短标题完全包含+长标题 70% 重叠）
**踩坑**: 订阅 tab 高度问题反复修了 4 轮（#2/#16/#17/#18），根因是多个 tab 容器高度不统一，最终方案是所有 tab 共用同一个 flex 容器；切换 tab 回顶部不稳定需要 setTimeout 50ms 延迟等 DOM 更新完成

## 2026-04-15 TODO 清理 + 5 项功能补完 + AI 规则升级
**变更**: 
- 对照代码逐项校验 6 个 TODO 文件，10 项标记未完成但实际已实现的更正为 ✅
- 实现 5 项真正未完成的功能：SSE 搜索进度(/api/search/stream)、下载完成自动局部刷新(_trigger_local_refresh)、发现页候选面板(ExpandDetail 内嵌 TMDB+豆瓣候选)、榜单 tmdb_id 主动补全(_async_enrich_tmdb_ids)、BT 各源结果数量统计
- AI 规则升级：融入 Karpathy LLM 编码原则，新增最小改动原则(#2)、多步任务计划(#4)、前后端同时验证(#3 强化)
- 测试修复：test 辅助函数改名 run_case 避免 pytest fixture 冲突；requirements.txt 补 pytest
- 技术债务记录：Pydantic V1 迁移、路由文件超长(search.py 507行/discover.py 700+行)、日志迁移
**决策**: AI 规则参考 forrestchang/andrej-karpathy-skills（Karpathy 的 4 原则：Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution），结合项目实际痛点（前端验证遗漏）定制；sub-agent 审查后微调了"手术式修改"的例外条件和"多步任务"的触发范围
**踩坑**: 测试文件中定义 `def test(name, fn)` 辅助函数会被 pytest 误收集为测试用例（name 参数当 fixture 找不到报错），改名为 run_case 解决；`sys.exit(1)` 在模块顶层会在 pytest 收集阶段执行导致 INTERNALERROR，需加 `if __name__ == "__main__"` 守卫

## 2026-04-14 搜索源大扩展（网盘修复 + BT 5 源 + 反爬升级）
**变更**: 网盘搜索修复 rrdynb(CSS选择器重写)+ddys(改JSON API)；BT 新增 5 个直搜源(Bitsearch/磁力熊/XL720/Nyaa/蜜柑)；scraper_base 新增 curl_cffi 浏览器指纹+CF 统一检测；前端 indexer 标签品牌色；蜜柑 RSS 接入订阅框架
**决策**: Bitsearch JSON API 作为欧美片源核心补充（Prowlarr 不可达时的替代）；1337x/TorrentGalaxy CF 高级保护无法绕过，放弃；所有有 CF 风险的爬虫统一启用 curl_cffi；搜索路由用 _merge_bt_extra_sources 统一合并+infohash 去重
**踩坑**: rrdynb 多次搜索触发 CF 限频（临时性，过段时间自动解除）；ddys 已从 WordPress 升级为自建站有 JSON API；Bitsearch HTML 是 JS 渲染但有隐藏的 /api/v1/search JSON API；1337x.is/1337x.so 镜像站能通但数据为空；订阅系统 6 个前端测试因组件改动未同步（📌角标合并文本+operating 选择器偏移），已修复

## 2026-04-14 .kiro 架构重组
**变更**: ai-rules 从 80 行精简到 35 行，project-memory 从 200 行精简到 55 行
**决策**: memory 定位为"跨域知识+核心红线+领域索引"，特定领域拆到独立 knowledge 文件
**新增**: discover-recommend.md、subscribe-system.md、devlog.md；ai-rules 加写入纪律和会话接力规则
**参考**: 综合 Kiro/Gemini/Opus/sub-agent 四方意见，采纳 Keep a Changelog + ADR 的轻量化思路

## 2026-04-13 订阅系统（阶段 3+4 完成）
**变更**: 订阅 CRUD + RSS 框架(Prowlarr源) + 匹配引擎 + 定时调度 + 频率衰减 + 100分制质量评分 + 洗版匹配 + 前端全套 UI + 日历视图
**决策**: 频率衰减策略（前72h每4h → 3-14天每12h → 14-30天每24h → 30天无果暂停），避免无效搜索浪费资源
**踩坑**: 订阅按钮即时反馈需要 localSubscribed 状态，不能等服务端返回；卡片状态标签统一到右下角信息行避免布局冲突

## 2026-04-13 本地媒体感知
**变更**: local_media_matcher.py 三层匹配 + 内存索引 + 异步 TMDB ID 补全
**决策**: 中文匹配用前缀（startswith）而非子串（in），避免"你的名字"误匹配"以你的名字呼唤我"
**踩坑**: height=0 时需从文件名解析分辨率兜底；id_mapping_cache.json 持久化避免重复 API 调用

## 2026-04-12 发现页阶段2（探索筛选+滚动阻尼）
**变更**: 探索页分类筛选（豆瓣/TMDB/Bangumi 三源）、滚动阻尼吸附交互、详情面板外部链接+三源评分
**决策**: 滚动交互放弃 CSS scroll-snap，改用自定义 hook（snap 在动态高度卡片上不稳定）
**踩坑**: Bangumi 评分人数少时排序失真需降权；豆瓣探索 sort=T 数据量不稳定，自动用 sort=U 补位

## 2026-04-12 代码大文件拆分
**变更**: 后端 4 个大文件 + 前端 2 个大组件拆分，67 项回归测试全部通过
**决策**: 所有拆分通过 re-export 保持向后兼容，前端 api.ts 零改动
**踩坑**: 循环依赖通过延迟导入解决（函数内部 import）

## 2026-04-10 发现页重构 + 网盘搜索扩展
**变更**: 多源推荐（豆瓣v2+TMDB+Bangumi）、网盘搜索从 1 源扩展到 4 源（pansearch+pansou+gogopanso+github）
**决策**: 豆瓣用 App API v2 签名鉴权（比 web API 稳定），网盘搜索用通用站点框架方便后续扩展
**踩坑**: pansearch.me 连续搜索被限频；gogopanso 标题有拼音首字母前缀需清洗

## 2026-04-09 后端模块化拆分
**变更**: 旧 main.py（4163 行）拆分为 67 行入口 + 9 个路由模块 + shared.py
**决策**: shared.py 作为唯一单例源，路由层只做参数校验和调用业务层
**踩坑**: 不用 --reload 启动 uvicorn（会导致 import 链路崩溃）

## 2026-04-03 初始版本
**变更**: 项目初始化，包含媒体库管理、刮削、搜索下载、整理替换等核心功能
