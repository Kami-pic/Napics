"""豆瓣 API v2 客户端 — 基于 App 签名鉴权，数据比网页版丰富得多。
参考 MoviePilot 的 apiv2.py 实现，精简为同步版本 + 文件缓存。
"""
import base64
import hashlib
import hmac
import json
import os
import time
import random
import requests
from datetime import datetime
from typing import Optional, Dict, List, Any
from urllib import parse


# ── 签名参数（豆瓣 App 内置，公开已知） ──
_API_SECRET_KEY = "bf7dddc7c9cfe6f7"
_API_KEY = "0dad551ec0f84ed02907ff5c42e8ec70"
_BASE_URL = "https://frodo.douban.com/api/v2"

# 随机 User-Agent 池（模拟豆瓣 App 请求）
_USER_AGENTS = [
    "api-client/1 com.douban.frodo/7.22.0.beta9(231) Android/23 product/Mate 40 vendor/HUAWEI model/Mate 40 brand/HUAWEI  rom/android  network/wifi  platform/AndroidPad",
    "api-client/1 com.douban.frodo/7.18.0(230) Android/22 product/MI 9 vendor/Xiaomi model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
    "api-client/1 com.douban.frodo/7.1.0(205) Android/29 product/perseus vendor/Xiaomi model/Mi MIX 3  rom/miui6  network/wifi  platform/mobile nd/1",
    "api-client/1 com.douban.frodo/7.3.0(207) Android/22 product/MI 9 vendor/Xiaomi model/MI 9 brand/Android  rom/miui6  network/wifi platform/mobile nd/1",
]

# ── URL 端点映射 ──
_URLS = {
    # 榜单/合集
    "movie_showing": "/subject_collection/movie_showing/items",
    "movie_hot_gaia": "/subject_collection/movie_hot_gaia/items",
    "movie_soon": "/subject_collection/movie_soon/items",
    "movie_top250": "/subject_collection/movie_top250/items",
    "tv_hot": "/subject_collection/tv_hot/items",
    "tv_animation": "/subject_collection/tv_animation/items",
    "tv_variety_show": "/subject_collection/tv_variety_show/items",
    "tv_chinese_best_weekly": "/subject_collection/tv_chinese_best_weekly/items",
    "tv_global_best_weekly": "/subject_collection/tv_global_best_weekly/items",
    # 探索
    "movie_recommend": "/movie/recommend",
    "tv_recommend": "/tv/recommend",
    # 搜索
    "search": "/search/weixin",
    # 详情
    "movie_detail": "/movie/",
    "tv_detail": "/tv/",
    # 推荐（相似影片）
    "movie_recommendations": "/movie/%s/recommendations",
    "tv_recommendations": "/tv/%s/recommendations",
}

# ── 缓存配置 ──
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "scrape_cache")
# 不同接口的缓存时长（秒）
_CACHE_TTL = {
    "movie_showing": 86400,          # 正在热映：1 天
    "movie_hot_gaia": 86400 * 7,     # 热门电影：7 天
    "movie_soon": 86400,             # 即将上映：1 天
    "movie_top250": 86400 * 30,      # TOP250：30 天
    "tv_hot": 86400 * 7,             # 热门剧集：7 天
    "tv_animation": 86400 * 7,       # 动画：7 天
    "tv_variety_show": 86400 * 7,
    "tv_chinese_best_weekly": 86400 * 7,
    "tv_global_best_weekly": 86400 * 7,
    "movie_recommend": 86400 * 7,
    "tv_recommend": 86400 * 7,
    "search": 86400,                 # 搜索：1 天
    "movie_detail": 86400 * 30,      # 详情：30 天
    "tv_detail": 86400 * 30,
}
_DEFAULT_TTL = 86400 * 7  # 默认 7 天


def _sign(url: str, ts: str, method: str = "GET") -> str:
    """HMAC-SHA1 签名"""
    url_path = parse.urlparse(url).path
    raw_sign = "&".join([method.upper(), parse.quote(url_path, safe=""), ts])
    return base64.b64encode(
        hmac.new(
            _API_SECRET_KEY.encode(),
            raw_sign.encode(),
            hashlib.sha1
        ).digest()
    ).decode()


