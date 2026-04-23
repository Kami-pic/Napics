---
name: scraping-anti-bot
description: >
  爬虫与反爬通用模式：ScraperBase 继承体系 + 代理分配 + 限频退避 + CF 检测 + curl_cffi。
  Use when adding new scraper sources, debugging 429/CF blocks, adjusting retry/delay strategies,
  or implementing new scraper base features.
  Do NOT use for search orchestration (use L5 multi-source-search).
---

# L6 爬虫与反爬

> 15+ 个爬虫源的共性模式。新增源时继承 ScraperBase 即可获得全套反爬能力。

## ScraperBase 继承体系

```python
class ScraperBase:
    def __init__(self, proxy=None, cache_ttl=600,
                 use_curl_cffi=False, impersonate="chrome131"):
        # proxy: HTTP 代理地址（由 get_source_proxy 按源决定）
        # cache_ttl: 结果缓存秒数（默认 10 分钟）
        # use_curl_cffi: 是否启用 curl_cffi 绕 CF
        # impersonate: curl_cffi 浏览器指纹（默认 chrome131）

    # 子类必须实现
    def search(self, keyword: str) -> List: ...

    # 基类提供的能力
    def request_with_backoff(url, method, timeout, **kwargs)
    def random_delay(min_s, max_s)
    def get_cached(keyword) / set_cached(keyword, results)
    def is_cf_blocked(response) -> bool
    def warm_up() -> None  # 预热首页获取 cookie，默认空实现
```

## 代理分配机制

每个源的代理由 `search_service.get_source_proxy(source_name)` 统一决定：

1. `BT_SOURCE_DEFAULTS[source].needs_proxy` 定义默认值
2. `config.bt_search_sources` 可按源覆盖（新格式 `{"proxy": false}`）
3. 最终返回 `config.http_proxy` 或 `None`

| 源 | 默认代理 | 原因 |
|---|---|---|
| Bitsearch/Nyaa/蜜柑/YTS/EZTV/动漫花园/1337x | ✅ 走代理 | 海外站点，国内直连不通 |
| 磁力熊/XL720/Bangumi Moe | ❌ 直连 | 国内站点 |
| ACG.RIP | ✅ 走代理 | 直连超时（被墙），默认禁用（TLS 不通） |
| LimeTorrents | ✅ 走代理 | 海外站点（默认禁用，TLS 不通） |
| rrdynb | ❌ 直连 | 国内站点 |
| TMDB/豆瓣 | ✅ 走代理 | 和搜索源共用 config.http_proxy |

用户可在搜索设置页切换每个源的代理开关，持久化到 config.json。

## Cloudflare 保护分级与应对

| CF 等级 | 特征 | curl_cffi 能绕过？ | 应对策略 |
|---|---|---|---|
| 无/低 | 无 CF 或仅频率触发 | ✅ | 正常请求 + 限频即可 |
| 中（TLS 指纹检测） | 特定 impersonate 报 TLS 错误 | ✅ 换指纹 | 换 impersonate（如 chrome120） |
| 高（JS Challenge） | 403 + "Just a moment" 页面 | ❌ | 用镜像站绕过，或放弃 |
| 极高（Turnstile） | 需要人机验证 | ❌ | 需无头浏览器，不适合本项目 |

### 各源 CF 等级实测

| 源 | CF 等级 | impersonate | 备注 |
|---|---|---|---|
| rrdynb | 低（频率触发） | chrome131 + warm_up | 预热首页拿 cookie |
| Bitsearch | 无 | chrome131 | 直接访问 |
| Nyaa | 无 | chrome131 | 直接访问 |
| 动漫花园 | 中（TLS 指纹） | chrome124 | chrome131/120 TLS 报错，指纹动态变化 |
| 1337x 镜像 1337xx.to | 低 | chrome120 | 主站 1337x.to 高级 CF |
| 1337x 主站 1337x.to | 高（JS Challenge） | ❌ 所有指纹 403 | 用镜像站绕过 |
| EZTV 搜索页 | 高（JS Challenge） | ❌ 所有指纹 403 | RSS 端点无 CF |
| LimeTorrents | 极高（TLS 拒绝） | ❌ TLS 报错 | 所有域名不通 |

### impersonate 选择经验

- `chrome131`：默认首选，大部分站点兼容
- `chrome120`：动漫花园/1337x 镜像站需要，对旧 SSL 配置兼容性更好
- 遇到 TLS 报错时依次尝试：chrome120 → chrome124 → chrome131
- 遇到 403 时所有指纹都试过仍 403 → 该站点是高级 JS Challenge，换镜像站

## 镜像站策略

当主站 CF 保护过严时，用镜像站绕过：

| 主站 | 镜像站 | 状态 |
|---|---|---|
| 1337x.to | 1337xx.to | ✅ 可用 |
| YTS yts.mx | yts.am + movies-api.accel.li | ✅ 可用 |

镜像站风险：可能随时失效，需要备用域名列表 + 自动切换。

## 限频策略

