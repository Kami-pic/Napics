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
    _tmdb_client, get_clients,
    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,
)
import scanner, searcher, downloader, tmdb_client, config_manager
import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer
from organize_history import history_m
from global_filter import GlobalFilter
from download_manager import DownloadManager, DownloadTask

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
    """搜索豆瓣影片"""
    results = douban_client.search(query)
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
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
