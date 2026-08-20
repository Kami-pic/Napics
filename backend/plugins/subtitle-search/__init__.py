"""字幕搜索与下载插件。

三个源：assrt.net（中文主力）+ SubHD（中文补充）+ SubDL（英文/小语种回退）。
安装后注册 /subtitle/* 路由。
"""

import os
import sys

# 插件目录加入 sys.path，使内部模块可以互相 import
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)


def register(ctx):
    """插件注册入口"""
    import subtitle_search_service as service
    from assrt_client import AssrtClient
    from subdl_client import SubdlClient
    from subhd_client import SubhdClient
    from subtitle_routes import router

    proxy = ctx.get_proxy()
    assrt_token = (ctx.get_config("assrt_token", "") or "").strip()
    subdl_key = (ctx.get_config("subdl_api_key", "") or "").strip()

    # 有凭据的源预建客户端；没有的留空，请求时按最新配置再尝试
    if assrt_token:
        service.set_assrt_client(AssrtClient(token=assrt_token, proxy=proxy))
    if subdl_key:
        service.set_subdl_client(SubdlClient(api_key=subdl_key, proxy=proxy))
    # SubHD 无需凭据
    service.set_subhd_client(SubhdClient(proxy=proxy))

    enabled = ["SubHD"]
    if assrt_token:
        enabled.insert(0, "assrt")
    if subdl_key:
        enabled.append("SubDL")
    ctx.logger.info(f"[subtitle-search] 已加载，可用源: {', '.join(enabled)}")
    if not assrt_token:
        ctx.logger.warning("[subtitle-search] 未配置 assrt_token，中文主力源不可用")

    # 路由始终注册：先安装后填凭据也能直接生效，不需要重启
    ctx.register_router(router, tags=["subtitle"])


def unregister():
    """插件卸载：清空客户端单例"""
    try:
        import subtitle_search_service as service
        service.reset_clients()
    except Exception:
        pass
