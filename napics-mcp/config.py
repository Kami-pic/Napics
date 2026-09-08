"""配置加载 —— 全部走环境变量，绝不读 napics 的 config.json（明文凭据）。

MCP 与 napics 解耦，可能跑在不同机器/容器：变的只是 NAPICS_API_BASE / QB_URL
填局域网 IP 还是 127.0.0.1（见 todo §1）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


@dataclass(frozen=True)
class Config:
    napics_api_base: str
    napics_agent_token: str
    qb_url: str
    qb_username: str
    qb_password: str
    http_timeout: float

    @property
    def qb_configured(self) -> bool:
        return bool(self.qb_url)

    @property
    def napics_configured(self) -> bool:
        return bool(self.napics_api_base)


def load_config() -> Config:
    """从环境变量装配配置。缺省值对齐 todo §1 的示例。"""
    return Config(
        napics_api_base=_env("NAPICS_API_BASE", "http://127.0.0.1:8001").rstrip("/"),
        napics_agent_token=_env("NAPICS_AGENT_TOKEN"),
        qb_url=_env("QB_URL", "http://127.0.0.1:8080").rstrip("/"),
        qb_username=_env("QB_USERNAME", "admin"),
        qb_password=_env("QB_PASSWORD"),
        http_timeout=float(_env("MCP_HTTP_TIMEOUT", "15")),
    )
