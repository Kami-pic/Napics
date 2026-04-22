"""夸克网盘转存模块 — 将分享链接的文件保存到自己的夸克网盘。

流程：
1. 从 Alist 配置中自动提取夸克 Cookie
2. 解析分享链接获取 stoken
3. 获取分享文件列表
4. 调用转存接口保存到指定目录
"""

import re
import time
import json
import hashlib
import logging
import requests
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
# 夸克 API 基础 URL
QUARK_API = "https://drive-pc.quark.cn/1/clouddrive"
QUARK_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
QUARK_REFERER = "https://pan.quark.cn"


class QuarkTransfer:
    """夸克网盘转存客户端。"""

    def __init__(self, cookie: str = ""):
        self.cookie = cookie
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": QUARK_UA,
            "Referer": QUARK_REFERER,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        })
        if cookie:
            self.session.headers["Cookie"] = cookie

    @classmethod
    def from_alist(cls, alist_url: str, alist_token: str) -> Optional["QuarkTransfer"]:
        """从 Alist 存储配置中自动提取夸克 Cookie 并创建实例。"""
        try:
            headers = {"Authorization": alist_token}
            r = requests.get(
                f"{alist_url}/api/admin/storage/list",
                headers=headers, timeout=5
            )
            storages = r.json().get("data", {}).get("content", [])

            for s in storages:
                if s.get("driver") == "Quark" and s.get("status") == "work":
                    detail_r = requests.get(
                        f"{alist_url}/api/admin/storage/get?id={s['id']}",
                        headers=headers, timeout=5
                    )
                    if detail_r.status_code == 200:
                        addition = detail_r.json().get("data", {}).get("addition", "")
                        if addition:
                            add_data = json.loads(addition)
                            cookie = add_data.get("cookie", "")
                            if cookie:
                                logger.info("[QuarkTransfer] 从 Alist 提取夸克 Cookie 成功")
                                return cls(cookie=cookie)
        except Exception as e:
            logger.error("[QuarkTransfer] 从 Alist 提取 Cookie 失败: %s", str(e))
        return None

    def _ts(self) -> str:
        """当前毫秒时间戳。"""
        return str(int(time.time() * 1000))

    def _extract_pwd_id(self, share_url: str) -> Optional[str]:
        """从分享链接提取 pwd_id（分享码）。
        支持格式：
        - https://pan.quark.cn/s/abc123
        - https://drive.quark.cn/s/abc123
        """
        m = re.search(r"/s/([a-zA-Z0-9]+)", share_url)
        return m.group(1) if m else None

    def get_stoken(self, pwd_id: str, passcode: str = "") -> Optional[str]:
        """获取分享页面的 stoken（访问令牌）。"""
        url = f"{QUARK_API}/share/sharepage/token?pr=ucpro&fr=pc&uc_param_str=&__dt=&__t={self._ts()}"
        payload = {"pwd_id": pwd_id, "passcode": passcode}

        try:
            resp = self.session.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                return data["data"].get("stoken")
            else:
                logger.warning("[QuarkTransfer] 获取 stoken 失败: %s", data.get("message", ""))
                return None
        except Exception as e:
            logger.error("[QuarkTransfer] 获取 stoken 异常: %s", str(e))
            return None

    def get_share_files(self, pwd_id: str, stoken: str,
                        pdir_fid: str = "0") -> List[Dict]:
        """获取分享文件列表。"""
        from urllib.parse import quote
        url = (f"{QUARK_API}/share/sharepage/detail"
               f"?pr=ucpro&fr=pc&pwd_id={pwd_id}&stoken={quote(stoken, safe='')}"
               f"&pdir_fid={pdir_fid}&force=0&_page=1&_size=50"
               f"&_sort=file_type:asc,updated_at:desc&__dt=&__t={self._ts()}")

        try:
            resp = self.session.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == 200 and data.get("data"):
                return data["data"].get("list", [])
            else:
                logger.warning("[QuarkTransfer] 获取文件列表失败: %s", data.get("message", ""))
                return []
        except Exception as e:
            logger.error("[QuarkTransfer] 获取文件列表异常: %s", str(e))
            return []

    def save_to_my_drive(self, pwd_id: str, stoken: str,
                         fid_list: List[str], fid_token_list: List[str],
                         to_pdir_fid: str = "0") -> Dict:
        """将分享文件转存到自己的网盘。"""
        url = f"{QUARK_API}/share/sharepage/save?pr=ucpro&fr=pc&uc_param_str=&__dt=&__t={self._ts()}"
        payload = {
            "fid_list": fid_list,
            "fid_token_list": fid_token_list,
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        }

        try:
            resp = self.session.post(url, json=payload, timeout=15)
            data = resp.json()

            if data.get("status") == 200:
                task_id = data.get("data", {}).get("task_id", "")
                logger.info("[QuarkTransfer] 转存成功, task_id=%s", task_id)
                return {"success": True, "error_code": "", "error_message": "",
                        "task_id": task_id}
            else:
                msg = data.get("message", "未知错误")
                code = self._map_error(msg, data.get("code", 0))
                logger.warning("[QuarkTransfer] 转存失败: %s (code=%s)", msg, data.get("code"))
                return {"success": False, "error_code": code,
                        "error_message": msg, "task_id": ""}

        except Exception as e:
            logger.error("[QuarkTransfer] 转存异常: %s", str(e))
            return {"success": False, "error_code": "network_error",
                    "error_message": str(e), "task_id": ""}

    def transfer(self, share_url: str, passcode: str = "",
                 to_pdir_fid: str = "0") -> Dict:
        """一键转存：从分享链接到自己的网盘。

        完整流程：解析链接 → 获取 stoken → 获取文件列表 → 转存全部文件。
        """
        # 1. 解析分享码
        pwd_id = self._extract_pwd_id(share_url)
        if not pwd_id:
            return {"success": False, "error_code": "invalid_url",
                    "error_message": "无法解析分享链接"}

        # 2. 获取 stoken
        stoken = self.get_stoken(pwd_id, passcode)
        if not stoken:
            return {"success": False, "error_code": "stoken_failed",
                    "error_message": "获取分享令牌失败（链接可能已失效或需要提取码）"}

        # 3. 获取文件列表
        files = self.get_share_files(pwd_id, stoken)
        if not files:
            return {"success": False, "error_code": "no_files",
                    "error_message": "分享中没有文件"}

        # 4. 提取所有文件 ID 和 token
        fid_list = [f.get("fid", "") for f in files if f.get("fid")]
        fid_token_list = [f.get("share_fid_token", "") for f in files if f.get("fid")]
        if not fid_list:
            return {"success": False, "error_code": "no_fids",
                    "error_message": "无法获取文件 ID"}

        # 5. 转存
        return self.save_to_my_drive(pwd_id, stoken, fid_list, fid_token_list, to_pdir_fid)

    def _map_error(self, msg: str, code: int = 0) -> str:
        """错误码映射。"""
        msg_lower = msg.lower()
        if "已转存" in msg or "already" in msg_lower or code == 41017:
            return "already_saved"
        if "空间" in msg or "space" in msg_lower or "quota" in msg_lower:
            return "disk_full"
        if "失效" in msg or "expired" in msg_lower or "not found" in msg_lower:
            return "link_expired"
        if "密码" in msg or "passcode" in msg_lower or "提取码" in msg:
            return "wrong_password"
        if "频繁" in msg or "frequent" in msg_lower:
            return "rate_limited"
        return "transfer_failed"
