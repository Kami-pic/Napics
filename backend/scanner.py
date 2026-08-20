import os
import logging
import shutil
import subprocess
import json
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
class VideoInfo(BaseModel):
    file_path: str
    file_name: str
    folder_name: str  # 所属文件夹（用于分组）
    size_gb: float
    duration_min: float
    resolution: str
    height: int
    width: int
    bitrate_kbps: float
    codec: str
    container: str = ""  # 容器格式（mkv/mp4/avi…），取 ffprobe format_name 的第一项
    audio_codec: str  # 音频编码
    audio_channels: int # 声道数
    subtitle_count: int # 内封字幕总数
    # 内封字幕按可用性拆分：文本字幕能转 WebVTT 直接显示，
    # 图形字幕（PGS/VobSub）是图片，需 OCR，播放器无法渲染。
    # 混合片源很常见（同一部片子 subrip 和 PGS 各一套），要分开体现。
    subtitle_text_count: int = 0
    subtitle_graphic_count: int = 0
    hdr_type: str     # "SDR", "HDR10", "DV"
    has_poster: bool  # 目录下是否有封面图
    has_nfo: bool = False  # 是否有刮削 NFO 文件
    is_low_res: bool

def get_video_metadata(file_path: str) -> Optional[VideoInfo]:
    """使用 ffprobe 获取视频元数据"""
    try:
        # ffprobe 路径：优先使用 PATH 中的 ffprobe，找不到则用配置的绝对路径
        ffprobe_path = shutil.which("ffprobe") or "ffprobe"
        
        cmd = [
            ffprobe_path,
            "-v", "error", # 减少噪音
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        # 不用 shell=True，避免 cmd.exe 的代码页把中文 UNC 路径搞乱。
        # stdin 必须显式给 DEVNULL：uvicorn / pytest 下父进程 stdin 已被替换，
        # 继承句柄会抛 OSError（Windows 上是 WinError 6），
        # 然后被下面的 except 吞掉走 fallback —— 表现为整库 codec=unknown。
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            encoding='utf-8',
            errors='ignore',
            timeout=15  # 15 秒超时，防止 ffprobe 卡在 rm/rmvb 等老格式上
        )
        
        if result.returncode != 0:
            logger.error(f"FFprobe error for {file_path}: {result.stderr}")
            return _fallback_info(file_path)
            
        if not result.stdout.strip():
            logger.info(f"FFprobe returned empty output for {file_path}")
            return _fallback_info(file_path)
            return None
            
        data = json.loads(result.stdout)
        
        format_info = data.get("format", {})
        streams = data.get("streams", [])
        
        # 1. 视频流分析 (含 HDR 检测)
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not video_stream:
            return None
            
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        
        # HDR 检测
        hdr_type = "SDR"
        color_transfer = video_stream.get("color_transfer", "")
        if color_transfer == "smpte2084":
            hdr_type = "HDR10"
            # 检查是否有杜比视界 (Dolby Vision) 侧边数据
            side_data = video_stream.get("side_data_list", [])
            if any(sd.get("side_data_type") == "DOVI configuration record" for sd in side_data):
                hdr_type = "DV"
        
        # 2. 音频流分析
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        main_audio = audio_streams[0] if audio_streams else {}
        audio_codec = main_audio.get("codec_name", "none")
        audio_channels = int(main_audio.get("channels", 0))
        
        # 3. 字幕流分析：按能否直接渲染拆分
        subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        subtitle_count = len(subtitle_streams)
        # 与播放器插件的 GRAPHIC_SUBTITLE_CODECS 对齐
        _graphic_codecs = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}
        subtitle_graphic_count = sum(
            1 for s in subtitle_streams if s.get("codec_name") in _graphic_codecs
        )
        subtitle_text_count = subtitle_count - subtitle_graphic_count
        
        # 4. 其他信息
        duration = float(format_info.get("duration", 0))
        size = int(format_info.get("size", 0))
        bitrate = float(format_info.get("bit_rate", 0)) / 1000  # kbps
        
        # 5. 扫描同级目录下的封面图
        folder_path = os.path.dirname(file_path)
        poster_names = ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]
        has_poster = any(os.path.exists(os.path.join(folder_path, n)) for n in poster_names)
        
        # 检测 NFO 文件
        nfo_names = ["movie.nfo", "tvshow.nfo", "season.nfo"]
        base_nfo = os.path.splitext(file_path)[0] + ".nfo"
        has_nfo = os.path.exists(base_nfo) or any(os.path.exists(os.path.join(folder_path, n)) for n in nfo_names)
        
        return VideoInfo(
            file_path=file_path,
            file_name=os.path.basename(file_path),
            folder_name=os.path.basename(folder_path),
            size_gb=round(size / (1024**3), 2),
            duration_min=round(duration / 60, 2),
            resolution=f"{width}x{height}",
            height=height,
            width=width,
            bitrate_kbps=round(bitrate, 2),
            codec=video_stream.get("codec_name", "unknown"),
            # 用扩展名而不是 ffprobe 的 format_name：后者对 mkv 报 "matroska"、
            # 对 mp4 报 "mov"（因为 format_name 是 "mov,mp4,m4a,3gp,3g2,mj2" 这种
            # 候选列表），不是用户认知里的容器名。
            container=os.path.splitext(file_path)[1].lstrip(".").lower(),
            audio_codec=audio_codec,
            audio_channels=audio_channels,
            subtitle_count=subtitle_count,
            subtitle_text_count=subtitle_text_count,
            subtitle_graphic_count=subtitle_graphic_count,
            hdr_type=hdr_type,
            has_poster=has_poster,
            has_nfo=has_nfo,
            is_low_res=(height < 720 and bitrate < 2000)  # 综合判定
        )
    except Exception as e:
        logger.error(f"Error scanning {file_path}: {e}")
        # ffprobe 失败/超时时生成基础记录（文件名 + 大小）
        return _fallback_info(file_path)

