"""
路由模块：scrape
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

@router.post("/media/shadow-name")
def set_shadow_name(req: ShadowNameRequest):
    """设置影子名"""
    shadow_m.set(req.path, req.shadow_name, source=req.source)
    return {"status": "ok", "path": req.path, "shadow_name": req.shadow_name, "source": req.source}

class ShadowNameDeleteRequest(BaseModel):
    path: str

@router.delete("/media/shadow-name")
def clear_shadow_name(req: ShadowNameDeleteRequest):
    """清除影子名"""
    shadow_m.clear(req.path)
    return {"status": "ok", "path": req.path}

@router.post("/media/shadow-name/batch")
def batch_generate_shadow_names():
    """批量生成影子名（NFO + TMDB 搜索）"""
    api_key = config_m.config.tmdb_api_key
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '') if api_key else None
    stats = shadow_m.batch_generate(tmdb_client=client)
    return {"status": "ok", **stats}

# ── 索引器优先级管理 API ──

@router.get("/config/indexers")
def get_indexer_priorities():
    """获取索引器优先级列表，自动从 Prowlarr 同步已有索引器"""
    from indexer_priority_manager import IndexerConfig
    indexer_m.load()
    
    # 如果本地没有配置，从 Prowlarr 拉取索引器列表
    if not indexer_m.indexers:
        try:
            prowlarr_url = config_m.config.prowlarr_url.rstrip("/")
            prowlarr_key = config_m.config.prowlarr_api_key
            if prowlarr_url and prowlarr_key:
                import requests
                resp = requests.get(f"{prowlarr_url}/api/v1/indexer",
                                    params={"apikey": prowlarr_key}, timeout=5)
                resp.raise_for_status()
                prowlarr_indexers = resp.json()
                configs = []
                for idx in prowlarr_indexers:
                    if idx.get("enable", True):
                        name = idx.get("name", "")
                        # 根据名字猜测类型偏好
                        types = []
                        name_lower = name.lower()
                        if "nyaa" in name_lower:
                            types = ["anime"]
                        elif "yts" in name_lower:
                            types = ["movie"]
                        configs.append(IndexerConfig(
                            indexer_id=idx.get("id", 0),
                            name=name,
                            priority=50,
                            enabled=True,
                            preferred_types=types,
                            supports_chinese="chinese" in name_lower or "dmhy" in name_lower,
                        ))
                if configs:
                    indexer_m.save(configs)
                    indexer_m.indexers = configs
        except Exception as e:
            print(f"[Indexers] Failed to fetch from Prowlarr: {e}")
    
    return [
        {
            "indexer_id": idx.indexer_id,
            "name": idx.name,
            "priority": idx.priority,
            "enabled": idx.enabled,
            "preferred_types": idx.preferred_types,
            "supports_chinese": idx.supports_chinese,
        }
        for idx in indexer_m.indexers
    ]

class IndexerPriorityItem(BaseModel):
    indexer_id: int = 0
    name: str = ""
    priority: int = 50
    enabled: bool = True
    preferred_types: List[str] = []
    supports_chinese: bool = False

class IndexerPrioritySaveRequest(BaseModel):
    indexers: List[IndexerPriorityItem]

@router.post("/config/indexers")
def save_indexer_priorities(req: IndexerPrioritySaveRequest):
    """保存索引器优先级配置"""
    from indexer_priority_manager import IndexerConfig
    configs = [
        IndexerConfig(
            indexer_id=item.indexer_id,
            name=item.name,
            priority=item.priority,
            enabled=item.enabled,
            preferred_types=item.preferred_types,
            supports_chinese=item.supports_chinese,
        )
        for item in req.indexers
    ]
    indexer_m.save(configs)
    return {"status": "ok", "count": len(configs)}

# ── 刮削 API ──

@router.get("/scrape")
def scrape_by_name(name: str, path: str = "", enhanced: bool = False):
    """根据名字刮削，如果提供 path 则写入 NFO + 海报
    enhanced=True 时使用增强刮削流程，返回置信度信息"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if path and os.path.exists(path):
        if os.path.isdir(path):
            result = scraper.scrape_folder(path, client)
        else:
            result = scraper.scrape_video(path, client)
        return result
    
    # 增强刮削模式：使用影子名 + 别名 + 增强评分
    if enhanced:
        try:
            match_result = client.enhanced_scrape_by_filename(name, file_path=path or "")
            return {
                "status": "ok" if match_result.tmdb_id else "not_found",
                "data": match_result.item if match_result.item else {},
                "confidence": {
                    "level": match_result.confidence,
                    "score": match_result.score,
                    "details": match_result.match_details,
                },
                "tmdb_id": match_result.tmdb_id,
                "media_type": match_result.media_type,
            }
        except Exception as e:
            # 增强刮削失败时降级到普通刮削
            print(f"[Scrape] Enhanced scrape failed, fallback: {e}")
    
    # 普通刮削
    result = client.scrape_by_filename(name)
    return {"status": "ok" if result.tmdb_id else "not_found", "data": result.dict()}