def _get_cache(cache_key: str, ttl: int) -> Optional[Any]:
    """读取文件缓存，过期返回 None"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = os.path.join(_CACHE_DIR, f"dbv2_{cache_key}.json")
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if time.time() - mtime > ttl:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _set_cache(cache_key: str, data: Any):
    """写入文件缓存"""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = os.path.join(_CACHE_DIR, f"dbv2_{cache_key}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[DoubanV2] 缓存写入失败: {e}")


def _make_cache_key(endpoint: str, **kwargs) -> str:
    """生成缓存 key"""
    raw = f"{endpoint}_{json.dumps(kwargs, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _request(endpoint: str, use_cache: bool = True, **kwargs) -> Optional[Dict]:
    """统一请求方法：签名 + 随机 UA + 随机延迟 + 文件缓存"""
    # 缓存检查
    cache_key = _make_cache_key(endpoint, **kwargs)
    ttl = _CACHE_TTL.get(endpoint, _DEFAULT_TTL)
    if use_cache:
        cached = _get_cache(cache_key, ttl)
        if cached is not None:
            return cached

    # 构造请求
    url_path = _URLS.get(endpoint, endpoint)
    req_url = _BASE_URL + url_path
    ts = datetime.strftime(datetime.now(), "%Y%m%d")

    params = {
        "apiKey": _API_KEY,
        "os_rom": "android",
        "_ts": ts,
        "_sig": _sign(url=req_url, ts=ts),
    }
    params.update(kwargs)

    # 随机延迟 1-3 秒（防封）
    time.sleep(random.uniform(1.0, 3.0))

    try:
        resp = requests.get(
            req_url,
            params=params,
            headers={"User-Agent": random.choice(_USER_AGENTS)},
            timeout=8,
        )
        if resp.status_code != 200:
            print(f"[DoubanV2] {endpoint} 请求失败: HTTP {resp.status_code}")
            return None
        data = resp.json()
        # 缓存成功结果
        if data and use_cache:
            _set_cache(cache_key, data)
        return data
    except Exception as e:
        print(f"[DoubanV2] {endpoint} 请求异常: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 公开接口：榜单/合集
# ══════════════════════════════════════════════════════════════

def _collection(endpoint: str, start: int = 0, count: int = 20) -> List[Dict]:
    """通用合集接口，返回 subject_collection items"""
    data = _request(endpoint, start=start, count=count)
    if not data:
        return []
    # API 返回格式：{ "subject_collection_items": [...] } 或 { "items": [...] }
    items = data.get("subject_collection_items") or data.get("items") or []
    return [_normalize_item(item) for item in items]


def movie_showing(start: int = 0, count: int = 20) -> List[Dict]:
    """正在热映"""
    return _collection("movie_showing", start, count)


def movie_hot(start: int = 0, count: int = 20) -> List[Dict]:
    """热门电影"""
    return _collection("movie_hot_gaia", start, count)


def movie_top250(start: int = 0, count: int = 20) -> List[Dict]:
    """电影 TOP250"""
    return _collection("movie_top250", start, count)


def tv_hot(start: int = 0, count: int = 20) -> List[Dict]:
    """热门剧集"""
    return _collection("tv_hot", start, count)


def tv_animation(start: int = 0, count: int = 20) -> List[Dict]:
    """热门动画"""
    return _collection("tv_animation", start, count)


def tv_weekly_chinese(start: int = 0, count: int = 20) -> List[Dict]:
    """华语口碑周榜"""
    return _collection("tv_chinese_best_weekly", start, count)


def tv_weekly_global(start: int = 0, count: int = 20) -> List[Dict]:
    """全球口碑周榜"""
    return _collection("tv_global_best_weekly", start, count)


# ══════════════════════════════════════════════════════════════
# 公开接口：探索（按标签+排序筛选）
# ══════════════════════════════════════════════════════════════

def movie_explore(tags: str = "", sort: str = "R", start: int = 0, count: int = 20) -> List[Dict]:
    """豆瓣电影探索。sort: R=热度 T=近期热度 S=高分优先"""
    data = _request("movie_recommend", tags=tags, sort=sort, start=start, count=count)
    if not data:
        return []
    items = data.get("items") or []
    return [_normalize_item(item) for item in items]


def tv_explore(tags: str = "", sort: str = "R", start: int = 0, count: int = 20) -> List[Dict]:
    """豆瓣剧集探索。sort: R=热度 T=近期热度 S=高分优先"""
    data = _request("tv_recommend", tags=tags, sort=sort, start=start, count=count)
    if not data:
        return []
    items = data.get("items") or []
    return [_normalize_item(item) for item in items]


# ══════════════════════════════════════════════════════════════
# 公开接口：搜索
# ══════════════════════════════════════════════════════════════

def search(keyword: str, start: int = 0, count: int = 20) -> List[Dict]:
    """豆瓣搜索（API v2，比网页版 suggest 接口结果更全）"""
    data = _request("search", q=keyword, start=start, count=count)
    if not data:
        return []
    items = data.get("items") or []
    results = []
    for item in items:
        # 过滤非影视条目（音乐、书籍等）
        target_type = item.get("target_type") or ""
        if target_type and target_type not in ("movie", "tv"):
            continue
        target = item.get("target") or item
        if "target" in item:
            target["_type_name"] = item.get("type_name") or ""
            target["_target_type"] = target_type
        results.append(_normalize_item(target))
    return results


# ══════════════════════════════════════════════════════════════
# 公开接口：详情
# ══════════════════════════════════════════════════════════════

def movie_detail(subject_id: str) -> Optional[Dict]:
    """电影详情（结构化数据，比爬网页丰富得多）"""
    return _request_detail("movie", subject_id)


def tv_detail(subject_id: str) -> Optional[Dict]:
    """剧集详情"""
    return _request_detail("tv", subject_id)


def get_detail(subject_id: str, media_type: str = "movie") -> Optional[Dict]:
    """统一详情接口，自动选择 movie/tv"""
    if media_type == "tv":
        return tv_detail(subject_id)
    return movie_detail(subject_id)


def _request_detail(media_type: str, subject_id: str) -> Optional[Dict]:
    """请求详情接口（URL 直接拼接 subject_id）"""
    cache_key = _make_cache_key(f"{media_type}_detail", id=subject_id)
    ttl = _CACHE_TTL.get(f"{media_type}_detail", _DEFAULT_TTL)
    cached = _get_cache(cache_key, ttl)
    if cached is not None:
        return _normalize_detail(cached) if cached else None

    url_path = f"/{media_type}/{subject_id}"
    req_url = _BASE_URL + url_path
    ts = datetime.strftime(datetime.now(), "%Y%m%d")

    params = {
        "apiKey": _API_KEY,
        "os_rom": "android",
        "_ts": ts,
        "_sig": _sign(url=req_url, ts=ts),
    }

    time.sleep(random.uniform(1.0, 3.0))

    try:
        resp = requests.get(
            req_url,
            params=params,
            headers={"User-Agent": random.choice(_USER_AGENTS)},
            timeout=8,
        )
        if resp.status_code != 200:
            print(f"[DoubanV2] {media_type}_detail/{subject_id} 请求失败: HTTP {resp.status_code}")
            return None
        data = resp.json()
        if data:
            _set_cache(cache_key, data)
        return _normalize_detail(data) if data else None
    except Exception as e:
        print(f"[DoubanV2] {media_type}_detail/{subject_id} 请求异常: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 数据标准化
# ══════════════════════════════════════════════════════════════

def _normalize_item(item: Dict) -> Dict:
    """将 API v2 返回的条目标准化为统一格式"""
    if not item:
        return {}

    # 海报：优先取 pic.large，其次 cover_url，最后 pic.normal
    pic = item.get("pic") or {}
    poster = pic.get("large") or item.get("cover_url") or pic.get("normal") or ""
    # cover 可能是 dict
    cover = item.get("cover") or {}
    if isinstance(cover, dict):
        poster = poster or cover.get("url") or ""
    elif isinstance(cover, str):
        poster = poster or cover

    # 评分
    rating_obj = item.get("rating") or {}
    rating = rating_obj.get("value") or rating_obj.get("star_count") or 0
    if isinstance(rating, str):
        try:
            rating = float(rating)
        except ValueError:
            rating = 0

    # 年份
    year = str(item.get("year") or "")
    if not year:
        # 从 pubdate 提取
        pubdates = item.get("pubdate") or []
        if pubdates and isinstance(pubdates, list):
            year = pubdates[0][:4] if pubdates[0] else ""

    # 类型
    genres = item.get("genres") or []

    # 国家
    countries = item.get("countries") or []

    # card_subtitle 格式："年份 / 国家 / 类型 / 导演 / 演员"
    # 当 genres/countries/year 为空时（合集接口），从 card_subtitle 解析
    card_sub = item.get("card_subtitle") or ""
    if card_sub:
        parts = [p.strip() for p in card_sub.split("/")]
        # 已知类型关键词（豆瓣常用）
        _GENRE_KEYWORDS = {
            "剧情", "喜剧", "动作", "爱情", "科幻", "悬疑", "惊悚", "恐怖",
            "犯罪", "动画", "奇幻", "冒险", "战争", "传记", "历史", "音乐",
            "歌舞", "家庭", "儿童", "纪录片", "短片", "古装", "武侠", "西部",
            "灾难", "情色", "同性", "运动", "真人秀", "脱口秀", "黑色电影",
        }
        for p in parts:
            tokens = p.split()
            # 年份段：纯数字 4 位
            if not year and len(tokens) == 1 and tokens[0].isdigit() and len(tokens[0]) == 4:
                year = tokens[0]
            elif not genres and all(t in _GENRE_KEYWORDS for t in tokens) and tokens:
                genres = tokens
            elif not countries and not any(t in _GENRE_KEYWORDS for t in tokens) and tokens:
                # 国家段：不是年份、不是类型、不是人名（人名通常含 · 或较长）
                if all(len(t) <= 6 for t in tokens) and not any("·" in t for t in tokens) and not all(t.isdigit() for t in tokens):
                    countries = tokens

    # 导演
    directors = item.get("directors") or []
    director_names = []
    for d in directors:
        if isinstance(d, dict):
            director_names.append(d.get("name") or "")
        elif isinstance(d, str):
            director_names.append(d)

    # 演员
    actors = item.get("actors") or []
    actor_names = []
    for a in actors[:6]:
        if isinstance(a, dict):
            actor_names.append(a.get("name") or "")
        elif isinstance(a, str):
            actor_names.append(a)

    return {
        "douban_id": str(item.get("id") or ""),
        "title": item.get("title") or "",
        "original_title": item.get("original_title") or "",
        "year": year,
        "rating": round(float(rating), 1) if rating else 0,
        "poster_url": poster,
        "overview": item.get("intro") or "",
        "genres": genres,
        "directors": director_names,
        "actors": actor_names,
        "media_type": item.get("_target_type") or item.get("type") or item.get("subtype") or "",
        "episode_count": item.get("episodes_count") or 0,
        "episodes_info": item.get("episodes_info") or "",
        "countries": countries,
    }


def _normalize_detail(data: Dict) -> Optional[Dict]:
    """标准化详情数据"""
    if not data or data.get("code"):
        return None

    base = _normalize_item(data)

    # 详情页额外字段
    base["overview"] = data.get("intro") or base.get("overview") or ""
    base["runtime"] = 0
    durations = data.get("durations") or []
    if durations:
        # "120分钟" → 120
        import re
        m = re.search(r"(\d+)", str(durations[0]))
        if m:
            base["runtime"] = int(m.group(1))

    # 季集信息（剧集）
    base["seasons_count"] = data.get("seasons_count") or 0
    base["current_season"] = data.get("season") or ""
    base["episode_count"] = data.get("episodes_count") or 0

    # 标签
    base["tags"] = [t.get("name") or t for t in (data.get("tags") or []) if t]

    # 豆瓣链接
    base["url"] = data.get("url") or f"https://movie.douban.com/subject/{base['douban_id']}/"

    return base
