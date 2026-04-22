"""网盘搜索增强 — 统一数据模型。

所有网盘搜索源的输出必须严格映射到此模块中的模型。
严禁在 Service 层处理非标准字段。
"""

import re
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, model_validator


# ──────────────────────────────────────────────
# 枚举
# ──────────────────────────────────────────────

class PanType(str, Enum):
    """支持的网盘类型"""
    QUARK = "quark"       # 夸克
    ALIYUN = "aliyun"     # 阿里
    BAIDU = "baidu"       # 百度
    PAN115 = "pan115"     # 115
    PIKPAK = "pikpak"     # PikPak
    UNKNOWN = "unknown"   # 未识别


# ──────────────────────────────────────────────
# 核心模型：PanResult
# ──────────────────────────────────────────────

# 合法网盘域名白名单（防止爬虫抓到推广跳转链接）
VALID_PAN_DOMAINS = [
    "pan.quark.cn", "drive.quark.cn",
    "www.alipan.com", "www.aliyundrive.com",
    "pan.baidu.com",
    "115.com", "anxia.com",
    "mypikpak.com",
]

# 枪版关键词（命中即丢弃）
CAM_KEYWORDS = {"TS", "TC", "HC", "CAM", "HDTS", "HDTC"}

# 碎片集正则：含"第X集/EPxx"但不含整季标记
_EPISODE_FRAG_RE = re.compile(
    r"(?:第\s*\d+\s*集|EP?\s*\d+)", re.IGNORECASE
)
_COMPLETE_RE = re.compile(
    r"(?:全集|完结|S\d{1,2}|整季|合集)", re.IGNORECASE
)

# 分辨率提取正则
_RESOLUTION_RE_4K = re.compile(r"2160[piPI]|4[Kk]|UHD", re.IGNORECASE)
_RESOLUTION_RE_1080 = re.compile(r"1080[piPI]", re.IGNORECASE)
_RESOLUTION_RE_720 = re.compile(r"720[piPI]", re.IGNORECASE)

# 站点水印清洗正则（去除 www.xxx.com_ 等前缀）
_WATERMARK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?[a-zA-Z0-9\-]+\.[a-z]{2,6}[_\-\s]*",
    re.IGNORECASE,
)


def parse_resolution(title: str) -> str:
    """从标题提取分辨率标签。

    返回: "2160p" | "1080p" | "720p" | "unknown"
    """
    if _RESOLUTION_RE_4K.search(title):
        return "2160p"
    if _RESOLUTION_RE_1080.search(title):
        return "1080p"
    if _RESOLUTION_RE_720.search(title):
        return "720p"
    return "unknown"


def is_cam_quality(title: str) -> bool:
    """检测标题是否含枪版关键词。"""
    upper = title.upper()
    # 用词边界匹配，避免误伤（如 "HDTSC" 不应命中 "TS"）
    for kw in CAM_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            return True
    # 中文枪版标记
    if "枪版" in title:
        return True
    return False


def is_fragment_episode(title: str) -> bool:
    """判断是否为碎片集资源（含单集标记但无整季标记）。

    返回 True 表示是碎片集，应被过滤。
    """
    has_episode = bool(_EPISODE_FRAG_RE.search(title))
    has_complete = bool(_COMPLETE_RE.search(title))
    return has_episode and not has_complete


