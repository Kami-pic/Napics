"""
路由模块：scrape — 影子名、索引器优先级、刮削（TMDB 选择/执行/读取/删除）
"""
import os
import logging
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import (
    config_m, shadow_m, indexer_m,
    _get_category_from_path, _sync_library_paths, _update_clean_names_after_scrape,
)
import tmdb_client, scraper, organizer
from metadata_provider_factory import get_metadata_provider_map
from provider_models import MetadataSearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


class ShadowNameRequest(BaseModel):
    path: str
    shadow_name: str
    source: str = "manual"


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
    """获取索引器优先级列表，每次从 Prowlarr 同步最新状态（含连接状态和优先级）"""
    from indexer_priority_manager import IndexerConfig
    indexer_m.load()
    
    # 从 Prowlarr 拉取索引器列表（含状态）
    prowlarr_indexers = []
    prowlarr_status = {}  # {name: {"status": "ok"|"error"|"unknown", "error": ""}}
    try:
        prowlarr_url = config_m.config.prowlarr_url.rstrip("/")
        prowlarr_key = config_m.config.prowlarr_api_key
        if prowlarr_url and prowlarr_key:
            import requests
            resp = requests.get(f"{prowlarr_url}/api/v1/indexer",
                                params={"apikey": prowlarr_key}, timeout=5,
                                proxies={"http": None, "https": None})
            resp.raise_for_status()
            prowlarr_indexers = resp.json()
            # 获取索引器状态（Prowlarr /api/v1/indexerstatus）
            try:
                status_resp = requests.get(f"{prowlarr_url}/api/v1/indexerstatus",
                                           params={"apikey": prowlarr_key}, timeout=5,
                                           proxies={"http": None, "https": None})
                if status_resp.status_code == 200:
                    for s in status_resp.json():
                        iid = s.get("indexerId", 0)
                        prowlarr_status[iid] = {
                            "disabled_till": s.get("disabledTill", ""),
                            "error": s.get("lastRssSyncError", "") or s.get("lastSearchError", ""),
                        }
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[Indexers] Failed to fetch from Prowlarr: {e}")
    
    # 合并 Prowlarr 数据和本地配置
    local_map = {idx.name: idx for idx in indexer_m.indexers}
    result = []
    
    if prowlarr_indexers:
        for idx in prowlarr_indexers:
            name = idx.get("name", "")
            iid = idx.get("id", 0)
            prowlarr_priority = idx.get("priority", 25)
            enabled = idx.get("enable", True)
            
            # 本地有配置则合并，否则用 Prowlarr 默认值
            local = local_map.get(name)
            
            # 连接状态判断
            status_info = prowlarr_status.get(iid, {})
            if not enabled:
                conn_status = "disabled"
            elif status_info.get("disabled_till"):
                conn_status = "error"
            elif status_info.get("error"):
                conn_status = "warning"
            else:
                conn_status = "ok"
            
            # 根据名字猜测类型偏好
            types = local.preferred_types if local else []
            if not types:
                name_lower = name.lower()
                if "nyaa" in name_lower:
                    types = ["anime"]
                elif "yts" in name_lower:
                    types = ["movie"]
            
            result.append({
                "indexer_id": iid,
                "name": name,
                "priority": local.priority if local else prowlarr_priority,
                "prowlarr_priority": prowlarr_priority,
                "enabled": local.enabled if local else enabled,
                "preferred_types": types,
                "supports_chinese": local.supports_chinese if local else ("chinese" in name.lower() or "dmhy" in name.lower()),
                "status": conn_status,
                "status_error": status_info.get("error", ""),
            })
        
        # 如果本地没有配置，自动保存
        if not indexer_m.indexers:
            configs = [
                IndexerConfig(
                    indexer_id=r["indexer_id"], name=r["name"],
                    priority=r["priority"], enabled=r["enabled"],
                    preferred_types=r["preferred_types"],
                    supports_chinese=r["supports_chinese"],
                )
                for r in result
            ]
            indexer_m.save(configs)
    else:
        # Prowlarr 不可达，返回本地配置
        for idx in indexer_m.indexers:
            result.append({
                "indexer_id": idx.indexer_id,
                "name": idx.name,
                "priority": idx.priority,
                "prowlarr_priority": 0,
                "enabled": idx.enabled,
                "preferred_types": idx.preferred_types,
                "supports_chinese": idx.supports_chinese,
                "status": "unknown",
                "status_error": "Prowlarr 不可达",
            })
    
    return result

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
            logger.error(f"[Scrape] Enhanced scrape failed, fallback: {e}")
    
    # 普通刮削
    result = client.scrape_by_filename(name)
    return {"status": "ok" if result.tmdb_id else "not_found", "data": result.dict()}

