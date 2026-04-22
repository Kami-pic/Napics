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
    def __init__(self, proxy=None, cache_ttl=600, use_curl_cffi=False):
        # proxy: HTTP 代理地址（需代理的源传入）
        # cache_ttl: 结果缓存秒数（默认 10 分钟）
        # use_curl_cffi: 是否启用 curl_cffi 绕 CF

    # 子类必须实现
    def search(self, keyword: str) -> List: ...

    # 基类提供的能力
    def request_with_backoff(url, method, max_retries, backoff, timeout, **kwargs)
    def random_delay(min_s, max_s)
    def get_cached(keyword) / set_cached(keyword, results)
    def is_cf_blocked(response) -> bool
    def fast_check_url(url, timeout) -> bool
```

## 代理分配规则

| 源类型 | 代理 | 原因 |
|--------|------|------|
| Bitsearch/Nyaa/蜜柑/YTS/LimeTorrents/EZTV/动漫花园 | config.http_proxy | 海外站点，国内直连不通 |
| 磁力熊/XL720/ACG.RIP/Bangumi Moe/rrdynb | 不走代理 | 国内站点或直连可达 |
| TMDB/豆瓣 | config.http_proxy | 和搜索源共用代理 |

## 限频策略

| 源 | 策略 | 原因 |
|---|---|---|
| Bitsearch | 缓存 10 分钟 + 请求间延迟 2-4s | 429 限频 |
| rrdynb | 请求间延迟 1.5-3s | 多次搜索触发 CF |
| pansearch | 请求间间隔 | 连续搜索被限频 |
| 豆瓣 API v2 | 随机延迟 1-3s + 随机 UA | 防封 |
| XL720 | 超时 12s + 1 次重试 | 响应极慢 |

## curl_cffi 使用规则

- 所有有 CF 风险的爬虫必须 `use_curl_cffi=True`
- curl_cffi 模拟浏览器 TLS 指纹，绕过 CF 中低级保护
- `_curl_cffi_request` 在 `request_with_backoff` 内部自动切换
- `is_cf_blocked(response)` 检测 CF 拦截页（403 + 特征 HTML）

## request_with_backoff 重试机制

```
第 1 次请求 → 失败 → 等 backoff 秒
第 2 次请求 → 失败 → 等 backoff*2 秒
第 3 次请求 → 失败 → 返回 None
```

- 默认 max_retries=3, backoff=1.0
- 429 状态码：自动延长等待（backoff * 3）
- CF 拦截：如果未启用 curl_cffi，日志警告并返回 None

## 结果缓存

- 内存字典 `_cache`，key = `keyword_hash`，value = `(timestamp, results)`
- TTL 默认 600s（10 分钟），可在子类构造时覆盖
- 只缓存有结果的，空结果不缓存（避免缓存临时性 0 结果）

## 新增爬虫源的步骤

1. 新建 `bt_scraper_xxx.py` 或 `pan_scraper_xxx.py`
2. 继承 `ScraperBase`，构造时传入 proxy/cache_ttl/use_curl_cffi
3. 实现 `search(keyword)` 返回 `List[SearchResult]` 或 `List[PanResult]`
4. BT 源额外实现 `search_as_search_results(keyword, max_results)` 统一输出格式
5. `shared.py` 加 getter → `search_service.py` 注册 → 前端加标签

## 踩坑经验

- yts.mx SSL 不通，用 yts.am 替代 + movies-api.accel.li 备用
- Bangumi Moe API v1 返回 500，v2 才正确（`/api/v2/torrent/search`）
- Bangumi Moe size 字段是字符串（"118.6 GB"）不是字节数
- ACG.RIP 没有磁力链接只有 .torrent 下载链接
- LimeTorrents 所有域名 CF 保护严格，默认禁用
