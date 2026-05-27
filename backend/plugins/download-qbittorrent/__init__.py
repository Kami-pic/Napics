"""qBittorrent 下载后端插件。

安装后提供：一键 BT 下载、进度追踪、完成后自动整理。
"""


def register(ctx):
    """注册 qBittorrent 下载后端"""
    ctx.logger.info("qBittorrent 下载后端已加载")


def unregister():
    """卸载时注销"""
    pass
