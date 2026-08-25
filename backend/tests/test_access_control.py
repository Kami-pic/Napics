"""访问控制：密码哈希、会话 token、中间件拦截。

背景：后端不做鉴权、CORS 全开，而它能枚举服务端全部盘符（/fs/list 按设计
不受媒体库白名单约束）、直接吐文件内容、批量删除移动文件。移动端界面让这些
能力第一次有了面向手机的入口。

**只在前端路由上加门是无效的** —— 直接打 /backend/fs/list 就绕过了，
所以下面有一条专门钉住"中间件真的拦住了后端接口"。
"""

import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.access_guard import (
    SESSION_COOKIE, generate_secret, hash_password, issue_token, verify_password, verify_token,
)


# ── 密码哈希 ──

def test_hash_is_not_plaintext_and_is_salted():
    """config.json 会被备份、会被贴进 issue，绝不能存明文"""
    stored = hash_password("我的密码123")
    assert "我的密码123" not in stored
    assert stored.startswith("pbkdf2_sha256$")
    # 同一个密码两次哈希必须不同（加盐），否则能靠比对哈希判断两处密码是否相同
    assert stored != hash_password("我的密码123")


def test_verify_password_accepts_correct_and_rejects_wrong():
    stored = hash_password("正确密码")
    assert verify_password("正确密码", stored)
    assert not verify_password("错误密码", stored)
    assert not verify_password("", stored)
    assert not verify_password("正确密码", "")


def test_verify_password_survives_garbage_stored_value():
    """存储值被手改坏时只能算校验失败，不能抛异常（否则登录接口变 500）"""
    for broken in ("", "乱码", "pbkdf2_sha256$abc", "other$1$2$3", "pbkdf2_sha256$x$y$z"):
        assert verify_password("任意密码", broken) is False


def test_empty_password_is_rejected_at_hash_time():
    with pytest.raises(ValueError):
        hash_password("")


# ── 会话 token ──

def test_token_roundtrip():
    secret = generate_secret()
    assert verify_token(issue_token(secret), secret)


def test_token_signed_by_another_secret_is_rejected():
    """换掉 secret 等于让所有已签发 token 立即失效（全设备登出）"""
    token = issue_token(generate_secret())
    assert not verify_token(token, generate_secret())


def test_expired_token_is_rejected():
    secret = generate_secret()
    # 直接手工构造一个已过期但签名正确的 token
    import hashlib
    import hmac
    payload = str(int(time.time()) - 10)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert not verify_token(f"{payload}.{signature}", secret)


def test_tampered_token_is_rejected():
    secret = generate_secret()
    token = issue_token(secret)
    payload, _, signature = token.partition(".")
    # 把过期时间往后改，签名就对不上了
    forged = f"{int(payload) + 86400}.{signature}"
    assert not verify_token(forged, secret)


def test_malformed_tokens_are_rejected():
    secret = generate_secret()
    for broken in ("", ".", "abc", "abc.def", "123", f"notanumber.{'0' * 64}"):
        assert verify_token(broken, secret) is False


def test_verify_token_without_secret_is_rejected():
    """secret 为空（未启用）时任何 token 都不算通过 —— 启用判断由调用方做，
    这里绝不能因为 secret 空就放行。"""
    assert not verify_token(issue_token(generate_secret()), "")


# ── 中间件与接口 ──

@pytest.fixture
def client(tmp_path, monkeypatch):
    """每个用例一套独立的数据目录与 app"""
    monkeypatch.setenv("NAPICS_DATA_DIR", str(tmp_path))
    # main 与 shared 都是模块级单例，必须重新导入才能拿到指向 tmp 的配置
    for name in list(sys.modules):
        if name in ("main", "shared") or name.startswith("routes."):
            sys.modules.pop(name, None)
    import main
    return TestClient(main.app)


def test_disabled_by_default_nothing_changes(client):
    """默认关闭：不设密码时行为与以前完全一致，不会有人升级后被锁在外面"""
    assert client.get("/auth/status").json() == {"enabled": False, "authenticated": True}
    assert client.get("/library").status_code == 200
    assert client.get("/fs/list?path=").status_code == 200


def test_setting_password_blocks_unauthenticated_requests(client):
    res = client.post("/auth/password", json={"new_password": "letmein"})
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    # 设完当前会话应该直接可用，不用再登录一次
    assert client.get("/library").status_code == 200

    # 换一个没有 cookie 的客户端：必须被挡住
    import main
    anonymous = TestClient(main.app)
    assert anonymous.get("/library").status_code == 401
    # 这条是重点：目录枚举接口必须在后端被挡住，
    # 只在前端路由加门的话直接打这个地址就绕过了
    assert anonymous.get("/fs/list?path=").status_code == 401
    assert anonymous.get("/library").status_code == 401