def clean_title(raw_title: str) -> str:
    """标题清洗：去除站点水印、乱码后缀。

    示例：
      "www.xxx.com_流浪地球2_4K_HDR" → "流浪地球2 4K HDR"
    """
    cleaned = _WATERMARK_RE.sub("", raw_title).strip()
    # 去除常见乱码后缀（.mp4/.mkv 等文件扩展名）
    cleaned = re.sub(r"\.(mp4|mkv|avi|rmvb|ts|iso)$", "", cleaned, flags=re.IGNORECASE)
    # 将下划线/多余空格规范化
    cleaned = re.sub(r"[_]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def standardize_title(raw_title: str, cn_name: str = "", year: str = "",
                      season: str = "") -> str:
    """语义化重命名：强制格式 中文名 (年份) S0x。

    用于转存归位时重命名文件夹，解决 Windows 路径过长和检索困难。
    示例：
      raw="www.xxx.com_流浪地球2_4K_HDR", cn_name="流浪地球2", year="2023"
      → "流浪地球2 (2023)"

      raw="...", cn_name="权力的游戏", year="2011", season="1"
      → "权力的游戏 (2011) S01"
    """
    name = cn_name if cn_name else clean_title(raw_title)
    parts = [name]
    if year:
        parts.append(f"({year})")
    if season:
        s_num = int(season) if season.isdigit() else 0
        if s_num > 0:
            parts.append(f"S{s_num:02d}")
    return " ".join(parts)


class PanResult(BaseModel):
    """所有网盘搜索源的统一输出格式。

    字段说明：
    - title: 原始资源标题（爬虫直接抓取的）
    - clean_title: 清洗后的标题（去站点水印/乱码）
    - resolution: 从标题解析的分辨率（2160p/1080p/720p/unknown）
    - size_gb: 资源大小（GB），0 表示未知
    - is_complete: 是否完整资源（整季/全集），False 表示碎片集
    - file_count: 文件数量，0 表示未知
    - alive: 链接存活状态（预检后标记，默认 True）
    """
    title: str
    clean_title: str = ""
    pan_type: PanType
    share_url: str
    password: str = ""
    source: str                         # 来源站点标识（rrdynb/ddys/pansou）
    mounted: bool = True                # Alist 中是否已挂载该网盘类型
    resolution: str = ""                # "2160p" | "1080p" | "720p" | "unknown"
    size_gb: float = 0.0                # 资源大小（GB），0 = 未知
    is_complete: bool = True            # 整季/全集 = True，碎片集 = False
    file_count: int = 0                 # 文件数量，0 = 未知
    alive: bool = True                  # 链接存活预检结果

    @field_validator("share_url")
    @classmethod
    def validate_share_url(cls, v):
        """域名白名单校验：只允许已知网盘域名。"""
        if not v or not v.startswith("http"):
            raise ValueError("share_url 无效：必须以 http 开头")
        domain = urlparse(v).netloc
        if not any(d in domain for d in VALID_PAN_DOMAINS):
            raise ValueError(f"share_url 域名不在白名单: {domain}")
        return v

    @model_validator(mode="before")
    @classmethod
    def auto_fill_defaults(cls, data):
        """自动填充 clean_title / resolution / is_complete（未手动设置时从 title 推导）。"""
        if isinstance(data, dict):
            raw = data.get("title", "")
            if not data.get("clean_title") and raw:
                data["clean_title"] = clean_title(raw)
            if not data.get("resolution") and raw:
                data["resolution"] = parse_resolution(raw)
            if raw and is_fragment_episode(raw):
                data["is_complete"] = False
        return data


# ──────────────────────────────────────────────
# 搜索响应模型
# ──────────────────────────────────────────────

class SourceStatus(BaseModel):
    """单个搜索源的状态"""
    name: str                           # 源名称（rrdynb/ddys/pansou）
    status: str                         # "success" | "failed" | "disabled" | "timeout"
    count: int = 0                      # 该源返回的结果数
    error: str = ""                     # 错误信息


class PanSearchResponse(BaseModel):
    """网盘搜索聚合响应"""
    results: List[PanResult] = []                    # 去重+过滤后的结果列表
    groups: Dict[str, List[PanResult]] = {}          # 按 pan_type 分组
    source_statuses: List[SourceStatus] = []         # 各源状态
    total: int = 0                                   # 总结果数


# ──────────────────────────────────────────────
# Alist 挂载信息
# ──────────────────────────────────────────────

