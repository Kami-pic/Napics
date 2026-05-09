"""测试 DetailDrawer 拆分后的功能回归：验证刮削、重命名、整理等 API 链路"""
import requests


BASE = "http://localhost:8000"


def api_request(method, url, params=None, json_body=None):
    """通用 API 请求 helper；真实失败交给 pytest 断言暴露。"""
    if method == "GET":
        response = requests.get(f"{BASE}{url}", params=params, timeout=15)
    else:
        response = requests.post(f"{BASE}{url}", params=params, json=json_body, timeout=15)
    return response


def api_json(method, url, params=None, json_body=None):
    response = api_request(method, url, params=params, json_body=json_body)
    response.raise_for_status()
    return response.json()


def test_movie_folder_scrape_read_and_poster():
    data = api_json(
        "GET",
        "/scrape/read",
        {"path": r"\\DS218play\share\视频\其他视频\洗版测试"},
    )
    assert "status" in data
    assert data.get("status") == "ok", f"status={data.get('status')}"
    assert data.get("data", {}).get("title")

    poster = api_request(
        "GET",
        "/scrape/poster",
        {"path": r"\\DS218play\share\视频\其他视频\洗版测试"},
    )
    assert poster.status_code in [200, 404]


def test_anime_folder_scrape_read_status():
    data = api_json(
        "GET",
        "/scrape/read",
        {"path": r"\\DS218play\share\视频\动画番\测试动画合集"},
    )
    assert "status" in data
    assert data.get("status") in ["ok", "not_found"]


def test_movie_test_folder_scrape_read_status():
    data = api_json(
        "GET",
        "/scrape/read",
        {"path": r"\\DS218play\share\视频\电影\测试文件夹"},
    )
    assert "status" in data
    assert data.get("status") in ["ok", "not_found"]


def test_scrape_candidate_sources():
    tmdb = api_json("GET", "/scrape/candidates", {"name": "盗梦空间"})
    assert "candidates" in tmdb
    assert len(tmdb.get("candidates", [])) > 0
    assert "rating" in tmdb["candidates"][0]

    douban = api_json("GET", "/scrape/douban", {"name": "盗梦空间"})
    assert "candidates" in douban
    assert len(douban.get("candidates", [])) > 0
    assert douban["candidates"][0].get("rating", 0) > 0
    assert douban["candidates"][0].get("genres")

    bangumi = api_json("GET", "/scrape/bangumi", {"name": "进击的巨人"})
    assert "candidates" in bangumi
    assert len(bangumi.get("candidates", [])) > 0
    assert bangumi["candidates"][0].get("rating", 0) > 0


def test_media_info_multi_source():
    douban = api_json(
        "GET",
        "/media/info",
        {"title": "霸王别姬", "source": "douban", "type": "movie"},
    )
    assert douban.get("found")
    assert douban.get("source") == "douban"

    bangumi = api_json(
        "GET",
        "/media/info",
        {"title": "进击的巨人", "source": "bangumi", "type": "tv", "id": "12189"},
    )
    assert bangumi.get("found")
    assert bangumi.get("source") == "bangumi"

    tmdb = api_json(
        "GET",
        "/media/info",
        {"title": "Inception", "source": "tmdb", "type": "movie"},
    )
    assert tmdb.get("found")
    assert tmdb.get("source") == "tmdb"


def test_shadow_names_api_available():
    data = api_json("GET", "/media/shadow-names")
    assert data is not None


def test_no_scrape_api_available():
    data = api_json("GET", "/no-scrape")
    assert data is not None
