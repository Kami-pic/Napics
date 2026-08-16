"""Bangumi 刮削客户端 — 搜索 + 详情"""
import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
HEADERS = {
    "User-Agent": "nas-media-manager/1.0",
    "Accept": "application/json",
}
BASE = "https://api.bgm.tv"

# type: 1=书籍 2=动画 3=音乐 4=游戏 6=三次元
TYPE_MAP = {1: "书籍", 2: "动画", 3: "音乐", 4: "游戏", 6: "三次元"}

def _get_proxies():
    """Bangumi 的代理策略。

    api.bgm.tv 理论上国内可直连，但部分 NAS 环境下不可达（DNS 解析到不通的 IP
    或运营商封锁）。这里先尝试直连（proxies_from_config 返回 None），
    如果连不上，_session 会用后备代理重试。
    """
    try:
        from core.proxy_policy import proxies_from_config
        return proxies_from_config(BASE)
    except Exception:
        return None


def _get_fallback_proxy():
    """获取配置中的 http_proxy 作为 Bangumi 回退代理。"""
    try:
        from shared import config_m
        proxy = getattr(config_m.config, "http_proxy", "") or ""
        return {"http": proxy, "https": proxy} if proxy else None
    except Exception:
        return None


# 模块级单例
_bgm_session: requests.Session | None = None
_bgm_use_proxy: bool = False  # 直连失败后切换为代理模式


def _session():
    global _bgm_session
    if _bgm_session is None:
        _bgm_session = requests.Session()
    return _bgm_session


def _probe_direct_on_import():
    """模块加载时快速探测直连：1.5s 内能 TCP 握手则直连可用，否则直接标记代理模式。"""
    global _bgm_use_proxy
    import socket
    try:
        addrs = socket.getaddrinfo("api.bgm.tv", 443, socket.AF_INET, socket.SOCK_STREAM)
        if not addrs:
            _bgm_use_proxy = True
            logger.info("[Bangumi] DNS 无 IPv4 地址，启用代理模式")
            return
        ip = addrs[0][4][0]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect((ip, 443))
        s.close()
        logger.info(f"[Bangumi] 直连探测通过 ({ip})")
    except Exception as e:
        _bgm_use_proxy = True
        logger.info(f"[Bangumi] 直连探测失败 ({e})，启用代理模式")


try:
    _probe_direct_on_import()
except Exception as _e:
    _bgm_use_proxy = True
    logger.error(f"[Bangumi] 探测异常: {_e}，启用代理模式")


