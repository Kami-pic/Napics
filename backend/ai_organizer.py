"""AI 辅助整理业务层。
HTTP 调用已下沉到 ai_client.py，本模块只做业务编排。
"""
import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_client import get_ai_client, _extract_json
from ai_prompts import (
    prompt_extract_episode, prompt_extract_episode_batch,
    EXTRACT_EPISODE_SCHEMA, EXTRACT_EPISODE_BATCH_SCHEMA,
)

logger = logging.getLogger(__name__)


def ai_extract_episode(filename: str) -> Optional[dict]:
    """调用 LLM 从乱码文件名中提取结构化信息（单个文件）。
    返回 {"clean_name": str, "year": str|None, "season": int|None,
           "episode": int|None, "absolute_episode": int|None}
    失败返回 None。
    """
    client = get_ai_client()
    if not client.is_feature_enabled("extract_episode"):
        return None

    messages = prompt_extract_episode(filename)
    result = client.chat_json(
        messages, temperature=0, timeout=20,
        scene="extract_episode", schema=EXTRACT_EPISODE_SCHEMA,
    )
    if result is None:
        return None

    return _normalize_extract_result(result)


def ai_extract_episode_batch(filenames: List[str]) -> List[Optional[dict]]:
    """批量文件名解析。每批最多 10 个，超过时分批并发。
    返回与 filenames 等长的列表，解析失败的位置为 None。
    """
    client = get_ai_client()
    if not client.is_feature_enabled("extract_episode"):
        return [None] * len(filenames)

    if len(filenames) <= 10:
        return _extract_batch_single(client, filenames)

    # 分批并发
    results = [None] * len(filenames)
    batches = [filenames[i:i+10] for i in range(0, len(filenames), 10)]
    batch_indices = [(i * 10, min((i + 1) * 10, len(filenames))) for i in range(len(batches))]

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for idx, batch in enumerate(batches):
            future = executor.submit(_extract_batch_single, client, batch)
            futures[future] = batch_indices[idx]

        for future in as_completed(futures):
            start_idx, end_idx = futures[future]
            try:
                batch_results = future.result()
                for i, r in enumerate(batch_results):
                    results[start_idx + i] = r
            except Exception as e:
                logger.error(f"[AI] 批量解析异常: {e}")

    return results


def _extract_batch_single(client, filenames: List[str]) -> List[Optional[dict]]:
    """执行单批次的批量解析"""
    messages = prompt_extract_episode_batch(filenames)
    result = client.chat_json(
        messages, temperature=0, timeout=20,
        scene="extract_episode", schema=EXTRACT_EPISODE_BATCH_SCHEMA,
    )
    if result is None:
        # 批量失败，逐个 fallback
        logger.warning("[AI] 批量解析失败，逐个 fallback")
        return [_extract_single_fallback(client, fn) for fn in filenames]

    items = result.get("results", [])
    # 按 index 映射回原始位置
    parsed = [None] * len(filenames)
    for item in items:
        idx = item.get("index")
        if idx is not None and isinstance(idx, int) and 1 <= idx <= len(filenames):
            normalized = _normalize_extract_result(item)
            if normalized:
                parsed[idx - 1] = normalized

    return parsed


def _extract_single_fallback(client, filename: str) -> Optional[dict]:
    """单个文件的 fallback 解析（批量失败时使用）"""
    messages = prompt_extract_episode(filename)
    result = client.chat_json(
        messages, temperature=0, timeout=20,
        scene="extract_episode", schema=EXTRACT_EPISODE_SCHEMA,
    )
    if result is None:
        return None
    return _normalize_extract_result(result)