def _write_scrape_result(path: str, result):
    """将刮削结果写入 NFO + 海报，供 scrape_select / douban_select / bangumi_select 共用。"""
    proxy = getattr(config_m.config, 'http_proxy', '') or ''

    if os.path.isdir(path):
        for old_nfo in ["movie.nfo", "tvshow.nfo", "season.nfo"]:
            old_p = os.path.join(path, old_nfo)
            if os.path.exists(old_p):
                os.remove(old_p)
        if result.media_type == "movie":
            scraper.write_movie_nfo(path, result)
        else:
            scraper.write_tvshow_nfo(path, result)
        if result.poster_url:
            scraper.download_poster(path, result.poster_url, proxy=proxy)
        if getattr(result, 'backdrop_url', None):
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
                old_vnfo = os.path.splitext(vp)[0] + ".nfo"
                if os.path.exists(old_vnfo):
                    os.remove(old_vnfo)
                if result.media_type == "movie":
                    scraper._write_movie_nfo_for_video(vp, result)
                library = config_m.load_library()
                for v in library:
                    if v.get("file_path") == vp:
                        en = getattr(result, 'english_title', '') or ""
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
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, proxy=proxy)
        else:
            if result.media_type == "movie":
                scraper._write_movie_nfo_for_video(path, result)
            else:
                scraper.write_episode_nfo(path, result)
            base = os.path.splitext(os.path.basename(path))[0]
            if result.poster_url:
                scraper.download_poster(folder, result.poster_url, base + "-poster.jpg", proxy=proxy)
            if getattr(result, 'backdrop_url', None):
                scraper.download_poster(folder, result.backdrop_url, base + "-fanart.jpg", proxy=proxy)


@router.post("/scrape/select")
def scrape_select(path: str, tmdb_id: int, media_type: str):
    """用户选择候选后，用指定 TMDB ID 执行刮削"""
    api_key = config_m.config.tmdb_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="TMDB API Key not configured")
    provider = get_metadata_provider_map().get("tmdb")

    if media_type == "movie":
        detail = provider.get_detail(str(tmdb_id), "movie") if provider else None
    elif media_type in ("tv", "tvshow"):
        detail = provider.get_detail(str(tmdb_id), "tv") if provider else None
    else:
        raise HTTPException(status_code=400, detail="Invalid media_type")

    result = _metadata_detail_to_scrape_result(detail)
    if not result.tmdb_id:
        raise HTTPException(status_code=404, detail="TMDB detail not found")
    
    # 写入 NFO + 海报（先清理旧的标准 NFO 避免冲突）
    try:
        _write_scrape_result(path, result)
    except Exception as e:
        logger.error(f"[scrape_select] 写入失败: path={path}, error={e}")
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")
    
    return {"status": "ok", "data": result.dict()}


def _metadata_detail_to_scrape_result(detail):
    if not detail:
        return tmdb_client.ScrapeResult()
    poster_url = ""
    backdrop_url = ""
    for artwork in detail.artwork:
        if artwork.kind == "poster" and not poster_url:
            poster_url = artwork.url
        elif artwork.kind == "backdrop" and not backdrop_url:
            backdrop_url = artwork.url
    return tmdb_client.ScrapeResult(
        tmdb_id=int(detail.external_id) if str(detail.external_id).isdigit() else 0,
        media_type=detail.media_type,
        title=detail.title,
        original_title=detail.original_title,
        english_title=detail.aliases.en,
        year=str(detail.year or ""),
        poster_url=poster_url or None,
        backdrop_url=backdrop_url or None,
        overview=detail.overview,
        rating=detail.rating or 0,
        runtime=detail.runtime or 0,
    )

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
        # 单点自愈：读到 NFO 数据时，检查媒体库中对应文件夹/视频是否缺少 clean_name，缺则补全
        try:
            title = data.get("title", "")
            if title:
                from clean_name_system import clean_from_scrape, safe_update_clean_name
                library = config_m.load_library()
                changed = False
                norm_path = os.path.normpath(path)
                video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
                for v in library:
                    fp = v.get("file_path", "")
                    fp_dir = os.path.normpath(os.path.dirname(fp))
                    if fp == path or fp_dir == norm_path or fp_dir.startswith(norm_path + os.sep):
                        if os.path.splitext(fp)[1].lower() not in video_exts:
                            continue
                        if not v.get("clean_name_cn") and not v.get("clean_name_en"):
                            result = clean_from_scrape(
                                title=title,
                                original_title=data.get("original_title", ""),
                                english_title=data.get("english_title", ""),
                                year=data.get("year", ""),
                                filename=v.get("file_name", ""),
                                source="nfo",
                            )
                            if safe_update_clean_name(v, result):
                                changed = True
                if changed:
                    config_m.save_library(library)
        except Exception:
            pass
        return {"status": "ok", "data": data}
    return {"status": "not_found", "data": None}


