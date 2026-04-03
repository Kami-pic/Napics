"""质量解析模块：从 BT 资源标题中解析完整质量信息。"""

import re
from pydantic import BaseModel


class QualityTag(BaseModel):
    """BT 资源质量标签"""
    resolution: str = ""       # "720p" | "1080p" | "2160p" | ""
    source: str = ""           # "Bluray" | "WEB-DL" | "Remux" | "HDTV" | ""
    video_codec: str = ""      # "x264" | "x265" | "HEVC" | "AV1" | ""
    audio_codec: str = ""      # "AAC" | "DTS" | "DTS-HD" | "TrueHD" | "Atmos" | "DD5.1" | "DDP5.1" | "AC3" | ""
    has_chinese_sub: bool = False
    release_group: str = ""    # 发布组名称，如 "CMCT" | "HDHome" | "CHD"
    is_surround: bool = False  # 环绕声 5.0+（DTS/DTS-HD/TrueHD/Atmos/DD5.1/DDP5.1/AC3/7.1 等）
    display: str = ""          # 格式化显示字符串（不含发布组，发布组单独展示）


class QualityLevel(BaseModel):
    """质量等级，用于排序对比"""
    rank: int = 0
    label: str = ""


def parse_quality(title: str) -> QualityTag:
    """从 BT 标题解析完整质量标签。"""
    if not title:
        return QualityTag()

    upper = title.upper()

    # --- 分辨率（统一输出标准格式：2160p / 1080p / 720p）---
    resolution = ""
    if re.search(r"2160[piPI]|4[Kk]|UHD", title):
        resolution = "2160p"
    elif re.search(r"1080[piPI]", title):
        resolution = "1080p"
    elif re.search(r"720[piPI]", title):
        resolution = "720p"

    # --- 来源（优先级：Remux > Bluray > WEB-DL > HDTV）---
    source = ""
    if "REMUX" in upper:
        source = "Remux"
    elif "BLURAY" in upper or "BLU-RAY" in upper:
        source = "Bluray"
    elif "WEB-DL" in upper or "WEBDL" in upper or "WEB.DL" in upper:
        source = "WEB-DL"
    elif "HDTV" in upper:
        source = "HDTV"

    # --- 视频编码 ---
    video_codec = ""
    if "AV1" in upper:
        video_codec = "AV1"
    elif re.search(r"X\.?265|H\.?265|HEVC", upper):
        video_codec = "x265"
    elif re.search(r"X\.?264|H\.?264|AVC", upper):
        video_codec = "x264"

    # --- 音频编码（优先级：Atmos > TrueHD > DTS-HD > DDP5.1 > DD5.1 > DTS > AC3/EAC3 > AAC）---
    audio_codec = ""
    is_surround = False
    if "ATMOS" in upper:
        audio_codec = "Atmos"
        is_surround = True
    elif "TRUEHD" in upper or "TRUE-HD" in upper or "TRUE.HD" in upper:
        audio_codec = "TrueHD"
        is_surround = True
    elif "DTS-HD" in upper or "DTS.HD" in upper or "DTSHD" in upper or re.search(r"DTS[\s\-\.]?HD[\s\-\.]?MA", upper):
        audio_codec = "DTS-HD"
        is_surround = True
    elif re.search(r"DDP[\s\.]?5[\s\.]?1|DD\+[\s\.]?5[\s\.]?1|EAC3[\s\.]?5[\s\.]?1", upper):
        audio_codec = "DDP5.1"
        is_surround = True
    elif re.search(r"DD[\s\.]?5[\s\.]?1|AC3[\s\.]?5[\s\.]?1", upper):
        audio_codec = "DD5.1"
        is_surround = True
    elif "DTS" in upper:
        audio_codec = "DTS"
        is_surround = True
    elif "EAC3" in upper or "E-AC-3" in upper:
        audio_codec = "EAC3"
        is_surround = True  # EAC3 通常是 5.1
    elif "AC3" in upper or "AC-3" in upper:
        audio_codec = "AC3"
        is_surround = True  # AC3 通常是 5.1
    elif "AAC" in upper:
        audio_codec = "AAC"
    # 额外检测：标题中直接出现 5.1 / 7.1 / 6CH / 8CH
    if not is_surround and re.search(r"\b[5-9]\.[01]\b|7\.1|\b[6-8]CH\b", upper):
        is_surround = True

    # --- 中文字幕标记 ---
    chinese_sub_patterns = [
        r"CHS", r"CHT", r"中字", r"中文字幕", r"简繁", r"简体", r"繁体",
        r"内封", r"外挂", r"内嵌", r"双语", r"国语", r"粤语",
        r"简中", r"繁中", r"中英",
    ]
    has_chinese_sub = any(re.search(p, title, re.IGNORECASE) for p in chinese_sub_patterns)

    # --- 发布组提取 ---
    # 常见格式：标题末尾 -GroupName 或 @GroupName
    # 排除常见文件扩展名和技术标签，避免误提取
    _NON_GROUP_SUFFIXES = {
        "MP4", "MKV", "AVI", "SRT", "ASS", "SSA", "SUP", "SUB", "IDX",
        "HEVC", "AVC", "AAC", "DTS", "FLAC", "AC3", "EAC3",
        "HDR", "SDR", "DV", "DOVI",
        "REMUX", "PROPER", "REPACK", "INTERNAL",
        "CHS", "CHT", "ENG", "JPN",
    }
    release_group = ""
    # 先尝试末尾 -GroupName（最常见格式）
    rg_match = re.search(r'[-@]([A-Za-z0-9][A-Za-z0-9_.]{0,19})\s*$', title.strip())
    if rg_match:
        rg = rg_match.group(1)
        if rg.upper() not in _NON_GROUP_SUFFIXES:
            release_group = rg

    # --- 生成 display（不含发布组，发布组单独展示）---
    parts = []
    if source:
        parts.append(source)
    if resolution:
        parts.append(resolution)
    if video_codec:
        parts.append(video_codec)
    if audio_codec:
        parts.append(audio_codec)
    if has_chinese_sub:
        parts.append("中字")
    display = "-".join(parts) if parts else ""

    return QualityTag(
        resolution=resolution,
        source=source,
        video_codec=video_codec,
        audio_codec=audio_codec,
        has_chinese_sub=has_chinese_sub,
        release_group=release_group,
        is_surround=is_surround,
        display=display,
    )


