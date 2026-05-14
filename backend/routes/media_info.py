"""
路由模块：media_info — 候选搜索 + 详情多源
从 routes/scrape.py 拆分而来
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
    _tmdb_client, get_clients,
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
    from tmdb_client import ScrapeResult
    
    # 自动判断 media_type：优先用前端传入，否则先尝试 tv 再 movie
    detected_type = media_type or ""
    
    # 优先 API v2 拉取详情
    result = None
    v2_detail = None
    
    if detected_type == "tv" or not detected_type:
        # 先尝试 tv
        v2_detail = douban_api_v2.get_detail(douban_id, media_type="tv")
        if v2_detail and v2_detail.get("title"):
            detected_type = "tv"
    
    if not v2_detail or not v2_detail.get("title"):
        # 再尝试 movie
        v2_detail = douban_api_v2.get_detail(douban_id, media_type="movie")
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

@router.get("/scrape/bangumi")
def scrape_bangumi_candidates(name: str):
    """搜索 Bangumi 返回候选结果"""
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


@router.get("/media/info")
def get_media_info(title: str, year: str = "", type: str = "movie", subtitle: str = "", source: str = "tmdb", id: str = ""):
    """获取影片详细信息。source 控制优先级，id 可直接指定数据源 ID 跳过搜索：
    - tmdb: TMDB → 豆瓣 v2（默认）
    - douban: 豆瓣 v2（优先用 id）→ TMDB
    - bangumi: Bangumi（优先用 id）→ 豆瓣 v2 → TMDB
    """
    logger.info(f"[MediaInfo] 请求: title={title}, year={year}, type={type}, source={source}, id={id}")

    def _writeback_enrich_cache(detail: dict):
        """如果详情有英文名，回写到 enrich_cache"""
        if not detail or not detail.get("found"):
            return
        # 优先用 english_title（真正的英文名），其次判断 original_title 是否为英文
        en = detail.get("english_title", "")
        if not en:
            orig = detail.get("original_title", "")
            if orig:
                from text_processing import detect_language
                if detect_language(orig) == "en":
                    en = orig
        tmdb_id = detail.get("tmdb_id", 0)
        tmdb_rating = 0
        ratings = detail.get("ratings") or {}
        tmdb_rating = ratings.get("tmdb", 0) or detail.get("rating", 0)
        if not en and not tmdb_id:
            return
        try:
            from routes.discover import enrich_cache_put
            cache_key = ""
            if id and source == "douban":
                cache_key = f"douban_{id}"
            elif tmdb_id:
                cache_key = f"tmdb_{tmdb_id}"
            else:
                cache_key = f"title_{title}_{year}"
            if cache_key:
                enrich_cache_put(cache_key, tmdb_id=tmdb_id, en_title=en, tmdb_rating=tmdb_rating)
        except Exception as e:
            logger.error(f"[MediaInfo] enrich_cache 回写失败: {e}")

    # ── Bangumi 优先路径 ──
    if source == "bangumi":
        bgm_id = int(id) if id and id.isdigit() else 0
        logger.info(f"[MediaInfo] Bangumi 路径: bgm_id={bgm_id}")
        bgm_detail = _try_bangumi_detail(title, subtitle, bgm_id=bgm_id)
        if bgm_detail:
            logger.info(f"[MediaInfo] Bangumi 命中: rating={bgm_detail.get('rating')}, poster={bgm_detail.get('poster_url', '')[:60]}")
            _enrich_ratings(bgm_detail, title, year, type, subtitle)
            _writeback_enrich_cache(bgm_detail)
            return bgm_detail
        logger.info("[MediaInfo] Bangumi 未命中，fallback 豆瓣")
        db_detail = _try_douban_detail(title, year, type)
        if db_detail:
            logger.info(f"[MediaInfo] 豆瓣 fallback 命中: source=douban")
            _enrich_ratings(db_detail, title, year, type, subtitle)
            _writeback_enrich_cache(db_detail)
            return db_detail
        logger.info("[MediaInfo] 豆瓣也未命中，fallback TMDB")
        result = _try_tmdb_detail(title, year, type, subtitle)
        if result and result.get("found"):
            _enrich_ratings(result, title, year, type, subtitle)
        _writeback_enrich_cache(result)
        return result

    # ── 豆瓣优先路径 ──
    if source == "douban":
        logger.info(f"[MediaInfo] 豆瓣路径: douban_id={id}")
        db_detail = _try_douban_detail(title, year, type, douban_id=id if id else "")
        if db_detail:
            logger.info(f"[MediaInfo] 豆瓣命中: poster={db_detail.get('poster_url', '')[:80]}, source={db_detail.get('source')}")
            _enrich_ratings(db_detail, title, year, type, subtitle)
            _writeback_enrich_cache(db_detail)
            return db_detail
        logger.info("[MediaInfo] 豆瓣未命中，fallback TMDB")
        result = _try_tmdb_detail(title, year, type, subtitle)
        if result and result.get("found"):
            _enrich_ratings(result, title, year, type, subtitle)
        _writeback_enrich_cache(result)
        return result

    # ── TMDB 优先路径（默认）──
    logger.info(f"[MediaInfo] TMDB 默认路径, id={id}")
    # 有 tmdb_id 直接拉详情，跳过搜索
    if id and id.isdigit():
        tmdb_detail = _try_tmdb_detail_by_id(int(id), type)
        if tmdb_detail and tmdb_detail.get("found"):
            _enrich_ratings(tmdb_detail, title, year, type, subtitle)
            _writeback_enrich_cache(tmdb_detail)
            return tmdb_detail
        logger.info(f"[MediaInfo] TMDB ID {id} 拉取失败，fallback 搜索")
    tmdb_detail = _try_tmdb_detail(title, year, type, subtitle)
    if tmdb_detail and tmdb_detail.get("found"):
        _enrich_ratings(tmdb_detail, title, year, type, subtitle)
        _writeback_enrich_cache(tmdb_detail)
        return tmdb_detail
    db_detail = _try_douban_detail(title, year, type)
    if db_detail:
        _enrich_ratings(db_detail, title, year, type, subtitle)
        _writeback_enrich_cache(db_detail)
        return db_detail
    return {"found": False}


def _enrich_ratings(detail: dict, title: str, year: str, type: str, subtitle: str = ""):
    """补充其他源的评分和 ID。豆瓣先跑（拿 original_title），然后 TMDB+Bangumi 并行。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    source = detail.get("source", "")
    ratings = {}
    external_ids = {}

    # 主源评分和 ID
    if source and detail.get("rating"):
        ratings[source] = detail["rating"]
    if detail.get("tmdb_id"):
        external_ids["tmdb_id"] = detail["tmdb_id"]
    if detail.get("imdb_id"):
        external_ids["imdb_id"] = detail["imdb_id"]

    orig_title = detail.get("original_title", "") or subtitle

    # 第一步：补充豆瓣（需要先拿 original_title 给 TMDB 用）
    if source != "douban":
        try:
            db = _try_douban_detail(title, year, type)
            if db:
                if db.get("rating"): ratings["douban"] = db["rating"]
                if not orig_title:
                    orig_title = db.get("original_title", "")
        except Exception:
            pass

    # 第二步：TMDB + Bangumi 并行
    def _fetch_tmdb():
        if source == "tmdb": return None
        try:
            return _try_tmdb_detail(title, year, type, orig_title)
        except Exception:
            return None

    def _fetch_bangumi():
        if source == "bangumi": return None
        try:
            return _try_bangumi_detail(title, subtitle)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {"tmdb": pool.submit(_fetch_tmdb), "bangumi": pool.submit(_fetch_bangumi)}
        for key, future in futures.items():
            try:
                result = future.result(timeout=10)
                if key == "tmdb" and result and result.get("found"):
                    if result.get("rating"): ratings["tmdb"] = result["rating"]
                    if result.get("tmdb_id"): external_ids["tmdb_id"] = result["tmdb_id"]
                    if result.get("imdb_id"): external_ids["imdb_id"] = result["imdb_id"]
                    # 补全英文名：优先用 english_title，其次判断 original_title 是否为英文
                    en = result.get("english_title", "")
                    if not en:
                        tmdb_orig = result.get("original_title", "")
                        if tmdb_orig and tmdb_orig != detail.get("title", ""):
                            import re as _re
                            if not _re.search(r'[\u3000-\u9fff\uac00-\ud7af]', tmdb_orig):
                                en = tmdb_orig
                    if en and en != detail.get("title", ""):
                        detail["english_title"] = en
                elif key == "bangumi" and result and result.get("rating"):
                    ratings["bangumi"] = result["rating"]
            except Exception:
                pass

    detail["ratings"] = ratings
    detail["external_ids"] = external_ids


