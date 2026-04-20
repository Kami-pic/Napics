"""
路由模块：search
"""
import os
import json
import re
import time
import asyncio
import shutil
import requests
import subprocess
import sys
import threading
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, Response
from pydantic import BaseModel

from shared import (
    config_m, shadow_m, indexer_m, torrent_bl, analysis_cache,
    _get_download_manager, _get_pan_search_service, _get_recycle_bin, _get_file_relocator,
    _get_bitsearch_scraper, _get_cilixiong_scraper, _get_xl720_scraper, _get_nyaa_scraper,
    _get_mikan_scraper, _get_yts_scraper, _get_limetorrents_scraper, _get_acgrip_scraper,
    _get_bangumi_moe_scraper,
    _tmdb_client, get_clients,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask
from quality_parser import compute_quality_score

router = APIRouter()


def _enrich_result(r, search_query: str = "") -> dict:
    """给搜索结果附加 quality_score（100 分制）、match_score（0-100）、is_junk 标记"""
    try:
        if hasattr(r, "dict"):
            d = r.dict()
        elif hasattr(r, "model_dump"):
            d = r.model_dump()
        else:
            d = dict(r)
        # quality 字段可能是 Pydantic model，转为 dict
        if d.get("quality") and hasattr(d["quality"], "dict"):
            d["quality"] = d["quality"].dict()
        elif d.get("quality") and hasattr(d["quality"], "model_dump"):
            d["quality"] = d["quality"].model_dump()
        if r.quality:
            d["quality_score"] = compute_quality_score(r.quality)
        else:
            d["quality_score"] = 0
        # match_score：用 L2 match_chain 计算搜索词和标题的匹配度
        if search_query:
            try:
                from match_scoring import match_chain
                from text_processing import split_by_language as _split
                # 从搜索词提取中英文变体作为候选
                parts = _split(search_query)
                candidates = [n for n in [search_query, parts["cn"], parts["en"]] if n]
                # 从 BT 标题提取干净的作品名作为目标
                bt_clean = _extract_bt_title_for_match(d.get("title", ""))
                bt_parts = _split(bt_clean)
                targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
                d["match_score"] = match_chain(candidates, targets, [])
            except Exception:
                d["match_score"] = 0
        else:
            d["match_score"] = 0
        # is_junk + junk_reasons：L3 软过滤标记（多条件，UI 开关控制显示/隐藏）
        d.update(_compute_junk_flags(d))
        return d
    except Exception:
        return {"title": getattr(r, "title", ""), "download_url": getattr(r, "download_url", ""),
                "indexer": getattr(r, "indexer", ""), "seeders": getattr(r, "seeders", 0),
                "size_gb": getattr(r, "size_gb", 0), "quality_score": 0, "match_score": 0,
                "is_junk": False, "junk_reasons": []}


# ── BT 标题清洗（专为搜索匹配设计，比 parse_filename 更激进）──
# 技术标签正则：分辨率、编码、来源、音频、发布组等
_BT_TECH_TAGS_RE = re.compile(
    r'(?i)\b('
    r'2160p|1080p|720p|480p|4K|UHD|FHD|HD|SD|'
    r'BluRay|Blu-?Ray|WEB-?DL|WEBRip|WEB|HDTV|DVDRip|BDRip|BRRip|Remux|PDTV|'
    r'x264|x265|H\.?264|H\.?265|HEVC|AVC|MPEG|VP9|AV1|10bit|HDR10\+?|HDR|DV|DoVi|'
    r'AAC|DTS|DTS-HD|DTS-X|FLAC|Atmos|TrueHD|AC3|EAC3|DD5\.?1|DD\+?|MA\.?5\.?1|7\.?1|5\.?1|2\.?0|'
    r'PROPER|REPACK|INTERNAL|SUBBED|DUBBED|MULTI|DUAL|'
    r'TS|CAM|HDTC|TC|TELECINE|HDTS|TELESYNC|HDCAM|'
    r'CMCT|CHD|Wiki|FLTth|HDChina|MTeam|TTG|FRDS|RARBG|YTS|YIFY|SPARKS|'
    r'SWTYBLZ|CAKES|NTb|FLUX|NOGRP|GROUP|'
    r'中英双字|中英字幕|中文字幕|双语字幕|简繁字幕|简体|繁体|中字|英字|字幕组'
    r')\b'
)
# 发布组后缀（-GroupName 格式）
_RELEASE_GROUP_RE = re.compile(r'-[A-Za-z0-9]{2,15}$')


def _extract_bt_title_for_match(title: str) -> str:
    """从 BT 标题中提取作品名，去掉所有技术标签。

    策略：
    1. 去掉方括号/圆括号内容（字幕组名、分辨率等）
    2. 在第一个技术标签处截断（技术标签之后都是噪声）
    3. 去掉发布组后缀（-GROUP）
    4. 去掉年份（匹配时不需要）
    5. 点号/下划线替换为空格
    """
    if not title:
        return ""

    s = title

    # 1. 去掉方括号/圆括号内容
    s = re.sub(r'[\[\(【（][^\]\)】）]*[\]\)】）]', ' ', s)

    # 2. 点号/下划线替换为空格（BT 标题常用 . 分隔）
    s = re.sub(r'[._]', ' ', s)

    # 3. 在第一个技术标签处截断
    m = _BT_TECH_TAGS_RE.search(s)
    if m:
        s = s[:m.start()]

    # 4. 去掉发布组后缀
    s = _RELEASE_GROUP_RE.sub('', s)

    # 5. 去掉年份
    s = re.sub(r'\b(19|20)\d{2}\b', '', s)

    # 6. 清理残留
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip(' -·|')

    return s if s else title


# 枪版/低质量关键词（词边界匹配）
_JUNK_QUALITY_PATTERNS = ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS", "TELESYNC", "HDCAM"]
# 匹配度阈值：低于此分数视为不相关
_MATCH_SCORE_THRESHOLD = 30


def _compute_junk_flags(d: dict) -> dict:
    """计算 is_junk 和 junk_reasons，供智能过滤使用"""
    reasons = []
    title = d.get("title", "")
    match_score = d.get("match_score", 0)
    seeders = d.get("seeders", 0)
    size_gb = d.get("size_gb", 0)

    # 1. 枪版/低质量源
    for p in _JUNK_QUALITY_PATTERNS:
        if re.search(r'\b' + p + r'\b', title, re.I):
            reasons.append(f"low_quality:{p}")
            break

    # 2. 匹配度过低（有 match_score 且低于阈值）
    if match_score > 0 and match_score < _MATCH_SCORE_THRESHOLD:
        reasons.append(f"low_match:{match_score}")

    # 3. 死种（seeders=0 但不是磁力链接源或无 tracker 信息的源）
    # 磁力链接源特征：seeders=0 且 size_gb=0（无 tracker 信息）
    # 字幕组站（acgrip/bangumi_moe）不提供做种数，不视为死种
    is_magnet_only = seeders == 0 and size_gb == 0
    indexer = d.get("indexer", "")
    no_seeder_sources = {"acgrip", "bangumi_moe"}
    if seeders == 0 and not is_magnet_only and indexer not in no_seeder_sources:
        reasons.append("dead_seed")

    return {"is_junk": len(reasons) > 0, "junk_reasons": reasons}


def _merge_bt_extra_sources(keyword: str, existing_results: list) -> list:
    """合并直搜源（Bitsearch/磁力熊/XL720/Nyaa）的结果到已有列表。

    按 infohash 去重，直搜源结果追加到末尾。
    """
    merged = list(existing_results)

    bt_overrides = config_m.config.bt_search_sources or {}
    scrapers = [
        ("bitsearch", _get_bitsearch_scraper),
        ("cilixiong", _get_cilixiong_scraper),
        ("xl720", _get_xl720_scraper),
        ("nyaa", _get_nyaa_scraper),
        ("mikan", _get_mikan_scraper),
        ("yts", _get_yts_scraper),
        ("limetorrents", _get_limetorrents_scraper),
        ("acgrip", _get_acgrip_scraper),
        ("bangumi_moe", _get_bangumi_moe_scraper),
    ]
    for name, getter in scrapers:
        if not bt_overrides.get(name, True):
            continue
        try:
            scraper = getter()
            results = scraper.search_as_search_results(keyword, max_results=20)
            added = 0
            # 同源内 infohash 去重
            source_hashes = set()
            for r in results:
                h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                if h:
                    hash_upper = h.group(1).upper()
                    if hash_upper in source_hashes:
                        continue
                    source_hashes.add(hash_upper)
                merged.append(r)
                added += 1
            if added:
                print(f"[Search] {name} 补充 {added} 条结果")
        except Exception as e:
            print(f"[Search] {name} 失败: {e}")

    return merged

@router.get("/api/search")
def search_resources(
    query: str,
    enhanced: bool = True,
    media_type: str = "",
    year: str = "",
    shadow_name: str = "",
    clean_name: str = "",
    season: int = 0,
    total_episodes: int = 0,
):
    """搜索资源。增强搜索：回退链 + 二次匹配 + 全局过滤 + 综合排序。"""
    clients = get_clients()
    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        resolver = AliasResolver(douban_client, bangumi_client)
        aliases = resolver.resolve(query, "", media_type)
        indexer_m.load()

        resp = searcher.enhanced_search(
            client=clients["search"],
            title=query,
            aliases=aliases,
            year="",
            media_type=media_type,
            indexer_manager=indexer_m,
            shadow_name=shadow_name,
            clean_name=clean_name,
            global_filter=gf,
        )

        bt_keyword = resp.hit_keyword or query
        bt_results_list = _merge_bt_extra_sources(bt_keyword, list(resp.results))

        return {
            "query": query,
            "bt_count": len(bt_results_list),
            "bt_results": [_enrich_result(r, query) for r in bt_results_list],
            "hit_keyword": resp.hit_keyword,
            "total_raw": resp.total_raw,
            "total_filtered": len(bt_results_list),
            "enhanced": True,
        }
    except Exception as e:
        print(f"[Search] Enhanced search failed, fallback: {e}")

    bt_results = clients["search"].search(query)
    bt_results = _merge_bt_extra_sources(query, bt_results)

    return {
        "query": query,
        "bt_count": len(bt_results),
        "bt_results": [_enrich_result(r, query) for r in bt_results],
        "hit_keyword": query,
        "total_raw": len(bt_results),
        "total_filtered": len(bt_results),
        "enhanced": False,
    }


@router.get("/api/search/stream")
def search_resources_stream(
    query: str,
    media_type: str = "",
    shadow_name: str = "",
    clean_name: str = "",
    cn_name: str = "",
    en_name: str = "",
):
    """SSE 流式搜索：所有源全部并行，每个源用最适合的语言搜索词。"""
    def _generate():
        import concurrent.futures
        from text_processing import split_by_language

        # 构造多语言搜索词
        # 英文词：en_name > shadow_name 去中文 > query 中英文部分
        # 中文词：cn_name > query 中中文部分
        from text_processing import normalize as _normalize
        parts = split_by_language(query)
        kw_cn = cn_name.strip() or parts.get("cn", "") or query
        kw_en = en_name.strip() or shadow_name.strip() or parts.get("en", "") or query
        # 日文/原名：en_name 可能是日文（Bangumi 源），直接用
        kw_original = en_name.strip() or query
        # 清洗：去掉标点、多余空格
        kw_cn = _normalize(kw_cn) if kw_cn else query
        kw_en = kw_en.strip() if kw_en else query
        clients = get_clients()
        conf = config_m.config
        bt_overrides = conf.bt_search_sources or {}

        def _search_prowlarr():
            """Prowlarr 优先用英文搜索（BT 站英文为主）"""
            try:
                # 优先英文，fallback 到原始 query
                search_kw = kw_en if kw_en and kw_en != kw_cn else query
                print(f"[SSE/Prowlarr] 搜索词: '{search_kw}' (kw_en='{kw_en}', kw_cn='{kw_cn}', query='{query}')")
                import time as _t
                t0 = _t.time()
                raw = clients["search"].search(search_kw)
                elapsed = _t.time() - t0
                print(f"[SSE/Prowlarr] 返回 {len(raw)} 条，耗时 {elapsed:.1f}s")
                seen = set()
                deduped = []
                for r in raw:
                    if r.download_url and r.download_url not in seen:
                        seen.add(r.download_url)
                        deduped.append(r)
                return "prowlarr", deduped, None
            except Exception as e:
                print(f"[SSE/Prowlarr] 异常: {e}")
                return "prowlarr", [], str(e)

        def _search_direct(name, getter):
            """直搜源按语言选择搜索词"""
            try:
                s = getter()
                # 中文源用中文，英文/日文源用对应语言
                if name in ("cilixiong", "xl720"):
                    search_kw = kw_cn
                elif name in ("nyaa", "mikan"):
                    search_kw = kw_original  # 日文原名或英文
                elif name in ("yts", "limetorrents", "bitsearch"):
                    search_kw = kw_en if kw_en and kw_en != kw_cn else query
                elif name in ("acgrip", "bangumi_moe"):
                    search_kw = kw_cn  # 中文字幕组站，中文优先
                else:
                    search_kw = kw_en if kw_en and kw_en != kw_cn else query
                results = s.search_as_search_results(search_kw, max_results=20)
                return name, results, None
            except Exception as e:
                return name, [], str(e)

        scrapers = [
            ("bitsearch", _get_bitsearch_scraper),
            ("cilixiong", _get_cilixiong_scraper),
            ("xl720", _get_xl720_scraper),
            ("nyaa", _get_nyaa_scraper),
            ("mikan", _get_mikan_scraper),
            ("yts", _get_yts_scraper),
            ("limetorrents", _get_limetorrents_scraper),
            ("acgrip", _get_acgrip_scraper),
            ("bangumi_moe", _get_bangumi_moe_scraper),
        ]

        # 推送所有源的 searching 状态
        all_sources = []
        if bt_overrides.get("prowlarr", True):
            all_sources.append("prowlarr")
        for name, _ in scrapers:
            if bt_overrides.get(name, True):
                all_sources.append(name)
        for name in all_sources:
            yield f"data: {json.dumps({'type': 'status', 'source': name, 'status': 'searching'})}\n\n"

        # 全部并行提交，用 as_completed 逐个 yield
        with concurrent.futures.ThreadPoolExecutor(max_workers=11) as pool:
            future_map = {}
            if bt_overrides.get("prowlarr", True):
                f = pool.submit(_search_prowlarr)
                future_map[f] = "prowlarr"
            for name, getter in scrapers:
                if bt_overrides.get(name, True):
                    f = pool.submit(_search_direct, name, getter)
                    future_map[f] = name

            completed_sources = set()
            try:
                for future in concurrent.futures.as_completed(future_map, timeout=65):
                    try:
                        name, results, err = future.result(timeout=65)
                    except Exception as e:
                        name = future_map[future]
                        results, err = [], str(e)
                    completed_sources.add(name)
                    # 同源内去重
                    source_deduped = []
                    source_hashes = set()
                    for r in results:
                        h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                        if h:
                            hu = h.group(1).upper()
                            if hu in source_hashes:
                                continue
                            source_hashes.add(hu)
                        source_deduped.append(r)
                    status = "done" if not err else "failed"
                    enriched = [_enrich_result(r, query) for r in source_deduped]
                    yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': status, 'count': len(results), 'added': len(source_deduped), 'error': err or '', 'results': enriched}, default=str)}\n\n"
            except concurrent.futures.TimeoutError:
                pass
            # 超时未完成的源推送 failed 状态
            for future, name in future_map.items():
                if name not in completed_sources:
                    yield f"data: {json.dumps({'type': 'source_done', 'source': name, 'status': 'failed', 'count': 0, 'added': 0, 'error': '搜索超时', 'results': []})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")

