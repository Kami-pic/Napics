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
    proxy = ctx.get_proxy()

    # 始终注册路由（token 为空时路由可达但会返回 503 提示配置）
    # 这样用户安装后填 token 不需要重启
    if token:
        client = AssrtClient(token=token, proxy=proxy)
        set_client(client)
        ctx.logger.info("[subtitle-search] 字幕搜索插件已加载")
    else:
        ctx.logger.warning("[subtitle-search] 未配置 assrt_token，安装后请在插件配置中填写")

    # 注册路由（无论 token 是否存在）
    ctx.register_router(router, tags=["subtitle"])


def unregister():
    """插件卸载"""
    pass