def _try_douban_detail(title: str, year: str, type: str, douban_id: str = "") -> dict | None:
    """尝试从豆瓣 v2 获取详情。douban_id 非空时直接拉详情，否则搜索"""
    try:
        media_type = "tv" if type == "tv" else "movie"

        # 有 ID 直接拉详情
        if douban_id:
            logger.info(f"[MediaInfo._try_douban] 用 ID 直接拉: douban_id={douban_id}, media_type={media_type}")
            # 先用指定 media_type 拉，失败则尝试另一种（电影/剧集可能分类不准）
            detail = douban_api_v2.get_detail(douban_id, media_type=media_type)
            if not detail or not detail.get("title"):
                alt_type = "tv" if media_type == "movie" else "movie"
                logger.info(f"[MediaInfo._try_douban] {media_type} 404，尝试 {alt_type}")
                detail = douban_api_v2.get_detail(douban_id, media_type=alt_type)
            if detail and detail.get("title"):
                logger.info(f"[MediaInfo._try_douban] ID 拉取成功: title={detail.get('title')}")
                return _format_douban_detail(detail)
            # ID 拉取彻底失败（可能是合集/豆列），不 fallback 搜索（避免匹配错误）
            logger.error(f"[MediaInfo._try_douban] ID {douban_id} 拉取失败（可能是非影视条目），跳过")
            return None

        # 无 ID 时搜索匹配
        logger.info(f"[MediaInfo._try_douban] 搜索: title={title}")
        results = douban_api_v2.search(title, count=5)
        if not results:
            logger.info(f"[MediaInfo._try_douban] 搜索无结果")
            return None
        # 模糊匹配：找最佳候选（标题相似度 + 年份匹配）
        best = _pick_best_douban_result(results, title, year)
        if not best:
            logger.info(f"[MediaInfo._try_douban] 无匹配候选")
            return None
        did = best.get("douban_id")
        if not did:
            return None
        detail = douban_api_v2.get_detail(did, media_type=media_type)
        if not detail or not detail.get("title"):
            return None
        return _format_douban_detail(detail)
    except Exception as e:
        logger.error(f"[MediaInfo] 豆瓣详情失败: {e}")
        return None