@router.get("/scrape/candidates")
def scrape_candidates(name: str):
    """搜索 TMDB 返回多个候选结果供用户选择"""
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
        })
    
    return {"query": query, "candidates": candidates}

@router.get("/scrape/douban")
def scrape_douban_candidates(name: str):
    """搜索豆瓣返回候选结果"""
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name
    results = douban_client.search(query)
    # 保留原始 URL 用于下载，代理 URL 用于前端显示
    for r in results:
        if r.get("poster_url") and "doubanio.com" in r["poster_url"]:
            r["poster_url_original"] = r["poster_url"]
            r["poster_url"] = f"/proxy/image?url={requests.utils.quote(r['poster_url'])}"
    return {"query": query, "candidates": results}

@router.get("/proxy/image")
def proxy_image(url: str):
    """代理外部图片请求（绕过防盗链 + 走 HTTP 代理）"""
    try:
        headers = {"Referer": "https://movie.douban.com/", "User-Agent": "Mozilla/5.0"}
        proxies = None
        http_proxy = getattr(config_m.config, 'http_proxy', '') or ''
        if http_proxy:
            proxies = {"http": http_proxy, "https": http_proxy}
        resp = requests.get(url, headers=headers, stream=True, timeout=10, proxies=proxies)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        from fastapi.responses import Response
        return Response(content=resp.content, media_type=content_type)
    except Exception:
        raise HTTPException(status_code=404, detail="Image fetch failed")

@router.post("/scrape/douban-select")
def scrape_douban_select(path: str, douban_id: str, title: str = "", year: str = "", poster_url: str = "", subtitle: str = ""):
    """用户选择豆瓣候选后，用搜索结果数据写入 NFO + 海报"""
    from tmdb_client import ScrapeResult
    
    # 尝试拉取详情，失败则用搜索结果的基本信息
    detail = douban_client.get_detail(douban_id)
    if detail and detail.get("title"):
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type="movie",
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
    else:
        # 详情解析失败，用搜索结果的基本信息
        result = ScrapeResult(
            tmdb_id=int(douban_id),
            media_type="movie",
            title=title,
            original_title=subtitle,
            year=year,
            poster_url=poster_url,
        )
    
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
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

@router.get("/scrape/bangumi")
def scrape_bangumi_candidates(name: str):
    """搜索 Bangumi 返回候选结果"""
    parsed = tmdb_client.parse_filename(name)
    query = parsed["clean_name"] or name
    results = bangumi_client.search(query)
    return {"query": query, "candidates": results}

