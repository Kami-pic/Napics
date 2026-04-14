# [TODO] BT/磁力搜索扩展 + 前端多源适配

> 目标：在 Prowlarr 基础上补充 5 个直搜源（Bitsearch/磁力熊/XL720/Nyaa/蜜柑），
> 前端 BT Tab 适配多源显示和筛选，反爬基础设施统一升级。
> 按优先级逐个推进，每个源独立可交付。

---

## 前置：网盘搜索源修复（2026-04-14 已完成）

- [x] `pan_scraper_rrdynb.py` 重写：去掉 cloudscraper 依赖，修复 CSS 选择器（dl.item-third-dl），a 标签+正则双路径提取，非分享链接过滤，启用 curl_cffi
- [x] `pan_scraper_ddys.py` 重写：从 HTML 爬虫改为 JSON API（POST /api/search-netdisk），base64 链接解码，域名从 ddys.pro 更新为 ddys.io
- [x] `shared.py` 启用 rrdynb + ddys（从 False 改为 True）
- [x] 探测并确认暂关源不可修复：慢读(JS渲染)/我能搜(资源太少)/凌风云(JS渲染)/盘搜搜(404)/小白盘(403)/趣盘搜(超时)
- [x] 探测新站：yingso.fun(SPA不可用)/LibVio(不稳定403)/NetflixGC(CF拦截)

---

## 基础设施（已完成）

- [x] `scraper_base.py` 新增 `use_curl_cffi` 选项（模拟浏览器 TLS 指纹绕 CF）
- [x] curl_cffi 未安装时自动降级到 requests
- [x] 缓存 TTL 从 5 分钟提到 10 分钟（减少重复请求触发限频）
- [x] 重试间延迟从 1-2s 提到 2-4s
- [x] `requirements.txt` 补上 beautifulsoup4 / cloudscraper / curl_cffi
- [x] `shared.py` 新增 `_get_bitsearch_scraper()` 单例

---

## 源 1：Bitsearch（欧美片源核心）✅

- [x] 1.1 `bt_scraper_bitsearch.py` — JSON API 搜索（GET /api/v1/search）
- [x] 1.2 curl_cffi + 代理（config.http_proxy）
- [x] 1.3 返回 SearchResult 格式（search_as_search_results）
- [x] 1.4 `routes/search.py` 主搜索 + fallback 都合并 Bitsearch 结果
- [x] 1.5 按 infohash 去重（和 Prowlarr 不重复）
- [x] 1.6 支持中英文搜索、分页（MAX_PAGES=2）

---

## 源 2：磁力熊（国产片补充）

> POST /e/search/index.php → 搜索结果页 → 详情页 /movie/xxxx.html → 磁力链接
> 直连无需代理，中文电影为主。

### 2.1 后端爬虫
- [x] 新建 `bt_scraper_cilixiong.py`，继承 ScraperBase（use_curl_cffi=True）
- [x] POST 搜索：keyboard + classid=1,2 + show=title + tempid=1
- [x] 解析搜索结果页：提取详情页链接（/movie/xxxx.html）+ 标题
- [x] 访问详情页：提取磁力链接（a[href^='magnet:']）
- [x] 从磁力链接提取 infohash、从 dn 参数提取标题
- [x] 输出 SearchResult 格式（search_as_search_results）
- [x] 请求间延迟 2-3s（详情页逐条访问，MAX_DETAIL_PAGES=5）

### 2.2 集成到搜索路由
- [x] `shared.py` 新增 `_get_cilixiong_scraper()` 单例
- [x] `routes/search.py` 合并磁力熊结果（统一 _merge_bt_extra_sources）

---

## 源 3：XL720（国产片补充）

> GET /search/关键词 → 搜索结果页 → 详情页 /thunder/xxxx.html → 磁力+迅雷链接
> 直连无需代理，中文电影/剧集。

### 3.1 后端爬虫
- [x] 新建 `bt_scraper_xl720.py`，继承 ScraperBase（use_curl_cffi=True）
- [x] GET 搜索：/search/关键词
- [x] 解析搜索结果页：提取详情页链接（/thunder/xxxx.html）+ 标题
- [x] 访问详情页：提取磁力链接 + 迅雷链接（thunder://）
- [x] 迅雷链接解码（base64 → magnet）
- [x] 输出 SearchResult 格式
- [x] 请求间延迟 2-3s

### 3.2 集成到搜索路由
- [x] `shared.py` 新增 `_get_xl720_scraper()` 单例
- [x] `routes/search.py` 合并 XL720 结果

---

## 源 4：Nyaa 直搜（动画/日剧核心）

> GET /search?q=关键词&c=0_0&f=0 → HTML 表格 → 磁力链接
> 需代理（config.http_proxy），日本动画/日剧覆盖率极高。
> 绕过 Prowlarr 直连，不受 tun 模式限制。

### 4.1 后端爬虫
- [x] 新建 `bt_scraper_nyaa.py`，继承 ScraperBase（use_curl_cffi=True）
- [x] GET 搜索：https://nyaa.si/?f=0&c=0_0&q=关键词
- [x] 解析 HTML 表格（table.torrent-list tbody tr）
- [x] 提取：标题、磁力链接、大小、做种/下载数、日期、分类
- [x] 分类参数：c=1_2（动画-英文翻译）、c=1_3（动画-非英文）、c=4_0（真人）
- [x] 输出 SearchResult 格式
- [x] 代理走 config.http_proxy

