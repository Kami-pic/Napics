# 第三方插件开发指南

## 快速开始

1. 在 `backend/plugins/` 下创建你的插件目录（如 `my-bt-source/`）
2. 创建 `manifest.json` 声明插件信息
3. 创建 `__init__.py` 实现注册逻辑
4. 重启后端，在插件中心安装即可使用

## 目录结构

```
plugins/
└── my-bt-source/
    ├── manifest.json    # 必须：插件声明
    ├── __init__.py      # 必须：注册入口
    └── scraper.py       # 可选：爬虫实现（可拆分多文件）
```

## manifest.json 格式

```json
{
    "id": "my-bt-source",
    "name": "我的搜索源",
    "version": "1.0.0",
    "description": "一个自定义 BT 搜索源",
    "category": "search",
    "icon": "🔍",
    "requires_config": [],
    "depends_on": [],
    "provides": ["SearchProvider:my_source"],
    "risk_level": "high"
}
```

### 字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| id | ✅ | 唯一标识，小写英文+连字符 |
| name | ✅ | 显示名称 |
| version | ✅ | 语义化版本号 |
| description | | 功能描述 |
| category | ✅ | 分类：search / metadata / rss / download / storage / feature |
| icon | | emoji 图标 |
| requires_config | | 需要的配置项（如 ["my_api_key"]） |
| depends_on | | 依赖的其他插件 ID |
| provides | | 提供的能力声明 |
| risk_level | | low / medium / high |

## __init__.py 注册入口

### 方式一：继承 ScraperBase（推荐）

适合需要 HTTP 请求的搜索源，自动获得缓存、重试、代理、UA 轮换等能力。

```python
def register(ctx):
    \"\"\"插件注册入口\"\"\"
    from searcher import SearchResult

    class MyScraper(ctx.ScraperBase):
        \"\"\"我的 BT 搜索爬虫\"\"\"

        def __init__(self, proxy=None):
            super().__init__(proxy=proxy, use_curl_cffi=True, cache_ttl=600)

        def search_as_search_results(self, keyword, max_results=20):
            \"\"\"搜索并返回结果列表\"\"\"
            # 检查缓存
            cached = self.get_cached(keyword)
            if cached is not None:
                return cached

            # 发起请求（自动重试+退避）
            resp = self.request_with_backoff(
                f"https://example.com/api/search?q={keyword}",
                timeout=15,
            )

            results = []
            for item in resp.json().get("results", []):
                results.append(SearchResult(
                    title=item["title"],
                    size_gb=item.get("size", 0) / (1024**3),
                    indexer="my_source",
                    seeders=item.get("seeders", 0),
                    leechers=item.get("leechers", 0),
                    download_url=item["magnet"],
                    info_url=item.get("url", ""),
                    quality_tag="",
                ))

            # 写入缓存（空结果不缓存）
            self.set_cached(keyword, results)
            return results

    # 注册到系统
    ctx.register_scraper_search_provider(
        provider_id="my_source",
        name="我的源",
        scraper_class=MyScraper,
        supports_proxy=True,
        capabilities=["keyword_en", "keyword_cn", "season_en"],
        description="一个自定义搜索源",
    )


def unregister():
    \"\"\"插件卸载时调用（可选）\"\"\"
    pass
```

### 方式二：直接注册搜索函数

适合简单场景，不需要继承基类。

```python
from provider_models import SearchCandidate

def register(ctx):
    def my_search(keyword: str, max_results: int) -> list:
        \"\"\"搜索函数 — 返回 SearchCandidate 列表\"\"\"
        import requests
        resp = requests.get(f"https://api.example.com/search?q={keyword}")
        results = []
        for item in resp.json():
            results.append(SearchCandidate(
                title=item["title"],
                downloadUrl=item["magnet"],
                sizeGb=item.get("size_gb", 0),
                seeders=item.get("seeders", 0),
                leechers=item.get("leechers", 0),
                providerId="my_source",
                indexer="my_source",
            ))
        return results[:max_results]

    ctx.register_search_provider(
        provider_id="my_source",
        name="我的源",
        search_fn=my_search,
    )
```

### 方式三：注册网盘搜索源

```python
from provider_models import PanSearchCandidate

def register(ctx):
    def my_pan_search(keyword: str, max_results: int) -> list:
        import requests
        resp = requests.get(f"https://pan-api.example.com/search?q={keyword}")
        results = []
        for item in resp.json():
            results.append(PanSearchCandidate(
                title=item["title"],
                shareUrl=item["share_url"],
                panType=item.get("pan_type", "unknown"),
                sourceProviderId="my_pan",
            ))
        return results[:max_results]

    ctx.register_pan_search_provider(
        provider_id="my_pan",
        name="我的网盘源",
        search_fn=my_pan_search,
    )
```

## PluginContext API

| 方法 | 说明 |
|------|------|
| `ctx.logger` | 日志器，直接使用 |
| `ctx.get_config(key, default)` | 读取系统配置 |
| `ctx.get_proxy()` | 获取代理地址 |
| `ctx.ScraperBase` | 爬虫基类，可继承 |
| `ctx.register_search_provider(...)` | 注册 BT 搜索源（函数式） |
| `ctx.register_pan_search_provider(...)` | 注册网盘搜索源 |
| `ctx.register_scraper_search_provider(...)` | 注册爬虫搜索源（推荐） |

