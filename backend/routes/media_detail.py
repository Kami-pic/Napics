"""
路由模块：media_detail — 影片详情多源获取
从 routes/media_info.py 拆分 — get_media_info + 各源详情辅助函数
"""
import logging
import requests
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from shared import config_m
import tmdb_client, douban_client, bangumi_client
import douban_api_v2
from metadata_provider_factory import get_metadata_provider_map
from provider_models import MetadataSearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


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
            from discover_enrich import enrich_cache_put
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
    """补充其他源的评分和 ID。三源全部并行，总超时 4s，超时则跳过。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    source = detail.get("source", "")
    ratings = {}
    external_ids = {}

    if source and detail.get("rating"):
        ratings[source] = detail["rating"]
    if detail.get("tmdb_id"):
        external_ids["tmdb_id"] = detail["tmdb_id"]
    if detail.get("imdb_id"):
        external_ids["imdb_id"] = detail["imdb_id"]

    orig_title = detail.get("original_title", "") or subtitle

    def _fetch_douban():
        if source == "douban": return None
        try:
            return _try_douban_detail(title, year, type)
        except Exception:
            return None

    def _fetch_tmdb():
        if source == "tmdb": return None
        try:
            return _try_tmdb_detail(title, year, type, orig_title)
        except Exception:
            return None

    def _fetch_bangumi():
        if source == "bangumi": return None
        # Bangumi 通过代理延迟太大（7s+/次），评分补全不主动联网
        # 只有在已有 bgm_id 或主结果中带 bangumi 数据时才补
        return None

    pool = ThreadPoolExecutor(max_workers=3)
    futures = {
        "douban": pool.submit(_fetch_douban),
        "tmdb": pool.submit(_fetch_tmdb),
        "bangumi": pool.submit(_fetch_bangumi),
    }
    try:
        for future in as_completed(futures.values(), timeout=4):
            key = next(k for k, f in futures.items() if f is future)
            try:
                result = future.result(timeout=0)
                if key == "douban" and result:
                    if result.get("rating"): ratings["douban"] = result["rating"]
                    if not orig_title:
                        orig_title = result.get("original_title", "")
                elif key == "tmdb" and result and result.get("found"):
                    if result.get("rating"): ratings["tmdb"] = result["rating"]
                    if result.get("tmdb_id"): external_ids["tmdb_id"] = result["tmdb_id"]
                    if result.get("imdb_id"): external_ids["imdb_id"] = result["imdb_id"]
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
    except (TimeoutError, Exception):
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    detail["ratings"] = ratings
    detail["external_ids"] = external_ids


def _try_douban_detail(title: str, year: str, type: str, douban_id: str = "") -> dict | None:
    """尝试从豆瓣 v2 获取详情"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("douban"):
        return None
    try:
        media_type = "tv" if type == "tv" else "movie"

        if douban_id:
            logger.info(f"[MediaInfo._try_douban] 用 ID 直接拉: douban_id={douban_id}, media_type={media_type}")
            detail = douban_api_v2.get_detail(douban_id, media_type=media_type)
            if not detail or not detail.get("title"):
                alt_type = "tv" if media_type == "movie" else "movie"
                logger.info(f"[MediaInfo._try_douban] {media_type} 404，尝试 {alt_type}")
                detail = douban_api_v2.get_detail(douban_id, media_type=alt_type)
            if detail and detail.get("title"):
                logger.info(f"[MediaInfo._try_douban] ID 拉取成功: title={detail.get('title')}")
                return _format_douban_detail(detail)
            logger.error(f"[MediaInfo._try_douban] ID {douban_id} 拉取失败（可能是非影视条目），跳过")
            return None

        logger.info(f"[MediaInfo._try_douban] 搜索: title={title}")
        results = douban_api_v2.search(title, count=5)
        if not results:
            logger.info(f"[MediaInfo._try_douban] 搜索无结果")
            return None
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
    """从豆瓣搜索结果中选最佳匹配"""
    import re
    query_cn = re.sub(r"[^\u4e00-\u9fff]", "", query_title)

    candidates = []
    for r in results:
        r_title = r.get("title", "")
        r_year = r.get("year", "")
        r_cn = re.sub(r"[^\u4e00-\u9fff]", "", r_title)

        if r_title == query_title:
            if not year or r_year == year:
                return r
            candidates.insert(0, r)
            continue

        if query_cn and r_cn:
            common = sum(1 for c in query_cn if c in r_cn)
            overlap = common / max(len(query_cn), 1)
            if overlap >= 0.7:
                candidates.append(r)
        elif not query_cn:
            if query_title.lower() in r_title.lower() or r_title.lower() in query_title.lower():
                candidates.append(r)

    if not candidates:
        return None

    if year:
        for c in candidates:
            if c.get("year") == year:
                return c
    return candidates[0]


