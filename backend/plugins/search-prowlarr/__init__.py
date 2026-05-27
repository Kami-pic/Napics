"""Prowlarr 搜索源插件。

安装后提供：通过 Prowlarr 聚合搜索 BT/PT 索引器。
"""


def register(ctx):
    """注册 Prowlarr 搜索源"""
    ctx.logger.info("Prowlarr 搜索源已加载")


def unregister():
    """卸载时注销"""
    pass
