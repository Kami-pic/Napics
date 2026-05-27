"""发现推荐 — TMDB 英文名/评分缓存 + 清洗名注入 + 本地状态注入。

从 routes/discover.py 拆分，属于业务逻辑层。
"""

import os
import logging
import json
import re
import time
import threading
import concurrent.futures
from datetime import datetime
from typing import Dict

from shared import _tmdb_client, media_matcher

logger = logging.getLogger(__name__)
# ── tmdb_enrich_cache：持久化 TMDB 英文名+评分缓存 ──
_enrich_cache: Dict[str, dict] = {}
_enrich_cache_lock = threading.Lock()
_ENRICH_CACHE_PATH = os.path.join("scrape_cache", "tmdb_enrich_cache.json")
_ENRICH_CACHE_MAX = 5000
_ENRICH_CACHE_TTL = 30 * 86400  # 30 天


def _load_enrich_cache():
    """启动时加载持久化缓存到内存"""
    global _enrich_cache
    if os.path.exists(_ENRICH_CACHE_PATH):
        try:
            with open(_ENRICH_CACHE_PATH, "r", encoding="utf-8") as f:
                _enrich_cache = json.load(f)
            logger.info(f"[Discover] enrich_cache 加载: {len(_enrich_cache)} 条")
        except Exception as e:
            logger.error(f"[Discover] enrich_cache 加载失败: {e}")
            _enrich_cache = {}


def _save_enrich_cache():
    """异步写入缓存文件（调用方需持有 _enrich_cache_lock）"""
    def _do_save():
        try:
            os.makedirs("scrape_cache", exist_ok=True)
            with open(_ENRICH_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_enrich_cache, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[Discover] enrich_cache 写入失败: {e}")
    threading.Thread(target=_do_save, daemon=True).start()


def _enrich_cache_key(item: dict) -> str:
    """生成缓存 key：douban_id > tmdb_id > title_year"""
    did = item.get("douban_id")
    if did:
        return f"douban_{did}"
    tid = item.get("tmdb_id")
    if tid:
        return f"tmdb_{tid}"
    return f"title_{item.get('title', '')}_{item.get('year', '')}"


def enrich_cache_put(key: str, tmdb_id: int = 0, en_title: str = "",
                     original_title: str = "", tmdb_rating: float = 0):
    """写入一条 enrich_cache 记录（线程安全）"""
    with _enrich_cache_lock:
        _enrich_cache[key] = {
            "tmdb_id": tmdb_id,
            "en_title": en_title,
            "original_title": original_title,
            "tmdb_rating": tmdb_rating,
            "updated_at": datetime.now().isoformat(),
        }
        # LRU 淘汰
        if len(_enrich_cache) > _ENRICH_CACHE_MAX:
            oldest = sorted(_enrich_cache, key=lambda k: _enrich_cache[k].get("updated_at", ""))
            for k in oldest[:len(_enrich_cache) - _ENRICH_CACHE_MAX]:
                _enrich_cache.pop(k, None)
        _save_enrich_cache()


# 启动时加载
_load_enrich_cache()


def inject_local_status(items: list) -> list:
    """给推荐/探索结果注入 local_status 字段"""
    if items:
        media_matcher.match_batch(items)
    return items


def inject_clean_names(items: list) -> list:
    """给推荐/探索结果注入结构化清洗名字段（cn/en/original）。
    C+E 方案：先查 enrich_cache，未命中的同步并发请求 TMDB（2 秒超时），超时的转交后台。
    """
    from clean_name_system import clean_from_scrape
    from text_processing import detect_language

    need_enrich = []  # 缺英文名且缓存未命中的条目

    for item in items:
        title = item.get("title", "")
        if not title:
            continue
        # 已有结构化字段则跳过
        if item.get("clean_name_cn"):
            continue

        # 查 enrich_cache
        cache_key = _enrich_cache_key(item)
        cached = _enrich_cache.get(cache_key)
        if cached:
            # 检查过期
            updated = cached.get("updated_at", "")
            if updated:
                try:
                    age = (datetime.now() - datetime.fromisoformat(updated)).total_seconds()
                    if age > _ENRICH_CACHE_TTL:
                        cached = None
                except Exception:
                    pass

        raw_original = item.get("original_title") or item.get("_tmdb_original_title") or ""
        subtitle = item.get("subtitle", "")

        # 判断 original_title 的语言，正确分配到 en 或 original
        en = ""
        original = ""
        if raw_original and raw_original != title:
            lang = detect_language(raw_original)
            if lang == "en":
                en = raw_original
            elif lang in ("jp", "ko", "mixed"):
                original = raw_original

        # 从 subtitle 中提取英文名
        if not en and subtitle:
            parts = re.split(r'\s*/\s*', subtitle)
            for p in parts:
                p = p.strip()
                if not p or p == title:
                    continue
                lang = detect_language(p)
                if lang == "en":
                    en = p
                    break
                elif lang in ("jp", "ko") and not original:
                    original = p

        # 用缓存补全英文名 + TMDB 评分
        if cached:
            if not en and cached.get("en_title"):
                en = cached["en_title"]
            if cached.get("tmdb_rating") and not item.get("tmdb_rating"):
                item["tmdb_rating"] = cached["tmdb_rating"]

        result = clean_from_scrape(
            title=title,
            original_title=original,
            english_title=en,
            year=item.get("year", ""),
            source="tmdb",
        )
        item["clean_name_cn"] = result.cn
        item["clean_name_en"] = result.en
        item["clean_name_original"] = result.original

        # 仍然缺英文名 → 收集待补全
        if not item.get("clean_name_en"):
            need_enrich.append(item)

    # 同步并发补全缺英文名的条目（最多等 2 秒）
    if need_enrich:
        tmdb = _tmdb_client()
        if tmdb:
            timed_out_items = _sync_enrich_english_names(need_enrich, tmdb, timeout=2.0)
            # 超时的条目转交后台继续
            if timed_out_items:
                async_enrich_tmdb_ids(timed_out_items)

    return items


def _sync_enrich_english_names(items: list, tmdb, timeout: float = 2.0) -> list:
    """同步并发请求 TMDB 补全英文名，返回超时未完成的条目列表"""
    from text_processing import detect_language

    def _fetch_en(item):
        title = item.get("title", "")
        media_type = item.get("media_type", "movie")
        try:
            results = tmdb.search_tv(title) if media_type == "tv" else tmdb.search_movie(title)
            if not results:
                return item, None
            best = results[0]
            tid = best.get("id")
            orig = best.get("original_title") or best.get("original_name") or ""
            en_title = ""
            # 先看 original_title 是否为英文
            if orig and orig != title:
                lang = detect_language(orig)
                if lang == "en":
                    en_title = orig
            # 不是英文则用 en-US 请求
            if not en_title and tid:
                en_title = tmdb.get_english_title(
                    "tv" if media_type == "tv" else "movie", tid, orig or ""
                )
                if en_title == title:
                    en_title = ""
            tmdb_rating = best.get("vote_average", 0)
            return item, {"tid": tid, "en_title": en_title, "orig": orig, "tmdb_rating": tmdb_rating}
        except Exception:
            return item, None

    timed_out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(_fetch_en, it): it for it in items}
        try:
            for future in concurrent.futures.as_completed(future_map, timeout=timeout):
                item, result = future.result()
                if result:
                    if result.get("en_title"):
                        item["clean_name_en"] = result["en_title"]
                    if result.get("tmdb_rating") and not item.get("tmdb_rating"):
                        item["tmdb_rating"] = result["tmdb_rating"]
                    # 有英文名或评分时写入缓存
                    if result.get("en_title") or result.get("tmdb_rating"):
                        cache_key = _enrich_cache_key(item)
                        enrich_cache_put(
                            cache_key,
                            tmdb_id=result.get("tid", 0),
                            en_title=result.get("en_title", ""),
                            original_title=result.get("orig", ""),
                            tmdb_rating=result.get("tmdb_rating", 0),
                        )
        except concurrent.futures.TimeoutError:
            # 收集超时未完成的条目
            for f, it in future_map.items():
                if not f.done():
                    timed_out.append(it)
            logger.warning(f"[Discover] 同步补全超时，{len(timed_out)} 条转交后台")
    return timed_out


