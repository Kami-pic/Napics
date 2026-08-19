"""Web 播放器插件 — 提供浏览器内视频播放能力。

功能：
- HTTP Range 文件流（支持 mp4 等浏览器原生格式）
- ffmpeg 实时转码/转封装（mkv/ts/avi 等转为 fragmented MP4）
- 外挂字幕检测与格式转换（SRT/ASS/SSA/SUB → WebVTT）
- 内嵌字幕提取（ffmpeg → WebVTT）
- 多音轨列表与切换

系统依赖：ffmpeg / ffprobe（可选，不安装则转码和内嵌字幕功能不可用）
"""

import os
import sys

# 确保插件目录下的 playback 模块可以被导入
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from playback_routes import router


def register(ctx):
    """插件注册入口 — 把播放器路由注册到主应用"""
    ctx.register_router(router, tags=["playback"])
    ctx.logger.info("Web 播放器插件已注册")


def unregister():
    """插件卸载时清理（路由移除需重启生效）"""
    pass
