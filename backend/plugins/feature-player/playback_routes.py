"""播放路由：提供 HTTP Range 文件流，供前端播放器拉取视频数据。"""
import os
import logging
from urllib.parse import quote

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, Response

from shared import guard_path

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 音轨 remux 缓存 ──

import tempfile
import hashlib
import subprocess as _subprocess

_remux_cache: dict[str, str] = {}  # key: "path:audio_index" → 临时文件路径


def _get_remuxed_file(video_path: str, audio_index: int) -> str | None:
    """用 ffmpeg 将指定音轨 remux 为临时 mp4 文件（video/audio 都 copy，不重编码）。
    结果缓存在内存字典中，同文件+同音轨不重复 remux。"""
    cache_key = f"{video_path}:{audio_index}"
    if cache_key in _remux_cache:
        cached = _remux_cache[cache_key]
        if os.path.isfile(cached):
            return cached
        del _remux_cache[cache_key]

    # 生成临时文件路径
    name_hash = hashlib.md5(video_path.encode()).hexdigest()[:12]
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"napics_remux_{name_hash}_a{audio_index}.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-map", "0:v:0",
        "-map", f"0:a:{audio_index}",
        "-c", "copy",
        "-movflags", "+faststart",
        tmp_path,
    ]

    try:
        result = _subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"[Playback] remux 失败: {result.stderr[:200]}")
            return None
    except FileNotFoundError:
        logger.error("[Playback] ffmpeg 未安装，无法 remux 音轨")
        return None
    except _subprocess.TimeoutExpired:
        logger.error("[Playback] remux 超时")
        return None

    if os.path.isfile(tmp_path):
        _remux_cache[cache_key] = tmp_path
        logger.info(f"[Playback] 音轨 remux 完成: {tmp_path}")
        return tmp_path
    return None


@router.head("/playback/stream")
@router.get("/playback/stream")
def stream_file(
    path: str = Query(..., description="视频文件路径"),
    audio_index: int = Query(0, description="音轨索引（0=默认，>0 时 remux 指定音轨）"),
    request: Request = None,
):
    """HTTP Range 文件流端点。

    支持 Range 请求，供前端原生播放器按需拉取文件片段。
    当 audio_index > 0 时，用 ffmpeg remux 出只含指定音轨的临时 mp4 文件。
    """
    guard_path(path, "流式播放")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 如果指定了非默认音轨，使用 remux 后的临时文件
    actual_path = path
    if audio_index > 0:
        actual_path = _get_remuxed_file(path, audio_index)
        if actual_path is None:
            raise HTTPException(status_code=500, detail="音轨 remux 失败")

    file_size = os.path.getsize(actual_path)
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
            with open(actual_path, "rb") as f:
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
        with open(actual_path, "rb") as f:
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
def transcode_file(
    path: str = Query(..., description="视频文件路径"),
    start: float = Query(0, description="起始秒数（seek 用）"),
    audio_index: int = Query(0, description="音轨索引（0=第一条音轨）"),
):
    """用 ffmpeg 实时转封装/转码为 mp4 流。

    视频编码 copy（不重编码），音频转为 AAC，容器格式转为 fragmented MP4。
    支持 mkv/ts/avi/wmv/flv 等浏览器不能直接播放的格式。
    start 参数指定起始时间（秒），用于进度条拖拽 seek。
    audio_index 参数指定音轨索引（0=第一条），用于音轨切换。
    """
    import subprocess

    guard_path(path, "转码播放")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 构建 ffmpeg 命令
    cmd = ["ffmpeg"]

    # output seek（精确音画同步）
    cmd += [
        "-probesize", "5000000",
        "-analyzeduration", "3000000",
        "-i", path,
    ]

    if start > 0:
        cmd += ["-ss", str(start)]

    cmd += [
        "-map", "0:v:0",                    # 选第一条视频流
        "-map", f"0:a:{audio_index}",       # 选指定音轨
        "-c:v", "copy",         # 视频不重编码
        "-c:a", "aac",          # 音频统一转 AAC（兼容浏览器）
        "-ac", "2",             # 立体声
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-frag_duration", "500000",
        "-min_frag_duration", "200000",
        "-max_muxing_queue_size", "4096",
        "-f", "mp4",
        "-v", "quiet",
        "pipe:1",
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
            # 先读取一大块初始数据（等 ffmpeg 写出足够的交错音视频帧）
            initial = process.stdout.read(1024 * 512)  # 首次 512KB
            if initial:
                yield initial
            # 后续正常 chunk 输出
            while True:
                chunk = process.stdout.read(1024 * 128)  # 128KB chunks
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


@router.get("/playback/keyframe-time")
def get_keyframe_time(path: str = Query(..., description="视频文件路径"), time: float = Query(..., description="目标时间")):
    """查询目标时间之前最近的关键帧时间。前端据此校正 seek 后的字幕偏移。"""
    import subprocess

    guard_path(path, "关键帧查询")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    cmd = [
        "ffprobe",
        "-read_intervals", f"%{time}",
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_frames",
        "-show_entries", "frame=pts_time,key_frame",
        "-of", "csv=p=0",
        path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"actual_start": time}

    for line in result.stdout.strip().split("\n"):
        parts = line.strip().split(",")
        if len(parts) >= 2 and parts[1] == "1":
            try:
                return {"actual_start": float(parts[0])}
            except ValueError:
                break
    return {"actual_start": time}


@router.get("/playback/duration")
def get_duration(path: str = Query(..., description="视频文件路径")):
    """用 ffprobe 获取视频总时长（秒）。前端用此值渲染自定义进度条。"""
    import subprocess
    import json as json_mod

    guard_path(path, "时长查询")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe 未安装")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="ffprobe 超时")

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="无法获取视频信息")

    try:
        info = json_mod.loads(result.stdout)
        duration = float(info["format"]["duration"])
    except (KeyError, ValueError, json_mod.JSONDecodeError):
        raise HTTPException(status_code=500, detail="无法解析视频时长")

    return {"duration": duration, "path": path}


