# 订阅系统

## 核心架构

- `subscriber.py`：订阅管理器，CRUD + JSON 持久化（subscriptions.json）+ 别名预拉取 + 媒体库查重
- `routes/subscribe.py`：10 个路由（CRUD + check + search + sources 管理），懒加载单例

## 数据模型

- Subscription（含 EpisodeInfo 指纹对象），电影用 "0" 作 key
- downloaded_episodes 用对象结构存储指纹（info_hash/title/quality_tag/source/channel/task_id/timestamp）
- DownloadTask 新增 subscription_id + subscription_episode 字段（订阅→下载→回调纽带）
- 状态机：active ↔ paused，电影下载完成 → completed，剧集全部集数下载完成 → completed

## RSS 订阅框架

- `rss_source_base.py`：RSS 源基类 + RSSItem 标准化结构 + 集号/季号提取工具
- `rss_source_prowlarr.py`：Prowlarr 源（第一个可用源），Search Group 多词并查
- `rss_matcher.py`：匹配引擎（质量过滤 + 关键词过滤 + 集数匹配 + 指纹去重 + 整季包识别）
- `rss_engine.py`：RSSSourceManager（源注册/启用/禁用）+ SubscriptionScheduler（定时调度+频率衰减）
- 频率衰减：前72h每4h → 3-14天每12h → 14-30天每24h → 30天无果自动暂停
- 新增源只需实现 RSSSourceBase 并注册，不改框架代码

## 洗版机制

- `rss_matcher` 支持 best_version 洗版模式
- `rss_engine._select_best_version()` 按集比较质量分数
- 质量评分基准见 project-memory.md 的"质量评分体系"

## 媒体库联动

- 新增剧集订阅时自动扫描已有集数，填充 downloaded_episodes（source="local"）
- `_scan_local_episodes` + `_extract_episode_from_filename`
- `GET /subscribe/calendar`：从 TMDB 拉剧集播出日期，返回时间线

## 前端

- useSubscriptions hook、ExpandDetail 订阅按钮（localSubscribed 即时反馈）
- SubscribePanel 侧边抽屉 + SubscribeInline 内嵌列表（发现页订阅tab）
- FoundResourcesList 资源列表（标题+质量+大小+做种数+下载按钮）
- 推荐/探索/搜索三个场景统一支持订阅按钮+卡片角标
- 卡片状态标签统一到右下角信息行（半透明样式，合并标签：✓已有·订阅 / ↑升级·订阅）
- 一级tab点击+搜索框聚焦时自动置顶到发现页
- api.ts 11 个订阅 API 函数（含源管理+日历）
