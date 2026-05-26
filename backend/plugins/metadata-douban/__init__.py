"""豆瓣元数据插件。

安装后提供：中文元数据补充（评分、简介、演员信息）。
"""


def register(ctx):
    """注册豆瓣元数据源"""
    ctx.logger.info("豆瓣元数据源已加载")


def unregister():
    """卸载时注销"""
    pass
