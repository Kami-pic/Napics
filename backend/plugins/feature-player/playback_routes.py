"""播放路由：提供 HTTP Range 文件流，供前端播放器拉取视频数据。"""
import hashlib
import json
import logging
import os
import subprocess as _subprocess
import tempfile
import threading
import time
from urllib.parse import quote

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, Response

from shared import guard_path

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 音轨 remux 缓存 ──

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
        "ffmpeg", "-nostdin", "-y",
        "-i", video_path,
        "-map", "0:v:0",
        "-map", f"0:a:{audio_index}",
        "-c", "copy",
        "-movflags", "+faststart",
        tmp_path,
    ]

    try:
        result = _subprocess.run(
            cmd, capture_output=True, stdin=_subprocess.DEVNULL, timeout=120,
        )
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
    cmd = ["ffmpeg", "-nostdin"]

    # input seek：-ss 必须在 -i 之前。
    # 放在 -i 之后是 output seek，要从文件头 demux 到 start，耗时随位置线性增长
    # （实测 300s→0.94s、900s→2.58s、1800s→4.58s），而 input seek 恒定约 0.1s。
    if start > 0:
        cmd += ["-ss", str(start)]

    cmd += [
        "-probesize", "5000000",
        "-analyzeduration", "3000000",
        "-i", path,
        # 分片 MP4 会把时间戳归零，这里显式声明避免负时间戳
        "-avoid_negative_ts", "make_zero",
    ]

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
            stdin=subprocess.DEVNULL,
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
            # 客户端断连（换 src、关窗口、拖进度条）时生成器会被关闭。
            # 不 kill 的话 ffmpeg 会一直转到文件尾，拖几次就堆出一批孤儿进程把 IO 打满。
            try:
                process.stdout.close()
            except Exception:
                pass
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except Exception:
                pass

    return StreamingResponse(
        stream_output(),
        media_type="video/mp4",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/playback/keyframe-time")
def get_keyframe_time(
    path: str = Query(..., description="视频文件路径"),
    time: float = Query(..., description="目标时间（秒）"),
):
    """查询 ffmpeg 用 `-ss time` 实际会落到的关键帧时间。

    转码时 ffmpeg 会 snap 到 <= time 的最近关键帧，实测偏差 1.4-5.3 秒，
    GOP 长的片源最坏可达 10 秒。前端必须用这个返回值同时作为
    `-ss` 参数和字幕时间轴的 offset，否则字幕会整体偏移。

    实现用 ffmpeg 自己输出一帧再读时间戳，而不是 ffprobe 查关键帧列表：
    ffprobe 的 `-read_intervals` 自身 seek 不精确会漏帧，实测在 900s / 1800s
    处分别报 891.724 / 1786.368，而 ffmpeg 实际落点是 898.064 / 1798.547。
    只有让 ffmpeg 自报才和转码行为一致。

    注意输出**不能**带 `-movflags empty_moov`：分片 MP4 的 muxer 会把时间戳
    归零，就读不到绝对时间了。
    """
    import subprocess

    guard_path(path, "关键帧查询")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if time <= 0:
        return {"actual_start": 0.0, "requested": time}

    tmp_path = os.path.join(
        tempfile.gettempdir(),
        f"napics_kf_{os.getpid()}_{threading.get_ident()}.mp4",
    )
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-ss", str(time),
        "-copyts",              # 保留原始时间戳，才能读出绝对位置
        "-i", path,
        "-map", "0:v:0",
        "-c:v", "copy",
        "-frames:v", "1",       # 只要一帧，实测约 0.16s
        "-f", "mp4", tmp_path,
    ]

    actual = time
    try:
        result = subprocess.run(
            cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=30,
        )
        if result.returncode != 0 or not os.path.isfile(tmp_path):
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")
            logger.warning(f"[Playback] 关键帧查询失败，回退到请求值: {stderr[:200]}")
            return {"actual_start": time, "requested": time}

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_packets",
             "-show_entries", "packet=pts_time", tmp_path],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=15, encoding="utf-8",
        )
        packets = json.loads(probe.stdout).get("packets", [])
        if packets:
            actual = float(packets[0]["pts_time"])
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"[Playback] 关键帧查询异常，回退到请求值: {e}")
        return {"actual_start": time, "requested": time}
    except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
        logger.warning(f"[Playback] 关键帧时间戳解析失败: {e}")
        return {"actual_start": time, "requested": time}
    finally:
        if os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return {"actual_start": actual, "requested": time}


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
        result = subprocess.run(
            cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=10, encoding="utf-8",
        )
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
        result = subprocess.run(
            cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=10, encoding="utf-8",
        )
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

