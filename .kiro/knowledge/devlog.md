# 开发日志

> 里程碑归档，记录每个阶段做了什么、为什么这么做、踩了什么坑。只追加，不删除。
> AI 加载项目时读此文件了解版本递进脉络。

---

## 2026-04-16 搜索弹窗全面改造（SSE 并行 + 筛选器 + 设置弹窗）
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
