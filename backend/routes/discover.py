"""
路由模块：discover
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
    _tmdb_client, get_clients, media_matcher,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
import douban_api_v2
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask

router = APIRouter()


def _inject_local_status(items: list) -> list:
    """给推荐/探索结果注入 local_status 字段"""
    if items:
        media_matcher.match_batch(items)
    return items


def _inject_clean_names(items: list) -> list:
    """给推荐/探索结果注入结构化清洗名字段（cn/en/original）"""
    import re
    from clean_name_system import clean_from_scrape
    from text_processing import detect_language
    for item in items:
        title = item.get("title", "")
        if not title:
            continue
        # 已有结构化字段则跳过
        if item.get("clean_name_cn"):
            continue
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
            # lang == "cn" 时不赋值（和 title 重复）

        # 从 subtitle 中提取英文名（豆瓣格式："Inception / 盗梦空间"）
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
    return items


def _async_enrich_tmdb_ids(items: list):
    """后台线程：为豆瓣榜单数据补全 tmdb_id（用 TMDB 搜索），结果缓存到 id_mapping_cache。"""
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
                        # 补全英文名：用 _get_english_title 获取真正的英文名
                        orig = best.get("original_title") or best.get("original_name") or ""
                        if orig and orig != title:
                            from text_processing import detect_language as _dl
                            lang = _dl(orig)
                            if lang == "en":
                                item["_tmdb_original_title"] = orig
                                if not item.get("clean_name_en"):
                                    item["clean_name_en"] = orig
                            elif lang in ("jp", "ko"):
                                if not item.get("clean_name_original"):
                                    item["clean_name_original"] = orig
                        # 如果还没有英文名，尝试用 en-US 请求
                        if not item.get("clean_name_en") and tid:
                            try:
                                en_title = tmdb._get_english_title(
                                    "tv" if media_type == "tv" else "movie", tid, orig or ""
                                )
                                if en_title and en_title != title:
                                    item["clean_name_en"] = en_title
                            except Exception:
                                pass
                    time.sleep(0.5)  # 避免 TMDB 限频
                except Exception:
                    pass
            if enriched > 0:
                media_matcher._save_id_cache()
                print(f"[Discover] 榜单 tmdb_id 补全: {enriched} 条")
        except Exception as e:
            print(f"[Discover] tmdb_id 补全失败: {e}")
    threading.Thread(target=_do_enrich, daemon=True).start()


@router.get("/movie/poster")
def get_movie_poster(name: str):
    """从 TMDB 获取电影海报并缓存到本地"""
    cache_dir = os.path.join(os.getcwd(), "posters")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    safe_name = "".join(x for x in name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(cache_dir, f"{safe_name}.jpg")
    
    if os.path.exists(cache_path):
        return FileResponse(cache_path)
        
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=404, detail="TMDB API Key not configured")

    try:
        # 先清洗文件名：去掉扩展名、质量标签、字幕组等杂质
        import re
        clean = name
        clean = re.sub(r'\.[a-zA-Z0-9]{2,4}$', '', clean)  # 去扩展名
        clean = re.sub(r'(?i)(BD|HD|4K|1080[pi]?|720[pi]?|2160[pi]?|REMUX|BluRay|WEB-?DL|DVDRip|BDRip|x264|x265|HEVC|AAC|DTS|FLAC|10bit)', '', clean)
        clean = re.sub(r'(?i)(日语|中字|中文|英文|双语|国语|粤语|字幕|简体|繁体|简繁|内嵌|外挂|特效)', '', clean)
        clean = re.sub(r'\[.*?\]', '', clean)  # 去方括号标签
        clean = re.sub(r'[._\-]+', ' ', clean).strip()
        clean = clean.strip() or name

        search_url = f"https://api.themoviedb.org/3/search/movie"
        params = {"api_key": api_key, "query": clean, "language": "zh-CN"}
        resp = requests.get(search_url, params=params, timeout=5)
        results = resp.json().get("results", [])
        
        if not results:
            search_url = f"https://api.themoviedb.org/3/search/tv"
            resp = requests.get(search_url, params=params, timeout=5)
            results = resp.json().get("results", [])

        if not results:
            raise HTTPException(status_code=404, detail="Not found")

        poster_path = results[0].get("poster_path")
        if not poster_path:
            raise HTTPException(status_code=404, detail="No poster path")
            
        img_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        img_resp = requests.get(img_url, stream=True, timeout=10)
        with open(cache_path, "wb") as f:
            shutil.copyfileobj(img_resp.raw, f)
            
        return FileResponse(cache_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/douban/hot")
def douban_hot(type: str = "movie", page_start: int = 0, tag: str = "热门"):
    """获取热榜列表。动画 tab 用 Bangumi，其他用豆瓣+TMDB（文件缓存+并发）"""
    import concurrent.futures
    import hashlib, time as _time

    # 动画 tab 走 Bangumi
    if tag == "动画":
        items = bangumi_client.get_hot_anime(page_start, 12)
        return {"type": type, "items": items}

    # 文件缓存：1 小时内直接返回
    cache_key = hashlib.md5(f"hot_{type}_{tag}_{page_start}".encode()).hexdigest()[:12]
    cache_path = os.path.join("scrape_cache", f"hot_{cache_key}.json")
    if os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            if _time.time() - mtime < 604800:  # 7 天
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass

    items = douban_client.get_hot_list(type, page_start, tag)
    if not items:
        return {"type": type, "items": items}

    # 先把豆瓣封面走代理（作为 fallback）
    for item in items:
        cover = item.get("cover_url", "")
        if cover and "doubanio.com" in cover:
            item["cover_url_proxy"] = f"/proxy/image?url={requests.utils.quote(cover)}"

    # 并发搜索 TMDB 补充封面和年份
    clients = get_clients()
    tmdb = clients["tmdb"]

    def enrich_item(item):
        title = item.get("title", "")
        if not title:
            return
        try:
            results = tmdb.search_movie(title) if type == "movie" else tmdb.search_tv(title)
            if results:
                best = results[0]
                poster_path = best.get("poster_path")
                if poster_path:
                    item["cover_url"] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                if not item.get("year"):
                    tmdb_date = best.get("release_date") or best.get("first_air_date") or ""
                    if tmdb_date:
                        item["year"] = tmdb_date[:4]
                # 补全英文名
                en_title = best.get("original_title") or best.get("original_name") or ""
                if en_title and en_title != title:
                    item["original_title"] = en_title
                return
        except:
            pass
        # TMDB 搜不到，用代理封面
        if item.get("cover_url_proxy"):
            item["cover_url"] = item["cover_url_proxy"]
        # 补充 year
        if not item.get("year"):
            try:
                suggest = douban_client.search(title)
                if suggest:
                    item["year"] = suggest[0].get("year", "")
                    if not item.get("subtitle"):
                        item["subtitle"] = suggest[0].get("subtitle", "")
            except:
                pass

    # 最多 4 个并发线程，超时 8 秒
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(enrich_item, item) for item in items]
        concurrent.futures.wait(futures, timeout=4)

    # 清理临时字段 + 确保所有豆瓣封面都走代理
    for item in items:
        cover = item.get("cover_url", "")
        proxy = item.get("cover_url_proxy", "")
        # 如果 cover_url 还是豆瓣原始 URL（TMDB 超时没替换），用代理 URL
        if cover and "doubanio.com" in cover and proxy:
            item["cover_url"] = proxy
        item.pop("cover_url_proxy", None)

    # 注入结构化清洗名
    _inject_clean_names(items)

    # 保存缓存
    result = {"type": type, "items": items}
    try:
        os.makedirs("scrape_cache", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
    except:
        pass

    return result

@router.get("/douban/search")
def douban_search(query: str):
    """搜索豆瓣影片（优先 API v2）"""
    # 优先 API v2
    results = douban_api_v2.search(query, count=15)
    if results:
        for r in results:
            poster = r.get("poster_url", "")
            if poster and "doubanio.com" in poster:
                r["poster_url_original"] = poster
                r["poster_url"] = f"/proxy/image?url={requests.utils.quote(poster)}"
        _inject_local_status(results)
        return {"query": query, "candidates": results}
    # Fallback
    results = douban_client.search(query)
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    _inject_local_status(results)
    return {"query": query, "candidates": results}

@router.post("/add-media")
def add_media(req: AddMediaRequest):
    """在目标目录创建影片文件夹并生成预刮削 NFO + 封面"""
    from tmdb_client import ScrapeResult

    # 创建以影片名命名的文件夹
    folder_name = req.title.strip() or "Unknown"
    if req.year:
        folder_name = f"{folder_name} ({req.year})"
    # 清理文件名中不合法的字符
    folder_name = "".join(c for c in folder_name if c not in r'\/:*?"<>|').strip()
    folder_path = os.path.join(req.save_path, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # 构造 ScrapeResult 用于写入 NFO
    result = ScrapeResult(
        tmdb_id=int(req.douban_id) if req.douban_id.isdigit() else 0,
        media_type="movie",
        title=req.title,
        original_title=req.original_title,
        year=req.year,
        overview=req.overview,
        rating=req.rating,
        genres=req.genres,
        director=req.director,
        cast=req.cast,
        poster_url=req.poster_url,
    )

    # 写入 NFO
    nfo_written = False
    try:
        scraper.write_movie_nfo(folder_path, result)
        nfo_written = True
    except Exception as e:
        print(f"[AddMedia] NFO write error: {e}")

    # 下载封面（豆瓣图片需带 Referer 头，scraper.download_poster 已处理）
    poster_downloaded = False
    if req.poster_url:
        try:
            poster_downloaded = scraper.download_poster(folder_path, req.poster_url)
        except Exception as e:
            print(f"[AddMedia] poster download error: {e}")

    return {
        "status": "ok",
        "folder_path": folder_path,
        "nfo_written": nfo_written,
        "poster_downloaded": poster_downloaded,
    }


# ══════════════════════════════════════════════════════════════
# 二期功能 API
# ══════════════════════════════════════════════════════════════

# ── 种子排序权重配置 ──


# ══════════════════════════════════════════════════════════════
# 发现推荐 API（豆瓣 API v2 + Bangumi）
# ══════════════════════════════════════════════════════════════

def _tmdb_trending_paged(start: int, count: int) -> list:
    """TMDB trending 支持分页拼接（每页 20 条）"""
    tmdb = get_clients()["tmdb"]
    all_items = []
    page = 1
    while len(all_items) < start + count and page <= 3:
        items = tmdb.trending(page=page)
        if not items:
            break
        all_items.extend(items)
        page += 1
    return all_items[start:start + count]


# 推荐源映射
_RECOMMEND_SOURCES = {
    "combined": None,  # 综合推荐走独立逻辑
    "douban_showing": lambda start, count: douban_api_v2.movie_showing(start, count),
    "douban_movie_hot": lambda start, count: douban_api_v2.movie_hot(start, count),
    "douban_tv_hot": lambda start, count: douban_api_v2.tv_hot(start, count),
    "douban_animation": lambda start, count: douban_api_v2.tv_animation(start, count),
    "douban_weekly_chinese": lambda start, count: douban_api_v2.tv_weekly_chinese(start, count),
    "douban_weekly_global": lambda start, count: douban_api_v2.tv_weekly_global(start, count),
    "tmdb_trending": lambda start, count: _tmdb_trending_paged(start, count),
    "bangumi_calendar": lambda start, count: bangumi_client.get_hot_anime(start, count),
}


@router.get("/discover/recommend/{source}")
def discover_recommend(source: str, start: int = 0, count: int = 20):
    """统一推荐接口，豆瓣 API v2 失败时 fallback 到旧版网页接口"""
    # 综合推荐走独立逻辑（带文件缓存 1 小时）
    if source == "combined":
        import hashlib
        cache_key = hashlib.md5(b"combined_recommend").hexdigest()[:12]
        cache_path = os.path.join("scrape_cache", f"combined_{cache_key}.json")
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                if time.time() - mtime < 3600:  # 1 小时缓存
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    sliced = cached[start:start + count]
                    _inject_local_status(sliced)
                    _inject_clean_names(sliced)
                    return {"source": "combined", "items": sliced, "count": len(cached)}
            except Exception:
                pass
        from combined_recommend import get_combined_recommend
        items = get_combined_recommend()
        # 缓存结果
        try:
            os.makedirs("scrape_cache", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False)
        except Exception:
            pass
        return {"source": "combined", "items": _inject_clean_names(_inject_local_status(items[start:start + count])), "count": len(items)}

    fetcher = _RECOMMEND_SOURCES.get(source)
    if not fetcher:
        raise HTTPException(status_code=400, detail=f"未知推荐源: {source}，可选: {list(_RECOMMEND_SOURCES.keys())}")
    try:
        items = fetcher(start, count)
        if items:
            # 豆瓣源：后台异步补全 tmdb_id
            if source.startswith("douban"):
                _async_enrich_tmdb_ids(items)
            return {"source": source, "items": _inject_clean_names(_inject_local_status(items)), "count": len(items)}
    except Exception as e:
        print(f"[Discover] recommend/{source} API v2 失败: {e}")

    # Fallback：豆瓣旧版网页接口（仅豆瓣源）
    _FALLBACK_MAP = {
        "douban_showing": ("movie", "热映"),
        "douban_movie_hot": ("movie", "热门"),
        "douban_tv_hot": ("tv", "热门"),
        "douban_animation": ("tv", "动画"),
        "douban_top250": ("movie", "豆瓣高分"),
    }
    fb = _FALLBACK_MAP.get(source)
    if fb:
        try:
            print(f"[Discover] {source} fallback 到旧版网页接口")
            items = douban_client.get_hot_list(fb[0], start, fb[1])
            return {"source": source, "items": _inject_clean_names(_inject_local_status(items or [])), "count": len(items or []), "fallback": True}
        except Exception as e2:
            print(f"[Discover] {source} fallback 也失败: {e2}")
    return {"source": source, "items": [], "count": 0}


@router.get("/discover/explore")
def discover_explore(
    provider: str = "douban", type: str = "movie", sort: str = "T",
    tags: str = "", page: int = 0, count: int = 20,
    # TMDB 扩展参数
    with_original_language: str = "", with_keywords: str = "",
    vote_average: float = 0, vote_count: int = 0, vote_max: float = 10,
    # Bangumi 扩展参数
    cat: int = None, year: str = "",
):
    """探索接口。provider: douban/tmdb/bangumi"""
    try:
        if provider == "douban":
            has_rating_filter = vote_average > 0 or vote_max < 10
            # 多请求 20% 以应对过滤损耗（垃圾条目+评分过滤）
            fetch_count = int(count * 1.3) if not has_rating_filter else int(count * 1.5)
            if sort == "TOP250" and type == "movie":
                items = douban_api_v2.movie_top250(start=page * count, count=fetch_count)
            elif type == "tv":
                items = douban_api_v2.tv_explore(tags=tags, sort=sort, start=page * count, count=fetch_count)
            else:
                items = douban_api_v2.movie_explore(tags=tags, sort=sort, start=page * count, count=fetch_count)
            # 评分范围过滤（双滑块）
            if has_rating_filter:
                items = [i for i in (items or []) if _in_rating_range(i.get("rating", 0), vote_average, vote_max)]
            # 通用候补：过滤后不足 count 条时，用其他排序补位
            if items is not None and len(items) < count and sort != "TOP250":
                existing_ids = {i.get("douban_id") for i in items if i.get("douban_id")}
                fill_sort = "U" if sort != "U" else "S"
                fill_fn = douban_api_v2.tv_explore if type == "tv" else douban_api_v2.movie_explore
                fill = fill_fn(tags=tags, sort=fill_sort, start=0, count=count)
                for fi in (fill or []):
                    if has_rating_filter and not _in_rating_range(fi.get("rating", 0), vote_average, vote_max):
                        continue
                    if fi.get("douban_id") and fi.get("douban_id") not in existing_ids:
                        items.append(fi)
                        existing_ids.add(fi.get("douban_id"))
                        if len(items) >= count:
                            break
            items = (items or [])[:count]
        elif provider == "tmdb":
            tmdb = get_clients()["tmdb"]
            import math
            # 有评分上限过滤时多请求 30%
            tmdb_count = int(count * 1.3) if vote_max < 10 else count
            pages_per_req = max(1, math.ceil(tmdb_count / 20))
            tmdb_start_page = page * max(1, math.ceil(count / 20)) + 1
            items = tmdb.discover(
                media_type=type,
                sort_by=sort if "." in sort else "popularity.desc",
                genres=tags,
                language=with_original_language,
                vote_avg=vote_average,
                vote_count=vote_count,
                page=tmdb_start_page,
                count=tmdb_count,
            )
            # TMDB 评分上限过滤
            if vote_max < 10 and items:
                items = [i for i in items if (i.get("rating", 0) or 0) <= vote_max]
            items = (items or [])[:count]
        elif provider == "bangumi":
            bgm_type = 2  # 默认动画
            if type == "book": bgm_type = 1
            elif type == "game": bgm_type = 4
            elif type == "real": bgm_type = 6
            items = bangumi_client.discover(
                type=bgm_type, cat=cat, sort=sort if sort in ("rank", "date") else "rank",
                year=year or None, limit=count, offset=page * count,
            )
        else:
            raise HTTPException(status_code=400, detail=f"未知 provider: {provider}")
        return {"provider": provider, "type": type, "items": _inject_clean_names(_inject_local_status(items or [])), "count": len(items or [])}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Discover] explore 失败: {e}")
        return {"provider": provider, "type": type, "items": [], "count": 0, "error": str(e)}


def _in_rating_range(rating: float, min_r: float, max_r: float) -> bool:
    """评分范围判断：评分为 0（未评分）的条目始终保留"""
    if not rating or rating <= 0:
        return True
    return min_r <= rating <= max_r


@router.get("/discover/sources")
def discover_sources():
    """返回所有可用的推荐源和探索源列表"""
    return {
        "recommend": list(_RECOMMEND_SOURCES.keys()),
        "explore": {
            "douban": {"types": ["movie", "tv"], "sorts": ["R", "S", "T"]},
            "tmdb": {"types": ["movie", "tv"], "sorts": ["popularity.desc", "vote_average.desc", "primary_release_date.desc"]},
            "bangumi": {"types": [2, 1, 4, 6], "sorts": ["rank", "date"]},
        },
    }


@router.post("/discover/refresh/{source}")
def discover_refresh(source: str):
    """清除指定推荐源的后端文件缓存，下次请求会重新拉取"""
    import glob
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scrape_cache")
    if not os.path.exists(cache_dir):
        return {"status": "ok", "cleared": 0}
    # 清除 douban_api_v2 的缓存文件（前缀 dbv2_）
    cleared = 0
    for f in glob.glob(os.path.join(cache_dir, "dbv2_*.json")):
        try:
            # 简单策略：清除所有 dbv2 缓存（因为 cache_key 是 hash，无法精确匹配 source）
            os.remove(f)
            cleared += 1
        except:
            pass
    # 也清除旧版热榜缓存
    for f in glob.glob(os.path.join(cache_dir, "hot_*.json")):
        try:
            os.remove(f)
            cleared += 1
        except:
            pass
    return {"status": "ok", "cleared": cleared, "source": source}
