"""示例第三方搜索源插件。

展示如何用最少的代码接入一个自定义 BT 搜索源。
第三方开发者可以复制此目录作为起点。
"""

from provider_models import SearchCandidate


def register(ctx):
    """插件注册入口"""

    def example_search(keyword: str, max_results: int) -> list:
        """示例搜索函数 — 返回模拟数据"""
        # 实际开发中这里是 HTTP 请求逻辑
        ctx.logger.info(f"示例源搜索: {keyword}")
        return [
            SearchCandidate(
                title=f"[ExampleSource] {keyword} - 1080p BluRay x265",
                downloadUrl=f"magnet:?xt=urn:btih:{'a' * 40}&dn={keyword}",
                sizeGb=4.2,
                seeders=100,
                leechers=20,
                providerId="example_source",
                indexer="example_source",
            ),
        ]

    ctx.register_search_provider(
        provider_id="example_source",
        name="示例源",
        search_fn=example_search,
        capabilities=["keyword_en", "keyword_cn"],
        description="第三方插件开发示例",
    )


def unregister():
    """插件卸载时清理"""
    pass