def async_enrich_tmdb_ids(items: list):
    """后台线程：为豆瓣榜单数据补全 tmdb_id + 英文名，结果写入 enrich_cache 持久化。"""
    def _do_enrich():
        try:
            tmdb = _tmdb_client()
            if not tmdb:
                return
            enriched = 0
            for item in items:
                if item.get("tmdb_id"):
                    continue
                douban_id = item.get("douban_id")
                if not douban_id:
                    continue
                # 检查 matcher 缓存
                cached_tid = media_matcher._id_cache.get(str(douban_id))
                if cached_tid:
                    item["tmdb_id"] = cached_tid
                    enriched += 1
                    continue
                # TMDB 搜索补全
                title = item.get("original_title") or item.get("title") or ""
                if not title:
                    continue
                year = item.get("year", "")
                media_type = item.get("media_type", "movie")
                try:
                    if media_type == "tv":
                        results = tmdb.search_tv(title)
                    else:
                        results = tmdb.search_movie(title)
                    if results:
                        best = results[0]
                        tid = best.get("id")
                        if tid:
                            item["tmdb_id"] = tid
                            media_matcher.add_id_mapping(str(douban_id), tid)
                            enriched += 1
                        orig = best.get("original_title") or best.get("original_name") or ""
                        en_title = ""
                        if orig and orig != title:
                            from text_processing import detect_language as _dl

                            lang = _dl(orig)
                            if lang == "en":
                                item["_tmdb_original_title"] = orig
                                en_title = orig
                                if not item.get("clean_name_en"):
                                    item["clean_name_en"] = orig
                            elif lang in ("jp", "ko"):
                                if not item.get("clean_name_original"):
                                    item["clean_name_original"] = orig
                        # 如果还没有英文名，尝试用 en-US 请求
                        if not en_title and not item.get("clean_name_en") and tid:
                            try:
                                en_title = tmdb.get_english_title(
                                    "tv" if media_type == "tv" else "movie", tid, orig or ""
                                )
                                if en_title and en_title != title:
                                    item["clean_name_en"] = en_title
                                else:
                                    en_title = ""
                            except Exception:
                                pass
                        # 写入 enrich_cache
                        if en_title or tid:
                            cache_key = _enrich_cache_key(item)
                            enrich_cache_put(
                                cache_key,
                                tmdb_id=tid or 0,
                                en_title=en_title or "",
                                original_title=orig or "",
                                tmdb_rating=best.get("vote_average", 0),
                            )
                    time.sleep(0.5)  # 避免 TMDB 限频
                except Exception:
                    pass
            if enriched > 0:
                media_matcher._save_id_cache()
                logger.info(f"[Discover] 榜单 tmdb_id 补全: {enriched} 条")
        except Exception as e:
            logger.error(f"[Discover] tmdb_id 补全失败: {e}")
    threading.Thread(target=_do_enrich, daemon=True).start()


def in_rating_range(rating: float, min_r: float, max_r: float) -> bool:
    """评分范围判断：评分为 0（未评分）的条目始终保留"""
    if not rating or rating <= 0:
        return True
    return min_r <= rating <= max_r
