# napics-plugin-sdk

Napics 插件开发 SDK — 提供 Provider 协议定义、数据模型和运行时上下文。

## 安装

```bash
pip install napics-plugin-sdk
```

## 快速开始

```python
from napics_sdk import SearchCandidate, PanSearchCandidate

def register(ctx):
    """插件注册入口 — napics 启动时自动调用"""

    def my_search(keyword: str, max_results: int) -> list:
        import requests
        resp = requests.get(f"https://api.example.com/search?q={keyword}")
        results = []
        for item in resp.json():
            results.append(SearchCandidate(
                title=item["title"],
                downloadUrl=item["magnet"],
                sizeGb=item.get("size_gb", 0),
                seeders=item.get("seeders", 0),
                providerId="my_source",
                indexer="my_source",
            ))
        return results[:max_results]

    ctx.register_search_provider(
        provider_id="my_source",
        name="我的搜索源",
        search_fn=my_search,
    )
```

## 包含内容

- **数据模型**：`SearchCandidate`、`PanSearchCandidate`、`RSSCandidate`、`MetadataCandidate` 等
- **枚举类型**：`ProviderKind`、`ProviderRiskLevel`、`ProviderHealthStatus`
- **运行时上下文**：`ProviderContext`（配置、日志、缓存、HTTP 客户端）

## 文档

完整开发指南见 [PLUGIN_DEV_GUIDE.md](https://github.com/nicq/napics/blob/main/backend/plugins/PLUGIN_DEV_GUIDE.md)

## License

MIT
