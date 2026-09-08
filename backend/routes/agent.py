"""
路由模块：agent — 面向上层 agent / MCP 的薄接口。

这一层不做业务判断，只把 napics 已有的能力包装成结构可预期、字段展平的端点，
供 napics-mcp（stdio MCP server）转发。设计契约见 docs/napics-mcp-server-todo.md §2/§3。

三条与主界面不同的取舍：
- 认证走独立的 X-Agent-Token（config.agent_api_token），不吃浏览器 cookie。
  编程接口带不了也不该带 cookie；两套门互不干扰（见 §2.5）。
- 搜索端点显式做 enrich + 展平，因为 /search/single 默认分支返回的是未 enrich 的
  裸 SearchResult，顶层没有 quality_score / match_score（见 §2.1）。
- /process 不依赖前端回传 action_plan：内部先 dry_run 拿 plan 再执行，
  并自己组装 library_path / files（organize_full 的返回里没有这两个字段，见 §2.4）。
"""
import os
import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from shared import config_m, get_clients

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent")


# ── 认证 ──

def _require_agent_token(x_agent_token: str = Header(default="")) -> None:
    """写操作的 token 门。

    config.agent_api_token 留空时不校验（默认，与升级前一致）；
    非空时请求必须带对上的 X-Agent-Token，否则 401。
    """
    expected = (config_m.config.agent_api_token or "").strip()
    if not expected:
        return
    if x_agent_token.strip() != expected:
        raise HTTPException(status_code=401, detail="无效的 Agent token")


# ── §2.1 展平搜索端点 ──

def _flatten_resource(d: dict) -> dict:
    """把 enrich 后的搜索结果 dict 展平成 §3 的 Resource DTO。

    d 来自 search_service.search_all_sources / enrich_result：顶层有 title/indexer/
    download_url/seeders/leechers/size_gb 与 quality_score/match_score，
    quality 是子 dict（resolution/source/video_codec/release_group/has_chinese_sub）。
    只做字段搬运，不新解析。
    """
    quality = d.get("quality") or {}
    if not isinstance(quality, dict):
        # 兜底：万一 quality 还是对象
        quality = getattr(quality, "__dict__", {}) or {}
    q_score = d.get("quality_score") or 0
    m_score = d.get("match_score") or 0
    return {
        "title": d.get("title", ""),
        "source": quality.get("source"),
        "indexer": d.get("indexer"),
        "download_url": d.get("download_url", ""),
        "size_gb": d.get("size_gb"),
        "seeders": d.get("seeders"),
        "leechers": d.get("leechers"),
        "resolution": quality.get("resolution"),
        "codec": quality.get("video_codec"),
        "release_group": quality.get("release_group"),
        "has_chinese_sub": quality.get("has_chinese_sub"),
        "score": (q_score or 0) + (m_score or 0),
    }


@router.get("/search")
def agent_search(
    query: str,
    media_type: str = "",
    title: str = "",
    year: str = "",
    season: int = 0,
    limit: int = 30,
):
    """面向 agent 的搜索：走 search_service 统一多源搜索 → enrich → 展平。

    只吃结构化参数，语言解析 / 筛选（4k、<50g）由上层 agent 负责。
    """
    from plugin_guard import get_allowed_bt_sources
    from search_service import build_keywords, search_all_sources, _build_match_names

    allowed_bt = get_allowed_bt_sources()
    if not allowed_bt:
        return {"query": query, "total": 0, "results": [], "error": "no_source",
                "message": "未安装搜索插件，请在插件中心安装搜索源"}

    keywords = build_keywords(
        query=query,
        cn_name=title,
        year=str(year) if year else "",
        season_number=season or 0,
    )
    bt_overrides = config_m.config.bt_search_sources or {}
    search_client = None
    if "prowlarr" in allowed_bt:
        try:
            search_client = get_clients()["search"]
        except Exception as e:
            logger.warning(f"[Agent] Prowlarr 客户端获取失败: {e}")

    match_names = _build_match_names(keywords, query)
    try:
        results = search_all_sources(
            keywords, query,
            bt_overrides=bt_overrides,
            search_client=search_client,
            match_names=match_names,
        )
    except Exception as e:
        logger.error(f"[Agent] 搜索失败: {e}")
        raise HTTPException(status_code=502, detail=f"搜索失败: {e}")

    # 按合成分排序，截断到 limit
    flattened = [_flatten_resource(r) for r in results]
    flattened.sort(key=lambda r: r.get("score") or 0, reverse=True)
    if limit and limit > 0:
        flattened = flattened[:limit]

    return {"query": query, "total": len(flattened), "results": flattened}


# ── §2.4 无状态后处理端点 ──

def _list_video_files(root: str) -> list:
    """扫描目录下的视频文件，返回绝对路径列表。整理后用于组装 files[]。"""
    from core.constants import VIDEO_EXTS

    found = []
    if not os.path.isdir(root):
        if os.path.isfile(root):
            return [root]
        return found
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in VIDEO_EXTS:
                found.append(os.path.join(dirpath, fn))
    return found


@router.post("/process")
async def agent_process(
    path: str = "",
    task_id: str = "",
    _auth: None = Depends(_require_agent_token),
):
    """下载完成后一键刮削 + 整理归位（无状态）。

    入参二选一：path（目标目录）或 task_id（内部查 save_path）。
    内部：organize_full(dry_run=True) 拿 action_plan → organize_full(dry_run=False,
    action_plan) 执行。自己组装 library_path / files（organize_full 不回这两项）。

    TMDB 未配时降级：只整理不刮削，返回 status="partial"。
    """
    from routes.organize import organize_full
    from shared import _tmdb_client, _get_download_manager

    # 解析目标路径
    target = (path or "").strip()
    if not target and task_id:
        dm = _get_download_manager()
        task = dm.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"下载任务不存在: {task_id}")
        target = task.save_path or task.download_dir
    if not target or not os.path.isdir(target):
        raise HTTPException(status_code=400, detail="path 不是有效目录（或 task 无有效 save_path）")

    tmdb_configured = bool(_tmdb_client())
    partial = not tmdb_configured

    try:
        # 1) 推演拿 plan
        plan = await organize_full(path=target, dry_run=True, use_ai=False, request=None)
        action_plan = {
            "wrap_plan": plan.get("wrap_plan", []),
            "archive_plan": plan.get("archive_plan", []),
            "tmdb_match": plan.get("tmdb_match", {}),
            "plan": plan.get("plan", []),
            "folder_type": plan.get("folder_type", ""),
        }
        # 2) 执行
        await organize_full(path=target, dry_run=False, use_ai=False,
                            request=None, action_plan=action_plan)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agent] process 失败: {e}")
        return {"status": "failed", "library_path": None, "files": [], "error": str(e)}

    # 3) 组装 library_path / files —— organize_full 不回这两项，整理后重扫目标目录
    files = _list_video_files(target)
    library_path = target

    status = "partial" if partial else "processed"
    result = {"status": status, "library_path": library_path, "files": files}
    if partial:
        result["message"] = "未配置 TMDB，仅整理归位未刮削"
    return result


# ── §3.1 探活（napics 侧）──

@router.get("/health")
def agent_health():
    """napics 侧探活。qB 可达性由 MCP 直连 qB 判定，这里只报 napics 自己。"""
    return {"ok": True, "service": "napics"}