# 图形/位图字幕：像素图而非文本，转 WebVTT 需要 OCR，浏览器无法直接渲染。
# 这类轨仍会出现在字幕列表里（标记 unsupported），否则用户会以为片源没字幕。
GRAPHIC_SUBTITLE_CODECS = {
    "hdmv_pgs_subtitle",   # 蓝光 PGS，remux 片源最常见
    "dvd_subtitle",        # DVD VobSub
    "dvb_subtitle",        # DVB 广播字幕
    "xsub",                # DivX
}

# 非标准文本字幕：ffmpeg 的 webvtt 编码器不支持，转换会失败。
# 过去这些 codec 能通过过滤，然后在提取阶段静默 500。
UNCONVERTIBLE_SUBTITLE_CODECS = {
    "dvb_teletext",
    "arib_caption",
    "hdmv_text_subtitle",
    "eia_608",
    "eia_708",
}

# 可转 WebVTT 的文本字幕
TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt", "text", "srt", "microdvd"}


def _classify_subtitle_codec(codec: str) -> tuple[bool, str]:
    """判断字幕 codec 能否转成 WebVTT。

    返回 (supported, reason)。reason 仅在不支持时有意义，用于前端提示。
    未知 codec 一律当作可尝试，失败时由提取阶段报错，避免误杀新格式。
    """
    codec = (codec or "").lower()
    if codec in GRAPHIC_SUBTITLE_CODECS:
        return False, "图形字幕（需 OCR），浏览器无法渲染"
    if codec in UNCONVERTIBLE_SUBTITLE_CODECS:
        return False, f"{codec} 格式无法转为 WebVTT"
    return True, ""


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

    # 不校验的话，路径不可达（SMB 掉线等）会和"真的没字幕"返回同样的空列表
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

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
                    "codec": ext.lstrip("."),
                    "lang": lang,
                    "url": f"/playback/subtitle/file?path={quote(full_path)}",
                    "embedded": False,
                    # 外挂字幕都是文本格式，一律可用。字段与内嵌字幕保持一致，
                    # 免得消费端要区分两种结构。
                    "unsupported": False,
                    "unsupported_reason": "",
                    "forced": False,
                })
        except OSError:
            pass

    # ── 内嵌字幕（ffprobe 检测） ──
    embedded = _detect_embedded_subtitles(path)
    subtitles.extend(embedded)

    return {"subtitles": subtitles}


def _detect_embedded_subtitles(video_path: str) -> list:
    """用 ffprobe 检测视频内嵌字幕流。

    图形字幕（PGS/VobSub）与不可转换的 codec 也会返回，但带 unsupported=True，
    让前端能显示「有 6 条 PGS 字幕但无法渲染」而不是伪装成"没有字幕"。
    """
    import subprocess
    import json as json_mod

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "s",
        video_path,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=20, encoding="utf-8",
        )
    except FileNotFoundError:
        logger.error("[Playback] ffprobe 未安装，无法检测内嵌字幕")
        return []
    except subprocess.TimeoutExpired:
        logger.warning(f"[Playback] 内嵌字幕检测超时(20s): {os.path.basename(video_path)}")
        return []

    if result.returncode != 0:
        logger.warning(
            f"[Playback] 内嵌字幕检测失败 rc={result.returncode}: "
            f"{(result.stderr or '')[:200]}"
        )
        return []

    try:
        info = json_mod.loads(result.stdout)
        streams = info.get("streams", [])
    except (json_mod.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Playback] 内嵌字幕 ffprobe 输出解析失败: {e}")
        return []

    subtitles = []
    text_count = 0
    unsupported_count = 0
    # 相对索引（第几条字幕轨）单独计数，仅用于显示，不参与 -map
    sub_ordinal = 0
    for stream in streams:
        # ffprobe 的 index 是文件内绝对流索引，与 ffmpeg `-map 0:<n>` 语义一致
        index = stream.get("index", 0)
        codec = stream.get("codec_name", "")
        tags = stream.get("tags", {})
        lang = tags.get("language", "")
        title = tags.get("title", "")
        disposition = stream.get("disposition", {})

        sub_ordinal += 1
        supported, reason = _classify_subtitle_codec(codec)

        label = title or f"内嵌字幕 {sub_ordinal}"
        norm_lang = _normalize_lang(lang)
        if norm_lang:
            label = f"{label} ({norm_lang})"
        if disposition.get("forced"):
            label = f"{label} [强制]"
        if not supported:
            label = f"{label} — {reason}"
            unsupported_count += 1
        else:
            text_count += 1

        subtitles.append({
            "name": label,
            "format": "embedded",
            "codec": codec,
            "lang": norm_lang,
            "url": f"/playback/subtitle/extract?path={quote(video_path)}&index={index}",
            "embedded": True,
            "unsupported": not supported,
            "unsupported_reason": reason,
            "forced": bool(disposition.get("forced")),
        })

    if subtitles:
        logger.info(
            f"[Playback] 内嵌字幕检测: {os.path.basename(video_path)} → "
            f"可用 {text_count} 条，不支持 {unsupported_count} 条"
        )
    return subtitles


