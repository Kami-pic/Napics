"""
NAS Video Upgrader API — 模块化入口
路由按业务域拆分到 routes/ 目录下。
"""
import os
import sys

# 确保 backend/ 在 sys.path
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Windows stdout 编码修复（只做一次，shared.py 也有但会检查）
if sys.platform == 'win32':
    try:
        import io
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from routes.auth import router as auth_router
from routes.config import router as config_router
from routes.discover import router as discover_router
from routes.filesystem import router as filesystem_router
from routes.download import router as download_router
from routes.library import router as library_router
from routes.library_sync import router as library_sync_router
from routes.library_tree import router as library_tree_router
from routes.library_crud import router as library_crud_router
from routes.library_clean_name import router as library_clean_name_router
from routes.library_completeness import router as library_completeness_router
from routes.organize import router as organize_router
from routes.rename import router as rename_router
from routes.organize_stream import router as organize_stream_router
from routes.relocate import router as relocate_router
from routes.analyze import router as analyze_router
from routes.scrape import router as scrape_router
from routes.scrape_execute import router as scrape_execute_router
from routes.media_info import router as media_info_router
from routes.media_detail import router as media_detail_router
from routes.poster import router as poster_router
from routes.search import router as search_router
from routes.search_single import router as search_single_router
from routes.subscribe import router as subscribe_router
from routes.system import router as system_router
from routes.tools import router as tools_router
from providers import router as providers_router
from routes.plugins import router as plugins_router

app = FastAPI(title='NAS Video Upgrader API')

# SSE 流式路由：gzip 会缓冲输出、破坏实时进度推送，必须排除。
# 新增 StreamingResponse(media_type="text/event-stream") 的路由时要同步加到这里。
_SSE_PATHS = (
    '/scan',
    '/sync',
    '/batch-search',
    '/organize/full-stream',
    '/api/search/stream',
)


class ConditionalGZipMiddleware(GZipMiddleware):
    """按路径条件启用 gzip：媒体库等大 JSON 响应压缩，SSE 流式响应透传"""

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'http' and scope.get('path', '').startswith(_SSE_PATHS):
            return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)


# ── 访问控制 ──
# 不设访问密码时完全不生效（现有部署升级后行为不变）。
# 必须在后端做：只在前端路由上加门的话，直接打 /backend/fs/list 就绕过了。
#
# 白名单只包含"没有它就设不了密码 / 登不了录"的路径，以及 API 文档。
_AUTH_FREE_PREFIXES = (
    '/auth/',
    '/docs',
    '/redoc',
    '/openapi.json',
)

# 健康检查必须免鉴权：Dockerfile 的 HEALTHCHECK 和 entrypoint 的就绪探测都打这里，
# 拦下来会让容器在启用访问密码后被判成不健康、反复重启。
# 这两个端点只返回固定字符串，不泄漏任何信息。
_AUTH_FREE_EXACT = ('/', '/healthz')