@router.get("/search/pan")
def search_pan(keyword: str, media_type: str = ""):
    """网盘搜索聚合接口。"""
    try:
        service = _get_pan_search_service()
        response = service.search_sync(keyword, media_type=media_type)
        return response.dict()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"results": [], "groups": {}, "source_statuses": [{"name": "error", "status": "failed", "count": 0, "error": str(e)}], "total": 0}

@router.get("/alist/mounts")
def get_alist_mounts():
    """获取 Alist 已挂载网盘列表。"""
    try:
        clients = get_clients()
        alist = clients.get("alist")
        if not alist:
            return {"mounts": [], "error": "Alist 未配置"}
        mounts = alist.get_mounts_list()
        return {"mounts": [m.dict() for m in mounts]}
    except Exception as e:
        return {"mounts": [], "error": str(e)}

@router.post("/alist/transfer")
def transfer_pan_resource(req: dict):
    """网盘资源转存接口。
    夸克链接 → 调用夸克转存 API 自动保存到自己的夸克网盘。
    其他网盘 → 返回提示让用户手动保存。
    """
    try:
        share_url = req.get("share_url", "")
        pan_type = req.get("pan_type", "")
        passcode = req.get("password", "")

        if not share_url:
            return {"success": False, "error_code": "missing_url", "error_message": "缺少分享链接"}

        # 夸克链接 → 自动转存
        if pan_type == "quark":
            from quark_transfer import QuarkTransfer
            conf = config_m.config
            qt = QuarkTransfer.from_alist(conf.alist_url, conf.alist_token)
            if not qt:
                return {"success": False, "error_code": "no_cookie", "error_message": "无法获取夸克 Cookie，请检查 Alist 夸克存储配置"}
            result = qt.transfer(share_url, passcode)
            return result

        # 其他网盘 → 暂不支持自动转存
        return {"success": False, "error_code": "unsupported",
                "error_message": f"{pan_type} 暂不支持自动转存，请手动打开链接保存"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error_code": "server_error", "error_message": str(e)}

@router.get("/search/single")
def search_single_keyword(
    keyword: str,
    media_type: str = "",
    skip_filter: bool = False,
):
    """单关键词搜索。

    skip_filter=False（默认）：含二次匹配+全局过滤（不含年份匹配）
    skip_filter=True：Prowlarr 裸搜，不做任何过滤
    """
    clients = get_clients()

    # 搜索 Prowlarr
    try:
        raw_results = clients["search"].search(keyword)
    except Exception as e:
        print(f"[Search/Single] Prowlarr error: {e}")
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    total_raw = len(raw_results)
    if not raw_results:
        return {"keyword": keyword, "bt_count": 0, "bt_results": [], "total_raw": 0, "total_filtered": 0}

    # 去重
    seen = set()
    deduped = []
    for r in raw_results:
        if r.download_url and r.download_url not in seen:
            seen.add(r.download_url)
            deduped.append(r)

    # 裸搜模式：跳过所有过滤，合并直搜源（后台线程，不阻塞返回）
    if skip_filter:
        # 先返回 Prowlarr 结果，直搜源结果通过 /api/search 接口获取
        all_results = list(deduped)
        # 尝试快速合并直搜源（有缓存时秒返回）
        try:
            bt_overrides = config_m.config.bt_search_sources or {}
            from shared import _get_bitsearch_scraper, _get_cilixiong_scraper, _get_xl720_scraper, _get_nyaa_scraper, _get_mikan_scraper, _get_yts_scraper, _get_limetorrents_scraper, _get_acgrip_scraper, _get_bangumi_moe_scraper
            scrapers = [
                ("bitsearch", _get_bitsearch_scraper),
                ("cilixiong", _get_cilixiong_scraper),
                ("xl720", _get_xl720_scraper),
                ("nyaa", _get_nyaa_scraper),
                ("mikan", _get_mikan_scraper),
                ("yts", _get_yts_scraper),
                ("limetorrents", _get_limetorrents_scraper),
                ("acgrip", _get_acgrip_scraper),
                ("bangumi_moe", _get_bangumi_moe_scraper),
            ]
            existing_hashes = set()
            for r in all_results:
                h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                if h:
                    existing_hashes.add(h.group(1).upper())

            import concurrent.futures
            def _search_source(name_getter):
                name, getter = name_getter
                if not bt_overrides.get(name, True):
                    return []
                try:
                    scraper = getter()
                    return scraper.search_as_search_results(keyword, max_results=20)
                except:
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(_search_source, sg): sg[0] for sg in scrapers}
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        results = future.result(timeout=5)
                        for r in results:
                            h = re.search(r"btih:([a-fA-F0-9]{40})", r.download_url, re.IGNORECASE)
                            if h:
                                hash_upper = h.group(1).upper()
                                if hash_upper not in existing_hashes:
                                    existing_hashes.add(hash_upper)
                                    all_results.append(r)
                    except:
                        pass
        except Exception as e:
            print(f"[Search/Single] 直搜源合并失败: {e}")

        return {
            "keyword": keyword,
            "bt_count": len(all_results),
            "bt_results": [_enrich_result(r, keyword) for r in all_results],
            "total_raw": total_raw,
            "total_filtered": len(all_results),
        }

    # 智能过滤模式
    conf = config_m.config
    gf = GlobalFilter(
        must_include=conf.search_filter.must_include,
        must_exclude=conf.search_filter.must_exclude if conf.search_filter.must_exclude else None,
    )

    try:
        from alias_resolver import AliasResolver, AliasSet
        from secondary_matcher import SecondaryMatcher

        # 二次匹配（仅标题匹配，不含年份）
        if media_type:
            resolver = AliasResolver(douban_client, bangumi_client)
            aliases = resolver.resolve(keyword, "", media_type)
            target_titles = [keyword]
            if aliases:
                target_titles.extend(aliases.cn_names or [])
                target_titles.extend(aliases.en_names or [])
            target_titles = list(dict.fromkeys(t for t in target_titles if t))

            matcher = SecondaryMatcher()
            passed = matcher.batch_filter(
                bt_titles=[r.title for r in deduped],
                target_titles=target_titles,
                target_year="",
                media_type=media_type,
            )
            deduped = [deduped[i] for i in passed]

        # 全局过滤
        if deduped:
            filter_passed = gf.apply([r.title for r in deduped])
            deduped = [deduped[i] for i in filter_passed]

        return {
            "keyword": keyword,
            "bt_count": len(deduped),
            "bt_results": [r.dict() for r in deduped],
            "total_raw": total_raw,
            "total_filtered": len(deduped),
        }
    except Exception as e:
        print(f"[Search/Single] error: {e}")
        # fallback 到裸搜
        raw = clients["search"].search(keyword)
        return {"keyword": keyword, "bt_count": len(raw), "bt_results": [r.dict() for r in raw], "total_raw": len(raw), "total_filtered": len(raw)}


