"""
海报下载模块：从 scraper.py 拆分而来
"""
import os
import requests


def download_poster(folder_path: str, poster_url: str, filename: str = "poster.jpg", proxy: str = "") -> bool:
    """下载海报到文件夹（强制覆盖）"""
    if not poster_url:
        return False
    target = os.path.join(folder_path, filename)
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        headers = {"Referer": "https://movie.douban.com/", "User-Agent": "Mozilla/5.0"} if "doubanio.com" in poster_url else {}
        resp = requests.get(poster_url, stream=True, timeout=15, headers=headers, proxies=proxies)
        resp.raise_for_status()
        os.makedirs(folder_path, exist_ok=True)
        with open(target, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        print(f"[Poster] OK: {filename} <- {poster_url[:60]}")
        return True
    except Exception as e:
        print(f"[Poster] FAIL: {filename} <- {poster_url[:60]} error={e}")
        return False
