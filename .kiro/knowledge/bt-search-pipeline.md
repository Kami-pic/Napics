# BT 搜索流水线

## 架构概览

```
用户输入关键词 (cnName / enName / shadow_name)
    ↓
enhanced_search() ← searcher.py
    ├── 1. 别名解析: AliasResolver → 豆瓣/Bangumi 获取中英日别名
    ├── 2. 回退链搜索: shadow_name → clean_name → cnName → enName
    ├── 3. Prowlarr 调用: ProwlarrClient.search() → 多索引器并发
    └── 4. Bitsearch 补充: BitsearchScraper.search_as_search_results()
    ↓
后处理流水线
    ├── 1. 二次匹配: SecondaryMatcher (标题相似度 + 年份校验)
    ├── 2. 全局过滤: GlobalFilter (must_include / must_exclude)
    ├── 3. 索引器优先级: IndexerPriorityManager (按站点权重排序)
    ├── 4. 综合评分: sort_weights (标题匹配/分辨率/编码/做种/字幕/大小)
    ├── 5. 种子黑名单: TorrentBlacklist (已知无效种子过滤)
    └── 6. infohash 去重: Prowlarr + Bitsearch 结果按 btih 去重
    ↓
前端展示 (SearchModal BT Tab)
    ├── 筛选器: 索引器 / 分辨率 / 来源 / 编码 / 音频 / 大小 / 做种数
    ├── 三行布局: 标题行 + 质量标签行 + 操作行
    └── 操作: 下载到 qB / 复制磁力链接
```

## 搜索词构造规则

- cnName: clean_name 提取中文字符
- enName: shadow_name 去年份去中文 > clean_name 英文部分
- 搜索框默认: cnName + enName (相同时只用 cn)
- 回退链: shadow_name → clean_name → 原始 query

## 关键模块

| 模块 | 文件 | 职责 |
|---|---|---|
| Prowlarr 客户端 | searcher.py | 调用 Prowlarr API, 解析种子结果 |
| Bitsearch 爬虫 | bt_scraper_bitsearch.py | JSON API 搜索, 欧美片源补充, curl_cffi+代理 |
| 磁力熊 爬虫 | bt_scraper_cilixiong.py | 中文磁力链接源, 直连 |
| XL720 爬虫 | bt_scraper_xl720.py | 中文磁力链接源, 直连, 响应慢 |
| Nyaa 爬虫 | bt_scraper_nyaa.py | 日文/英文动画站, HTML 解析, curl_cffi+代理 |
| 蜜柑 爬虫 | bt_scraper_mikan.py | 中文字幕组 RSS, curl_cffi+代理 |
| YTS 爬虫 | bt_scraper_yts.py | 电影专站 JSON API, 小体积 YIFY 编码, 代理, 主域名 yts.am |
| LimeTorrents 爬虫 | bt_scraper_limetorrents.py | 综合站 HTML 爬虫, 代理, 站点 CF 保护严格默认禁用 |
| ACG.RIP 爬虫 | bt_scraper_acgrip.py | 动画字幕组站 HTML 爬虫, 直连, 无做种数信息 |
| Bangumi Moe 爬虫 | bt_scraper_bangumi_moe.py | 动画字幕组站 JSON API (v2), 直连, 无做种数信息 |
| 别名解析 | alias_resolver.py | 豆瓣/Bangumi 获取多语言别名 |
| 二次匹配 | secondary_matcher.py | 标题相似度过滤, 防止误匹配 |
| 全局过滤 | global_filter.py | 关键词黑白名单 |
| 质量解析 | quality_parser.py | 从标题提取分辨率/编码/来源/字幕 |
| 索引器管理 | indexer_priority_manager.py | 站点优先级和权重 |
| 种子黑名单 | torrent_blacklist.py | 无效种子记录 |

## 评分权重 (可配置)

| 维度 | 默认权重 | 说明 |
|---|---|---|
| title_match | 0.30 | 标题匹配度 |
| resolution_upgrade | 0.25 | 分辨率提升 |
| codec_match | 0.15 | 编码偏好匹配 |
| seeder_health | 0.15 | 做种健康度 |
| chinese_sub | 0.10 | 中文字幕 |
| size_reasonable | 0.05 | 大小合理性 |