def _format_douban_detail(detail: dict) -> dict:
    """格式化豆瓣详情为统一结构"""
    poster = detail.get("poster_url", "")
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
    """尝试从 Bangumi 获取详情"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("bangumi"):
        return None
    try:
        if bgm_id > 0:
            logger.info(f"[MediaInfo._try_bangumi] 用 ID 直接拉: bgm_id={bgm_id}")
            detail = bangumi_client.get_detail(bgm_id)
            if detail and detail.get("title"):
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
    """用 tmdb_id 直接拉详情"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("tmdb"):
        return {"found": False}
    try:
        provider = get_metadata_provider_map().get("tmdb")
        detail = provider.get_detail(str(tmdb_id), "tv" if type == "tv" else "movie") if provider else None
        if not detail or not detail.external_id:
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
    """尝试从 TMDB 获取详情"""
    import plugin_guard

    if not plugin_guard.is_metadata_allowed("tmdb"):
        return {"found": False}
    try:
        provider = get_metadata_provider_map().get("tmdb")
        if not provider:
            return {"found": False}
        type_key = "name" if type == "tv" else "title"

        def _search(query):
            request = MetadataSearchRequest(query=query, mediaType=type, limit=20)
            return [_tmdb_candidate_to_best_match_item(candidate) for candidate in provider.search_metadata(request)]

        def _search_nolang(query):
            request = MetadataSearchRequest(query=query, mediaType=type, limit=10)
            return [_tmdb_candidate_to_best_match_item(candidate) for candidate in provider.search_metadata(request)]

        def _pick_best(query, results, yr):
            return tmdb_client.best_match(query, results, year=yr, type_key=type_key)

        best = _pick_best(title, _search(title), year)
        if not best and subtitle and subtitle != title:
            best = _pick_best(subtitle, _search(subtitle), year)
        if not best and plugin_guard.is_metadata_allowed("douban"):
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

        tmdb_id = best.get("id", 0) or best.get("tmdb_id", 0)
        detail = provider.get_detail(str(tmdb_id), "tv" if type == "tv" else "movie")
        return _format_tmdb_metadata_detail(detail) if detail else {"found": False}
    except Exception as e:
        logger.error(f"[MediaInfo] TMDB 详情失败: {e}")
        return {"found": False}


def _tmdb_candidate_to_best_match_item(candidate) -> dict:
    extra = candidate.extra if isinstance(candidate.extra, dict) else {}
    item = dict(extra)
    tmdb_id = int(candidate.external_id) if str(candidate.external_id).isdigit() else 0
    item.setdefault("id", tmdb_id)
    item.setdefault("tmdb_id", tmdb_id)
    item.setdefault("title", candidate.title)
    item.setdefault("name", candidate.title)
    item.setdefault("original_title", candidate.original_title)
    item.setdefault("original_name", candidate.original_title)
    if candidate.year:
        item.setdefault("release_date", f"{candidate.year}-01-01")
        item.setdefault("first_air_date", f"{candidate.year}-01-01")
    return item