# ── 音轨相关 ──

@router.get("/playback/audio-tracks")
def list_audio_tracks(path: str = Query(..., description="视频文件路径")):
    """用 ffprobe 获取视频中的音轨列表。前端用于音轨切换菜单。"""
    import subprocess
    import json as json_mod

    guard_path(path, "音轨查询")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "a",
        path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe 未安装")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="ffprobe 超时")

    if result.returncode != 0:
        return {"tracks": []}

    try:
        info = json_mod.loads(result.stdout)
        streams = info.get("streams", [])
    except (json_mod.JSONDecodeError, ValueError):
        return {"tracks": []}

    tracks = []
    audio_index = 0
    for stream in streams:
        tags = stream.get("tags", {})
        lang = tags.get("language", "")
        title = tags.get("title", "")
        codec = stream.get("codec_name", "")
        channels = stream.get("channels", 0)
        sample_rate = stream.get("sample_rate", "")

        label = title or f"音轨 {audio_index + 1}"
        if lang:
            label = f"{label} ({_normalize_lang(lang)})"
        if channels:
            ch_label = {1: "单声道", 2: "立体声", 6: "5.1", 8: "7.1"}.get(channels, f"{channels}ch")
            label = f"{label} [{ch_label}]"

        tracks.append({
            "index": audio_index,
            "stream_index": stream.get("index", 0),
            "label": label,
            "lang": _normalize_lang(lang),
            "codec": codec,
            "channels": channels,
            "sample_rate": sample_rate,
        })
        audio_index += 1

    return {"tracks": tracks}


# ── 字幕相关 ──

SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}


def _read_subtitle_file(path: str) -> str:
    """读取字幕文件，自动检测编码（BOM → UTF-8 → GBK/GB18030 → Latin-1）"""
    with open(path, "rb") as f:
        raw = f.read()

    if raw.startswith(b"\xff\xfe"):
        content = raw[2:].decode("utf-16-le", errors="replace")
    elif raw.startswith(b"\xfe\xff"):
        content = raw[2:].decode("utf-16-be", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        content = raw[3:].decode("utf-8", errors="replace")
    else:
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = raw.decode("gb18030")
            except UnicodeDecodeError:
                content = raw.decode("latin-1", errors="replace")

    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    return content


@router.get("/playback/subtitles")
def list_subtitles(path: str = Query(..., description="视频文件路径")):
    """列出外挂字幕 + 内嵌字幕流"""
    guard_path(path, "字幕查询")

    subtitles = []

    # ── 外挂字幕 ──
    video_dir = os.path.dirname(path)
    if os.path.isdir(video_dir):
        try:
            for f in os.listdir(video_dir):
                ext = os.path.splitext(f)[1].lower()
                if ext not in SUBTITLE_EXTS:
                    continue
                full_path = os.path.join(video_dir, f)
                if not os.path.isfile(full_path):
                    continue
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
                    "embedded": False,
                })
        except OSError:
            pass

    # ── 内嵌字幕（ffprobe 检测） ──
    embedded = _detect_embedded_subtitles(path)
    subtitles.extend(embedded)

    return {"subtitles": subtitles}


def _detect_embedded_subtitles(video_path: str) -> list:
    """用 ffprobe 检测视频内嵌字幕流，返回字幕列表"""
    import subprocess
    import json as json_mod

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "s",
        video_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    try:
        info = json_mod.loads(result.stdout)
        streams = info.get("streams", [])
    except (json_mod.JSONDecodeError, ValueError):
        return []

    subtitles = []
    for stream in streams:
        index = stream.get("index", 0)
        codec = stream.get("codec_name", "")
        tags = stream.get("tags", {})
        lang = tags.get("language", "")
        title = tags.get("title", "")

        if codec in ("hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle"):
            continue

        label = title or f"内嵌字幕 #{index}"
        if lang:
            label = f"{label} ({lang})"

        subtitles.append({
            "name": label,
            "format": "embedded",
            "lang": _normalize_lang(lang),
            "url": f"/playback/subtitle/extract?path={quote(video_path)}&index={index}",
            "embedded": True,
        })

    return subtitles


