"""配置加载 —— 全部走环境变量。

安全红线（todo §12）：本 MCP 不读 napics 的 backend/config.json（明文凭据），
自己一套配置。qB 凭据、agent token 都从 env 来。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    # MCP server 自身
    mcp_host: str
    mcp_port: int

    # napics 后端（注意是 :8001 后端，不是 :3032 前端）
    napics_api_base: str
    napics_agent_token: str

    # 容器名（docker 白名单，qB 不在内）
    napics_container: str
    prowlarr_container: str

    # 外部服务地址
    prowlarr_url: str
    qb_url: str
    qb_username: str
    qb_password: str

    # probe 参数
    probe_batch_size: int
    probe_interval_seconds: int
    probe_timeout_seconds: int
    probe_min_speed_bytes: int
    stabilization_window_seconds: int

    # 下载/后处理超时
    processing_timeout_seconds: int
    download_timeout_seconds: int  # 0 = 无限等

    # 服务生命周期
    stop_services_after_task: bool
    recover_active_download: bool

    # 持久化
    database_path: str
    log_path: str

    # 推送渠道（§9，第一版可留空）
    notify_channel: str


def load_config() -> Config:
    return Config(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=_int("MCP_PORT", 8787),
        napics_api_base=os.getenv("NAPICS_API_BASE", "http://192.168.100.111:8001").rstrip("/"),
        napics_agent_token=os.getenv("NAPICS_AGENT_TOKEN", ""),
        napics_container=os.getenv("NAPICS_CONTAINER", "kami-pic"),
        prowlarr_container=os.getenv("PROWLARR_CONTAINER", "prowlarr"),
        prowlarr_url=os.getenv("PROWLARR_URL", "http://192.168.100.111:9696").rstrip("/"),
        qb_url=os.getenv("QB_URL", "http://192.168.100.111:8085").rstrip("/"),
        qb_username=os.getenv("QB_USERNAME", "admin"),
        qb_password=os.getenv("QB_PASSWORD", ""),
        probe_batch_size=_int("PROBE_BATCH_SIZE", 3),
        probe_interval_seconds=_int("PROBE_INTERVAL_SECONDS", 5),
        probe_timeout_seconds=_int("PROBE_TIMEOUT_SECONDS", 120),
        probe_min_speed_bytes=_int("PROBE_MIN_SPEED_BYTES", 10240),
        stabilization_window_seconds=_int("STABILIZATION_WINDOW_SECONDS", 10),
        processing_timeout_seconds=_int("PROCESSING_TIMEOUT_SECONDS", 1800),
        download_timeout_seconds=_int("DOWNLOAD_TIMEOUT_SECONDS", 0),
        stop_services_after_task=os.getenv("STOP_SERVICES_AFTER_TASK", "true").lower() == "true",
        recover_active_download=os.getenv("RECOVER_ACTIVE_DOWNLOAD", "true").lower() == "true",
        database_path=os.getenv("DATABASE_PATH", "/app/data/tasks.db"),
        log_path=os.getenv("LOG_PATH", "/app/logs"),
        notify_channel=os.getenv("NOTIFY_CHANNEL", ""),
    )
