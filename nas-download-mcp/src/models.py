"""对外 DTO、统一状态枚举、错误契约（todo §3/§4/§11）。"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── §4 对 Hermes 暴露的统一状态（屏蔽 qB/napics 原始串）──
class TaskStatus(str, Enum):
    STARTING = "starting"
    SEARCHING = "searching"
    SELECTING = "selecting"
    PROBING = "probing"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    WAITING_USER = "waiting_user"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    EXHAUSTED = "exhausted"


TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.TIMEOUT,
    TaskStatus.EXHAUSTED,
}


# ── 内部细粒度阶段（SQLite current_stage，比对外状态更细）──
class Stage(str, Enum):
    CREATED = "CREATED"
    STARTING_SERVICES = "STARTING_SERVICES"
    SERVICES_READY = "SERVICES_READY"
    SEARCHING = "SEARCHING"
    RESOURCE_SELECTION = "RESOURCE_SELECTION"
    PROBING_RESOURCES = "PROBING_RESOURCES"
    DOWNLOADING = "DOWNLOADING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    CLEANING_UP = "CLEANING_UP"
    SERVICES_STOPPED = "SERVICES_STOPPED"
    WAITING_USER = "WAITING_USER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


# ── §11 错误契约 ──
class ErrorCode(str, Enum):
    NAPICS_UNAVAILABLE = "NAPICS_UNAVAILABLE"
    QB_UNAVAILABLE = "QB_UNAVAILABLE"
    PROWLARR_UNAVAILABLE = "PROWLARR_UNAVAILABLE"
    SERVICE_START_FAILED = "SERVICE_START_FAILED"
    SEARCH_FAILED = "SEARCH_FAILED"
    NO_RESULTS = "NO_RESULTS"
    SOURCE_MISSING = "SOURCE_MISSING"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    DOWNLOAD_NOT_FOUND = "DOWNLOAD_NOT_FOUND"
    PROBE_EXHAUSTED = "PROBE_EXHAUSTED"
    PROCESS_FAILED = "PROCESS_FAILED"
    PROCESS_PARTIAL = "PROCESS_PARTIAL"
    CANCEL_FAILED = "CANCEL_FAILED"
    AUTH_FAILED = "AUTH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool = False


def err(code: ErrorCode, message: str, retryable: bool = False) -> dict:
    """构造统一错误返回（不抛裸异常给上层）。"""
    return {"error": ToolError(code=code, message=message, retryable=retryable).model_dump(mode="json")}


# ── §2.1 napics 搜索返回的展平资源 ──
class Resource(BaseModel):
    title: str = ""
    source: Optional[str] = None          # 片源类型 BluRay/WEB-DL
    indexer: Optional[str] = None          # 索引器/站点
    download_url: str = ""
    size_gb: Optional[float] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    resolution: Optional[str] = None       # 2160p 等，用于筛 4k
    codec: Optional[str] = None
    release_group: Optional[str] = None
    has_chinese_sub: Optional[bool] = None
    score: Optional[int] = None

    def is_magnet(self) -> bool:
        return self.download_url.lower().startswith("magnet:")


# ── qB 直连查进度的统一结果 ──
class QbState(str, Enum):
    DOWNLOADING = "downloading"
    STALLED = "stalled"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    UNKNOWN = "unknown"


class DownloadStatus(BaseModel):
    state: QbState = QbState.UNKNOWN
    percentage: float = 0.0
    download_speed_bytes: int = 0
    eta_seconds: Optional[int] = None


# ── download_movie 入参 ──
def normalize_resolution(s: str) -> str:
    """把口语分辨率归一到标准档：4k/2160->2160p, 1080->1080p, 720->720p。"""
    if not s:
        return ""
    t = s.lower().strip()
    if "2160" in t or "4k" in t or "uhd" in t:
        return "2160p"
    if "1080" in t:
        return "1080p"
    if "720" in t:
        return "720p"
    if "480" in t:
        return "480p"
    return t


class Constraints(BaseModel):
    resolution: Optional[str] = None       # 精确档位："1080p" 就只要 1080p，不要 2160p/720p
    max_size_gb: Optional[float] = None


class DownloadMovieInput(BaseModel):
    title: str
    media_type: str = "movie"              # movie | tv
    year: Optional[int] = None
    original_title: Optional[str] = None
    original_language: Optional[str] = None
    queries: list[str] = Field(default_factory=list)
    constraints: Optional[Constraints] = None
    save_path: Optional[str] = None
    season: Optional[int] = None
    interactive: bool = True


# ── 容器/服务健康 ──
class ServiceHealth(BaseModel):
    container: Optional[str] = None
    running: bool = False
    healthy: bool = False
    managed: bool = True
    reachable: Optional[bool] = None       # qB 用（不 managed 时看 reachable）
