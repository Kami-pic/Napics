"""ServiceManager（todo §5/§8）：容器生命周期。

启动顺序：kami-pic → 等 napics health → prowlarr → 等 prowlarr health → 检查 qB。
停止顺序反向：prowlarr → kami-pic。cleanup best-effort，单个失败不阻断其它。
qB 是飞牛官方应用，只探活不启停。
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from adapters.docker_adapter import DockerAdapter
from adapters.qb_client import QbClient
from config import Config

logger = logging.getLogger("nas_download_mcp.service")


class ServiceStartError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ServiceManager:
    def __init__(self, cfg: Config, docker: DockerAdapter):
        self.cfg = cfg
        self.docker = docker
        # 记录本任务是否亲手启动了容器（ownership，用于按策略决定是否 stop）
        self.started_by_task = {"napics": False, "prowlarr": False}

    # ── 健康探测 ──
    async def _wait_http_ok(self, url: str, timeout_s: int = 60, expect_json_ok: bool = False) -> bool:
        """轮询直到 HTTP 可用。expect_json_ok=True 时要求返回体 {ok:true}（napics health）。

        不能只判 TCP 端口（todo §15）——容器起来了但应用没就绪会误判。
        """
        deadline = time.time() + timeout_s
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.time() < deadline:
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        if not expect_json_ok:
                            return True
                        try:
                            if bool(r.json().get("ok")):
                                return True
                        except Exception:
                            pass
                except Exception:
                    pass
                await asyncio.sleep(2)
        return False

    def _qb_reachable(self) -> bool:
        c = QbClient(self.cfg.qb_url, self.cfg.qb_username, self.cfg.qb_password)
        try:
            return c.reachable()
        finally:
            c.close()

    # ── 启动 ──
    async def ensure_started(self) -> None:
        """按顺序拉起 napics/prowlarr 并健康检查；qB 只探活。失败抛 ServiceStartError。"""
        # 1) napics
        if not self.docker.is_running(self.cfg.napics_container):
            if not self.docker.start(self.cfg.napics_container):
                raise ServiceStartError("SERVICE_START_FAILED", f"启动 {self.cfg.napics_container} 失败")
            self.started_by_task["napics"] = True
        # 2) 等 napics health
        health_url = f"{self.cfg.napics_api_base}/api/agent/health"
        if not await self._wait_http_ok(health_url, timeout_s=90, expect_json_ok=True):
            raise ServiceStartError("NAPICS_UNAVAILABLE", "napics 健康检查超时")

        # 3) prowlarr（napics 起不来就不启动 prowlarr，见 §71）
        if not self.docker.is_running(self.cfg.prowlarr_container):
            if not self.docker.start(self.cfg.prowlarr_container):
                raise ServiceStartError("SERVICE_START_FAILED", f"启动 {self.cfg.prowlarr_container} 失败")
            self.started_by_task["prowlarr"] = True
        # 4) 等 prowlarr health（:9696 返回 200，登录页也算可达）
        if not await self._wait_http_ok(self.cfg.prowlarr_url, timeout_s=90, expect_json_ok=False):
            raise ServiceStartError("PROWLARR_UNAVAILABLE", "prowlarr 健康检查超时")

        # 5) qB 探活（不启停，但必须可达，否则 §72 FAILED）
        if not self._qb_reachable():
            raise ServiceStartError("QB_UNAVAILABLE", "qBittorrent 不可达")

    # ── 停止 / cleanup（best-effort）──
    def _should_stop(self, which: str) -> bool:
        if self.cfg.stop_services_after_task:
            return True  # 用户要"下完释放内存"，即便任务开始时已在跑也停
        return self.started_by_task.get(which, False)

    async def cleanup(self) -> dict:
        """停 prowlarr → 停 kami-pic，逐个 best-effort。返回每个容器成功与否。"""
        result: dict[str, dict] = {}
        # prowlarr 先停
        if self._should_stop("prowlarr"):
            ok = self.docker.stop(self.cfg.prowlarr_container)
            result["prowlarr"] = {"success": ok}
            if not ok:
                logger.error("[service] 停止 prowlarr 失败，继续停 napics（best-effort）")
        # napics 后停（即使上面失败也要停，§44）
        if self._should_stop("napics"):
            ok = self.docker.stop(self.cfg.napics_container)
            result["napics"] = {"success": ok}
        result["qbittorrent"] = {"managed": False}
        return result

    def status(self) -> dict:
        """get_system_status 用（todo §3.5）。"""
        napics_running = self.docker.is_running(self.cfg.napics_container)
        prowlarr_running = self.docker.is_running(self.cfg.prowlarr_container)
        return {
            "napics": {"container": self.cfg.napics_container, "running": napics_running},
            "prowlarr": {"container": self.cfg.prowlarr_container, "running": prowlarr_running},
            "qbittorrent": {"managed": False, "reachable": self._qb_reachable()},
        }
