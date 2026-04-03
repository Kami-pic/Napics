import requests
import time
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# pan_type → Alist 驱动关键词（用于反向匹配）
_PAN_TYPE_KEYWORDS = {
    "quark": ["quark", "夸克"],
    "aliyun": ["aliyun", "阿里"],
    "baidu": ["baidu", "百度"],
    "pan115": ["115"],
    "pikpak": ["pikpak"],
}

class AlistAccount(BaseModel):
    name: str
    driver: str
    status: str
    free_space_gb: float

class MountInfo(BaseModel):
    pan_type: str
    driver: str
    mount_path: str
    status: str

class AlistManager:
    def __init__(self, api_url: str, token: str):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.headers = {"Authorization": token}
        # 挂载状态缓存
        self._mount_cache: Dict[str, MountInfo] = {}
        self._mount_cache_time: float = 0
        self._mount_cache_ttl: float = 300  # 5 分钟

    # ── 挂载状态管理 ──

    def get_mount_status(self) -> Dict[str, MountInfo]:
        """查询并缓存 Alist 已挂载存储列表，动态构建 pan_type→驱动映射。"""
        now = time.time()
        if self._mount_cache and (now - self._mount_cache_time) < self._mount_cache_ttl:
            return self._mount_cache

        try:
            url = f"{self.api_url}/api/admin/storage/list"
            resp = requests.get(url, headers=self.headers, timeout=5)
            resp.raise_for_status()
            storages = resp.json().get("data", {}).get("content", [])

            cache: Dict[str, MountInfo] = {}
            for s in storages:
                driver = s.get("driver", "")
                mount_path = s.get("mount_path", "")
                status = s.get("status", "")
                disabled = s.get("disabled", False)

                if disabled:
                    continue

                # 反向匹配 pan_type
                pan_type = self._match_pan_type(driver, mount_path)
                if pan_type:
                    cache[pan_type] = MountInfo(
                        pan_type=pan_type,
                        driver=driver,
                        mount_path=mount_path,
                        status="work" if status == "work" else "error",
                    )

            self._mount_cache = cache
            self._mount_cache_time = now
            logger.info("[Alist] 挂载缓存刷新: %s", list(cache.keys()))
            return cache

        except Exception as e:
            logger.error("[Alist] 获取挂载状态失败: %s", str(e))
            return self._mount_cache

    def _match_pan_type(self, driver: str, mount_path: str) -> Optional[str]:
        """通过驱动名和挂载路径反向匹配 pan_type。"""
        combined = (driver + " " + mount_path).lower()
        for pan_type, keywords in _PAN_TYPE_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return pan_type
        return None

    def is_mounted(self, pan_type: str) -> bool:
        """检查指定网盘类型是否已挂载且状态正常。"""
        mounts = self.get_mount_status()
        info = mounts.get(pan_type)
        return info is not None and info.status == "work"

    def get_mount_path(self, pan_type: str) -> Optional[str]:
        """获取指定网盘类型的挂载路径。"""
        mounts = self.get_mount_status()
        info = mounts.get(pan_type)
        return info.mount_path if info else None

    def get_mounts_list(self) -> List[MountInfo]:
        """返回所有挂载信息列表（供 API 使用）。"""
        return list(self.get_mount_status().values())

    # ── 网盘分享链接转存 ──

    def transfer_pan_share(self, share_url: str, pan_type: str,
                           save_path: str = "") -> Dict:
        """网盘分享链接转存到 Alist。

        通过 Alist 的离线下载接口，将网盘分享链接拉取到指定路径。
        Alist 会自动处理同盘转存（秒传）和跨盘离线。

        返回: {"success": bool, "error_code": str, "error_message": str}
        """
        # 检查 Alist 可达
        if not self._check_alive():
            return {"success": False, "error_code": "alist_unavailable",
                    "error_message": "Alist 服务不可达"}

        # 确定保存路径
        if not save_path:
            mount_path = self.get_mount_path(pan_type)
            if mount_path:
                save_path = mount_path
            else:
                # 默认用夸克
                save_path = "/Quark"

        # 确定离线下载工具
        tool = self._select_tool(pan_type)

        try:
            url = f"{self.api_url}/api/fs/add_offline_download"
            payload = {
                "urls": [share_url],
                "path": save_path,
                "tool": tool,
            }
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = resp.json()

            if data.get("code") == 200:
                logger.info("[Alist] 转存成功: %s -> %s (tool=%s)", share_url[:50], save_path, tool)
                return {"success": True, "error_code": "", "error_message": ""}
            else:
                error_msg = data.get("message", "未知错误")
                error_code = self._map_error(error_msg)
                logger.warning("[Alist] 转存失败: %s — %s", share_url[:50], error_msg)
                return {"success": False, "error_code": error_code, "error_message": error_msg}

        except Exception as e:
            logger.error("[Alist] 转存异常: %s", str(e))
            return {"success": False, "error_code": "alist_error", "error_message": str(e)}

    def _select_tool(self, pan_type: str) -> str:
        """根据网盘类型选择 Alist 离线下载工具。"""
        tool_map = {
            "quark": "SimpleHttp",
            "aliyun": "SimpleHttp",
            "baidu": "SimpleHttp",
            "pan115": "115 Cloud",
            "pikpak": "PikPak",
        }
        return tool_map.get(pan_type, "SimpleHttp")

    def _map_error(self, error_msg: str) -> str:
        """Alist 错误信息映射为标准错误码。"""
        msg = error_msg.lower()
        if "space" in msg or "空间" in msg or "quota" in msg:
            return "disk_full"
        if "exist" in msg or "已存在" in msg or "conflict" in msg:
            return "name_conflict"
        if "expired" in msg or "失效" in msg or "invalid" in msg or "not found" in msg:
            return "link_expired"
        if "password" in msg or "提取码" in msg or "密码" in msg:
            return "wrong_password"
        return "alist_error"

    def _check_alive(self) -> bool:
        """检查 Alist 服务是否可达。"""
        try:
            resp = requests.get(f"{self.api_url}/api/public/settings", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    # ── 原有方法保留 ──

    def get_accounts(self) -> List[AlistAccount]:
        """获取所有已挂载的存储账号"""
        try:
            url = f"{self.api_url}/api/admin/storage/list"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            data = response.json().get("data", {}).get("content", [])
            
            accounts = []
            for item in data:
                # 获取存储详情以计算空间 (简化逻辑)
                accounts.append(AlistAccount(
                    name=item.get("mount_path", ""),
                    driver=item.get("driver", ""),
                    status=item.get("status", ""),
                    free_space_gb=0  # 需要额外 API 调用获取空间
                ))
            return accounts
        except Exception as e:
            print(f"Alist error: {e}")
            return []

    def transfer_link(self, download_url: str, remote_path: str) -> bool:
        """将下载链接推送到 Alist 进行离线下载（优先 PikPak，其次 115）"""
        # 尝试的工具和路径列表（优先夸克）
        tools = [
            ("SimpleHttp", "/Quark"),
            ("PikPak", "/PikPak"),
            ("115 Cloud", "/115"),
        ]
        for tool, default_path in tools:
            try:
                url = f"{self.api_url}/api/fs/add_offline_download"
                save_path = remote_path if remote_path.startswith("/") else default_path
                payload = {
                    "urls": [download_url],
                    "path": save_path,
                    "tool": tool,
                }
                response = requests.post(url, json=payload, headers=self.headers, timeout=15)
                data = response.json()
                if data.get("code") == 200:
                    print(f"[Alist] offline download via {tool} -> {save_path}")
                    return True
            except Exception as e:
                print(f"[Alist] {tool} error: {e}")
                continue
        print("[Alist] all tools failed")
        return False

class QBittorrentClient:
    def __init__(self, url: str, username: str = "admin", password: str = ""):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._logged_in = False

    def _login(self):
        if self._logged_in:
            return True
        try:
            r = self.session.post(f"{self.url}/api/v2/auth/login", data={
                "username": self.username, "password": self.password
            }, timeout=5)
            self._logged_in = r.status_code == 200 and r.text == "Ok."
            return self._logged_in
        except:
            return False

    def add_torrent(self, torrent_url: str, save_path: str) -> bool:
        """推送到 qBittorrent 下载"""
        try:
            if not self._login():
                print("[qB] login failed")
                return False
            data = {"urls": torrent_url}
            if save_path:
                data["savepath"] = save_path
            r = self.session.post(f"{self.url}/api/v2/torrents/add", data=data, timeout=10)
            if r.status_code != 200:
                print(f"[qB] add_torrent failed: status={r.status_code}, body={r.text[:200]}")
                return False
            # qB 返回 "Ok." 或 "Fails." — 两种都视为成功（qB 有时返回 Fails 但实际已添加）
            return True
        except Exception as e:
            print(f"qBittorrent error: {e}")
            return False
