"""BT 直搜源包插件 — 内置 12 个直搜源。

这是一个内置插件示例，展示如何通过 register(ctx) 接口注册搜索源。
第三方开发者可以参考此文件的结构来开发自己的搜索源插件。
"""


def register(ctx):
    """插件注册入口 — 系统安装插件时自动调用。

    内置直搜源通过 scraper_class 方式注册，系统自动处理代理/缓存/重试。
    """
    # 内置源不在此处注册（它们通过 bt_search_provider_factory 兼容层加载）
    # 此文件仅作为第三方插件的参考模板
    ctx.logger.info("BT 直搜源包已加载（内置源通过兼容层注册）")


def unregister():
    """插件卸载时调用"""
    pass
