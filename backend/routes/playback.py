"""播放路由：提供 HTTP Range 文件流，供前端播放器拉取视频数据。"""
import os
import logging
from urllib.parse import quote

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, Response

from shared import config_m, guard_path

logger = logging.getLogger(__name__)
router = APIRouter()


@router.head("/playback/stream")
@router.get("/playback/stream")
def stream_file(path: str = Query(..., description="视频文件路径"), request: Request = None):
    """HTTP Range 文件流端点。

    支持 Range 请求，供前端 libav-wasm 播放器按需拉取文件片段。
    """
    guard_path(path, "流式播放")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    file_size = os.path.getsize(path)
    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".ts": "video/mp2t",
        ".m4v": "video/mp4",
        ".mov": "video/quicktime",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
        ".webm": "video/webm",
        ".rmvb": "application/vnd.rn-realmedia-vbr",
        ".rm": "application/vnd.rn-realmedia",
    }
    content_type = mime_map.get(ext, "application/octet-stream")

    # HEAD 请求：只返回文件元信息
    if request and request.method == "HEAD":
        return Response(
            content=b"",
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            },
        )

    # 解析 Range 请求头
    range_header = request.headers.get("range") if request else None

    if range_header:
        # 格式：bytes=start-end
        try:
            range_spec = range_header.replace("bytes=", "").strip()
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            start, end = 0, file_size - 1

        # 限制范围
        start = max(0, min(start, file_size - 1))
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def range_iterator(chunk_size: int = 1024 * 1024):
            with open(path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            range_iterator(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            },
        )

    # 非 Range 请求：返回完整文件
    def file_iterator(chunk_size: int = 1024 * 1024):
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/playback/transcode")
def transcode_file(path: str = Query(..., description="视频文件路径")):
    """用 ffmpeg 实时转封装/转码为 mp4 流。

    视频编码 copy（不重编码），音频转为 AAC，容器格式转为 fragmented MP4。
    支持 mkv/ts/avi/wmv/flv 等浏览器不能直接播放的格式。
    """
    import subprocess

    guard_path(path, "转码播放")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # ffmpeg 命令：输入文件 → 视频 copy + 音频 aac → fragmented mp4 输出到 stdout
    cmd = [
        "ffmpeg",
        "-i", path,
        "-c:v", "copy",         # 视频不重编码
        "-c:a", "aac",          # 音频统一转 AAC（兼容浏览器）
        "-ac", "2",             # 立体声（浏览器兼容性最好）
        "-movflags", "frag_keyframe+empty_moov+faststart",
        "-f", "mp4",            # 输出 mp4 容器
        "-v", "quiet",          # 静默
        "pipe:1",               # 输出到 stdout
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffmpeg 未安装")

    def stream_output():
        try:
            while True:
                chunk = process.stdout.read(1024 * 256)  # 256KB chunks
                if not chunk:
                    break
                yield chunk
        finally:
            process.stdout.close()
            process.wait()

    return StreamingResponse(
        stream_output(),
        media_type="video/mp4",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
        },
    )


# ── 字幕相关 ──

SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}


@router.get("/playback/subtitles")
def list_subtitles(path: str = Query(..., description="视频文件路径")):
    """列出与视频文件同目录下的外挂字幕文件"""
    guard_path(path, "字幕查询")

    video_dir = os.path.dirname(path)
    if not os.path.isdir(video_dir):
        return {"subtitles": []}

    video_stem = os.path.splitext(os.path.basename(path))[0].lower()
    subtitles = []

    try:
        for f in os.listdir(video_dir):
            ext = os.path.splitext(f)[1].lower()
            if ext not in SUBTITLE_EXTS:
                continue
            full_path = os.path.join(video_dir, f)
            if not os.path.isfile(full_path):
                continue
            # 推断语言标签（从文件名后缀猜测，如 movie.chs.srt → chs）
            parts = os.path.splitext(f)[0].split(".")
            lang = ""
            if len(parts) >= 2:
                candidate = parts[-1].lower()
                if candidate in ("chs", "cht", "zh", "cn", "sc", "tc", "chi", "chinese"):
                    lang = "zh"
                elif candidate in ("eng", "en", "english"):
                    lang = "en"
                elif candidate in ("jpn", "jp", "ja", "japanese"):
                    lang = "ja"
                elif candidate in ("kor", "ko", "korean"):
                    lang = "ko"
                else:
                    lang = candidate if len(candidate) <= 5 else ""

            subtitles.append({
                "name": f,
                "path": full_path,
                "format": ext.lstrip("."),
                "lang": lang,
                "url": f"/playback/subtitle/file?path={quote(full_path)}",
            })
    except OSError:
        pass

    return {"subtitles": subtitles}


@router.get("/playback/subtitle/file")
def serve_subtitle(path: str = Query(..., description="字幕文件路径"), request: Request = None):
    """提供字幕文件内容（自动转为 WebVTT 格式供浏览器 <track> 使用）"""
    guard_path(path, "字幕文件")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="字幕文件不存在")

    ext = os.path.splitext(path)[1].lower()

    # 读取字幕内容
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取字幕失败: {e}")

    # 如果已经是 VTT 格式直接返回
    if ext == ".vtt":
        return Response(content=content, media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    # SRT → WebVTT 转换
    if ext == ".srt":
        vtt = _srt_to_vtt(content)
        return Response(content=vtt, media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    # ASS/SSA → WebVTT 简易转换（去掉格式标签，保留文本和时间轴）
    if ext in (".ass", ".ssa"):
        vtt = _ass_to_vtt(content)
        return Response(content=vtt, media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    # 不支持的格式返回原文
    return Response(content=content, media_type="text/plain; charset=utf-8",
                    headers={"Access-Control-Allow-Origin": "*"})


def _srt_to_vtt(srt_content: str) -> str:
    """SRT → WebVTT 转换"""
    import re
    # WebVTT header
    lines = ["WEBVTT", ""]
    # SRT 时间戳用逗号分隔毫秒，VTT 用点
    converted = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt_content)
    lines.append(converted.strip())
    return "\n".join(lines)


def _ass_to_vtt(ass_content: str) -> str:
    """ASS/SSA → WebVTT 简易转换（只提取 Dialogue 行）"""
    import re
    lines = ["WEBVTT", ""]
    cue_index = 0

    for line in ass_content.split("\n"):
        line = line.strip()
        if not line.startswith("Dialogue:"):
            continue

        # Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue

        start_raw = parts[1].strip()
        end_raw = parts[2].strip()
        text = parts[9].strip()

        # 去掉 ASS 格式标签 {\xxx}
        text = re.sub(r"\{[^}]*\}", "", text)
        # \N 和 \n 换行
        text = text.replace("\\N", "\n").replace("\\n", "\n")

        if not text.strip():
            continue

        # ASS 时间格式 H:MM:SS.CC → WebVTT HH:MM:SS.MMM
        start_vtt = _ass_time_to_vtt(start_raw)
        end_vtt = _ass_time_to_vtt(end_raw)

        if start_vtt and end_vtt:
            cue_index += 1
            lines.append(str(cue_index))
            lines.append(f"{start_vtt} --> {end_vtt}")
            lines.append(text)
            lines.append("")

    return "\n".join(lines)


def _ass_time_to_vtt(time_str: str) -> str:
    """ASS 时间 H:MM:SS.CC → WebVTT HH:MM:SS.MMM"""
    import re
    m = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d{2})", time_str)
    if not m:
        return ""
    h, mi, s, cs = m.groups()
    return f"{int(h):02d}:{mi}:{s}.{cs}0"