def _normalize_lang(lang: str) -> str:
    """标准化语言代码为两字母 ISO 639-1。

    覆盖 ISO 639-2/T、639-2/B 与常见非标准写法。
    Netflix / WEB-DL 片源常用 cmn / yue / zh-Hans 这类标记，
    不归一化会变成非法的 <track srclang> 值。
    """
    lang = (lang or "").lower().strip().replace("_", "-")
    zh_codes = (
        "chi", "zho", "zh", "chs", "cht", "cn", "chinese",
        "cmn", "yue",                                    # 普通话 / 粤语
        "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-hk", "zh-sg",
    )
    en_codes = ("eng", "en", "english", "en-us", "en-gb")
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
    # 其余三字母码取常见映射，剩下的原样返回
    misc = {
        "fra": "fr", "fre": "fr", "deu": "de", "ger": "de",
        "spa": "es", "por": "pt", "rus": "ru", "ita": "it",
        "tha": "th", "vie": "vi", "ara": "ar", "hin": "hi",
        "ind": "id", "may": "ms", "msa": "ms", "nld": "nl", "dut": "nl",
    }
    return misc.get(lang, lang)


# ── 内嵌字幕提取（落盘缓存） ──
#
# 字幕包沿整个时长交错分布，提取任意一条都要把整个文件 demux 完一遍。
# 实测约 5.8 秒/GB（SMB 挂载），8GB 文件要 46 秒 —— 旧实现 30s 硬超时
# 让所有超过约 5GB 的片源内嵌字幕 100% 失败。
#
# 因此改为：首次请求时一次 ffmpeg 调用提取**全部**文本字幕轨落盘，
# 之后任意轨的请求都走缓存。切字幕不再重复付全量 demux 的代价。

_subtitle_cache: dict[str, dict[int, str]] = {}  # 视频指纹 → {绝对流索引: vtt 文件路径}
_subtitle_locks: dict[str, threading.Lock] = {}  # 视频指纹 → 提取锁，避免并发重复提取
_subtitle_locks_guard = threading.Lock()

# 提取超时：按 5.8 s/GB 估算，600s 可覆盖约 100GB 的片源
SUBTITLE_EXTRACT_TIMEOUT = 600


def _video_fingerprint(video_path: str) -> str:
    """视频文件指纹（路径+大小+mtime），文件被替换后缓存自动失效"""
    try:
        st = os.stat(video_path)
        raw = f"{video_path}:{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        raw = video_path
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _get_subtitle_lock(fingerprint: str) -> threading.Lock:
    """取得某个视频的提取锁（同一文件的并发请求串行化）"""
    with _subtitle_locks_guard:
        if fingerprint not in _subtitle_locks:
            _subtitle_locks[fingerprint] = threading.Lock()
        return _subtitle_locks[fingerprint]


