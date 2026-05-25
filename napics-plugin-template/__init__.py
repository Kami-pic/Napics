"""我的插件 — 自定义搜索源示例。

修改此文件实现你的搜索逻辑，然后打包为 zip 发布。
"""

from napics_sdk import SearchCandidate


def register(ctx):
    """插件注册入口 — napics 启动时自动调用。

    参数:
        ctx: PluginContext 实例，提供系统能力（日志、配置、代理、ScraperBase 等）
    """

    def my_search(keyword: str, max_results: int) -> list:
        """搜索函数 — 返回 SearchCandidate 列表。

        参数:
            keyword: 搜索关键词
            max_results: 最大返回数量

        返回:
            List[SearchCandidate]
        """
        import requests

        proxy = ctx.get_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None

        try:
            resp = requests.get(
                f"https://api.example.com/search?q={keyword}&limit={max_results}",
                timeout=15,
                proxies=proxies,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            ctx.logger.warning(f"搜索失败: {e}")
            return []

        results = []
        for item in resp.json().get("results", []):
            results.append(SearchCandidate(
                title=item["title"],
                downloadUrl=item.get("magnet", ""),
                sizeGb=item.get("size_gb", 0),
                seeders=item.get("seeders", 0),
                leechers=item.get("leechers", 0),
                providerId="my_source",
                indexer="my_source",
                infoUrl=item.get("url", ""),
            ))

        return results[:max_results]

    ctx.register_search_provider(
        provider_id="my_source",
        name="我的搜索源",
        search_fn=my_search,
        supports_proxy=True,
        capabilities=["keyword_en", "keyword_cn"],
        description="一个自定义搜索源示例",
    )


def unregister():
    """插件卸载时调用（可选）— 清理资源"""
    pass
