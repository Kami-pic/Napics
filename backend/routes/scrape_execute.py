"""
路由模块：scrape_execute — 刮削执行（一键刮削/批量刮削/删除刮削）
从 routes/scrape.py 拆分
"""
import os
import logging
from typing import List

from fastapi import APIRouter, HTTPException

from shared import (
    config_m,
    _get_category_from_path, _sync_library_paths, _update_clean_names_after_scrape,
)
import tmdb_client, scraper, organizer
from metadata_provider_factory import get_metadata_provider_map
from provider_models import MetadataSearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/scrape/execute")
def execute_scrape(path: str, force: bool = True):
    """一键刮削 — 递归刮削指定路径及其所有子文件夹/子文件"""
    # 检查禁止刮削列表
    no_scrape = config_m.load_no_scrape()
    if path in no_scrape:
        return {"self": {"status": "no_scrape", "data": None}}

    conf = config_m.config
    default_source = conf.default_scrape_source or "tmdb"

    # 豆瓣源：用豆瓣搜索+详情刮削
    if default_source == "douban":
        return _execute_scrape_douban(path, force)

    # TMDB 源（默认）
    api_key = conf.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(conf, 'http_proxy', '') or '')

    if os.path.isdir(path):
        category_hint = _get_category_from_path(path)
        ft = organizer.classify_folder(path, category_hint=category_hint).get("type", "")

        # tv 类型扁平目录：先强制季化再刮削
        if category_hint == "tv" and ft == "tv":
            reorg = organizer.reorganize_seasons(path, client, dry_run=False, category_hint=category_hint)
            if reorg.get("ops"):
                _sync_library_paths(reorg["ops"])

        # 递归刮削
        result = scraper.scrape_folder(path, client, force=force, folder_type=ft, max_depth=10)
        _update_clean_names_after_scrape(path, result)
        return result
    elif os.path.isfile(path):
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


def _execute_scrape_douban(path: str, force: bool = True):
    """豆瓣源刮削：搜索 → 取第一个候选 → 拉详情 → 写 NFO"""
    from tmdb_client import ScrapeResult, parse_filename
    from clean_name_system import strip_noise, split_names

    if os.path.isdir(path):
        folder_name = os.path.basename(path)
        cleaned = strip_noise(folder_name + ".tmp")
        names = split_names(cleaned)
        search_name = names.get("cn") or names.get("en") or folder_name
    else:
        file_name = os.path.basename(path)
        parsed = parse_filename(file_name)
        search_name = parsed.get("clean_name") or file_name

    provider = get_metadata_provider_map().get("douban")
    candidates = provider.search_metadata(MetadataSearchRequest(query=search_name, limit=5)) if provider else []
    if not candidates:
        return {"self": {"status": "not_found", "data": None}}

    best = candidates[0]
    douban_id = best.external_id
    if not douban_id:
        return {"self": {"status": "not_found", "data": None}}

    v2_detail = _douban_metadata_detail_to_legacy(provider.get_detail(str(douban_id), "tv") if provider else None)
    detected_type = "tv"
    if not v2_detail or not v2_detail.get("overview"):
        v2_detail = _douban_metadata_detail_to_legacy(provider.get_detail(str(douban_id), "movie") if provider else None)
        detected_type = "movie"

    if not v2_detail or not v2_detail.get("title"):
        return {"self": {"status": "not_found", "data": None}}

    result = ScrapeResult(
        tmdb_id=int(douban_id),
        media_type=detected_type,
        title=v2_detail.get("title", ""),
        original_title=v2_detail.get("original_title", ""),
        year=v2_detail.get("year", ""),
        overview=v2_detail.get("overview", ""),
        rating=v2_detail.get("rating", 0),
        genres=v2_detail.get("genres", []),
        director=v2_detail.get("directors", [""])[0] if v2_detail.get("directors") else "",
        cast=v2_detail.get("actors", []),
        runtime=v2_detail.get("runtime", 0),
        poster_url=v2_detail.get("poster_url", ""),
    )

    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                try:
                    os.remove(old_p)
                except OSError:
                    pass
        if result.media_type == "tv":
            scraper.write_tvshow_nfo(path, result)
        else:
            scraper.write_movie_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url)
    elif os.path.isfile(path):
        scraper._write_movie_nfo_for_video(path, result)
        folder = os.path.dirname(path)
        if result.poster_url:
            base = os.path.splitext(os.path.basename(path))[0]
            scraper.download_poster(folder, result.poster_url, base + "-poster.jpg")

    _update_clean_names_after_scrape(path, {"self": {"status": "ok", "data": result.dict()}})
    return {"self": {"status": "ok", "data": result.dict(), "confidence": {"level": "medium", "reason": "豆瓣自动匹配"}}}


def _douban_metadata_detail_to_legacy(detail):
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


@router.post("/scrape/batch")
def batch_scrape_api(paths: List[str]):
    """批量刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    client = tmdb_client.TMDBClient(api_key, proxy=getattr(config_m.config, 'http_proxy', '') or '')
    return scraper.batch_scrape(paths, client)


@router.post("/scrape/delete-scrape")
def delete_scrape(path: str, recursive: bool = False):
    """删除刮削数据（NFO + 封面）"""
    deleted = []
    logger.info(f"[DeleteScrape] path={path} isdir={os.path.isdir(path)} recursive={recursive}")
    if os.path.isdir(path):
        for name in ["movie.nfo", "tvshow.nfo", "season.nfo", "poster.jpg", "poster.png",
                      "fanart.jpg", "folder.jpg", "cover.jpg", "folder.png", "cover.png", ".no-poster"]:
            p = os.path.join(path, name)
            if os.path.exists(p):
                os.remove(p)
                deleted.append(p)
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