def test_login_with_correct_password_grants_access(client):
    client.post("/auth/password", json={"new_password": "letmein"})

    import main
    fresh = TestClient(main.app)
    assert fresh.get("/library").status_code == 401

    assert fresh.post("/auth/login", json={"password": "letmein"}).status_code == 200
    assert SESSION_COOKIE in fresh.cookies
    assert fresh.get("/library").status_code == 200


def test_login_with_wrong_password_is_rejected(client):
    client.post("/auth/password", json={"new_password": "letmein"})

    import main
    fresh = TestClient(main.app)
    res = fresh.post("/auth/login", json={"password": "wrong"})
    assert res.status_code == 401
    assert SESSION_COOKIE not in fresh.cookies
    assert fresh.get("/library").status_code == 401


def test_auth_endpoints_stay_reachable_when_locked(client):
    """登录相关接口不能被自己挡住，否则设了密码就再也进不来"""
    client.post("/auth/password", json={"new_password": "letmein"})

    import main
    anonymous = TestClient(main.app)
    assert anonymous.get("/auth/status").status_code == 200
    assert anonymous.get("/auth/status").json() == {"enabled": True, "authenticated": False}
    assert anonymous.post("/auth/login", json={"password": "x"}).status_code == 401  # 能到达，只是密码错


def test_logout_clears_session(client):
    client.post("/auth/password", json={"new_password": "letmein"})
    assert client.get("/library").status_code == 200

    client.post("/auth/logout")
    assert client.get("/library").status_code == 401


def test_changing_password_requires_old_one(client):
    client.post("/auth/password", json={"new_password": "first"})

    assert client.post("/auth/password", json={"new_password": "second"}).status_code == 401
    assert client.post(
        "/auth/password", json={"new_password": "second", "old_password": "wrong"},
    ).status_code == 401
    assert client.post(
        "/auth/password", json={"new_password": "second", "old_password": "first"},
    ).status_code == 200

    import main
    fresh = TestClient(main.app)
    assert fresh.post("/auth/login", json={"password": "first"}).status_code == 401
    assert fresh.post("/auth/login", json={"password": "second"}).status_code == 200


def test_changing_password_invalidates_old_sessions(client):
    """改密码必须踢掉旧会话，否则改了等于没改"""
    client.post("/auth/password", json={"new_password": "first"})

    import main
    other_device = TestClient(main.app)
    other_device.post("/auth/login", json={"password": "first"})
    assert other_device.get("/library").status_code == 200

    client.post("/auth/password", json={"new_password": "second", "old_password": "first"})

    assert other_device.get("/library").status_code == 401


def test_disabling_password_requires_old_one_and_reopens_access(client):
    client.post("/auth/password", json={"new_password": "letmein"})

    assert client.post("/auth/password", json={"new_password": ""}).status_code == 401
    res = client.post("/auth/password", json={"new_password": "", "old_password": "letmein"})
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    import main
    anonymous = TestClient(main.app)
    assert anonymous.get("/library").status_code == 200


def test_too_short_password_is_rejected(client):
    assert client.post("/auth/password", json={"new_password": "abc"}).status_code == 400
    # 被拒之后不能留下半启用状态
    assert client.get("/auth/status").json()["enabled"] is False


def test_password_hash_and_secret_are_persisted(client, tmp_path):
    """重启后仍然生效：hash 和签名密钥都要落盘"""
    client.post("/auth/password", json={"new_password": "letmein"})

    import json
    with open(tmp_path / "config.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["access_password_hash"].startswith("pbkdf2_sha256$")
    assert saved["access_token_secret"]
    # 明文不能出现在配置文件里
    assert "letmein" not in json.dumps(saved, ensure_ascii=False)


def test_health_endpoints_stay_open_when_locked(client):
    """健康检查必须免鉴权。

    Dockerfile 的 HEALTHCHECK 打 /backend（转发到后端 /），entrypoint 的就绪探测
    也打 /。这两处被 401 挡住的话，启用访问密码的容器会被判成不健康、反复重启。
    这两个端点只返回固定字符串，放开它们不泄漏任何信息。
    """
    client.post("/auth/password", json={"new_password": "letmein"})

    import main
    anonymous = TestClient(main.app)
    assert anonymous.get("/").status_code == 200
    assert anonymous.get("/healthz").status_code == 200
    assert anonymous.get("/healthz").json() == {"status": "ok"}
    # 对照：真正的业务接口仍然被挡住
    assert anonymous.get("/library").status_code == 401


def test_plugin_routes_are_protected(client):
    """插件路由（播放、字幕）也必须在保护范围内。

    /playback/stream 直接吐文件内容，是这次加访问控制最重要的目标之一。
    中间件在最外层，插件路由挂载后同样经过它。
    """
    client.post("/auth/password", json={"new_password": "letmein"})

    import main
    anonymous = TestClient(main.app)
    # 未安装播放插件时是 404，安装了是 401；无论哪种都不能是 200
    for path in ("/playback/stream?path=/etc/passwd", "/playback/subtitles?path=/x"):
        assert anonymous.get(path).status_code in (401, 404)