# ── 搜索源管理 ──

# BT 源默认配置
_BT_SOURCE_DEFAULTS = {
    "prowlarr": {"label": "Prowlarr", "enabled": True, "type": "bt"},
    "bitsearch": {"label": "Bitsearch", "enabled": True, "type": "bt"},
    "cilixiong": {"label": "磁力熊", "enabled": True, "type": "bt"},
    "xl720": {"label": "XL720", "enabled": True, "type": "bt"},
    "nyaa": {"label": "Nyaa", "enabled": True, "type": "bt"},
    "mikan": {"label": "蜜柑计划", "enabled": True, "type": "bt"},
    "yts": {"label": "YTS", "enabled": True, "type": "bt"},
    "limetorrents": {"label": "LimeTorrents", "enabled": False, "type": "bt"},  # 站点 CF 保护严格，暂不可用
    "acgrip": {"label": "ACG.RIP", "enabled": True, "type": "bt"},
    "bangumi_moe": {"label": "Bangumi Moe", "enabled": True, "type": "bt"},
}
# 网盘源默认配置
_PAN_SOURCE_DEFAULTS = {
    "pansearch": {"label": "PanSearch", "enabled": True, "type": "pan"},
    "gogopanso": {"label": "狗狗盘搜", "enabled": True, "type": "pan"},
    "github": {"label": "GitHub", "enabled": True, "type": "pan"},
    "rrdynb": {"label": "人人电影", "enabled": True, "type": "pan"},
    "ddys": {"label": "低端影视", "enabled": True, "type": "pan"},
    "pansou": {"label": "PanSou", "enabled": False, "type": "pan"},
}


