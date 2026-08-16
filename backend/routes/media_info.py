"""
路由模块：media_info — 候选搜索 + 选择确认
详情获取已拆分到 routes/media_detail.py
"""
import os
import logging
import json
import requests
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import (
    config_m, shadow_m,
    _tmdb_client,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
)
import tmdb_client, douban_client, bangumi_client, scraper, organizer
import douban_api_v2
from metadata_provider_factory import get_metadata_provider_map
from provider_models import MetadataSearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scrape/candidates")
def scrape_candidates(name: str):
    """搜索 TMDB 返回多个候选结果供用户选择"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("tmdb"):
        return {"query": name, "candidates": [], "error": "plugin_not_installed"}
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    # 优先用清洗后的名字搜索（任务 7）
    from analyzer import _clean_filename_for_folder
    clean = _clean_filename_for_folder(name)
    if clean and len(clean) >= 2:
        query = clean
    else:
        parsed = tmdb_client.parse_filename(name)
        query = parsed["clean_name"] or name
    search_query = query.replace("-", " ").replace("–", " ").replace("—", " ").strip()
    
    movies = client.search_movie(search_query)
    tvs = client.search_tv(search_query)
    
    def _is_latin(text):
        if not text: return False
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        total = sum(1 for c in text if c.isalpha())
        return total > 0 and latin / total > 0.5
    
    candidates = []
    for m in movies[:8]:
        orig = m.get("original_title", "")
        en_title = ""
        if orig and _is_latin(orig):
            en_title = orig
        else:
            try:
                en_title = client._get_english_title("movie", m["id"], orig) or ""
            except Exception:
                en_title = ""
        candidates.append({
            "tmdb_id": m["id"], "media_type": "movie",
            "title": m.get("title", ""), "original_title": orig,
            "english_title": en_title,
            "year": (m.get("release_date", "") or "")[:4],
            "overview": (m.get("overview", "") or "")[:120],
            "poster_url": f"https://image.tmdb.org/t/p/w200{m['poster_path']}" if m.get("poster_path") else None,
            "popularity": m.get("popularity", 0),
            "rating": round(m.get("vote_average", 0), 1),
        })
    for t in tvs[:5]:
        orig = t.get("original_name", "")
        en_title = ""
        if orig and _is_latin(orig):
            en_title = orig
        else:
            try:
                en_title = client._get_english_title("tv", t["id"], orig) or ""
            except Exception:
                en_title = ""
        candidates.append({
            "tmdb_id": t["id"], "media_type": "tv",
            "title": t.get("name", ""), "original_title": orig,
            "english_title": en_title,
            "year": (t.get("first_air_date", "") or "")[:4],
            "overview": (t.get("overview", "") or "")[:120],
            "poster_url": f"https://image.tmdb.org/t/p/w200{t['poster_path']}" if t.get("poster_path") else None,
            "popularity": t.get("popularity", 0),
            "rating": round(t.get("vote_average", 0), 1),
        })
    
    return {"query": query, "candidates": candidates}

@router.get("/scrape/douban")
def scrape_douban_candidates(name: str):
    """搜索豆瓣返回候选结果（优先 API v2，fallback 旧版网页接口）"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("douban"):
        return {"query": name, "candidates": [], "source": "disabled", "error": "plugin_not_installed"}
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name

    # 优先 API v2 provider
    provider = get_metadata_provider_map().get("douban")
    results = []
    if provider:
        candidates = provider.search_metadata(MetadataSearchRequest(query=query, limit=15))
        results = [_douban_candidate_to_legacy(candidate) for candidate in candidates]
    if results:
        # API v2 返回的海报是直链，不需要代理
        for r in results:
            poster = r.get("poster_url", "")
            if poster and "doubanio.com" in poster:
                r["poster_url_original"] = poster
                r["poster_url"] = f"/proxy/image?url={requests.utils.quote(poster)}"
        return {"query": query, "candidates": results, "source": "api_v2"}

    # Fallback: 旧版网页接口
    results = douban_client.search(query)
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    return {"query": query, "candidates": results, "source": "web_fallback"}


def _douban_candidate_to_legacy(candidate):
    extra = candidate.extra if isinstance(candidate.extra, dict) else {}
    return {
        **extra,
        "douban_id": candidate.external_id,
        "title": candidate.title,
        "original_title": candidate.original_title,
        "year": str(candidate.year or ""),
        "poster_url": candidate.poster_url,
        "rating": candidate.rating or 0,
        "overview": candidate.overview,
        "media_type": candidate.media_type,
    }


