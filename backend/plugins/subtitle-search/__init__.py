"""字幕搜索与下载插件。

提供 assrt.net 字幕搜索和下载功能。
安装后注册 /subtitle/* 路由。
"""

import os
import sys

# 将插件目录加入 sys.path（使 routes.py 能 import 同目录模块）
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)


def register(ctx):
    """插件注册入口"""
    from assrt_client import AssrtClient
    from subtitle_routes import router, set_client

    # 从系统配置获取 assrt token
    token = ctx.get_config("assrt_token", "")
    if not token:
        ctx.logger.warning("[subtitle-search] 未配置 assrt_token，字幕搜索不可用")
        return

    # 初始化客户端
    proxy = ctx.get_proxy()
    client = AssrtClient(token=token, proxy=proxy)
    set_client(client)

    # 注册路由
    ctx.register_router(router, tags=["subtitle"])
    ctx.logger.info("[subtitle-search] 字幕搜索插件已加载")


def unregister():
    """插件卸载"""
    pass
