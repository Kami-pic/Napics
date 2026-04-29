# 季集完整性检测测试
import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from completeness import (
    _extract_season_episode_from_filename,
    _extract_episode_only,
    _extract_season_from_dir,
    collect_local_episodes,
    compute_completeness,
)
from tmdb_client import ScrapeResult


class TestFilenameExtraction:
    """文件名季集号提取测试"""

    def test_s01e02(self):
        assert _extract_season_episode_from_filename("Better.Call.Saul.S01E02.720p.mkv") == (1, 2)

    def test_s1e10(self):
        assert _extract_season_episode_from_filename("Breaking.Bad.S1E10.mkv") == (1, 10)

    def test_chinese_season_episode(self):
        assert _extract_season_episode_from_filename("纸牌屋 第3季第7集.mkv") == (3, 7)

    def test_season_episode_words(self):
        assert _extract_season_episode_from_filename("Season 2 Episode 5.mkv") == (2, 5)

    def test_no_match(self):
        assert _extract_season_episode_from_filename("movie.2024.mkv") is None

    def test_episode_only_e02(self):
        assert _extract_episode_only("E02.mkv") == 2

    def test_episode_only_ep12(self):
        assert _extract_episode_only("EP12.mkv") == 12

    def test_episode_only_chinese(self):
        assert _extract_episode_only("第5集.mkv") == 5

    def test_episode_only_number(self):
        assert _extract_episode_only("03.mkv") == 3

    def test_season_dir_season_1(self):
        assert _extract_season_from_dir("Season 1") == 1

    def test_season_dir_s02(self):
        assert _extract_season_from_dir("S02") == 2

    def test_season_dir_chinese(self):
        assert _extract_season_from_dir("第3季") == 3


class TestComputeCompleteness:
    """完整度计算测试"""

    def _mock_tmdb_client(self, seasons_info, season_episodes):
        """构造 mock TMDB 客户端"""
        client = MagicMock()
        client.get_tv_detail.return_value = ScrapeResult(
            tmdb_id=1396,
            media_type="tv",
            title="绝命毒师",
            english_title="Breaking Bad",
            total_seasons=len(seasons_info),
            seasons_info=seasons_info,
        )
        client.get_season_detail.return_value = ScrapeResult()

        def mock_get(path, params=None):
            # /tv/1396/season/N
            for s_num, eps in season_episodes.items():
                if f"/season/{s_num}" in path:
                    return {"episodes": [{"episode_number": i, "name": f"E{i}", "air_date": "2024-01-01"} for i in eps]}
            return {"episodes": []}

        client._get = mock_get
        return client

    def test_all_complete(self):
        """全部完整"""
        seasons_info = [{"season_number": 1, "episode_count": 3}]
        season_eps = {1: [1, 2, 3]}
        client = self._mock_tmdb_client(seasons_info, season_eps)
        local = {1: [1, 2, 3]}

        result = compute_completeness(client, 1396, local)
        assert result["status"] == "ok"
        assert result["completeness_pct"] == 100.0
        assert result["seasons"][0]["status"] == "complete"
        assert result["seasons"][0]["missing_episodes"] == []

    def test_partial(self):
        """部分缺失"""
        seasons_info = [{"season_number": 1, "episode_count": 5}]
        season_eps = {1: [1, 2, 3, 4, 5]}
        client = self._mock_tmdb_client(seasons_info, season_eps)
        local = {1: [1, 3, 5]}

        result = compute_completeness(client, 1396, local)
        assert result["status"] == "ok"
        assert result["completeness_pct"] == 60.0
        assert result["seasons"][0]["status"] == "partial"
        missing_eps = [m["episode"] for m in result["seasons"][0]["missing_episodes"]]
        assert missing_eps == [2, 4]

    def test_entire_season_missing(self):
        """整季缺失"""
        seasons_info = [
            {"season_number": 1, "episode_count": 3},
            {"season_number": 2, "episode_count": 3},
        ]
        season_eps = {1: [1, 2, 3], 2: [1, 2, 3]}
        client = self._mock_tmdb_client(seasons_info, season_eps)
        local = {1: [1, 2, 3]}  # 只有 S1

        result = compute_completeness(client, 1396, local)
        assert result["status"] == "ok"
        assert result["completeness_pct"] == 50.0
        assert result["seasons"][0]["status"] == "complete"
        assert result["seasons"][1]["status"] == "missing"

    def test_specials_excluded_by_default(self):
        """特别篇默认不计入"""
        seasons_info = [
            {"season_number": 0, "episode_count": 5},
            {"season_number": 1, "episode_count": 3},
        ]
        season_eps = {0: [1, 2, 3, 4, 5], 1: [1, 2, 3]}
        client = self._mock_tmdb_client(seasons_info, season_eps)
        local = {1: [1, 2, 3]}

        result = compute_completeness(client, 1396, local)
        assert result["total_seasons"] == 1  # 只有 S1
        assert result["completeness_pct"] == 100.0

    def test_specials_included(self):
        """明确包含特别篇"""
        seasons_info = [
            {"season_number": 0, "episode_count": 2},
            {"season_number": 1, "episode_count": 3},
        ]
        season_eps = {0: [1, 2], 1: [1, 2, 3]}
        client = self._mock_tmdb_client(seasons_info, season_eps)
        local = {1: [1, 2, 3]}

        result = compute_completeness(client, 1396, local, include_specials=True)
        assert result["total_seasons"] == 2
        assert result["completeness_pct"] == 60.0  # 3/5

    def test_unaired_episodes(self):
        """未播出的集标记为 aired=False"""
        seasons_info = [{"season_number": 1, "episode_count": 3}]
        client = MagicMock()
        client.get_tv_detail.return_value = ScrapeResult(
            tmdb_id=1, media_type="tv", title="Test",
            seasons_info=seasons_info,
        )
        client.get_season_detail.return_value = ScrapeResult()
        client._get = lambda path, params=None: {
            "episodes": [
                {"episode_number": 1, "name": "E1", "air_date": "2024-01-01"},
                {"episode_number": 2, "name": "E2", "air_date": "2024-06-01"},
                {"episode_number": 3, "name": "E3", "air_date": "2099-12-31"},
            ]
        }
        local = {}

        result = compute_completeness(client, 1, local)
        missing = result["seasons"][0]["missing_episodes"]
        assert len(missing) == 3
        assert missing[0]["aired"] is True   # 2024-01-01
        assert missing[1]["aired"] is True   # 2024-06-01
        assert missing[2]["aired"] is False  # 2099-12-31

    def test_tmdb_error(self):
        """TMDB 获取失败"""
        client = MagicMock()
        client.get_tv_detail.return_value = ScrapeResult()  # 空结果
        result = compute_completeness(client, 99999, {})
        assert result["status"] == "tmdb_error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
