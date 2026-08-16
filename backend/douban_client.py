"""豆瓣刮削客户端 — 搜索 + 详情"""
import requests
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://movie.douban.com/",
}


def _douban_proxies(url: str):
    """豆瓣域名在内置直连列表里，返回 None 表示直连。"""
    try:
        from core.proxy_policy import proxies_from_config
        return proxies_from_config(url)
    except Exception:
        return None


def search(query: str) -> List[Dict]:
    """豆瓣搜索建议，返回候选列表"""
    url = "https://movie.douban.com/j/subject_suggest"
    try:
        resp = requests.get(url, params={"q": query}, headers=HEADERS, timeout=8, proxies=_douban_proxies(url))
        resp.raise_for_status()
        items = resp.json()
        results = []
        for item in items:
            if item.get("type") not in ("movie",):
                continue
            # 替换缩略图为较大尺寸
            img = item.get("img", "")
            if img:
                img = img.replace("/s_ratio_poster/", "/m_ratio_poster/")
            results.append({
                "douban_id": item.get("id", ""),
                "title": item.get("title", ""),
                "year": item.get("year", ""),
                "poster_url": img,
                "subtitle": item.get("sub_title", ""),  # 原名/别名
                "type": item.get("type", ""),
                "episode": item.get("episode", ""),  # 集数（剧集才有）
            })
        return results
    except Exception as e:
        logger.error(f"[Douban] search error: {e}")
        return []


def get_hot_list(media_type: str = "movie", page_start: int = 0, tag: str = "热门") -> List[Dict]:
    """获取豆瓣热榜列表，type 为 movie 或 tv，tag 可选热门/动画等"""
    url = "https://movie.douban.com/j/search_subjects"
    params = {
        "type": media_type,
        "tag": tag,
        "page_limit": 12,
        "page_start": page_start,
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=8, proxies=_douban_proxies(url))
        resp.raise_for_status()
        data = resp.json()
        subjects = data.get("subjects", [])
        results = []
        for item in subjects:
            # 提取 douban_id from url: https://movie.douban.com/subject/12345/
            douban_id = ""
            subject_url = item.get("url", "")
            id_match = re.search(r'/subject/(\d+)/', subject_url)
            if id_match:
                douban_id = id_match.group(1)
            elif item.get("id"):
                douban_id = str(item["id"])

            # 替换缩略图为较大尺寸
            cover = item.get("cover", "")
            if cover:
                cover = cover.replace("/s_ratio_poster/", "/m_ratio_poster/")

            results.append({
                "douban_id": douban_id,
                "title": item.get("title", ""),
                "year": item.get("year", ""),
                "rating": float(item.get("rate", 0) or 0),
                "cover_url": cover,
                "subtitle": item.get("sub_title", ""),
                "episode": item.get("episodes_info", ""),
            })
        return results
    except Exception as e:
        logger.error(f"[Douban] hot list error: {e}")
        return []


def get_detail(douban_id: str) -> Optional[Dict]:
    """获取豆瓣影视详情（从网页解析）"""
    url = f"https://movie.douban.com/subject/{douban_id}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, proxies=_douban_proxies(url))
        resp.raise_for_status()
        html = resp.text

        def extract(pattern, text, default=""):
            m = re.search(pattern, text, re.S)
            return m.group(1).strip() if m else default

        title = extract(r'<span property="v:itemreviewed">(.*?)</span>', html)
        year = extract(r'<span class="year">\((\d{4})\)</span>', html)
        rating = extract(r'<strong class="ll rating_num" property="v:average">([\d.]+)</strong>', html, "0")
        overview = extract(r'<span property="v:summary"[^>]*>\s*(.*?)\s*</span>', html)
        overview = re.sub(r'<[^>]+>', '', overview).strip()

        # 导演
        director = extract(r'<a[^>]*rel="v:directedBy"[^>]*>(.*?)</a>', html)

        # 类型
        genres = re.findall(r'<span property="v:genre">(.*?)</span>', html)

        # 演员（前6个）
        cast = re.findall(r'<a[^>]*rel="v:starring"[^>]*>(.*?)</a>', html)[:6]

        # 封面
        poster_url = extract(r'<img[^>]*src="(https://img\d+\.doubanio\.com/view/photo/[^"]+)"[^>]*title="点击看更多海报"', html)
        if not poster_url:
            poster_url = extract(r'<img[^>]*src="(https://img\d+\.doubanio\.com/view/photo/[^"]+)"', html)

        # 原名
        original_title = ""
        info_block = extract(r'<div id="info">(.*?)</div>', html)
        orig_match = re.search(r'又名:</span>\s*(.*?)<br', info_block)
        if orig_match:
            aliases = [a.strip() for a in orig_match.group(1).split('/')]
            original_title = aliases[0] if aliases else ""

        # 时长
        runtime = extract(r'<span property="v:runtime"[^>]*>(\d+)</span>', html, "0")

        return {
            "douban_id": douban_id,
            "title": title,
            "original_title": original_title,
            "year": year,
            "rating": float(rating) if rating else 0,
            "overview": overview,
            "director": director,
            "genres": genres,
            "cast": cast,
            "poster_url": poster_url,
            "runtime": int(runtime) if runtime else 0,
        }
    except Exception as e:
        logger.error(f"[Douban] detail error: {e}")
        return None
