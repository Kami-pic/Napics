"""订阅追更插件。

安装后提供：RSS 定时轮询 + 自动下载新集。
"""


def register(ctx):
    """注册订阅追更功能"""
    ctx.logger.info("订阅追更功能已加载")


def unregister():
    """卸载时注销"""
    pass