def _fallback_info(file_path: str) -> Optional[VideoInfo]:
    """ffprobe 失败时的兜底：用文件名和大小生成基础记录"""
    try:
        size = os.path.getsize(file_path)
        folder_path = os.path.dirname(file_path)
        poster_names = ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]
        has_poster = any(os.path.exists(os.path.join(folder_path, n)) for n in poster_names)
        nfo_names = ["movie.nfo", "tvshow.nfo", "season.nfo"]
        base_nfo = os.path.splitext(file_path)[0] + ".nfo"
        has_nfo = os.path.exists(base_nfo) or any(os.path.exists(os.path.join(folder_path, n)) for n in nfo_names)
        return VideoInfo(
            file_path=file_path,
            file_name=os.path.basename(file_path),
            folder_name=os.path.basename(folder_path),
            size_gb=round(size / (1024**3), 2),
            duration_min=0,
            resolution="未知",
            height=0, width=0,
            bitrate_kbps=0,
            codec="unknown",
            # ffprobe 失败时容器格式退化成扩展名，至少不显示为空
            container=os.path.splitext(file_path)[1].lstrip(".").lower(),
            audio_codec="unknown",
            audio_channels=0,
            subtitle_count=0,
            subtitle_text_count=0,
            subtitle_graphic_count=0,
            hdr_type="SDR",
            has_poster=has_poster,
            has_nfo=has_nfo,
            is_low_res=True,
        )
    except:
        return None

def scan_directory(path: str, exclude_str: str = "", extensions=[".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"]) -> List[VideoInfo]:
    """遍历目录，识别视频文件并获取元数据"""
    results = []
    excludes = [s.strip() for s in exclude_str.split(",") if s.strip()]
    
    for root, dirs, files in os.walk(path):
        # 排除目录
        if excludes:
            dirs[:] = [d for d in dirs if not any(ex in d for ex in excludes)]
            
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                full_path = os.path.join(root, file)
                info = get_video_metadata(full_path)
                if info:
                    # 计算相对于扫描根目录的相对路径作为分组标识
                    rel_dir = os.path.relpath(root, path)
                    info.folder_name = "" if rel_dir == "." else rel_dir
                    results.append(info)
    return results

if __name__ == "__main__":
    # 测试代码
    test_dir = r"C:\Videos"  # 修改为你的本地视频目录
    if os.path.exists(test_dir):
        logger.info(f"Scanning {test_dir}...")
        videos = scan_directory(test_dir)
        for v in videos:
            logger.info(f"{'[LOW-RES]' if v.is_low_res else '[HD]'} {v.file_name} ({v.resolution})")