@router.post("/scrape/douban-select")
def scrape_douban_select(path: str, douban_id: str, title: str = "", year: str = "", poster_url: str = "", subtitle: str = "", media_type: str = ""):
    """用户选择豆瓣候选后，用搜索结果数据写入 NFO + 海报"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("douban"):
        return {"status": "plugin_not_installed", "data": None}
    from tmdb_client import ScrapeResult
    
    # 自动判断 media_type：优先用前端传入，否则先尝试 tv 再 movie
    detected_type = media_type or ""
    
    # 优先 API v2 拉取详情
    result = None
    v2_detail = None
    
    provider = get_metadata_provider_map().get("douban")

    if detected_type == "tv" or not detected_type:
        # 先尝试 tv
        v2_detail = _get_douban_provider_detail(provider, douban_id, "tv")
        if v2_detail and v2_detail.get("title"):
            detected_type = "tv"
    
    if not v2_detail or not v2_detail.get("title"):
        # 再尝试 movie
        v2_detail = _get_douban_provider_detail(provider, douban_id, "movie")
        if v2_detail and v2_detail.get("title"):
            if not detected_type:
                detected_type = "movie"
    
    if v2_detail and v2_detail.get("title"):
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type=detected_type or "movie",
            title=v2_detail.get("title", "") or title,
            original_title=v2_detail.get("original_title", "") or subtitle,
            year=v2_detail.get("year", "") or year,
            overview=v2_detail.get("overview", ""),
            rating=v2_detail.get("rating", 0),
            genres=v2_detail.get("genres", []),
            director=v2_detail.get("directors", [""])[0] if v2_detail.get("directors") else "",
            cast=v2_detail.get("actors", []),
            runtime=v2_detail.get("runtime", 0),
            poster_url=v2_detail.get("poster_url", "") or poster_url,
        )

    # Fallback: 旧版网页爬取
    if not result:
        detail = douban_client.get_detail(douban_id)
        if detail and detail.get("title"):
            result = ScrapeResult(
                tmdb_id=int(douban_id),
                media_type=detected_type or "movie",
                title=detail.get("title", "") or title,
                original_title=detail.get("original_title", "") or subtitle,
                year=detail.get("year", "") or year,
                overview=detail.get("overview", ""),
                rating=detail.get("rating", 0),
                genres=detail.get("genres", []),
                director=detail.get("director", ""),
                cast=detail.get("cast", []),
                runtime=detail.get("runtime", 0),
                poster_url=detail.get("poster_url", "") or poster_url,
            )

    # 都失败了，用搜索结果的基本信息
    if not result:
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type=detected_type or "movie",
            title=title,
            original_title=subtitle,
            year=year,
            poster_url=poster_url,
        )
    
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                try:
                    os.remove(old_p)
                except OSError:
                    pass
        # 根据 media_type 写入对应类型的 NFO
        if result.media_type == "tv":
            scraper.write_tvshow_nfo(path, result)
        else:
            scraper.write_movie_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url)
    elif os.path.isfile(path):
        scraper._write_movie_nfo_for_video(path, result)
        base = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.dirname(path)
        if result.poster_url:
            scraper.download_poster(folder, result.poster_url, base + "-poster.jpg")
    
    return {"status": "ok", "data": result.dict()}


def _get_douban_provider_detail(provider, douban_id: str, media_type: str):
    if not provider:
        return None
    detail = provider.get_detail(str(douban_id), media_type)
    if not detail:
        return None
    extra = detail.extra if isinstance(detail.extra, dict) else {}
    poster_url = ""
    for artwork in detail.artwork:
        if artwork.kind == "poster":
            poster_url = artwork.url
            break
    return {
        "title": detail.title,
        "original_title": detail.original_title,
        "year": str(detail.year or ""),
        "overview": detail.overview,
        "rating": detail.rating or 0,
        "genres": extra.get("genres", []),
        "directors": extra.get("directors", []),
        "actors": extra.get("actors", []),
        "runtime": detail.runtime or 0,
        "poster_url": poster_url,
    }

@router.get("/scrape/bangumi")
def scrape_bangumi_candidates(name: str):
    """搜索 Bangumi 返回候选结果"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("bangumi"):
        return {"query": name, "candidates": [], "error": "plugin_not_installed"}
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name
    provider = get_metadata_provider_map().get("bangumi")
    results = []
    if provider:
        candidates = provider.search_metadata(MetadataSearchRequest(query=query, limit=15))
        results = [_bangumi_candidate_to_legacy(candidate) for candidate in candidates]
    return {"query": query, "candidates": results}


def _bangumi_candidate_to_legacy(candidate):
    extra = candidate.extra if isinstance(candidate.extra, dict) else {}
    return {
        "bgm_id": int(candidate.external_id) if str(candidate.external_id).isdigit() else 0,
        "title": candidate.title,
        "original_title": candidate.original_title,
        "year": str(candidate.year or ""),
        "poster_url": candidate.poster_url,
        "summary": candidate.overview,
        "type": extra.get("type", ""),
        "type_id": extra.get("type_id", 0),
        "rating": candidate.rating or 0,
        "rank": extra.get("rank", 0),
    }

@router.post("/scrape/bangumi-select")
def scrape_bangumi_select(path: str, bgm_id: int):
    """用户选择 Bangumi 候选后，拉取详情写入 NFO + 海报"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("bangumi"):
        return {"status": "plugin_not_installed", "data": None}
    provider = get_metadata_provider_map().get("bangumi")
    detail = provider.get_detail(str(bgm_id), "") if provider else None
    if not detail:
        raise HTTPException(status_code=404, detail="Bangumi detail not found")
    
    from tmdb_client import ScrapeResult
    extra = detail.extra if isinstance(detail.extra, dict) else {}
    poster_url = ""
    for artwork in detail.artwork:
        if artwork.kind == "poster":
            poster_url = artwork.url
            break
    result = ScrapeResult(
        tmdb_id=bgm_id,
        media_type="movie" if extra.get("total_episodes", 0) <= 1 else "tv",
        title=detail.title,
        original_title=detail.original_title,
        year=str(detail.year or ""),
        overview=detail.overview,
        rating=detail.rating or 0,
        genres=extra.get("genres", []),
        director=extra.get("director", ""),
        cast=extra.get("cast", []),
        poster_url=poster_url,
    )
    
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        if result.media_type == "tv":
            scraper.write_tvshow_nfo(path, result)
        else:
            scraper.write_movie_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url)
    elif os.path.isfile(path):
        scraper._write_movie_nfo_for_video(path, result)
        base = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.dirname(path)
        if result.poster_url:
            scraper.download_poster(folder, result.poster_url, base + "-poster.jpg")
    
    return {"status": "ok", "data": result.dict()}