def _bgm_get(url: str, **kwargs):
    """Bangumi 请求包装：直连失败时自动回退到代理，后续请求直接走代理。
    始终强制 IPv4 解析，避免容器解析到不可达的 IPv6。
    """
    global _bgm_use_proxy
    import socket as _socket

    _orig_gai = _socket.getaddrinfo

    def _ipv4_gai(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_gai(host, port, _socket.AF_INET, type, proto, flags)

    session = _session()

    if _bgm_use_proxy:
        kwargs["proxies"] = _get_fallback_proxy()
        _socket.getaddrinfo = _ipv4_gai
        try:
            return session.get(url, **kwargs)
        finally:
            _socket.getaddrinfo = _orig_gai

    # 先尝试直连（超时缩短到 2s，快速失败后切代理）
    proxies = _get_proxies()
    kwargs["proxies"] = proxies
    kwargs.setdefault("timeout", 2)
    _socket.getaddrinfo = _ipv4_gai
    try:
        resp = session.get(url, **kwargs)
        return resp
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
        # 直连不通，切换到代理模式
        fallback = _get_fallback_proxy()
        if fallback:
            logger.info("[Bangumi] 直连超时，切换到代理模式")
            _bgm_use_proxy = True
            kwargs["proxies"] = fallback
            kwargs["timeout"] = 10  # 代理模式给足超时
            return session.get(url, **kwargs)
        raise
    finally:
        _socket.getaddrinfo = _orig_gai

def search(query: str, type_filter: int = 0) -> List[Dict]:
    """搜索 Bangumi，返回候选列表。type_filter=0 搜全部，2=动画，6=三次元"""
    url = f"{BASE}/search/subject/{requests.utils.quote(query)}"
    params = {"responseGroup": "large", "max_results": 15}
    if type_filter:
        params["type"] = type_filter
    try:
        resp = _bgm_get(url, params=params, headers=HEADERS, timeout=8)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        items = data.get("list", [])
        results = []
        for item in items:
            bgm_type = item.get("type", 0)
            results.append({
                "bgm_id": item.get("id", 0),
                "title": item.get("name_cn", "") or item.get("name", ""),
                "original_title": item.get("name", ""),
                "year": (item.get("air_date", "") or "")[:4],
                "poster_url": (item.get("images", {}) or {}).get("medium", ""),
                "summary": (item.get("summary", "") or "")[:120],
                "type": TYPE_MAP.get(bgm_type, "其他"),
                "type_id": bgm_type,
                "rating": (item.get("rating", {}) or {}).get("score", 0),
                "rank": item.get("rank", 0),
            })
        return results
    except Exception as e:
        logger.error(f"[Bangumi] search error: {e}")
        return []


def get_hot_anime(page_start: int = 0, page_limit: int = 12) -> List[Dict]:
    """获取当季热门动画（Bangumi 每日放送，按评分排序）"""
    try:
        resp = requests.get(f"{BASE}/calendar", headers=HEADERS, timeout=8, proxies=_get_proxies() or None)
        resp.raise_for_status()
        days = resp.json()
        all_items = []
        for day in days:
            all_items.extend(day.get("items", []))
        # 去重（同一部可能出现在多天）
        seen = set()
        unique = []
        for item in all_items:
            bid = item.get("id", 0)
            if bid and bid not in seen:
                seen.add(bid)
                # 过滤：评分人数不足 50 且评分低于 5 的不展示（排除刷分/无人评分的条目）
                score = (item.get("rating", {}) or {}).get("score", 0)
                total = (item.get("rating", {}) or {}).get("total", 0)
                if total < 50 and score < 5:
                    continue
                if score <= 0 and total <= 0:
                    continue
                unique.append(item)
        # 按评分降序（评分人数不足 100 的降权排后面）
        unique.sort(key=lambda x: (
            1 if (x.get("rating", {}) or {}).get("total", 0) >= 100 else 0,
            (x.get("rating", {}) or {}).get("score", 0)
        ), reverse=True)
        # 分页
        page_items = unique[page_start:page_start + page_limit]
        results = []
        for item in page_items:
            images = item.get("images", {}) or {}
            poster = images.get("large", "") or images.get("common", "") or images.get("medium", "")
            results.append({
                "douban_id": str(item.get("id", "")),
                "title": item.get("name_cn", "") or item.get("name", ""),
                "original_title": item.get("name", ""),
                "year": (item.get("air_date", "") or "")[:4],
                "rating": round((item.get("rating", {}) or {}).get("score", 0), 1),
                "cover_url": poster,
                "subtitle": item.get("name", ""),
                "episode": "",
                "media_type": "tv",
            })
        return results
    except Exception as e:
        logger.error(f"[Bangumi] hot anime error: {e}")
        return []


def discover(type: int = 2, cat: int = None, sort: str = "rank",
             year: str = None, limit: int = 30, offset: int = 0) -> List[Dict]:
    """探索 Bangumi 条目（v0/subjects 接口）。
    type: 1=书籍 2=动画 3=音乐 4=游戏 6=三次元
    sort: rank(排名) / date(日期)
    """
    params = {"type": type, "sort": sort, "limit": limit, "offset": offset}
    if cat is not None:
        params["cat"] = cat
    if year:
        # Bangumi v0/subjects 支持 filter 参数
        params["year"] = year
    try:
        resp = requests.get(f"{BASE}/v0/subjects", params=params, headers=HEADERS, timeout=8, proxies=_get_proxies() or None)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or data.get("list") or (data if isinstance(data, list) else [])
        results = []
        for item in items:
            images = item.get("images", {}) or {}
            poster = images.get("large", "") or images.get("common", "") or images.get("medium", "")
            bgm_type = item.get("type", 0)
            results.append({
                "douban_id": str(item.get("id", "")),
                "title": item.get("name_cn", "") or item.get("name", ""),
                "original_title": item.get("name", ""),
                "year": (item.get("date", "") or item.get("air_date", "") or "")[:4],
                "rating": round((item.get("rating", {}) or {}).get("score", 0), 1),
                "cover_url": poster,
                "subtitle": item.get("name", ""),
                "episode": "",
                "media_type": "tv",
                "genres": [],
                "type": TYPE_MAP.get(bgm_type, "其他"),
                "rank": item.get("rank", 0),
            })
        return results
    except Exception as e:
        logger.error(f"[Bangumi] discover error: {e}")
        return []


def get_detail(bgm_id: int) -> Optional[Dict]:
    """获取 Bangumi 条目详情"""
    url = f"{BASE}/v0/subjects/{bgm_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, proxies=_get_proxies() or None)
        resp.raise_for_status()
        item = resp.json()
        
        # 提取 staff
        director = ""
        cast = []
        for info in (item.get("infobox", []) or []):
            key = info.get("key", "")
            val = info.get("value", "")
            if key == "导演" and isinstance(val, str):
                director = val
            elif key == "导演" and isinstance(val, list):
                director = val[0].get("v", "") if val else ""
            elif key in ("主演", "声优", "配音") and isinstance(val, list):
                cast = [v.get("v", "") for v in val[:6]]

        # 提取标签作为 genres
        genres = [t.get("name", "") for t in (item.get("tags", []) or [])[:6]]

        images = item.get("images", {}) or {}
        poster_url = images.get("large", "") or images.get("medium", "")

        return {
            "bgm_id": bgm_id,
            "title": item.get("name_cn", "") or item.get("name", ""),
            "original_title": item.get("name", ""),
            "year": (item.get("date", "") or "")[:4],
            "rating": (item.get("rating", {}) or {}).get("score", 0),
            "overview": item.get("summary", ""),
            "director": director,
            "cast": cast,
            "genres": genres,
            "poster_url": poster_url,
            "total_episodes": item.get("total_episodes", 0),
            "type": TYPE_MAP.get(item.get("type", 0), "其他"),
            "platform": item.get("platform", ""),
        }
    except Exception as e:
        logger.error(f"[Bangumi] detail error: {e}")
        return None


def get_episodes(bgm_id: int) -> List[Dict]:
    """获取 Bangumi 条目的每集信息（含播出日期）。

    返回: [{"episode": 1, "air_date": "2025-04-05", "name": "第1话 xxx", "name_cn": "xxx"}, ...]
    """
    url = f"{BASE}/v0/episodes"
    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=10,
            params={"subject_id": bgm_id, "type": 0, "limit": 100},
            proxies=_get_proxies() or None,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else data
        episodes = []
        for ep in items:
            air_date = ep.get("airdate", "") or ""
            ep_num = ep.get("ep", 0) or ep.get("sort", 0)
            if not ep_num:
                continue
            episodes.append({
                "episode": int(ep_num),
                "air_date": air_date,
                "name": ep.get("name", ""),
                "name_cn": ep.get("name_cn", ""),
            })
        return episodes
    except Exception as e:
        logger.error(f"[Bangumi] episodes error bgm_id={bgm_id}: {e}")
        return []
