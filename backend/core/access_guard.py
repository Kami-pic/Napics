"""访问控制：单一访问密码 + HMAC 签名 token。

## 为什么需要

后端不做鉴权、CORS 全开，而它提供的能力包括：`/fs/list` 枚举服务端全部盘符
（按设计不受媒体库白名单约束）、`/playback/stream` 直接吐文件内容、
批量删除与移动文件。移动端界面让这些能力第一次有了面向手机的入口，
同网段任何设备都能打开。

只在前端路由上加门是无效的 —— 直接打 `/backend/fs/list` 就绕过了。所以门必须在后端。

## 设计取舍

- **默认关闭**：没设密码时完全不校验。现有部署升级后行为零变化，
  不会出现"更新一下就把自己锁在外面"。
- **cookie 而不是 Authorization 头**：`<video src>` / `<img src>` 带不了自定义头，
  用头会让播放和海报全部 401。cookie 是唯一能覆盖这些标签的方案。
- **无服务端 session**：token 是 `过期时间.HMAC签名`，重启后仍然有效，
  也不需要在 JSON 里存一份会话表。代价是没法单独踢掉某个设备 ——
  要全部登出就换 secret。
- **单一密码，无用户体系**：Napics 是单人自用工具，多用户和权限分级不解决任何真实问题。

## 明确不解决的

这不是把 Napics 变成可以暴露到公网的东西。它挡住的是"同网段别人顺手打开"，
不是有针对性的攻击。公网访问仍然要靠 Tailscale / WireGuard 这类私有网络。
"""

import base64
import hashlib
import hmac
import secrets
import time

# 会话 cookie 名。加 __Host- 前缀会强制要求 https，局域网 http 用不了，所以不加。
SESSION_COOKIE = "napics_session"

# pbkdf2 轮数。这个值只在登录和改密码时各算一次，
# 200k 在树莓派级别的 CPU 上约 0.1 秒，够慢也不影响体验。
_PBKDF2_ROUNDS = 200_000
_HASH_SCHEME = "pbkdf2_sha256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    """把明文密码变成可落盘的字符串。绝不存明文 —— config.json 会被备份、
    会被贴到 issue 里，明文密码泄漏的路径太多。"""
    if not password:
        raise ValueError("密码不能为空")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"{_HASH_SCHEME}${_PBKDF2_ROUNDS}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码。任何格式异常都当成校验失败，不抛异常 ——
    调用方是登录接口，抛异常会变成 500 而不是"密码错误"。"""
    if not password or not stored:
        return False
    try:
        scheme, rounds_text, salt_text, expected_text = stored.split("$")
        if scheme != _HASH_SCHEME:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _unb64(salt_text), int(rounds_text),
        )
    except (ValueError, TypeError):
        return False
    # compare_digest 而不是 ==：避免按字节短路造成的时序泄漏
    return hmac.compare_digest(derived, _unb64(expected_text))


def generate_secret() -> str:
    """签名密钥。换掉它等于让所有已签发的 token 立即失效（全设备登出）。"""
    return secrets.token_urlsafe(32)


def issue_token(secret: str, ttl_days: int = 30) -> str:
    """签发会话 token。格式 `过期时间戳.HMAC`，服务端不存任何东西。"""
    if not secret:
        raise ValueError("缺少签名密钥")
    expires_at = int(time.time()) + max(1, ttl_days) * 86400
    payload = str(expires_at)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> bool:
    """校验 token：签名对得上且没过期。"""
    if not token or not secret:
        return False
    payload, _, signature = token.partition(".")
    if not payload or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    try:
        # 签名先验、再看过期：顺序反了会让攻击者用畸形 payload 探测行为差异
        return int(payload) > int(time.time())
    except ValueError:
        return False