class AccessControlMiddleware:
    """纯 ASGI 中间件，不用 BaseHTTPMiddleware。

    后者会把响应包一层 memory stream 转发，对 SSE 的实时性有已知风险；
    而这个项目的扫描 / 同步 / 搜索全靠 SSE 推进度，不能冒这个险。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            return await self.app(scope, receive, send)

        from starlette.datastructures import Headers
        from starlette.responses import JSONResponse
        from http.cookies import SimpleCookie
        from core.access_guard import SESSION_COOKIE, verify_token
        from shared import config_m

        config = config_m.config
        if not config.access_password_hash:
            return await self.app(scope, receive, send)

        path = scope.get('path', '')
        # CORS 预检不带 cookie，拦下来会让跨源请求全部失败
        if scope.get('method') == 'OPTIONS':
            return await self.app(scope, receive, send)
        if path in _AUTH_FREE_EXACT or path.startswith(_AUTH_FREE_PREFIXES):
            return await self.app(scope, receive, send)

        cookie_header = Headers(scope=scope).get('cookie', '')
        jar = SimpleCookie()
        try:
            jar.load(cookie_header)
        except Exception:
            jar = SimpleCookie()
        morsel = jar.get(SESSION_COOKIE)
        if verify_token(morsel.value if morsel else '', config.access_token_secret):
            return await self.app(scope, receive, send)

        response = JSONResponse({'detail': '未授权，请先输入访问密码'}, status_code=401)
        return await response(scope, receive, send)


app.add_middleware(AccessControlMiddleware)


# 先注册 gzip，再注册 CORS，使 CORS 处于最外层
app.add_middleware(ConditionalGZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# 注册所有路由
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(discover_router)
app.include_router(filesystem_router)
app.include_router(download_router)
app.include_router(library_router)
app.include_router(library_sync_router)
app.include_router(library_tree_router)
app.include_router(library_crud_router)
app.include_router(library_clean_name_router)
app.include_router(library_completeness_router)
app.include_router(organize_router)
app.include_router(rename_router)
app.include_router(organize_stream_router)
app.include_router(relocate_router)
app.include_router(analyze_router)
app.include_router(scrape_router)
app.include_router(scrape_execute_router)
app.include_router(media_info_router)
app.include_router(media_detail_router)
app.include_router(poster_router)
app.include_router(search_router)
app.include_router(search_single_router)
app.include_router(subscribe_router)
app.include_router(system_router)
app.include_router(tools_router)
app.include_router(providers_router)
app.include_router(plugins_router)


@app.get('/')
def read_root():
    return {'message': 'NAS Video Upgrader API is running'}


@app.get('/healthz')
def healthz():
    """存活探测。免鉴权（见 _AUTH_FREE_EXACT），只返回固定内容。"""
    return {'status': 'ok'}


@app.on_event("startup")
def startup_event():
    """后端启动时初始化插件系统、订阅调度器和文件夹监控"""
    # 加载已安装的插件（注册 provider 到 plugin_context）
    try:
        from routes.plugins import _get_plugin_manager
        from shared import config_m
        pm = _get_plugin_manager()
        pm.load_installed_plugins(config_m.config.installed_plugins)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Main] 插件加载失败: {e}")

    # 挂载插件注册的路由
    try:
        from plugin_context import get_plugin_routers
        for plugin_id, router_entries in get_plugin_routers().items():
            for entry in router_entries:
                kwargs = {}
                if entry.get("prefix"):
                    kwargs["prefix"] = entry["prefix"]
                if entry.get("tags"):
                    kwargs["tags"] = entry["tags"]
                app.include_router(entry["router"], **kwargs)
                import logging
                logging.getLogger(__name__).info(
                    f"[Main] 挂载插件路由: {plugin_id} prefix={entry.get('prefix', '')!r}"
                )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Main] 插件路由挂载失败: {e}")

    try:
        from routes.subscribe import _get_scheduler
        _get_scheduler()  # 懒加载 + start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Main] 订阅调度器启动失败: {e}")

    # 启动文件夹监控定时器
    try:
        from plugin_guard import has_any_download_backend
        from shared import config_m
        watch_dirs = config_m.config.download_watch_dirs or []
        if watch_dirs and not has_any_download_backend():
            import threading
            from folder_watcher import FolderWatcher
            watcher = FolderWatcher(watch_dirs)
            def _watch_loop():
                import time
                while True:
                    time.sleep(60)
                    try:
                        new_items = watcher.scan()
                        if new_items:
                            import logging
                            logging.getLogger("folder_watcher").info(f"[FolderWatcher] 检测到 {len(new_items)} 个新项，待整理")
                            # TODO: 创建 DownloadTask(status=completed, channel="watch") 并触发归位
                    except Exception as e:
                        import logging
                        logging.getLogger("folder_watcher").error(f"[FolderWatcher] 扫描异常: {e}")
            threading.Thread(target=_watch_loop, daemon=True, name="folder-watcher").start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Main] 文件夹监控启动失败: {e}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=8001, reload=False)
