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

from routes.config import router as config_router
from routes.discover import router as discover_router
from routes.download import router as download_router
from routes.library import router as library_router
from routes.organize import router as organize_router
from routes.rename import router as rename_router
from routes.organize_stream import router as organize_stream_router
from routes.relocate import router as relocate_router
from routes.analyze import router as analyze_router
from routes.scrape import router as scrape_router
from routes.media_info import router as media_info_router
from routes.poster import router as poster_router
from routes.search import router as search_router
from routes.subscribe import router as subscribe_router
from routes.system import router as system_router
from routes.tools import router as tools_router
from providers import router as providers_router
from routes.plugins import router as plugins_router

app = FastAPI(title='NAS Video Upgrader API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# 注册所有路由
app.include_router(config_router)
app.include_router(discover_router)
app.include_router(download_router)
app.include_router(library_router)
app.include_router(organize_router)
app.include_router(rename_router)
app.include_router(organize_stream_router)
app.include_router(relocate_router)
app.include_router(analyze_router)
app.include_router(scrape_router)
app.include_router(media_info_router)
app.include_router(poster_router)
app.include_router(search_router)
app.include_router(subscribe_router)
app.include_router(system_router)
app.include_router(tools_router)
app.include_router(providers_router)
app.include_router(plugins_router)


@app.get('/')
def read_root():
    return {'message': 'NAS Video Upgrader API is running'}


@app.on_event("startup")
def startup_event():
    """后端启动时初始化订阅调度器和文件夹监控"""
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
    uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=False)