def _extract_all_text_subtitles(video_path: str, fingerprint: str) -> dict[int, str]:
    """一次 ffmpeg 调用把全部可转换的文本字幕轨提取为 VTT 落盘。

    返回 {绝对流索引: vtt 文件路径}。失败返回空字典。
    """
    streams = _detect_embedded_subtitles(video_path)
    targets = []
    for item in streams:
        if item.get("unsupported"):
            continue
        # url 里带的就是绝对流索引，这里直接从 detect 结果反解，避免再 probe 一次
        try:
            idx = int(item["url"].rsplit("index=", 1)[1])
        except (KeyError, IndexError, ValueError):
            continue
        targets.append(idx)

    if not targets:
        return {}

    tmp_dir = os.path.join(tempfile.gettempdir(), "napics_subs")
    os.makedirs(tmp_dir, exist_ok=True)

    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", video_path]
    out_paths: dict[int, str] = {}
    for idx in targets:
        out_path = os.path.join(tmp_dir, f"{fingerprint}_s{idx}.vtt")
        cmd += ["-map", f"0:{idx}", "-c:s", "webvtt", "-f", "webvtt", out_path]
        out_paths[idx] = out_path

    logger.info(
        f"[Playback] 开始提取内嵌字幕 {len(targets)} 条: "
        f"{os.path.basename(video_path)}（大文件可能需要数十秒）"
    )
    started = time.time()
    try:
        # stdin 必须显式给 DEVNULL：uvicorn / pytest 下父进程 stdin 可能已被替换，
        # 继承句柄会直接抛 OSError（Windows 上是 WinError 6）。
        result = _subprocess.run(
            cmd, capture_output=True, stdin=_subprocess.DEVNULL,
            timeout=SUBTITLE_EXTRACT_TIMEOUT,
        )
    except FileNotFoundError:
        logger.error("[Playback] ffmpeg 未安装，无法提取内嵌字幕")
        return {}
    except _subprocess.TimeoutExpired:
        logger.error(
            f"[Playback] 内嵌字幕提取超时({SUBTITLE_EXTRACT_TIMEOUT}s): "
            f"{os.path.basename(video_path)}"
        )
        return {}

    elapsed = time.time() - started
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        logger.error(
            f"[Playback] 内嵌字幕提取失败 rc={result.returncode} "
            f"({elapsed:.1f}s): {stderr[:300]}"
        )
        # 部分输出可能已成功落盘，保留能用的
    # 只保留真正写出了内容的轨
    valid: dict[int, str] = {}
    for idx, out_path in out_paths.items():
        if os.path.isfile(out_path) and os.path.getsize(out_path) > len("WEBVTT\n\n"):
            valid[idx] = out_path
        elif os.path.isfile(out_path):
            os.remove(out_path)  # 空 VTT 没有意义，删掉避免命中缓存
    logger.info(
        f"[Playback] 内嵌字幕提取完成: {len(valid)}/{len(targets)} 条有内容，"
        f"耗时 {elapsed:.1f}s"
    )
    return valid


@router.get("/playback/subtitle/extract")
def extract_embedded_subtitle(
    path: str = Query(..., description="视频文件路径"),
    index: int = Query(..., description="字幕流索引（文件内绝对流索引）"),
):
    """提取视频内嵌字幕流，转为 WebVTT 返回。

    首次调用会一次性提取该文件的全部文本字幕轨并落盘缓存，
    后续（含切换其他字幕轨）直接命中缓存。
    """
    guard_path(path, "内嵌字幕提取")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    fingerprint = _video_fingerprint(path)
    cached = _subtitle_cache.get(fingerprint)

    # 缓存命中且文件还在
    if cached and index in cached and os.path.isfile(cached[index]):
        with open(cached[index], "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="text/vtt; charset=utf-8",
            headers={"Access-Control-Allow-Origin": "*", "X-Subtitle-Cache": "hit"},
        )

    # 未命中：加锁提取（同一文件并发请求只跑一次 ffmpeg）
    lock = _get_subtitle_lock(fingerprint)
    with lock:
        # 双检：等锁期间可能已被别的请求填好
        cached = _subtitle_cache.get(fingerprint)
        if not (cached and index in cached and os.path.isfile(cached[index])):
            extracted = _extract_all_text_subtitles(path, fingerprint)
            if extracted:
                _subtitle_cache[fingerprint] = extracted
            cached = extracted

    if not cached or index not in cached:
        raise HTTPException(
            status_code=404,
            detail="该字幕轨提取失败或无文本内容（可能是图形字幕）",
        )

    with open(cached[index], "rb") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/vtt; charset=utf-8",
        headers={"Access-Control-Allow-Origin": "*", "X-Subtitle-Cache": "miss"},
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