def _pick_best_douban_result(results: list, query_title: str, year: str) -> dict | None:
    """从豆瓣搜索结果中选最佳匹配。

    策略：
    1. 精确匹配标题 + 年份 → 直接返回
    2. 模糊匹配：中文字符重叠率 >= 0.7 → 候选
    3. 候选中年份匹配的优先
    4. 无候选 → 返回 None（不强行匹配，避免错误）
    """
    import re
    query_cn = re.sub(r"[^\u4e00-\u9fff]", "", query_title)

    candidates = []
    for r in results:
        r_title = r.get("title", "")
        r_year = r.get("year", "")
        r_cn = re.sub(r"[^\u4e00-\u9fff]", "", r_title)

        # 精确匹配
        if r_title == query_title:
            if not year or r_year == year:
                return r
            candidates.insert(0, r)
            continue

        # 中文字符重叠率
        if query_cn and r_cn:
            common = sum(1 for c in query_cn if c in r_cn)
            overlap = common / max(len(query_cn), 1)
            if overlap >= 0.7:
                candidates.append(r)
        elif not query_cn:
            # 纯英文标题，用子串匹配
            if query_title.lower() in r_title.lower() or r_title.lower() in query_title.lower():
                candidates.append(r)

    if not candidates:
        return None

    # 年份匹配的优先
    if year:
        for c in candidates:
            if c.get("year") == year:
                return c
    return candidates[0]