# pan_type → Alist 驱动关键词（用于反向匹配，不硬编码驱动名）
# 启动时从 /api/admin/storage/list 动态构建实际映射表
PAN_TYPE_DRIVER_KEYWORDS = {
    PanType.QUARK: ["quark", "夸克"],
    PanType.ALIYUN: ["aliyun", "阿里"],
    PanType.BAIDU: ["baidu", "百度"],
    PanType.PAN115: ["115"],
    PanType.PIKPAK: ["pikpak"],
}


class MountInfo(BaseModel):
    """Alist 挂载状态信息（动态从 Alist API 获取）"""
    pan_type: PanType                   # 网盘类型（通过关键词反向匹配）
    driver: str                         # Alist 实际驱动名称（从 API 获取）
    mount_path: str                     # 挂载路径（如 /Quark）
    status: str                         # "work" | "disabled" | "error"


# ──────────────────────────────────────────────
# 转存请求与结果
# ──────────────────────────────────────────────

class TransferRequest(BaseModel):
    """转存请求"""
    share_url: str                      # 分享链接
    password: str = ""                  # 提取码
    pan_type: str                       # 网盘类型
    save_path: str                      # 目标保存路径（SMB 路径）
    media_name: str = ""                # 媒体名称（用于语义化重命名）
    year: str = ""                      # 年份（用于语义化重命名）
    season: str = ""                    # 季号（用于语义化重命名）


class TransferResult(BaseModel):
    """转存结果"""
    success: bool
    task_id: str = ""                   # DownloadManager 任务 ID
    transfer_type: str = ""             # "instant"（同盘秒传）| "async"（跨盘离线）
    error_code: str = ""                # 错误码枚举见下方
    error_message: str = ""             # 用户可读的错误提示

    # error_code 枚举：
    # "disk_full"          — 目标网盘空间不足
    # "local_cache_full"   — PC 本地缓存盘空间不足（跨盘转存需要）
    # "smb_full"           — 目标 SMB 磁盘空间不足
    # "name_conflict"      — 同名文件冲突
    # "link_expired"       — 分享链接已失效
    # "wrong_password"     — 提取码错误
    # "not_complete"       — 非整季资源，拒绝转存
    # "no_path_mapping"    — 无法建立 SMB↔Alist 路径映射，无法归位
    # "duplicate"          — 重复任务（transfer_id 已存在）
    # "alist_unavailable"  — Alist 服务不可达
    # "not_mounted"        — 该网盘类型未挂载


# ──────────────────────────────────────────────
# 路径映射（SMB ↔ Alist）
# ──────────────────────────────────────────────

class PathMapping(BaseModel):
    """SMB 本地路径与 Alist 虚拟路径的映射关系。

    用于转存完成后自动触发"拉回本地"的闭环流程。
    示例：
      smb_root = "\\\\DS218play\\share\\视频"
      alist_root = "/视频"
      → SMB 路径 "\\\\DS218play\\share\\视频\\电影\\流浪地球"
        对应 Alist 路径 "/视频/电影/流浪地球"
    """
    smb_root: str                       # SMB 挂载根路径（如 \\DS218play\share\视频）
    alist_root: str                     # Alist 对应的虚拟根路径（如 /视频）

    def smb_to_alist(self, smb_path: str) -> Optional[str]:
        """SMB 路径 → Alist 虚拟路径"""
        # 统一分隔符
        normalized = smb_path.replace("\\", "/")
        root_normalized = self.smb_root.replace("\\", "/")
        if not normalized.startswith(root_normalized):
            return None
        relative = normalized[len(root_normalized):]
        return self.alist_root.rstrip("/") + "/" + relative.lstrip("/")

    def alist_to_smb(self, alist_path: str) -> Optional[str]:
        """Alist 虚拟路径 → SMB 路径"""
        if not alist_path.startswith(self.alist_root):
            return None
        relative = alist_path[len(self.alist_root):]
        # 转回 Windows 分隔符
        return self.smb_root.rstrip("\\") + "\\" + relative.lstrip("/").replace("/", "\\")