@router.get("/search/sources")
def get_search_sources():
    """获取所有搜索源及启用状态。"""
    conf = config_m.config
    bt_overrides = conf.bt_search_sources or {}
    pan_overrides = conf.pan_search_sources or {}

    sources = []
    for name, info in _BT_SOURCE_DEFAULTS.items():
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": bt_overrides.get(name, info["enabled"]),
        })
    for name, info in _PAN_SOURCE_DEFAULTS.items():
        sources.append({
            "name": name, "label": info["label"], "type": info["type"],
            "enabled": pan_overrides.get(name, info["enabled"]),
        })
    return {"sources": sources}


@router.put("/search/sources/{name}")
def toggle_search_source(name: str, req: dict):
    """切换搜索源启用/禁用。"""
    enabled = req.get("enabled", True)
    conf = config_m.config

    # 判断是 BT 源还是网盘源
    if name in _BT_SOURCE_DEFAULTS:
        if not conf.bt_search_sources:
            conf.bt_search_sources = {}
        conf.bt_search_sources[name] = enabled
    elif name in _PAN_SOURCE_DEFAULTS:
        if not conf.pan_search_sources:
            conf.pan_search_sources = {}
        conf.pan_search_sources[name] = enabled
    else:
        raise HTTPException(status_code=404, detail=f"未知搜索源: {name}")

    config_m.save(conf)
    return {"ok": True, "name": name, "enabled": enabled}
