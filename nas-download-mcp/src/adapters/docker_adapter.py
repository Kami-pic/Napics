"""Docker adapter（todo §5/§12/§62）。

安全红线：只允许对白名单容器做 start/stop/inspect。禁止 exec/rm/run/pull/prune，
禁止 agent 传任意 container name（防命令注入/越权）。
走 docker socket；用 docker SDK（无 SDK 时回落 subprocess，仍受白名单约束）。
"""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("nas_download_mcp.docker")

# 逻辑名 → 真实容器名（白名单，qB 不在内）。
# 默认用中性逻辑名；真实容器名由部署方经 env（NAPICS_CONTAINER/PROWLARR_CONTAINER）注入，
# 开源代码里不写死任何具体部署的容器名。
DEFAULT_CONTAINERS = {
    "napics": "napics",
    "prowlarr": "prowlarr",
}

try:
    import docker as _docker_sdk  # type: ignore
    _HAS_SDK = True
except Exception:
    _HAS_SDK = False


class DockerAdapter:
    def __init__(self, containers: dict[str, str] | None = None):
        # 逻辑名 → 真实容器名。部署方经 env 注入真实名；缺省回落到中性逻辑名。
        self._allowed = dict(containers) if containers else dict(DEFAULT_CONTAINERS)
        self._allowed_real = set(self._allowed.values())
        self._client = None
        if _HAS_SDK:
            try:
                self._client = _docker_sdk.from_env()
            except Exception as e:
                logger.warning("[docker] SDK init 失败，回落 subprocess: %s", e)
                self._client = None

    def _check(self, container: str) -> str:
        """校验并返回真实容器名。传逻辑名或真实名都接受，非白名单一律拒绝。"""
        real = self._allowed.get(container, container)
        if real not in self._allowed_real:
            raise PermissionError(f"容器不在白名单: {container!r}（仅允许 {sorted(self._allowed_real)}）")
        return real

    @classmethod
    def from_config(cls, cfg) -> "DockerAdapter":
        """用部署方经 env 注入的真实容器名构造白名单。"""
        return cls({
            "napics": cfg.napics_container,
            "prowlarr": cfg.prowlarr_container,
        })

    # ── SDK 路径 ──
    def _sdk_action(self, real: str, action: str) -> bool:
        c = self._client.containers.get(real)
        if action == "start":
            c.start()
        elif action == "stop":
            c.stop()
        return True

    def _sdk_running(self, real: str) -> bool:
        try:
            c = self._client.containers.get(real)
            return c.status == "running"
        except Exception:
            return False

    # ── subprocess 回落（仍只接受校验过的真实名，非 shell）──
    @staticmethod
    def _run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=60
        )

    def start(self, container: str) -> bool:
        real = self._check(container)
        try:
            if self._client:
                return self._sdk_action(real, "start")
            r = self._run(["start", real])
            return r.returncode == 0
        except Exception as e:
            logger.error("[docker] start %s 失败: %s", real, e)
            return False

    def stop(self, container: str) -> bool:
        real = self._check(container)
        try:
            if self._client:
                return self._sdk_action(real, "stop")
            r = self._run(["stop", real])
            return r.returncode == 0
        except Exception as e:
            logger.error("[docker] stop %s 失败: %s", real, e)
            return False

    def is_running(self, container: str) -> bool:
        real = self._check(container)
        try:
            if self._client:
                return self._sdk_running(real)
            r = self._run(["inspect", "-f", "{{.State.Running}}", real])
            return r.returncode == 0 and r.stdout.strip() == "true"
        except Exception as e:
            logger.error("[docker] inspect %s 失败: %s", real, e)
            return False