def get_quality_level(tag: QualityTag) -> QualityLevel:
    """根据 QualityTag 计算质量等级排名。

    优先级：2160p Remux(8) > 2160p Bluray(7) > 2160p WEB-DL(6)
           > 1080p Remux(5) > 1080p Bluray(4) > 1080p WEB-DL(3)
           > 720p(2) > 其他(1)
    """
    res = tag.resolution
    src = tag.source

    if res == "2160p":
        if src == "Remux":
            return QualityLevel(rank=8, label="2160p Remux")
        elif src == "Bluray":
            return QualityLevel(rank=7, label="2160p Bluray")
        elif src == "WEB-DL":
            return QualityLevel(rank=6, label="2160p WEB-DL")
        # 2160p with other/unknown source — treat as WEB-DL tier
        return QualityLevel(rank=6, label="2160p WEB-DL")
    elif res == "1080p":
        if src == "Remux":
            return QualityLevel(rank=5, label="1080p Remux")
        elif src == "Bluray":
            return QualityLevel(rank=4, label="1080p Bluray")
        elif src == "WEB-DL":
            return QualityLevel(rank=3, label="1080p WEB-DL")
        # 1080p with other/unknown source — treat as WEB-DL tier
        return QualityLevel(rank=3, label="1080p WEB-DL")
    elif res == "720p":
        return QualityLevel(rank=2, label="720p")
    else:
        return QualityLevel(rank=1, label="其他")


def _resolution_to_label(height_str: str) -> str:
    """将 VideoInfo.height 映射为分辨率标签。"""
    try:
        height = int(height_str)
    except (ValueError, TypeError):
        return "SD"
    if height >= 2160:
        return "2160p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    else:
        return "SD"


# 分辨率标签到排序值的映射
_RESOLUTION_ORDER = {"SD": 0, "720p": 1, "1080p": 2, "2160p": 3}


def compare_quality(current_resolution: str, result_tag: QualityTag) -> str:
    """对比当前视频分辨率与搜索结果的质量。

    current_resolution: 当前视频的高度像素值字符串（如 "1080", "2160"）
                        或已映射的标签（如 "1080p", "2160p", "SD"）
    result_tag: 搜索结果的 QualityTag

    返回 "higher" | "equal" | "lower"
    """
    # 如果传入的是像素高度数值，先映射为标签
    current_label = current_resolution
    if current_label not in _RESOLUTION_ORDER:
        current_label = _resolution_to_label(current_resolution)

    result_label = result_tag.resolution if result_tag.resolution else "SD"

    current_order = _RESOLUTION_ORDER.get(current_label, 0)
    result_order = _RESOLUTION_ORDER.get(result_label, 0)

    if result_order > current_order:
        return "higher"
    elif result_order == current_order:
        return "equal"
    else:
        return "lower"
