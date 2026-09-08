"""对外 DTO（Pydantic）、统一状态枚举、错误契约。见 todo §3 / §4 / §5。

对外只暴露统一枚举，绝不让上层看到 qB 原始 state 字符串。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ── §4 统一状态枚举 ──

STATUS_QUEUED = "queued"
STATUS_DOWNLOADING = "downloading"
STATUS_STALLED = "stalled"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_PROCESSING = "processing"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_UNKNOWN = "unknown"

# qB 原始 state → 统一枚举。progress==1 在映射函数里另行短路。
_QB_STATE_MAP = {
    "downloading": STATUS_DOWNLOADING,
    "metaDL": STATUS_DOWNLOADING,
    "forcedDL": STATUS_DOWNLOADING,
    "allocating": STATUS_DOWNLOADING,
    "checkingDL": STATUS_DOWNLOADING,
    "queuedDL": STATUS_QUEUED,
    "stalledDL": STATUS_STALLED,
    "pausedDL": STATUS_PAUSED,
    "stoppedDL": STATUS_PAUSED,
    "uploading": STATUS_COMPLETED,
    "forcedUP": STATUS_COMPLETED,
    "stalledUP": STATUS_COMPLETED,
    "queuedUP": STATUS_COMPLETED,
    "pausedUP": STATUS_COMPLETED,
    "stoppedUP": STATUS_COMPLETED,
    "checkingUP": STATUS_COMPLETED,
    "error": STATUS_FAILED,
    "missingFiles": STATUS_FAILED,
}


def map_qb_state(state: str, progress: float) -> str:
    """qB 原始 state + progress → 统一枚举。progress==1 一律视作 completed。"""
    if progress is not None and progress >= 1.0:
        # error/missingFiles 仍应报失败，即便 progress 满
        mapped = _QB_STATE_MAP.get(state, STATUS_UNKNOWN)
        if mapped == STATUS_FAILED:
            return STATUS_FAILED
        return STATUS_COMPLETED
    return _QB_STATE_MAP.get(state, STATUS_UNKNOWN)


# ── §3 DTO ──

class BackendReach(BaseModel):
    configured: bool = False
    available: bool = False


class HealthResult(BaseModel):
    ok: bool
    napics: BackendReach
    qbittorrent: BackendReach


class Resource(BaseModel):
    title: str
    source: Optional[str] = None
    indexer: Optional[str] = None
    download_url: str
    size_gb: Optional[float] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    release_group: Optional[str] = None
    has_chinese_sub: Optional[bool] = None
    score: Optional[int] = None


class SearchResult(BaseModel):
    query: str
    total: int
    results: List[Resource]


class DownloadCreated(BaseModel):
    task_id: str
    qb_hash: Optional[str] = None
    status: str


class DownloadStatus(BaseModel):
    status: str
    percentage: float
    download_speed_bytes: int
    eta_seconds: Optional[int] = None


class ProcessResult(BaseModel):
    status: str  # processed | partial | failed
    library_path: Optional[str] = None
    files: List[str] = []
    message: Optional[str] = None


# ── §5 错误契约 ──

# 错误码
ERR_NAPICS_UNAVAILABLE = "NAPICS_UNAVAILABLE"
ERR_QB_UNAVAILABLE = "QB_UNAVAILABLE"
ERR_SEARCH_FAILED = "SEARCH_FAILED"
ERR_NO_RESULTS = "NO_RESULTS"
ERR_DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
ERR_DOWNLOAD_NOT_FOUND = "DOWNLOAD_NOT_FOUND"
ERR_PROCESS_FAILED = "PROCESS_FAILED"
ERR_CANCEL_FAILED = "CANCEL_FAILED"
ERR_AUTH_FAILED = "AUTH_FAILED"
ERR_INTERNAL = "INTERNAL_ERROR"


def error(code: str, message: str, retryable: bool) -> dict:
    """统一错误结构。工具失败返回它，绝不抛裸异常给上层。"""
    return {"error": {"code": code, "message": message, "retryable": retryable}}