## ScraperBase 提供的能力

继承 `ctx.ScraperBase` 后自动获得：

- **请求重试**：`request_with_backoff(url, timeout=10)` — 429/503/超时自动重试 3 次
- **结果缓存**：`get_cached(keyword)` / `set_cached(keyword, results)` — 内存缓存 10 分钟
- **随机延迟**：`random_delay(min_s, max_s)` — 防频率限制
- **UA 轮换**：每次请求自动切换 User-Agent
- **代理支持**：构造时传 `proxy` 参数
- **CF 绕过**：`use_curl_cffi=True` 模拟浏览器 TLS 指纹
- **标题清洗**：`self.clean_title(raw)` / `self.parse_resolution(title)`

## 注意事项

1. 插件代码不要直接 `from shared import ...`，通过 `ctx` 获取系统能力
2. 搜索函数必须是线程安全的（会被并发调用）
3. 网络请求务必设置 timeout，建议 10-15 秒
4. 空结果不要缓存，避免临时故障导致长时间无结果
5. `provider_id` 必须全局唯一，建议用 `作者名_源名` 格式
6. 插件目录名和 manifest.id 保持一致


## 方式四：注册 RSS 源

RSS 源插件用于订阅追更功能，定时拉取新内容。

```python
import importlib
import os
import sys

# 将 sources/ 目录加入 sys.path（如果有多个源文件）
_SOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources")
if _SOURCES_DIR not in sys.path:
    sys.path.insert(0, _SOURCES_DIR)

def register(ctx):
    """注册 RSS 源到 plugin registry。"""
    from plugin_context import _plugin_providers

    # 方式 A：直接注册源类
    from my_rss_source import MyRSSSource

    _plugin_providers["rss_my_source"] = {
        "type": "rss_source",
        "source_id": "my_source",
        "source_class": MyRSSSource,
        "plugin_id": "my-rss-plugin",
    }

    ctx.logger.info("我的 RSS 源已注册")


def unregister():
    pass
```

### RSS 源类实现

RSS 源需要继承 `RSSSourceBase`：

```python
# sources/my_rss_source.py
from rss_source_base import RSSSourceBase

class MyRSSSource(RSSSourceBase):
    """我的 RSS 源"""

    source_id = "my_source"
    source_name = "我的源"
    base_url = "https://example.com/rss"

    def fetch_items(self, keyword: str, limit: int = 50) -> list:
        """拉取 RSS 条目。

        返回字典列表，每个字典包含：
        - title: 标题
        - download_url: 下载链接（magnet 或 torrent URL）
        - published_at: 发布时间（datetime 或 ISO 字符串）
        - size_gb: 文件大小（GB）
        - episode: 集数（可选）
        - season: 季数（可选）
        """
        import requests
        resp = requests.get(f"{self.base_url}?q={keyword}", timeout=15)
        # 解析 RSS XML 或 JSON...
        items = []
        for entry in self._parse_feed(resp.text):
            items.append({
                "title": entry["title"],
                "download_url": entry["link"],
                "published_at": entry.get("pubDate"),
                "size_gb": entry.get("size", 0) / (1024**3),
            })
        return items[:limit]
```

---

## 插件发布与分发

### 打包为 zip

```bash
# 在插件目录的父目录执行
zip -r my-plugin.zip my-plugin/
```

zip 包结构：
```
my-plugin.zip
└── my-plugin/
    ├── manifest.json
    ├── __init__.py
    └── sources/          # 可选：多文件时放这里
        └── scraper.py
```

### 创建插件源 index.json

```json
{
    "name": "我的插件源",
    "version": "1.0.0",
    "description": "自定义插件集合",
    "homepage": "https://github.com/你的用户名/my-plugins",
    "plugins": [
        {
            "id": "my-plugin",
            "name": "我的插件",
            "version": "1.0.0",
            "description": "一个自定义搜索源",
            "category": "search",
            "icon": "🔍",
            "risk_level": "low",
            "depends_on": [],
            "download_url": "https://github.com/你的用户名/my-plugins/releases/download/v1.0.0/my-plugin.zip",
            "sha256": "用 sha256sum my-plugin.zip 计算",
            "min_napics_version": "1.0.0"
        }
    ]
}
```

### 发布到 GitHub

1. 创建 GitHub 仓库，放入 `index.json` 和插件源代码
2. 创建 Release，上传 zip 包
3. 用户在 napics 插件中心 → 第三方插件源 → 添加你的仓库 URL

### 使用 napics-plugin-sdk 开发

```bash
pip install napics-plugin-sdk
```

SDK 提供类型提示和数据模型，方便 IDE 自动补全：

```python
from napics_sdk import SearchCandidate, PanSearchCandidate, RSSCandidate
from napics_sdk import ProviderKind, ProviderMetadata
```

---

## 插件模板

快速开始：使用 [napics-plugin-template](https://github.com/nicq/napics-plugin-template) 模板仓库。

```bash
# 克隆模板
git clone https://github.com/nicq/napics-plugin-template my-plugin
# 修改 manifest.json 和 __init__.py
# 打包发布
```