def _format_douban_detail(detail: dict) -> dict:
    """格式化豆瓣详情为统一结构"""
    poster = detail.get("poster_url", "")
    # 豆瓣图片走代理（防盗链）
    if poster and "doubanio.com" in poster:
        poster = f"/proxy/image?url={requests.utils.quote(poster)}"
    return {
        "found": True,
        "tmdb_id": 0,
        "title": detail.get("title", ""),
        "original_title": detail.get("original_title", ""),
        "year": detail.get("year", ""),
        "poster_url": poster,
        "backdrop_url": "",
        "overview": detail.get("overview", ""),
        "rating": detail.get("rating", 0),
        "genres": detail.get("genres", []),
        "director": (detail.get("directors") or [""])[0],
        "cast": detail.get("actors", [])[:6],
        "runtime": detail.get("runtime", 0),
        "imdb_id": "",
        "total_seasons": detail.get("seasons_count", 0),
        "episode_count": detail.get("episode_count", 0),
        "status": "",
        "countries": detail.get("countries", []),
        "source": "douban",
    }


def _try_bangumi_detail(title: str, subtitle: str = "", bgm_id: int = 0) -> dict | None:
    """尝试从 Bangumi 获取详情。bgm_id > 0 时直接拉详情，否则搜索。
    如果 ID 拉到的标题和请求 title 差异太大，放弃 ID 走搜索。"""
    try:
        # 有 ID 直接拉详情，跳过搜索
        if bgm_id > 0:
            logger.info(f"[MediaInfo._try_bangumi] 用 ID 直接拉: bgm_id={bgm_id}")
            detail = bangumi_client.get_detail(bgm_id)
            if detail and detail.get("title"):
                # 标题校验：ID 拉到的标题和请求 title 至少有 2 个字重叠
                detail_title = detail.get("title", "")
                detail_orig = detail.get("original_title", "")
                import re as _re

                title_chars = set(_re.findall(r'[\u4e00-\u9fff]', title))
                detail_chars = set(_re.findall(r'[\u4e00-\u9fff]', detail_title))
                overlap = len(title_chars & detail_chars)
                title_in_orig = title.lower() in (detail_orig or "").lower() or (subtitle and subtitle.lower() in (detail_orig or "").lower())
                if overlap >= 2 or title_in_orig or not title_chars:
                    formatted = _format_bangumi_detail(detail)
                    logger.info(f"[MediaInfo._try_bangumi] ID 拉取成功: title={detail_title}, rating={detail.get('rating')}")
                    return formatted
                else:
                    logger.info(f"[MediaInfo._try_bangumi] ID 标题不匹配: 请求={title}, 返回={detail_title}，改走搜索")

        # 搜索匹配
        logger.info(f"[MediaInfo._try_bangumi] 搜索: title={title}")
        results = bangumi_client.search(title)
        if not results:
            return None
        best = results[0]
        for r in results:
            if r.get("type") == "动画" and (r.get("title") == title or r.get("original_title") == subtitle):
                best = r
                break
            if r.get("type") == "动画":
                best = r
                break
        bid = best.get("bgm_id")
        if not bid:
            return None
        detail = bangumi_client.get_detail(bid)
        if not detail:
            return None
        return _format_bangumi_detail(detail)
    except Exception as e:
        logger.error(f"[MediaInfo] Bangumi 详情失败: {e}")
        return None


def _format_bangumi_detail(detail: dict) -> dict:
    """格式化 Bangumi 详情为统一结构"""
    return {
        "found": True,
        "tmdb_id": 0,
        "title": detail.get("title", ""),
        "original_title": detail.get("original_title", ""),
        "year": detail.get("year", ""),
        "poster_url": detail.get("poster_url", ""),
        "backdrop_url": "",
        "overview": detail.get("overview", ""),
        "rating": detail.get("rating", 0),
        "genres": detail.get("genres", []),
        "director": detail.get("director", ""),
        "cast": detail.get("cast", [])[:6],
        "runtime": 0,
        "imdb_id": "",
        "total_seasons": 0,
        "episode_count": detail.get("total_episodes", 0),
        "status": "",
        "countries": [],
        "source": "bangumi",
    }


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