def _normalize_lang(lang: str) -> str:
    """标准化语言代码"""
    lang = lang.lower().strip()
    zh_codes = ("chi", "zho", "zh", "chs", "cht", "cn", "chinese")
    en_codes = ("eng", "en", "english")
    ja_codes = ("jpn", "jp", "ja", "japanese")
    ko_codes = ("kor", "ko", "korean")
    if lang in zh_codes:
        return "zh"
    if lang in en_codes:
        return "en"
    if lang in ja_codes:
        return "ja"
    if lang in ko_codes:
        return "ko"
    return lang


@router.get("/playback/subtitle/extract")
def extract_embedded_subtitle(
    path: str = Query(..., description="视频文件路径"),
    index: int = Query(..., description="字幕流索引"),
):
    """提取视频内嵌字幕流，实时转为 WebVTT 格式返回"""
    import subprocess

    guard_path(path, "内嵌字幕提取")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    cmd = [
        "ffmpeg",
        "-v", "quiet",
        "-i", path,
        "-map", f"0:{index}",
        "-c:s", "webvtt",
        "-f", "webvtt",
        "pipe:1",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffmpeg 未安装")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="字幕提取超时")

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="字幕提取失败")

    return Response(
        content=result.stdout,
        media_type="text/vtt; charset=utf-8",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@router.get("/playback/subtitle/file")
def serve_subtitle(path: str = Query(..., description="字幕文件路径"), request: Request = None):
    """提供字幕文件内容（自动转为 WebVTT 格式供浏览器 <track> 使用）"""
    guard_path(path, "字幕文件")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="字幕文件不存在")

    ext = os.path.splitext(path)[1].lower()

    try:
        content = _read_subtitle_file(path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取字幕失败: {e}")

    if ext == ".vtt":
        return Response(content=content.encode("utf-8"), media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    if ext == ".srt":
        vtt = _srt_to_vtt(content)
        logger.info(f"[Playback] SRT→VTT 转换完成，前30字符: {repr(vtt[:30])}")
        return Response(content=vtt.encode("utf-8"), media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    if ext in (".ass", ".ssa"):
        vtt = _ass_to_vtt(content)
        return Response(content=vtt.encode("utf-8"), media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    if ext == ".sub":
        vtt = _sub_to_vtt(content)
        return Response(content=vtt.encode("utf-8"), media_type="text/vtt; charset=utf-8",
                        headers={"Access-Control-Allow-Origin": "*"})

    return Response(content=content.encode("utf-8"), media_type="text/plain; charset=utf-8",
                    headers={"Access-Control-Allow-Origin": "*"})


def _srt_to_vtt(srt_content: str) -> str:
    """SRT → WebVTT 转换"""
    import re
    lines = ["WEBVTT", ""]
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

        parts = line.split(",", 9)
        if len(parts) < 10:
            continue

        start_raw = parts[1].strip()
        end_raw = parts[2].strip()
        text = parts[9].strip()

        text = re.sub(r"\{[^}]*\}", "", text)
        text = text.replace("\\N", "\n").replace("\\n", "\n")

        if not text.strip():
            continue

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


def _sub_to_vtt(sub_content: str) -> str:
    """SUB (MicroDVD) → WebVTT 转换。

    MicroDVD 格式：{start_frame}{end_frame}text
    第一行如果是 {1}{1}fps_value 则用该帧率，否则默认 23.976fps。
    """
    import re
    lines_raw = sub_content.strip().split("\n")
    fps = 23.976

    if lines_raw and re.match(r"\{1\}\{1\}", lines_raw[0]):
        try:
            fps_candidate = float(re.sub(r"\{1\}\{1\}", "", lines_raw[0]).strip())
            if 10 < fps_candidate < 120:
                fps = fps_candidate
            lines_raw = lines_raw[1:]
        except ValueError:
            pass

    lines = ["WEBVTT", ""]
    cue_index = 0

    for line in lines_raw:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\{(\d+)\}\{(\d+)\}(.*)", line)
        if not m:
            continue
        start_frame = int(m.group(1))
        end_frame = int(m.group(2))
        text = m.group(3).strip()

        if not text or end_frame <= start_frame:
            continue

        text = text.replace("|", "\n")
        text = re.sub(r"\{[^}]*\}", "", text).strip()

        if not text:
            continue

        start_sec = start_frame / fps
        end_sec = end_frame / fps

        cue_index += 1
        lines.append(str(cue_index))
        lines.append(f"{_seconds_to_vtt(start_sec)} --> {_seconds_to_vtt(end_sec)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def _seconds_to_vtt(seconds: float) -> str:
    """秒数 → WebVTT 时间戳 HH:MM:SS.MMM"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"
