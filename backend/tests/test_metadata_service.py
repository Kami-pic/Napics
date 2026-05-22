"""MetadataService 兼容性测试。

验证 MetadataService 包装 TMDBClient 后方法签名和返回类型不变。
"""
import pytest
from unittest.mock import MagicMock, patch
from tmdb_client import ScrapeResult
from metadata_service import MetadataService


@pytest.fixture
def mock_tmdb():
    """构造一个 mock TMDBClient。"""
    client = MagicMock()
    client.proxy = "http://127.0.0.1:7897"
    client.scrape_by_filename.return_value = ScrapeResult(title="测试电影", tmdb_id=12345, media_type="movie")
    client.search_movie.return_value = [{"id": 12345, "title": "测试电影", "release_date": "2024-01-01"}]
    client.search_tv.return_value = [{"id": 67890, "name": "测试剧集", "first_air_date": "2024-06-01"}]
    client.get_movie_detail.return_value = ScrapeResult(title="测试电影", tmdb_id=12345, media_type="movie", year="2024")
    client.get_tv_detail.return_value = ScrapeResult(title="测试剧集", tmdb_id=67890, media_type="tv", year="2024")
    client.get_season_detail.return_value = ScrapeResult(title="测试剧集", tmdb_id=67890, season_number=1)
    client.get_episode_detail.return_value = ScrapeResult(title="测试剧集", tmdb_id=67890, episode_title="第1集")
    client._get.return_value = {"seasons": [{"season_number": 1, "episode_count": 12}]}
    client._cache_path.return_value = "/tmp/cache/tv_67890.json"
    client._save_cache.return_value = None
    client._get_english_title.return_value = "Test Movie"
    return client


@pytest.fixture
def service(mock_tmdb):
    return MetadataService(mock_tmdb)


class TestMetadataServiceProxy:
    def test_proxy_property(self, service):
        assert service.proxy == "http://127.0.0.1:7897"

    def test_proxy_empty_when_not_set(self):
        client = MagicMock(spec=[])
        svc = MetadataService(client)
        assert svc.proxy == ""


class TestMetadataServiceSearch:
    def test_scrape_by_filename(self, service, mock_tmdb):
        result = service.scrape_by_filename("测试电影.2024.1080p.mkv")
        mock_tmdb.scrape_by_filename.assert_called_once_with("测试电影.2024.1080p.mkv")
        assert isinstance(result, ScrapeResult)
        assert result.tmdb_id == 12345

    def test_search_movie(self, service, mock_tmdb):
        results = service.search_movie("测试电影")
        mock_tmdb.search_movie.assert_called_once_with("测试电影")
        assert len(results) == 1
        assert results[0]["id"] == 12345

    def test_search_tv(self, service, mock_tmdb):
        results = service.search_tv("测试剧集")
        mock_tmdb.search_tv.assert_called_once_with("测试剧集")
        assert len(results) == 1
        assert results[0]["id"] == 67890


class TestMetadataServiceDetail:
    def test_get_movie_detail(self, service, mock_tmdb):
        result = service.get_movie_detail(12345)
        mock_tmdb.get_movie_detail.assert_called_once_with(12345)
        assert isinstance(result, ScrapeResult)
        assert result.year == "2024"

    def test_get_tv_detail(self, service, mock_tmdb):
        result = service.get_tv_detail(67890)
        mock_tmdb.get_tv_detail.assert_called_once_with(67890)
        assert isinstance(result, ScrapeResult)
        assert result.media_type == "tv"

    def test_get_season_detail(self, service, mock_tmdb):
        result = service.get_season_detail(67890, 1)
        mock_tmdb.get_season_detail.assert_called_once_with(67890, 1)
        assert isinstance(result, ScrapeResult)

    def test_get_episode_detail(self, service, mock_tmdb):
        result = service.get_episode_detail(67890, 1, 3)
        mock_tmdb.get_episode_detail.assert_called_once_with(67890, 1, 3)
        assert isinstance(result, ScrapeResult)
        assert result.episode_title == "第1集"


class TestMetadataServiceRawAccess:
    def test_get_raw(self, service, mock_tmdb):
        result = service.get_raw("/tv/67890")
        mock_tmdb._get.assert_called_once_with("/tv/67890", {})
        assert "seasons" in result

    def test_get_raw_with_params(self, service, mock_tmdb):
        service.get_raw("/tv/67890/season/1", {"language": "en-US"})
        mock_tmdb._get.assert_called_once_with("/tv/67890/season/1", {"language": "en-US"})

    def test_get_cache_path(self, service, mock_tmdb):
        path = service.get_cache_path("tv", 67890)
        mock_tmdb._cache_path.assert_called_once_with("tv", 67890)
        assert path == "/tmp/cache/tv_67890.json"

    def test_save_cache(self, service, mock_tmdb):
        service.save_cache("/tmp/cache/tv_67890.json", {"title": "test"})
        mock_tmdb._save_cache.assert_called_once_with("/tmp/cache/tv_67890.json", {"title": "test"})


class TestMetadataServiceEnglishTitle:
    def test_get_english_title(self, service, mock_tmdb):
        result = service.get_english_title("movie", 12345, "テスト映画")
        mock_tmdb._get_english_title.assert_called_once_with("movie", 12345, "テスト映画")
        assert result == "Test Movie"