def _try_tmdb_detail_by_id(tmdb_id: int, type: str) -> dict:
    """用 tmdb_id 直接拉详情，跳过搜索。type 不准时自动尝试 movie↔tv"""
    try:
        provider = get_metadata_provider_map().get("tmdb")
        # 先用指定 type 拉
        detail = provider.get_detail(str(tmdb_id), "tv" if type == "tv" else "movie") if provider else None
        if not detail or not detail.external_id:
            # type 可能不准（如 trending mixed），尝试另一种
            alt_type = "tv" if type == "movie" else "movie"
            logger.info(f"[MediaInfo] TMDB ID {tmdb_id} {type} 失败，尝试 {alt_type}")
            detail = provider.get_detail(str(tmdb_id), alt_type) if provider else None
        if not detail or not detail.external_id:
            return {"found": False}
        return _format_tmdb_metadata_detail(detail)
    except Exception as e:
        logger.error(f"[MediaInfo] TMDB ID 直接拉取失败: {e}")
        return {"found": False}


def _format_tmdb_metadata_detail(detail) -> dict:
    extra = detail.extra if isinstance(detail.extra, dict) else {}
    poster_url = ""
    backdrop_url = ""
    for artwork in detail.artwork:
        if artwork.kind == "poster" and not poster_url:
            poster_url = artwork.url
        elif artwork.kind == "backdrop" and not backdrop_url:
            backdrop_url = artwork.url
    return {
        "found": True,
        "tmdb_id": int(detail.external_id) if str(detail.external_id).isdigit() else 0,
        "title": detail.title,
        "original_title": detail.original_title,
        "english_title": detail.aliases.en,
        "year": str(detail.year or ""),
        "poster_url": poster_url or extra.get("poster_url"),
        "backdrop_url": backdrop_url or extra.get("backdrop_url"),
        "overview": detail.overview,
        "rating": detail.rating or 0,
        "genres": extra.get("genres", []),
        "director": extra.get("director", ""),
        "cast": (extra.get("cast", []) or [])[:6],
        "runtime": detail.runtime or 0,
        "imdb_id": extra.get("imdb_id", ""),
        "total_seasons": extra.get("total_seasons", 0),
        "episode_count": extra.get("episode_count", 0),
        "status": extra.get("status", ""),
        "countries": extra.get("countries", []),
        "source": "tmdb",
    }


def _try_tmdb_detail(title: str, year: str, type: str, subtitle: str = "") -> dict:
    """尝试从 TMDB 获取详情，使用 tmdb_client.best_match 多维度评分匹配"""
    try:
        clients = get_clients()
        tmdb = clients["tmdb"]
        type_key = "name" if type == "tv" else "title"

        def _search(query):
            return tmdb.search_tv(query) if type == "tv" else tmdb.search_movie(query)

        def _search_nolang(query):
            try:
                ep = "/search/tv" if type == "tv" else "/search/movie"
                return tmdb._get(ep, {"query": query, "language": "en-US"}).get("results", [])[:10]
            except:
                return []

        def _pick_best(query, results, yr):
            """使用 tmdb_client.best_match 多维度评分（标题相似度+年份+热度，30 分阈值）"""
            return tmdb_client.best_match(query, results, year=yr, type_key=type_key)

        best = _pick_best(title, _search(title), year)
        if not best and subtitle and subtitle != title:
            best = _pick_best(subtitle, _search(subtitle), year)
        if not best:
            douban_results = douban_api_v2.search(title, count=5) or douban_client.search(title)
            for dr in douban_results:
                alt_name = dr.get("subtitle", "") or dr.get("original_title", "")
                if alt_name and alt_name != title and alt_name != subtitle:
                    best = _pick_best(alt_name, _search(alt_name), year)
                    if best:
                        break
                    best = _pick_best(alt_name, _search_nolang(alt_name), year)
                    if best:
                        break
        if not best:
            best = _pick_best(title, _search_nolang(title), year)
        if not best:
            return {"found": False}

        tmdb_id = best.get("id", 0)
        detail = tmdb.get_tv_detail(tmdb_id) if type == "tv" else tmdb.get_movie_detail(tmdb_id)
        return {
            "found": True,
            "tmdb_id": detail.tmdb_id,
            "title": detail.title,
            "original_title": detail.original_title,
            "english_title": detail.english_title,
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
            "source": "tmdb",
        }
    except Exception as e:
        logger.error(f"[MediaInfo] TMDB 详情失败: {e}")
        return {"found": False}
