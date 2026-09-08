"""napics MCP server —— stdio transport。

把 napics 的「搜片 → 创建下载 → 后处理」和 qB 的「监控 → 删种」暴露成 MCP 工具，
供上层 agent（hermes / codex / kiro）调用。

本层只做转发与协议转换：不做自然语言理解、不做业务判断、不做筛选（4k/<50g
由上层 agent 拿到 results 后自己做）。所有工具只吃结构化参数、返回 §3 DTO 或
§5 统一错误结构，绝不抛裸异常给上层。
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from config import Config, load_config
from napics_client import NapicsClient, NapicsError
from qb_client import QbClient, QbError
import models as m

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("napics_mcp")

mcp = FastMCP("napics")

# 全局配置与客户端工厂。测试通过 set_clients() 注入 mock，绕开真实网络。
_config: Config = load_config()
_napics: NapicsClient | None = None
_qb: QbClient | None = None


def set_clients(napics: NapicsClient | None, qb: QbClient | None) -> None:
    """测试注入点：直接替换掉真实客户端。"""
    global _napics, _qb
    _napics = napics
    _qb = qb


def _napics_client() -> NapicsClient:
    global _napics
    if _napics is None:
        _napics = NapicsClient(_config.napics_api_base, _config.napics_agent_token,
                               _config.http_timeout)
    return _napics


def _qb_client() -> QbClient:
    global _qb
    if _qb is None:
        _qb = QbClient(_config.qb_url, _config.qb_username, _config.qb_password,
                       _config.http_timeout)
    return _qb


# ── §3.1 探活 ──

@mcp.tool()
def napics_health() -> dict:
    """探活：返回 napics 与 qBittorrent 的可达性。"""
    napics_up = False
    qb_up = False
    if _config.napics_configured:
        try:
            napics_up = _napics_client().reachable()
        except Exception:
            napics_up = False
    if _config.qb_configured:
        try:
            qb_up = _qb_client().reachable()
        except Exception:
            qb_up = False
    return m.HealthResult(
        ok=napics_up and qb_up,
        napics=m.BackendReach(configured=_config.napics_configured, available=napics_up),
        qbittorrent=m.BackendReach(configured=_config.qb_configured, available=qb_up),
    ).model_dump()


# ── §3.2 搜片 ──

@mcp.tool()
def napics_search(query: str, media_type: str = "", title: str = "",
                  year: int | None = None, keywords: list[str] | None = None,
                  season: int | None = None, limit: int = 30) -> dict:
    """搜片。只返回全量候选（含 size_gb/resolution/download_url），筛选由上层做。

    keywords 是上层给的回退词，透传给 napics（napics 侧自建回退链）。
    """
    try:
        raw = _napics_client().search(query, media_type=media_type, title=title,
                                      year=year, season=season, limit=limit)
    except NapicsError as e:
        if e.auth:
            return m.error(m.ERR_AUTH_FAILED, str(e), retryable=False)
        return m.error(m.ERR_NAPICS_UNAVAILABLE, str(e), retryable=True)
    except Exception as e:
        return m.error(m.ERR_SEARCH_FAILED, str(e), retryable=False)

    if raw.get("error") == "no_source":
        return m.error(m.ERR_SEARCH_FAILED,
                       raw.get("message", "未安装搜索插件"), retryable=False)

    results = raw.get("results") or []
    if not results:
        return m.error(m.ERR_NO_RESULTS, f"未找到与「{query}」匹配的资源", retryable=False)

    try:
        parsed = [m.Resource(**r) for r in results]
    except Exception as e:
        return m.error(m.ERR_SEARCH_FAILED, f"结果解析失败: {e}", retryable=False)

    return m.SearchResult(query=raw.get("query", query), total=len(parsed),
                          results=parsed).model_dump()


# ── §3.3 创建下载 ──

@mcp.tool()
def napics_download(download_url: str, media_name: str, idempotency_key: str,
                    save_path: str | None = None) -> dict:
    """创建下载。download_url 原样来自 Resource.download_url。

    idempotency_key 必填：上层用「任务语义唯一键」（如 hash(title+year+url)），
    同 key 重复调不会重复下载。
    """
    if not idempotency_key:
        return m.error(m.ERR_DOWNLOAD_FAILED, "idempotency_key 必填", retryable=False)
    try:
        raw = _napics_client().submit(download_url, media_name, idempotency_key,
                                      save_path=save_path)
    except NapicsError as e:
        if e.auth:
            return m.error(m.ERR_AUTH_FAILED, str(e), retryable=False)
        return m.error(m.ERR_NAPICS_UNAVAILABLE, str(e), retryable=True)
    except Exception as e:
        return m.error(m.ERR_DOWNLOAD_FAILED, str(e), retryable=False)

    # napics 返回 {"success": bool, "task": {...}}
    task = raw.get("task") or {}
    if not raw.get("success"):
        msg = raw.get("error") or task.get("error") or "创建下载失败"
        return m.error(m.ERR_DOWNLOAD_FAILED, msg, retryable=False)

    qb_hash = task.get("downloader_hash") or None
    return m.DownloadCreated(
        task_id=task.get("id", ""),
        qb_hash=qb_hash,
        status=task.get("status", m.STATUS_UNKNOWN),
    ).model_dump()


# ── §3.4 查进度（直连 qB）──

@mcp.tool()
def napics_download_status(qb_hash: str) -> dict:
    """查下载进度。直连 qB torrents/info，屏蔽 qB 原始 state。"""
    if not qb_hash:
        return m.error(m.ERR_DOWNLOAD_NOT_FOUND, "qb_hash 为空", retryable=False)
    try:
        info = _qb_client().torrent_info(qb_hash)
    except QbError as e:
        if e.auth:
            return m.error(m.ERR_AUTH_FAILED, str(e), retryable=False)
        return m.error(m.ERR_QB_UNAVAILABLE, str(e), retryable=True)
    except Exception as e:
        return m.error(m.ERR_QB_UNAVAILABLE, str(e), retryable=True)

    if info is None:
        return m.error(m.ERR_DOWNLOAD_NOT_FOUND,
                       f"qB 中找不到 hash={qb_hash} 的种子", retryable=False)

    progress = float(info.get("progress") or 0.0)
    eta = info.get("eta")
    # qB 用 8640000 表示"无穷/未知 ETA"
    eta_seconds = None if eta in (None, 8640000) else int(eta)
    return m.DownloadStatus(
        status=m.map_qb_state(info.get("state", ""), progress),
        percentage=round(progress * 100, 2),
        download_speed_bytes=int(info.get("dlspeed") or 0),
        eta_seconds=eta_seconds,
    ).model_dump()


# ── §3.5 删种（直连 qB）──

@mcp.tool()
def napics_cancel_download(qb_hash: str, delete_files: bool = False) -> dict:
    """取消下载（删 qB 侧种子）。注意 napics 内部 task 记录不会同步删。"""
    if not qb_hash:
        return m.error(m.ERR_DOWNLOAD_NOT_FOUND, "qb_hash 为空", retryable=False)
    try:
        _qb_client().delete(qb_hash, delete_files=delete_files)
    except QbError as e:
        if e.auth:
            return m.error(m.ERR_AUTH_FAILED, str(e), retryable=False)
        return m.error(m.ERR_CANCEL_FAILED, str(e), retryable=True)
    except Exception as e:
        return m.error(m.ERR_CANCEL_FAILED, str(e), retryable=False)
    return {"ok": True}


# ── §3.6 后处理 ──

@mcp.tool()
def napics_process(task_id: str = "", path: str = "", media_name: str = "") -> dict:
    """下载完成后刮削 + 整理归位。task_id 与 path 二选一。

    TMDB 未配时返回 status="partial"（仅整理未刮削）。
    """
    if not task_id and not path:
        return m.error(m.ERR_PROCESS_FAILED, "task_id 与 path 至少提供一个", retryable=False)
    try:
        raw = _napics_client().process(path=path or None, task_id=task_id or None)
    except NapicsError as e:
        if e.auth:
            return m.error(m.ERR_AUTH_FAILED, str(e), retryable=False)
        if e.not_found:
            return m.error(m.ERR_DOWNLOAD_NOT_FOUND, str(e), retryable=False)
        return m.error(m.ERR_NAPICS_UNAVAILABLE, str(e), retryable=True)
    except Exception as e:
        return m.error(m.ERR_PROCESS_FAILED, str(e), retryable=False)

    if raw.get("status") == "failed":
        return m.error(m.ERR_PROCESS_FAILED,
                       raw.get("error", "后处理失败"), retryable=False)
    return m.ProcessResult(
        status=raw.get("status", "processed"),
        library_path=raw.get("library_path"),
        files=raw.get("files") or [],
        message=raw.get("message"),
    ).model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