def _normalize_extract_result(result: dict) -> Optional[dict]:
    """标准化 AI 提取结果的字段和类型"""
    clean_title = result.get("clean_title", "")
    if not clean_title or len(clean_title) < 2:
        return None

    def _safe_int(v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    return {
        "clean_name": clean_title,
        "year": str(result["year"]) if result.get("year") else None,
        "season": _safe_int(result.get("season")),
        "episode": _safe_int(result.get("episode")),
        "absolute_episode": _safe_int(result.get("absolute_episode")),
        "ai_parsed": True,
    }


def ai_select_scrape_candidate(
    folder_name: str,
    file_list: List[str],
    candidates: List[dict],
) -> Optional[dict]:
    """AI 从 TMDB 候选中选择最佳匹配。
    返回 {"selected_index": int, "confidence": str, "reason": str}
    失败或候选不足时返回 None。
    """
    # 候选 <= 1 时不需要 AI
    if len(candidates) <= 1:
        return None

    client = get_ai_client()
    if not client.is_feature_enabled("scrape_candidate"):
        return None

    from ai_prompts import prompt_select_scrape_candidate, SELECT_CANDIDATE_SCHEMA
    messages = prompt_select_scrape_candidate(folder_name, file_list, candidates)
    result = client.chat_json(
        messages, temperature=0, timeout=20,
        scene="scrape_candidate", schema=SELECT_CANDIDATE_SCHEMA,
    )
    if result is None:
        return None

    # 校验 selected_index 范围
    idx = result.get("selected_index")
    if not isinstance(idx, int) or idx < -1 or idx >= len(candidates):
        logger.warning(f"[AI] 候选选择 index 越界: {idx}")
        return None

    return {
        "selected_index": idx,
        "confidence": result.get("confidence", "low"),
        "reason": result.get("reason", ""),
        "ai_selected": True,
    }


def ai_library_diagnosis() -> Optional[dict]:
    """AI 媒体库健康诊断。
    收集统计信息 → 调用 AI → 返回诊断报告。
    """
    client = get_ai_client()
    if not client.is_feature_enabled("library_diagnosis"):
        return None

    # 收集媒体库统计
    from shared import config_m
    library = config_m.load_library()
    if not library:
        return {"health_score": 0, "priorities": [], "summary": "媒体库为空，请先扫描 NAS 目录。"}

    stats = _collect_library_stats(library)
    issues = _collect_library_issues(library)

    from ai_prompts import prompt_library_diagnosis, DIAGNOSIS_SCHEMA
    messages = prompt_library_diagnosis(stats, issues)
    result = client.chat_json(
        messages, temperature=0, timeout=60,
        scene="library_diagnosis", schema=DIAGNOSIS_SCHEMA,
    )
    return result


def _collect_library_stats(library: list) -> dict:
    """收集媒体库统计信息（不含隐私数据）"""
    total = len(library)
    has_nfo = sum(1 for v in library if v.get("has_nfo"))
    has_poster = sum(1 for v in library if v.get("has_poster"))

    # 分辨率分布
    res_dist = {"4K": 0, "1080p": 0, "720p": 0, "SD": 0, "未知": 0}
    for v in library:
        h = v.get("height", 0) or 0
        if h >= 2160:
            res_dist["4K"] += 1
        elif h >= 1080:
            res_dist["1080p"] += 1
        elif h >= 720:
            res_dist["720p"] += 1
        elif h > 0:
            res_dist["SD"] += 1
        else:
            res_dist["未知"] += 1

    # 编码分布
    codec_dist = {}
    for v in library:
        codec = (v.get("codec") or "未知").lower()
        codec_dist[codec] = codec_dist.get(codec, 0) + 1

    return {
        "total_videos": total,
        "scrape_coverage": f"{has_nfo}/{total} ({round(has_nfo/total*100) if total else 0}%)",
        "poster_coverage": f"{has_poster}/{total} ({round(has_poster/total*100) if total else 0}%)",
        "resolution_distribution": res_dist,
        "codec_distribution": codec_dist,
    }


def _collect_library_issues(library: list) -> list:
    """收集媒体库问题列表（只传文件名，不传完整路径）"""
    issues = []

    # 缺失 NFO
    no_nfo = [v.get("file_name", "") for v in library if not v.get("has_nfo")]
    if no_nfo:
        issues.append({
            "type": "missing_nfo",
            "count": len(no_nfo),
            "examples": no_nfo[:5],
        })

    # 低分辨率
    low_res = [v.get("file_name", "") for v in library if v.get("is_low_res")]
    if low_res:
        issues.append({
            "type": "low_resolution",
            "count": len(low_res),
            "examples": low_res[:5],
        })

    # 缺失海报
    no_poster = [v.get("file_name", "") for v in library if not v.get("has_poster")]
    if no_poster:
        issues.append({
            "type": "missing_poster",
            "count": len(no_poster),
            "examples": no_poster[:5],
        })

    # 质量分过低
    low_quality = [v.get("file_name", "") for v in library
                   if (v.get("quality_score") or 0) > 0 and v.get("quality_score", 100) < 20]
    if low_quality:
        issues.append({
            "type": "low_quality_score",
            "count": len(low_quality),
            "examples": low_quality[:5],
        })

    return issues