| 源 | 策略 | 原因 |
|---|---|---|
| Bitsearch | 缓存 10 分钟 + 请求间延迟 2-4s | 429 限频 |
| rrdynb | warm_up + 请求间延迟 1.5-3s | 多次搜索触发 CF |
| pansearch | 请求间间隔 | 连续搜索被限频 |
| 豆瓣 API v2 | 随机延迟 1-3s + 随机 UA | 防封 |
| XL720 | 超时 12s + 1 次重试 | 响应极慢 |
| 1337x | 详情页并发 max_workers=5 | 需两步请求，控制并发 |

## request_with_backoff 重试机制

```
第 1 次请求 → 失败 → 等 2s
第 2 次请求 → 失败 → 等 4s
第 3 次请求 → 失败 → 抛异常
```

- 默认 max_retries=3, BACKOFF_DELAYS=[2, 4, 8]
- 429/503 状态码：自动重试
- curl_cffi 优先，失败降级到 requests
- 每次重试前轮换 UA

## 结果缓存

- 内存字典 `_cache`，key = `keyword_hash`，value = `(timestamp, results)`
- TTL 默认 600s（10 分钟），可在子类构造时覆盖
- 只缓存有结果的，空结果不缓存

## 新增 BT 直搜源的完整 Checklist

> ⚠️ 每个步骤都必须完成，遗漏任何一个都会导致新源在某些场景下不工作。

### 后端（7 个文件）

- [ ] **bt_scraper_xxx.py**（新建）：继承 ScraperBase，实现 `search_as_search_results()`
  - 构造时传 `use_curl_cffi=True`（有 CF 风险时）+ `impersonate`（按需）
  - 英文站加标题相关性过滤（`_filter_relevant`），防止返回不相关热门内容
- [ ] **shared.py**：加全局变量 + `_get_xxx_scraper()` getter（用 `get_source_proxy` 获取代理）
- [ ] **search_service.py**：
  - `BT_SOURCE_DEFAULTS` 加配置（label/enabled/type/needs_proxy）
  - `_get_scraper_list()` 加注册
  - `max_workers` 按需 +1
- [ ] **search_helpers.py**：`merge_bt_extra_sources` 的 import + scrapers 列表加注册
- [ ] **routes/search.py**：
  - 顶部 `from shared import` 加 getter
  - `search_single_source()` 的 `source_getters` 字典加注册
- [ ] **search_keyword_mapper.py**：
  - `SOURCE_LANG_PRIORITY` 加语言优先级映射
  - `CN_SEASON_SOURCES` 或 `EN_SEASON_SOURCES` 加季号格式

### 前端（3 个文件）

- [ ] **SourceTabs.tsx**：`BT_SOURCE_LABELS` 加中文标签
- [ ] **FilterBar.tsx**：
  - `INDEXER_DOT_COLOR` 加品牌色圆点
  - `INDEXER_TAG_STYLE` 加品牌色标签
  - `NO_SEEDER_INFO_SOURCES` 按需加入（无做种数信息的源）
- [ ] **SearchModal.tsx**：
  - `DIRECT_SOURCES` 集合加入
  - `NO_SEEDER_INFO` 集合按需加入
- [ ] **BtResultCard.tsx**：`DIRECT_SOURCE_NAMES` 集合加入

### 验证

- [ ] 后端单元测试：`search_as_search_results()` 返回正确结果
- [ ] SSE 端到端：`/api/search/stream` 中新源返回 source_done 事件
- [ ] 单源搜索：`/api/search/source?source=xxx` 返回正确结果
- [ ] 前端"全部"Tab：新源结果混入全量列表
- [ ] 前端单源 Tab：切换后显示该源结果
- [ ] 前端品牌色标签正确显示

## 踩坑经验

- yts.mx SSL 不通，用 yts.am 替代 + movies-api.accel.li 备用
- Bangumi Moe API v1 返回 500，v2 才正确（`/api/v2/torrent/search`）
- Bangumi Moe size 字段是字符串（"118.6 GB"）不是字节数
- ACG.RIP 没有磁力链接只有 .torrent 下载链接
- ACG.RIP 直连超时（被墙）、走代理所有指纹 TLS 报错，默认禁用
- LimeTorrents 所有域名 TLS 报错，默认禁用
- 动漫花园 chrome131/120 TLS 报错，chrome124 正常（CF 指纹检测动态变化，需定期验证）
- 1337x 主站所有指纹 403，镜像站 1337xx.to chrome120 正常
- EZTV RSS 端点不支持关键词搜索（返回全站最新），只能按 IMDB ID
- 1337x 磁力链接在详情页，需两步请求（列表→详情），用 ThreadPoolExecutor 并发取磁力
- 1337x 是综合站，搜索结果包含大量不相关内容，必须加标题相关性过滤（_filter_relevant）
- 单源搜索端点 `/api/search/source` 的 enrich_result 必须传 match_names，否则智能过滤对不相关结果失效
- 爬虫单例在首次创建时固定代理配置，改配置后需重启后端
