"""
搜索辅助函数：结果增强、BT 标题清洗、垃圾标记、直搜源合并。

从 routes/search.py 拆出，供路由层调用。
"""
import re
from quality_parser import compute_quality_score


# ── BT 标题清洗（专为搜索匹配设计，比 parse_filename 更激进）──
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
_RELEASE_GROUP_RE = re.compile(r'-[A-Za-z0-9]{2,15}$')

# 枪版/低质量关键词
_JUNK_QUALITY_PATTERNS = ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS", "TELESYNC", "HDCAM"]
_MATCH_SCORE_THRESHOLD = 30


def extract_bt_title_for_match(title: str) -> str:
    """从 BT 标题中提取作品名，去掉所有技术标签。"""
    if not title:
        return ""
    s = title
    s = re.sub(r'[\[\(【（][^\]\)】）]*[\]\)】）]', ' ', s)
    s = re.sub(r'[._]', ' ', s)
    m = _BT_TECH_TAGS_RE.search(s)
    if m:
        s = s[:m.start()]
    s = _RELEASE_GROUP_RE.sub('', s)
    s = re.sub(r'\b(19|20)\d{2}\b', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip(' -·|')
    return s if s else title


def compute_junk_flags(d: dict) -> dict:
    """计算 is_junk 和 junk_reasons，供智能过滤使用

    四条规则 + 一条业务层占比检查：
    1. 枪版检测（TS/CAM 等）
    2. 匹配度过低（match_score > 0 且 < 阈值）
    3. 完全不匹配（match_score=0 + 有多语言候选）
    4. 死种检测（seeders=0 且非磁力源）
    5. 标题占比过低（match_score 40-70 但搜索词只是长标题的一小部分）
    """
    reasons = []
    title = d.get("title", "")
    match_score = d.get("match_score", 0)
    seeders = d.get("seeders", 0)
    size_gb = d.get("size_gb", 0)
    has_multilang = d.get("_has_multilang_candidates", False)

    # 规则 1: 枪版
    for p in _JUNK_QUALITY_PATTERNS:
        if re.search(r'\b' + p + r'\b', title, re.I):
            reasons.append(f"low_quality:{p}")
            break

    # 规则 2: 匹配度过低
    if match_score > 0 and match_score < _MATCH_SCORE_THRESHOLD:
        reasons.append(f"low_match:{match_score}")

    # 规则 3: 完全不匹配（跨语言）
    if match_score == 0 and has_multilang:
        reasons.append("unmatched")

    # 规则 4: 死种
    is_magnet_only = seeders == 0 and size_gb == 0
    if seeders == 0 and not is_magnet_only:
        reasons.append("dead_seed")

    # 规则 5: 标题占比过低（业务层，基于 L2 评分 + BT 标题特征）
    # 当 match_score 在 40-70（非精确匹配）时，检查搜索词在清洗标题中的占比
    # 如果搜索词只占标题很小一部分，说明是"关键词被覆盖"而非"作品名匹配"
    if 40 <= match_score <= 70 and not any("low_match" in r for r in reasons):
        bt_clean = d.get("_bt_clean", "")
        search_names = d.get("_search_names", [])
        if bt_clean and search_names:
            from text_processing import normalize as _norm, split_by_language as _split, tokenize as _tok
            # 分别对中文和英文部分做占比检查，取最高
            bt_parts = _split(bt_clean)
            best_ratio = 0.0
            for name in search_names:
                name_parts = _split(name)
                # 中文部分占比
                cn_name = _norm(name_parts["cn"]) if name_parts["cn"] else ""
                cn_bt = _norm(bt_parts["cn"]) if bt_parts["cn"] else ""
                if cn_name and cn_bt:
                    if cn_name in cn_bt or cn_bt in cn_name:
                        shorter = min(len(cn_name), len(cn_bt))
                        best_ratio = max(best_ratio, shorter / max(len(cn_bt), 1))
                # 英文部分占比
                en_name = _norm(name_parts["en"]) if name_parts["en"] else ""
                en_bt = _norm(bt_parts["en"]) if bt_parts["en"] else ""
                if en_name and en_bt:
                    if en_name in en_bt or en_bt in en_name:
                        shorter = min(len(en_name), len(en_bt))
                        best_ratio = max(best_ratio, shorter / max(len(en_bt), 1))
                # 如果不是子串关系，用 token 交集占比
                if best_ratio < 0.3:
                    c_toks = set(_tok(name))
                    t_toks = set(_tok(bt_clean))
                    if t_toks:
                        overlap = len(c_toks & t_toks)
                        best_ratio = max(best_ratio, overlap / len(t_toks))
            # 占比低于 30% → 搜索词只是长标题的一小部分
            if best_ratio < 0.3:
                reasons.append(f"low_title_ratio:{best_ratio:.2f}")

    return {"is_junk": len(reasons) > 0, "junk_reasons": reasons}


def enrich_result(r, search_query: str = "", match_names: list = None) -> dict:
    """给搜索结果附加 quality_score、match_score、is_junk 标记

    match_names: 额外的匹配候选名称列表（cn_name/en_name/original_name），
                 和 search_query 一起构造 candidates，解决跨语言匹配问题。
    """
    try:
        if hasattr(r, "dict"):
            d = r.dict()
        elif hasattr(r, "model_dump"):
            d = r.model_dump()
        else:
            d = dict(r)
        if d.get("quality") and hasattr(d["quality"], "dict"):
            d["quality"] = d["quality"].dict()
        elif d.get("quality") and hasattr(d["quality"], "model_dump"):
            d["quality"] = d["quality"].model_dump()
        if r.quality:
            d["quality_score"] = compute_quality_score(r.quality)
        else:
            d["quality_score"] = 0
        if search_query:
            try:
                from match_scoring import match_chain
                from text_processing import split_by_language as _split
                # 从搜索词 + 额外名称构造候选列表
                parts = _split(search_query)
                candidates = [n for n in [search_query, parts["cn"], parts["en"]] if n]
                # 追加额外的匹配名称（cn_name/en_name/original_name）
                if match_names:
                    for name in match_names:
                        name = name.strip() if name else ""
                        if name and name not in candidates:
                            candidates.append(name)
                            # 也拆分中英文部分
                            name_parts = _split(name)
                            for p in [name_parts["cn"], name_parts["en"]]:
                                if p and p not in candidates:
                                    candidates.append(p)
                # 去重
                candidates = list(dict.fromkeys(candidates))
                # 从 BT 标题提取干净的作品名作为目标
                bt_clean = extract_bt_title_for_match(d.get("title", ""))
                bt_parts = _split(bt_clean)
                targets = [n for n in [bt_clean, bt_parts["cn"], bt_parts["en"]] if n]
                d["match_score"] = match_chain(candidates, targets, [])
                # 标记是否有多语言候选（用于 junk_flags 判断 match_score=0 的含义）
                d["_has_multilang_candidates"] = len(candidates) >= 3
                # 传递清洗标题和搜索名称给 junk_flags 做占比检查
                d["_bt_clean"] = bt_clean
                d["_search_names"] = candidates
            except Exception:
                d["match_score"] = 0
                d["_has_multilang_candidates"] = False
        else:
            d["match_score"] = 0
        d.update(compute_junk_flags(d))
        return d
    except Exception:
        return {"title": getattr(r, "title", ""), "download_url": getattr(r, "download_url", ""),
                "indexer": getattr(r, "indexer", ""), "seeders": getattr(r, "seeders", 0),
                "size_gb": getattr(r, "size_gb", 0), "quality_score": 0, "match_score": 0,
                "is_junk": False, "junk_reasons": []}


def merge_bt_extra_sources(keyword: str, existing_results: list) -> list:
    """合并直搜源结果到已有列表，按 infohash 去重。"""
    from shared import (
        config_m as _cfg,
        _get_bitsearch_scraper, _get_cilixiong_scraper, _get_xl720_scraper,
        _get_nyaa_scraper, _get_mikan_scraper, _get_yts_scraper,
        _get_limetorrents_scraper, _get_acgrip_scraper, _get_bangumi_moe_scraper,
    )
    merged = list(existing_results)
    bt_overrides = _cfg.config.bt_search_sources or {}
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
            s = getter()
            results = s.search_as_search_results(keyword, max_results=20)
            added = 0
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