@router.post("/scrape/bangumi-select")
def scrape_bangumi_select(path: str, bgm_id: int):
    """用户选择 Bangumi 候选后，拉取详情写入 NFO + 海报"""
    detail = bangumi_client.get_detail(bgm_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Bangumi detail not found")
    
    from tmdb_client import ScrapeResult
    result = ScrapeResult(
        tmdb_id=bgm_id,
        media_type="movie" if detail.get("total_episodes", 0) <= 1 else "tv",
        title=detail.get("title", ""),
        original_title=detail.get("original_title", ""),
        year=detail.get("year", ""),
        overview=detail.get("overview", ""),
        rating=detail.get("rating", 0),
        genres=detail.get("genres", []),
        director=detail.get("director", ""),
        cast=detail.get("cast", []),
        poster_url=detail.get("poster_url", ""),
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

@router.post("/scrape/select")
def scrape_select(path: str, tmdb_id: int, media_type: str):
    """用户选择候选后，用指定 TMDB ID 执行刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if media_type == "movie":
        result = client.get_movie_detail(tmdb_id)
    elif media_type in ("tv", "tvshow"):
        result = client.get_tv_detail(tmdb_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid media_type")
    
    if not result.tmdb_id:
        raise HTTPException(status_code=404, detail="TMDB detail not found")
    
    # 写入 NFO + 海报（先清理旧的标准 NFO 避免冲突）
    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        if result.media_type == "movie":
            scraper.write_movie_nfo(path, result)
        else:
            scraper.write_tvshow_nfo(path, result)
        proxy = getattr(config_m.config, 'http_proxy', '') or ''
        if result.poster_url:
            scraper.download_poster(path, result.poster_url, proxy=proxy)
        if result.backdrop_url:
            scraper.download_poster(path, result.backdrop_url, "fanart.jpg", proxy=proxy)
        
        # 单视频文件夹：同步影子名到 media_library.json
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(path)
            videos = [f for f in items if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subdirs = [f for f in items if os.path.isdir(os.path.join(path, f)) and not f.startswith('.')]
            if len(videos) == 1 and len(subdirs) == 0:
                vf = videos[0]
                vp = os.path.join(path, vf)
                # 写视频同名 NFO（给 Kodi/Emby 用）
                old_vnfo = os.path.splitext(vp)[0] + ".nfo"
                if os.path.exists(old_vnfo):
                    os.remove(old_vnfo)
                if result.media_type == "movie":
                    scraper._write_movie_nfo_for_video(vp, result)
                # 同步影子名
                library = config_m.load_library()
                for v in library:
                    if v.get("file_path") == vp:
                        en = result.english_title or ""
                        orig = result.original_title or ""
                        if not en and orig and orig != result.title:
                            latin = sum(1 for c in orig if c.isascii() and c.isalpha())
                            total = sum(1 for c in orig if c.isalpha())
                            if total > 0 and latin / total > 0.5:
                                en = orig
                        sn = result.title
                        if en and en != result.title:
                            sn += " " + en
                        if result.year:
                            sn += f" ({result.year})"
                        v["shadow_name"] = sn
                        v["shadow_name_source"] = "tmdb"
                        v["shadow_tmdb_id"] = result.tmdb_id
                        config_m.save_library(library)
                        break
        except OSError:
            pass
    elif os.path.isfile(path):
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            is_single_video_folder = len(vids) <= 1 and len(subs) == 0
        except OSError:
            is_single_video_folder = False
        
        if is_single_video_folder:
            # 清理历史 NFO 和封面
            for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
                old_p = os.path.join(folder, old_nfo)
                if os.path.exists(old_p): os.remove(old_p)
            for old_poster in ["poster.jpg", "poster.png", "fanart.jpg", "folder.jpg", "cover.jpg"]:
                old_p = os.path.join(folder, old_poster)
                if os.path.exists(old_p): os.remove(old_p)
            
            if result.media_type == "movie":
                scraper.write_movie_nfo(folder, result)
            else:
                scraper.write_tvshow_nfo(folder, result)
            
            proxy = getattr(config_m.config, 'http_proxy', '') or ''
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, proxy=proxy)
            
            # 同步数据库影子名
            library = config_m.load_library()
            for v in library.get("videos", []):
                if v.get("path") == path:
                    v["shadow_name"] = result.title + (f" ({result.year})" if result.year else "")
                    v["shadow_tmdb_id"] = result.tmdb_id
                    config_m.save_library(library)
                    break 
        else:
            if result.media_type == "movie":
                scraper._write_movie_nfo_for_video(path, result)
            else:
                scraper.write_episode_nfo(path, result)
            base = os.path.splitext(os.path.basename(path))[0]
            proxy = getattr(config_m.config, 'http_proxy', '') or ''
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, base + "-poster.jpg", proxy=proxy)
            if result.backdrop_url:
                scraper.download_poster(folder, result.backdrop_url, base + "-fanart.jpg", proxy=proxy)
    
    return {"status": "ok", "data": result.dict()}

@router.get("/scrape/read")
def read_scrape_data(path: str, no_fallback: bool = False):
    """读取文件夹或视频的已有刮削数据（NFO）
    no_fallback=True 时不 fallback 到子文件的 NFO（用于 tv/season 文件夹）"""
    if not os.path.exists(path):
        return {"status": "not_found", "data": None}
    
    if os.path.isdir(path):
        data = scraper.read_nfo(path, no_fallback=no_fallback)
        # 文件夹级 NFO 不存在且允许 fallback：尝试文件夹内视频同名 NFO
        if not data and not no_fallback:
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            try:
                for f in os.listdir(path):
                    if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in video_exts:
                        vdata = scraper.read_video_nfo(os.path.join(path, f))
                        if vdata:
                            data = vdata
                            break
            except OSError:
                pass
    else:
        # 先读视频同名 NFO，没有则 fallback 到文件夹级 NFO
        data = scraper.read_video_nfo(path)
        if not data:
            folder = os.path.dirname(path)
            data = scraper.read_nfo(folder)
    
    if data:
        return {"status": "ok", "data": data}
    return {"status": "not_found", "data": None}

@router.get("/scrape/poster")
def get_local_poster(path: str, cover: bool = False):
    """返回本地海报文件或回跳到在线 TMDB 海报"""
    from fastapi.responses import Response, RedirectResponse
    from fastapi import HTTPException
    import os
    import re

    def _poster_response(file_path: str):
        with open(file_path, "rb") as f:
            content = f.read()
        ext = os.path.splitext(file_path)[1].lower()
        mt = "image/png" if ext == ".png" else "image/jpeg"
        return Response(content=content, media_type=mt,
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # 1. 聚合容器模式
    if cover:
        if os.path.isdir(path):
            for name in ["cover.jpg", "cover.png"]:
                p = os.path.join(path, name)
                if os.path.exists(p):
                    return _poster_response(p)
        raise HTTPException(status_code=404, detail="No cover found")

    # 2. 物理路径查找
    if os.path.isdir(path):
        # 2a. 标准文件夹级海报
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
            p = os.path.join(path, name)
            if os.path.exists(p):
                return _poster_response(p)
        
        # 2b. 季文件夹：查找 seasonXX-poster.jpg，或 fallback 到父目录
        folder_name = os.path.basename(path)
        season_match = re.search(r'(?:S(\d+)|第(\d+)季|Season\s*(\d+))', folder_name, re.I)
        if season_match:
            sn = season_match.group(1) or season_match.group(2) or season_match.group(3)
            for fmt in [f"season{sn.zfill(2)}-poster.jpg", f"season{sn}-poster.jpg"]:
                p = os.path.join(path, fmt)
                if os.path.exists(p):
                    return _poster_response(p)
            # 季文件夹没有自己的封面：fallback 到父目录的 poster
            parent = os.path.dirname(path)
            if parent and os.path.isdir(parent):
                for name in ["poster.jpg", "poster.png"]:
                    p = os.path.join(parent, name)
                    if os.path.exists(p):
                        return _poster_response(p)
        
        # 2c. 非季文件夹：找 *-poster.jpg（视频同名封面）
        try:
            for f in os.listdir(path):
                fl = f.lower()
                if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                    return _poster_response(os.path.join(path, f))
        except OSError:
            pass
    else:
        # 单文件模式：寻找同名海报
        base = os.path.splitext(path)[0]
        for ext in ["-poster.jpg", "-poster.png", "-thumb.jpg", ".jpg", ".png"]:
            p = base + ext
            if os.path.exists(p):
                return _poster_response(p)
        
        # 模糊回退 1：寻找文件夹内的标准海报
        folder = os.path.dirname(path)
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                return _poster_response(p)
        
        # 模糊回退 2：高精度关键词匹配（处理重命名及大杂烩目录）
        try:
            items = os.listdir(folder)
            v_name = os.path.splitext(os.path.basename(path))[0].lower()
            keywords = [w for w in re.split(r'[^a-zA-Z0-9\u4e00-\u9fff]', v_name) if len(w) >= 2]
            
            if not keywords:
                # 兜底：如果目录下只有一个视频，直接认领
                video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".ts", ".m4v"}
                vids = [f for f in items if os.path.splitext(f)[1].lower() in video_exts]
                if len(vids) == 1:
                    for f in items:
                        if f.lower().endswith(("-poster.jpg", "-poster.png", "poster.jpg", "poster.png")):
                            return _poster_response(os.path.join(folder, f))
            else:
                best_match = None
                max_score = 0
                for f in items:
                    fl = f.lower()
                    if fl.endswith(("-poster.jpg", "-poster.png", "-thumb.jpg", "poster.jpg", "poster.png")):
                        score = sum(1 for k in keywords if k in fl)
                        if score > max_score:
                            max_score = score
                            best_match = f
                
                # 匹配门槛
                if best_match and (max_score >= 2 or max_score >= len(keywords) * 0.5):
                    return _poster_response(os.path.join(folder, best_match))
                
        except OSError:
            pass

    raise HTTPException(status_code=404, detail="No poster found")

@router.post("/scrape/execute")
def execute_scrape(path: str, force: bool = True):
    """一键刮削 — 递归刮削指定路径及其所有子文件夹/子文件"""
    # 检查禁止刮削列表
    no_scrape = config_m.load_no_scrape()
    if path in no_scrape:
        return {"self": {"status": "no_scrape", "data": None}}
    
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    
    if os.path.isdir(path):
        category_hint = _get_category_from_path(path)
        # 判断 folder_type
        ft = organizer.classify_folder(path, category_hint=category_hint).get("type", "")
        
        # tv 类型扁平目录：先强制季化再刮削
        if category_hint == "tv" and ft == "tv":
            reorg = organizer.reorganize_seasons(path, client, dry_run=False, category_hint=category_hint)
            if reorg.get("ops"):
                _sync_library_paths(reorg["ops"])
        
        # 递归刮削（max_depth=10 确保深层嵌套也能覆盖）
        result = scraper.scrape_folder(path, client, force=force, folder_type=ft, max_depth=10)
        # 刮削成功后：用刮削结果的 title 更新子视频的 clean_name
        _update_clean_names_after_scrape(path, result)
        return result
    elif os.path.isfile(path):
        # 单视频文件：用文件夹路径调 scrape_folder（写文件夹级 NFO + poster）
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            if len(vids) <= 1 and len(subs) == 0:
                result = scraper.scrape_folder(folder, client, force=force)
                _update_clean_names_after_scrape(folder, result)
                return result
        except OSError:
            pass
        return scraper.scrape_video(path, client, force=force)
    else:
        raise HTTPException(status_code=404, detail="Path not found")

@router.post("/scrape/batch")
def batch_scrape_api(paths: List[str]):
    """批量刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return scraper.batch_scrape(paths, client)


@router.post("/scrape/upload-poster")
async def upload_poster(path: str, file: UploadFile = File(...), cover: bool = False):
    """手动上传海报到指定文件夹。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    ext = os.path.splitext(file.filename or "poster.jpg")[1] or ".jpg"
    # 视频文件：写同名 poster
    if not os.path.isdir(path) and os.path.isfile(path):
        base = os.path.splitext(path)[0]
        target = base + f"-poster{ext}"
    else:
        filename = f"cover{ext}" if cover else f"poster{ext}"
        target = os.path.join(folder, filename)
    content = await file.read()
    with open(target, "wb") as f:
        f.write(content)
    return {"status": "ok", "path": target}

@router.post("/scrape/poster-url")
def set_poster_from_url(path: str, url: str, cover: bool = False):
    """通过 URL 拉取海报保存到本地。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    try:
        resp = requests.get(url, stream=True, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        
        if os.path.isdir(path):
            filename = f"cover{ext}" if cover else f"poster{ext}"
            target = os.path.join(path, filename)
        elif os.path.isfile(path):
            base = os.path.splitext(path)[0]
            target = base + f"-poster{ext}"
        else:
            raise HTTPException(status_code=404, detail="Path not found")
        
        with open(target, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return {"status": "ok", "path": target}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/delete-poster")
def delete_poster(path: str):
    """删除本地海报 — 模拟 get_local_poster 的查找逻辑，找到实际显示的封面并删除"""
    deleted = []
    errors = []
    
    target_dir = path if os.path.isdir(path) else os.path.dirname(path)
    
    def _try_delete(filepath: str):
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                deleted.append(filepath)
                return True
            except Exception as e:
                errors.append(f"{filepath}: {e}")
        return False
    
    if os.path.isdir(target_dir):
        folder_name = os.path.basename(target_dir)
        
        # 1. 当前目录标准封面
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg", "folder.png", "cover.png"]:
            _try_delete(os.path.join(target_dir, name))
        
        # 2. 当前目录 *-poster.jpg/png
        try:
            for f in os.listdir(target_dir):
                fl = f.lower()
                if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                    _try_delete(os.path.join(target_dir, f))
        except OSError:
            pass
        
        # 3. 如果当前目录没删到任何封面，检查父目录（和 get_local_poster 的 fallback 一致）
        if not deleted:
            parent = os.path.dirname(target_dir)
            if parent and os.path.isdir(parent):
                for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
                    _try_delete(os.path.join(parent, name))
                try:
                    for f in os.listdir(parent):
                        fl = f.lower()
                        if fl.endswith('-poster.jpg') or fl.endswith('-poster.png'):
                            _try_delete(os.path.join(parent, f))
                except OSError:
                    pass
    
    # 文件路径：删同名封面
    if not os.path.isdir(path):
        base = os.path.splitext(path)[0]
        for suffix in ["-poster.jpg", "-poster.png", "-thumb.jpg", ".jpg"]:
            _try_delete(base + suffix)
    
    # 删 TMDB 缓存
    folder_name = os.path.basename(target_dir)
    safe_name = "".join(x for x in folder_name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(os.getcwd(), "posters", f"{safe_name}.jpg")
    _try_delete(cache_path)
    
    print(f"[DeletePoster] path={path} deleted={len(deleted)} errors={errors}")
    return {"status": "ok", "deleted": deleted, "errors": errors}

@router.post("/scrape/delete-scrape")
def delete_scrape(path: str, recursive: bool = False):
    """删除刮削数据（NFO + 封面）
    recursive=False（默认）：只删文件夹级别的刮削（movie.nfo/tvshow.nfo/poster.jpg等）
    recursive=True：同时删除视频同名的刮削文件
    """
    deleted = []
    print(f"[DeleteScrape] path={path} isdir={os.path.isdir(path)} recursive={recursive}")
    if os.path.isdir(path):
        # 文件夹级别刮削：删除标准文件
        for name in ["movie.nfo", "tvshow.nfo", "season.nfo", "poster.jpg", "poster.png",
                      "fanart.jpg", "folder.jpg", "cover.jpg", "folder.png", "cover.png", ".no-poster"]:
            p = os.path.join(path, name)
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
        # 始终删除 *-poster.jpg 等视频同名刮削文件（单视频文件夹里这些也是刮削产物）
        try:
            for f in os.listdir(path):
                fl = f.lower()
                if (fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or 
                    fl.endswith('-thumb.jpg') or fl.endswith('-fanart.jpg') or
                    fl.endswith('-clearlogo.png')):
                    p = os.path.join(path, f)
                    os.remove(p)
                    deleted.append(p)
        except OSError:
            pass
        # recursive 模式：也删视频同名 NFO 文件
        if recursive:
            try:
                for f in os.listdir(path):
                    fl = f.lower()
                    if fl.endswith('.nfo') and fl not in ('movie.nfo', 'tvshow.nfo', 'season.nfo'):
                        p = os.path.join(path, f)
                        os.remove(p)
                        deleted.append(p)
            except OSError:
                pass
    elif os.path.isfile(path):
        base = os.path.splitext(path)[0]
        for suffix in [".nfo", "-poster.jpg", "-poster.png", "-fanart.jpg", "-clearlogo.png", "-thumb.jpg"]:
            p = base + suffix
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
        # 单视频文件夹：同时删除文件夹级刮削（movie.nfo/poster.jpg 等）
        folder = os.path.dirname(path)
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
        try:
            items = os.listdir(folder)
            vids = [f for f in items if os.path.isfile(os.path.join(folder, f)) and os.path.splitext(f)[1].lower() in video_exts]
            subs = [f for f in items if os.path.isdir(os.path.join(folder, f)) and not f.startswith('.')]
            if len(vids) <= 1 and len(subs) == 0:
                for name in ["movie.nfo", "tvshow.nfo", "season.nfo", "poster.jpg", "poster.png",
                              "fanart.jpg", "folder.jpg", "cover.jpg", "folder.png", "cover.png", ".no-poster"]:
                    p = os.path.join(folder, name)
                    if os.path.exists(p):
                        os.remove(p)
                        deleted.append(p)
        except OSError:
            pass
    # 也清 TMDB 缓存
    name = os.path.basename(os.path.splitext(path)[0] if os.path.isfile(path) else path)
    safe_name = "".join(x for x in name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(os.getcwd(), "posters", f"{safe_name}.jpg")
    if os.path.exists(cache_path):
        os.remove(cache_path)
        deleted.append(cache_path)
    return {"status": "ok", "deleted": deleted}


# ── 整理 API ──

import organizer
import analyzer

@router.get("/media/info")
def get_media_info(title: str, year: str = "", type: str = "movie", subtitle: str = ""):
    """通过 TMDB 搜索获取影片详细信息。搜索策略：中文标题 → subtitle（外文名）→ 豆瓣搜索获取外文名重试"""
    clients = get_clients()
    tmdb = clients["tmdb"]

    def _search(query: str):
        if type == "tv":
            return tmdb.search_tv(query)
        return tmdb.search_movie(query)

    def _search_nolang(query: str):
        """不带语言限制搜索，覆盖更多翻译版本"""
        try:
            if type == "tv":
                return tmdb._get("/search/tv", {"query": query, "language": "en-US"}).get("results", [])[:10]
            return tmdb._get("/search/movie", {"query": query, "language": "en-US"}).get("results", [])[:10]
        except:
            return []

    def _pick_best(results: list, yr: str):
        if not results:
            return None
        best = results[0]
        if yr:
            for r in results:
                r_year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
                if r_year == yr:
                    best = r
                    break
        return best

    try:
        # 1. 用中文标题搜
        best = _pick_best(_search(title), year)

        # 2. 没找到且有 subtitle（外文名），用 subtitle 搜
        if not best and subtitle and subtitle != title:
            best = _pick_best(_search(subtitle), year)

        # 3. 还没找到，用豆瓣搜索接口获取外文名重试
        if not best:
            douban_results = douban_client.search(title)
            for dr in douban_results:
                alt_name = dr.get("subtitle", "")
                if alt_name and alt_name != title and alt_name != subtitle:
                    best = _pick_best(_search(alt_name), year)
                    if best:
                        break
                    # 外文名也用英文搜索试试
                    best = _pick_best(_search_nolang(alt_name), year)
                    if best:
                        break

        # 4. 还没找到，用英文搜索中文标题（TMDB 有时只有英文条目）
        if not best:
            best = _pick_best(_search_nolang(title), year)

        if not best:
            return {"found": False}

        tmdb_id = best.get("id", 0)
        if type == "tv":
            detail = tmdb.get_tv_detail(tmdb_id)
        else:
            detail = tmdb.get_movie_detail(tmdb_id)
        return {
            "found": True,
            "tmdb_id": detail.tmdb_id,
            "title": detail.title,
            "original_title": detail.original_title,
            "year": detail.year,
            "poster_url": detail.poster_url,
            "backdrop_url": detail.backdrop_url,
            "overview": detail.overview,
            "rating": detail.rating,
            "genres": detail.genres,
            "director": detail.director,
            "cast": detail.cast[:6],
            "runtime": detail.runtime,
            "imdb_id": detail.imdb_id,
            "total_seasons": detail.total_seasons,
            "episode_count": detail.episode_count,
            "status": detail.status,
            "countries": detail.countries,
        }
    except Exception as e:
        print(f"[MediaInfo] error: {e}")
        return {"found": False}

class AddMediaRequest(BaseModel):
    title: str
    original_title: str = ""
    year: str = ""
    douban_id: str = ""
    rating: float = 0
    overview: str = ""
    genres: List[str] = []
    director: str = ""
    cast: List[str] = []
    poster_url: str = ""
    save_path: str