### 4.2 集成到搜索路由
- [x] `shared.py` 新增 `_get_nyaa_scraper()` 单例
- [x] `routes/search.py` 合并 Nyaa 结果

### 4.3 Nyaa RSS 源（接入订阅框架）
- [ ] 新建 `rss_source_nyaa.py`，实现 RSSSourceBase
- [ ] RSS URL：https://nyaa.si/?page=rss&q=关键词&c=0_0&f=0
- [ ] 解析 RSS XML → RSSItem 列表
- [ ] 注册到 RSSSourceManager

---

## 源 5：蜜柑计划 RSS（番剧订阅核心）✅

> 按番剧分组的字幕组聚合站，有 RSS 订阅。
> 需代理，和订阅系统（subscribe-todo）的 B.7 对接。

### 5.1 RSS 源
- [x] 新建 `rss_source_mikan.py`，实现 RSSSourceBase
- [x] 搜索 RSS：https://mikanani.me/RSS/Search?searchstr=关键词
- [x] 番剧 RSS：https://mikanani.me/RSS/Bangumi?bangumiId=xxx（按番剧订阅）
- [x] 解析 RSS XML → RSSItem 列表（标题/磁力/大小/日期/字幕组）
- [x] 从标题提取集号（extract_episode）
- [x] 注册到 RSSSourceManager（routes/subscribe.py）
- [x] 代理走 config.http_proxy

### 5.2 蜜柑搜索（BT Tab 补充）
- [x] 新建 `bt_scraper_mikan.py`，继承 ScraperBase
- [x] 复用 rss_source_mikan 的 RSS 解析逻辑
- [x] 输出 SearchResult 格式

### 5.3 集成
- [x] `shared.py` 新增 `_get_mikan_scraper()` 单例
- [x] `routes/search.py` 合并蜜柑结果（_merge_bt_extra_sources）
- [x] 订阅系统 `routes/subscribe.py` 注册蜜柑 RSS 源

---

## 前端多源适配

> 当前 BT Tab 只显示 Prowlarr 结果，需要适配多源显示和筛选。

### 6.1 索引器筛选增强
- [x] FilterBar 的索引器筛选自动包含新源（bitsearch/cilixiong/xl720/nyaa/mikan）
- [x] 索引器标签颜色区分：Prowlarr 站点用默认色，直搜源用品牌色
  - bitsearch: 蓝色（欧美）
  - cilixiong: 橙色（国产）
  - xl720: 橙色（国产）
  - nyaa: 紫色（动画）
  - mikan: 粉色（番剧）

### 6.2 来源标签显示
- [x] 搜索结果卡片的 indexer 标签增加颜色映射（INDEXER_TAG_STYLE）
- [x] IndexerSelect 下拉列表加品牌色圆点（INDEXER_DOT_COLOR）

### 6.3 搜索状态增强
- [ ] 搜索进度条显示各源状态（Prowlarr ✓ / Bitsearch ✓ / 磁力熊 加载中...）— 后续优化
- [ ] 各源搜索结果数量统计（类似网盘 Tab 的 source_statuses）— 后续优化

### 6.4 搜索源开关（设置页）
- [ ] 设置页新增 BT 搜索源开关（Prowlarr / Bitsearch / 磁力熊 / XL720 / Nyaa / 蜜柑）— 后续优化
- [ ] 开关状态存入 config.json（bt_search_sources）
- [ ] 后端根据开关决定是否调用对应爬虫

---

## 测试

- [x] `test_bt_expand.py` — 23 项集成测试全部通过
  - 反爬基础设施（curl_cffi / CF 检测 / 缓存）
  - 网盘源修复（rrdynb / ddys）
  - BT 直搜源（Bitsearch / 磁力熊 / XL720 / Nyaa / 蜜柑）
  - 蜜柑 RSS 源（XML 解析 / 集号提取）
  - 搜索路由合并（_merge_bt_extra_sources / shared getters）
  - 前端颜色映射（源名一致性）

---

## 反爬机制统一

- [x] scraper_base.py: curl_cffi 浏览器 TLS 指纹（use_curl_cffi=True）
- [x] scraper_base.py: 缓存 TTL 10 分钟 + 重试延迟 2-4s
- [x] rrdynb: 启用 curl_cffi
- [x] bitsearch: 启用 curl_cffi + 代理
- [x] 磁力熊: 启用 curl_cffi（预防 CF 升级）
- [x] XL720: 启用 curl_cffi
- [x] Nyaa: curl_cffi + 代理
- [x] 蜜柑: curl_cffi + 代理
- [x] CF 拦截检测：所有爬虫统一 `is_cf_blocked()` 方法，检测 "Just a moment" / "challenge-platform" / "turnstile"，触发时跳过不阻塞

---

## 技术要点

- 所有直搜源输出统一 SearchResult 格式，和 Prowlarr 结果无缝合并
- 去重统一用 infohash（btih hash 大写比较）
- 直搜源的 download_url 是 magnet: 链接，前端下载逻辑不变（qB 支持 magnet）
- 需要代理的源从 config.http_proxy 读取，和 TMDB 共用同一个代理
- 蜜柑 RSS 同时服务于 BT 搜索（即时搜索）和订阅系统（定时轮询）
- Nyaa RSS 同理，搜索和订阅双用
