"""
路由模块：auth — 访问密码的登录、登出与设置

这些接口本身不能要求鉴权（否则设不了密码也登不了录），
所以它们在 main.py 的中间件白名单里。安全性靠：
- login 校验密码（失败只回"密码错误"，不区分"没设密码"与"密码不对"以外的信息）
- 修改 / 关闭密码必须带旧密码
"""
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from core.access_guard import (
    SESSION_COOKIE, generate_secret, hash_password, issue_token, verify_password, verify_token,
)
from shared import config_m

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    password: str = ""


class PasswordRequest(BaseModel):
    # 留空表示关闭访问控制
    new_password: str = ""
    # 已经设过密码时必填
    old_password: str = ""


def is_access_enabled() -> bool:
    return bool(config_m.config.access_password_hash)


def _set_session_cookie(response: Response, token: str, days: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=days * 86400,
        httponly=True,      # JS 读不到，XSS 偷不走
        samesite="lax",
        # 不能设 secure：局域网是 http 访问，设了 secure 浏览器根本不会发这个 cookie
        secure=False,
        path="/",
    )


@router.get("/auth/status")
def auth_status(request: Request):
    """前端据此决定要不要显示登录页。未启用时一律算已通过。"""
    if not is_access_enabled():
        return {"enabled": False, "authenticated": True}
    token = request.cookies.get(SESSION_COOKIE, "")
    return {
        "enabled": True,
        "authenticated": verify_token(token, config_m.config.access_token_secret),
    }


@router.post("/auth/login")
def auth_login(req: LoginRequest, response: Response):
    if not is_access_enabled():
        return {"status": "ok", "enabled": False}

    config = config_m.config
    if not verify_password(req.password, config.access_password_hash):
        # 不记录密码本身，但记录失败事件 —— 局域网里被撞库时得能看出来
        logger.warning("[auth] 登录失败：密码错误")
        raise HTTPException(status_code=401, detail="密码错误")

    token = issue_token(config.access_token_secret, config.access_session_days)
    _set_session_cookie(response, token, config.access_session_days)
    return {"status": "ok", "enabled": True}


@router.post("/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.post("/auth/password")
def set_access_password(req: PasswordRequest, response: Response):
    """设置 / 修改 / 关闭访问密码。

    首次设置不需要旧密码（此时系统本来就是敞开的，要求旧密码没有意义）；
    已经设过之后，修改和关闭都必须带对旧密码。
    """
    config = config_m.config

    if config.access_password_hash and not verify_password(req.old_password, config.access_password_hash):
        raise HTTPException(status_code=401, detail="旧密码错误")

    if not req.new_password:
        # 关闭访问控制：连签名密钥一起清掉，已签发的 token 全部失效
        config.access_password_hash = ""
        config.access_token_secret = ""
        config_m.save(config)
        response.delete_cookie(SESSION_COOKIE, path="/")
        logger.info("[auth] 访问密码已关闭")
        return {"status": "ok", "enabled": False}

    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="密码至少 4 位")

    config.access_password_hash = hash_password(req.new_password)
    # 换密码同时换签名密钥：否则旧 token 还能继续用，改密码等于没改
    config.access_token_secret = generate_secret()
    config_m.save(config)

    # 设完立刻给当前浏览器发一个新会话，不然刚设完就把自己挡在外面
    token = issue_token(config.access_token_secret, config.access_session_days)
    _set_session_cookie(response, token, config.access_session_days)
    logger.info("[auth] 访问密码已设置")
    return {"status": "ok", "enabled": True}
