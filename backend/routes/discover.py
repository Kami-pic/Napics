"""
路由模块：discover
"""
import os
import logging
import json
import re
import time
import shutil
import requests
import concurrent.futures
import hashlib
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from shared import (
    config_m, get_clients, media_matcher,
)
import douban_client, bangumi_client, scraper
import douban_api_v2
from routes.media_detail import AddMediaRequest
from discover_enrich import (
    inject_local_status, inject_clean_names, async_enrich_tmdb_ids, in_rating_range,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("discover"):
        return {"type": type, "items": []}

    # 动画 tab 走 Bangumi
    if tag == "动画":
        items = bangumi_client.get_hot_anime(page_start, 12)
        return {"type": type, "items": items}

    # 文件缓存：7 天内直接返回
    cache_key = hashlib.md5(f"hot_{type}_{tag}_{page_start}".encode()).hexdigest()[:12]
    cache_path = os.path.join("scrape_cache", f"hot_{cache_key}.json")
    if os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            if time.time() - mtime < 604800:  # 7 天
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

    # 最多 4 个并发线程，超时 4 秒
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(enrich_item, item) for item in items]
        concurrent.futures.wait(futures, timeout=4)

    # 清理临时字段 + 确保所有豆瓣封面都走代理
    for item in items:
        cover = item.get("cover_url", "")
        proxy = item.get("cover_url_proxy", "")
        if cover and "doubanio.com" in cover and proxy:
            item["cover_url"] = proxy
        item.pop("cover_url_proxy", None)

    # 注入结构化清洗名
    inject_clean_names(items)

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
        inject_local_status(results)
        return {"query": query, "candidates": results}
    # Fallback
    results = douban_client.search(query)
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    inject_local_status(results)
    return {"query": query, "candidates": results}


@router.post("/add-media")
def add_media(req: AddMediaRequest):
    """在目标目录创建影片文件夹并生成预刮削 NFO + 封面"""
    from tmdb_client import ScrapeResult

    # 创建以影片名命名的文件夹
    folder_name = req.title.strip() or "Unknown"
    if req.year:
        folder_name = f"{folder_name} ({req.year})"
    folder_name = "".join(c for c in folder_name if c not in r'\/:*?"<>|').strip()
    folder_path = os.path.join(req.save_path, folder_name)
    os.makedirs(folder_path, exist_ok=True)

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

    nfo_written = False
    try:
        scraper.write_movie_nfo(folder_path, result)
        nfo_written = True
    except Exception as e:
        logger.error(f"[AddMedia] NFO write error: {e}")

    poster_downloaded = False
    if req.poster_url:
        try:
            poster_downloaded = scraper.download_poster(folder_path, req.poster_url)
        except Exception as e:
            logger.error(f"[AddMedia] poster download error: {e}")

    return {
        "status": "ok",
        "folder_path": folder_path,
        "nfo_written": nfo_written,
        "poster_downloaded": poster_downloaded,
    }


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
    "combined": None,
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
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("discover"):
        return {"source": source, "items": [], "total": 0}

    # 综合推荐走独立逻辑（带文件缓存 1 小时）
    if source == "combined":
        cache_key = hashlib.md5(b"combined_recommend").hexdigest()[:12]
        cache_path = os.path.join("scrape_cache", f"combined_{cache_key}.json")
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                if time.time() - mtime < 3600:  # 1 小时缓存
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    sliced = cached[start:start + count]
                    inject_local_status(sliced)
                    inject_clean_names(sliced)
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
        return {"source": "combined", "items": inject_clean_names(inject_local_status(items[start:start + count])), "count": len(items)}

    fetcher = _RECOMMEND_SOURCES.get(source)
    if not fetcher:
        raise HTTPException(status_code=400, detail=f"未知推荐源: {source}，可选: {list(_RECOMMEND_SOURCES.keys())}")
    try:
        items = fetcher(start, count)
        if items:
            # 豆瓣源：后台异步补全 tmdb_id
            if source.startswith("douban"):
                async_enrich_tmdb_ids(items)
            return {"source": source, "items": inject_clean_names(inject_local_status(items)), "count": len(items)}
    except Exception as e:
        logger.error(f"[Discover] recommend/{source} API v2 失败: {e}")

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
            logger.info(f"[Discover] {source} fallback 到旧版网页接口")
            items = douban_client.get_hot_list(fb[0], start, fb[1])
            return {"source": source, "items": inject_clean_names(inject_local_status(items or [])), "count": len(items or []), "fallback": True}
        except Exception as e2:
            logger.error(f"[Discover] {source} fallback 也失败: {e2}")
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
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("discover"):
        return {"items": [], "total": 0}

    try:
        if provider == "douban":
            has_rating_filter = vote_average > 0 or vote_max < 10
            fetch_count = int(count * 1.3) if not has_rating_filter else int(count * 1.5)
            if sort == "TOP250" and type == "movie":
                items = douban_api_v2.movie_top250(start=page * count, count=fetch_count)
            elif type == "tv":
                items = douban_api_v2.tv_explore(tags=tags, sort=sort, start=page * count, count=fetch_count)
            else:
                items = douban_api_v2.movie_explore(tags=tags, sort=sort, start=page * count, count=fetch_count)
            # 评分范围过滤（双滑块）
            if has_rating_filter:
                items = [i for i in (items or []) if in_rating_range(i.get("rating", 0), vote_average, vote_max)]
            # 通用候补：过滤后不足 count 条时，用其他排序补位
            if items is not None and len(items) < count and sort != "TOP250":
                existing_ids = {i.get("douban_id") for i in items if i.get("douban_id")}
                fill_sort = "U" if sort != "U" else "S"
                fill_fn = douban_api_v2.tv_explore if type == "tv" else douban_api_v2.movie_explore
                fill = fill_fn(tags=tags, sort=fill_sort, start=0, count=count)
                for fi in (fill or []):
                    if has_rating_filter and not in_rating_range(fi.get("rating", 0), vote_average, vote_max):
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
        return {"provider": provider, "type": type, "items": inject_clean_names(inject_local_status(items or [])), "count": len(items or [])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Discover] explore 失败: {e}")
        return {"provider": provider, "type": type, "items": [], "count": 0, "error": str(e)}


@router.get("/discover/sources")
def discover_sources():
    """返回所有可用的推荐源和探索源列表。未安装 feature-discover 插件时返回空。"""
    from plugin_guard import is_feature_allowed
    if not is_feature_allowed("discover"):
        return {"recommend": [], "explore": {}}
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
    cleared = 0
    for f in glob.glob(os.path.join(cache_dir, "dbv2_*.json")):
        try:
            os.remove(f)
            cleared += 1
        except:
            pass
    for f in glob.glob(os.path.join(cache_dir, "hot_*.json")):
        try:
            os.remove(f)
            cleared += 1
        except:
            pass
    return {"status": "ok", "cleared": cleared, "source": source}
