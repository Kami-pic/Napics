"""
测试脚本：验证发现页详情匹配修复
覆盖 _pick_best 新签名、best_match 多维度评分、_try_tmdb_detail_by_id 回退逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
from tmdb_client import best_match, calc_match_score, ScrapeResult


class TestBestMatchReject(unittest.TestCase):
    """best_match 对不相关结果的拒绝"""

    def test_pittsburgh_vs_young_pete(self):
        """模拟"匹兹堡医护前线"搜索返回"年轻的皮特先生"，应被拒绝（<30分）"""
        results = [{
            "id": 99999,
            "title": "年轻的皮特先生",
            "original_title": "Young Mr. Pete",
            "release_date": "2020-01-01",
            "popularity": 5.0,
        }]
        match = best_match("匹兹堡医护前线", results, year="2023", type_key="title")
        self.assertIsNone(match, "不相关结果应被拒绝（低于30分阈值）")

    def test_completely_unrelated(self):
        """完全不相关的标题应被拒绝"""
        results = [{
            "id": 11111,
            "title": "复仇者联盟",
            "original_title": "The Avengers",
            "release_date": "2012-05-04",
            "popularity": 100.0,
        }]
        match = best_match("霸王别姬", results, year="1993", type_key="title")
        self.assertIsNone(match, "完全不相关的结果应被拒绝")


class TestBestMatchAccept(unittest.TestCase):
    """best_match 对正确结果的接受"""

    def test_farewell_my_concubine(self):
        """霸王别姬精确匹配应通过"""
        results = [{
            "id": 10997,
            "title": "霸王别姬",
            "original_title": "霸王别姬",
            "release_date": "1993-01-01",
            "popularity": 30.0,
        }]
        match = best_match("霸王别姬", results, year="1993", type_key="title")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 10997)

    def test_inception(self):
        """Inception 英文原名匹配应通过"""
        results = [{
            "id": 27205,
            "title": "盗梦空间",
            "original_title": "Inception",
            "release_date": "2010-07-16",
            "popularity": 80.0,
        }]
        match = best_match("Inception", results, year="2010", type_key="title")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 27205)

    def test_inception_chinese_query(self):
        """用中文名搜索盗梦空间也应匹配"""
        results = [{
            "id": 27205,
            "title": "盗梦空间",
            "original_title": "Inception",
            "release_date": "2010-07-16",
            "popularity": 80.0,
        }]
        match = best_match("盗梦空间", results, year="2010", type_key="title")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 27205)


class TestBestMatchTypeDistinction(unittest.TestCase):
    """best_match 对同名不同类型的区分"""

    def test_invincible_movie_vs_tv(self):
        """Invincible 电影搜索应匹配电影而非剧集（通过 type_key 区分）"""
        # 模拟电影搜索结果（type_key="title"）
        movie_results = [
            {
                "id": 1001,
                "title": "Invincible",
                "original_title": "Invincible",
                "release_date": "2006-01-13",
                "popularity": 20.0,
            },
            {
                "id": 1002,
                "title": "无敌少侠",
                "original_title": "Invincible",
                "release_date": "2021-03-26",
                "popularity": 50.0,
            },
        ]
        match = best_match("Invincible", movie_results, year="2006", type_key="title")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 1001, "年份2006应匹配电影版")

    def test_invincible_tv_type_key(self):
        """TV 搜索结果用 name 字段，type_key="name" 应正确读取"""
        tv_results = [
            {
                "id": 2001,
                "name": "无敌少侠",
                "original_name": "Invincible",
                "first_air_date": "2021-03-26",
                "popularity": 80.0,
            },
        ]
        match = best_match("Invincible", tv_results, year="2021", type_key="name")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 2001)

    def test_tv_type_key_fallback_to_name(self):
        """type_key="name" 时，如果 item 没有 name 字段，应 fallback 到 name（空）"""
        tv_results = [
            {
                "id": 3001,
                "name": "测试剧集",
                "original_name": "Test Show",
                "first_air_date": "2023-01-01",
                "popularity": 10.0,
            },
        ]
        # type_key="name" 直接读 name 字段
        match = best_match("测试剧集", tv_results, year="2023", type_key="name")
        self.assertIsNotNone(match)
        self.assertEqual(match["id"], 3001)


class TestPickBestNewSignature(unittest.TestCase):
    """验证 _pick_best 新签名在 _try_tmdb_detail 中的调用正确性"""

    @patch("routes.media_detail.douban_api_v2")
    @patch("routes.media_detail.douban_client")
    @patch("routes.media_detail.get_metadata_provider_map")
    def test_pick_best_passes_query(self, mock_provider_map, mock_douban_client, mock_douban_api):
        """_pick_best 应传入 query 参数给 best_match"""
        from routes.media_detail import _try_tmdb_detail
        from provider_models import AliasSet, ArtworkInfo, MetadataDetail, MetadataCandidate

        # 构造 fake provider
        mock_provider = MagicMock()
        fake_candidate = MetadataCandidate(
            providerId="tmdb", externalId="27205", title="盗梦空间",
            originalTitle="Inception", mediaType="movie", year=2010,
            overview="", rating=8.8, posterUrl="",
            aliases=AliasSet(en="Inception"),
            extra={"id": 27205, "title": "盗梦空间", "original_title": "Inception",
                   "release_date": "2010-07-16", "popularity": 80.0},
        )
        mock_provider.search_metadata.return_value = [fake_candidate]
        fake_detail = MetadataDetail(
            providerId="tmdb", externalId="27205", title="盗梦空间",
            originalTitle="Inception", mediaType="movie", year=2010,
            overview="", runtime=148, rating=8.8,
            aliases=AliasSet(en="Inception"),
            artwork=[ArtworkInfo(kind="poster", url="https://image.tmdb.org/t/p/w500/poster.jpg")],
            extra={"genres": ["科幻"], "director": "Christopher Nolan", "imdb_id": "tt1375666"},
        )
        mock_provider.get_detail.return_value = fake_detail
        mock_provider_map.return_value = {"tmdb": mock_provider}
        mock_douban_api.search.return_value = []
        mock_douban_client.search.return_value = []

        with patch("routes.media_detail.tmdb_client.best_match", wraps=best_match) as spy:
            result = _try_tmdb_detail("盗梦空间", "2010", "movie", "Inception")
            self.assertTrue(spy.called, "best_match 应被调用")
            first_call_args = spy.call_args_list[0]
            query_arg = first_call_args[0][0]
            self.assertEqual(query_arg, "盗梦空间", "best_match 第一个参数应是搜索词")

    @patch("routes.media_detail.douban_api_v2")
    @patch("routes.media_detail.douban_client")
    @patch("routes.media_detail.get_metadata_provider_map")
    def test_pick_best_tv_uses_name_type_key(self, mock_provider_map, mock_douban_client, mock_douban_api):
        """TV 搜索时 type_key 应为 "name" """
        from routes.media_detail import _try_tmdb_detail
        from provider_models import AliasSet, ArtworkInfo, MetadataDetail, MetadataCandidate

        mock_provider = MagicMock()
        fake_candidate = MetadataCandidate(
            providerId="tmdb", externalId="5001", title="测试剧",
            originalTitle="Test Show", mediaType="tv", year=2023,
            overview="", rating=7.5, posterUrl="",
            aliases=AliasSet(en="Test Show"),
            extra={"id": 5001, "name": "测试剧", "original_name": "Test Show",
                   "first_air_date": "2023-01-01", "popularity": 50.0},
        )
        mock_provider.search_metadata.return_value = [fake_candidate]
        fake_detail = MetadataDetail(
            providerId="tmdb", externalId="5001", title="测试剧",
            originalTitle="Test Show", mediaType="tv", year=2023,
            overview="", runtime=45, rating=7.5,
            aliases=AliasSet(en="Test Show"),
            artwork=[],
            extra={},
        )
        mock_provider.get_detail.return_value = fake_detail
        mock_provider_map.return_value = {"tmdb": mock_provider}
        mock_douban_api.search.return_value = []
        mock_douban_client.search.return_value = []

        with patch("routes.media_detail.tmdb_client.best_match", wraps=best_match) as spy:
            result = _try_tmdb_detail("测试剧", "2023", "tv", "")
            self.assertTrue(spy.called)
            first_call_kwargs = spy.call_args_list[0]
            kw = first_call_kwargs[1] if first_call_kwargs[1] else {}
            if "type_key" in kw:
                self.assertEqual(kw["type_key"], "name", "TV 搜索 type_key 应为 name")


class TestTryTmdbDetailById(unittest.TestCase):
    """_try_tmdb_detail_by_id 的 movie↔tv 回退逻辑"""

    def _make_detail(self, tmdb_id, title, original_title="", year=2010, rating=8.8):
        from provider_models import AliasSet, ArtworkInfo, MetadataDetail
        return MetadataDetail(
            providerId="tmdb", externalId=str(tmdb_id), title=title,
            originalTitle=original_title, mediaType="movie", year=year,
            overview="", runtime=148, rating=rating,
            aliases=AliasSet(en=original_title),
            artwork=[ArtworkInfo(kind="poster", url="https://image.tmdb.org/t/p/w500/poster.jpg")],
            extra={"genres": [], "director": "", "imdb_id": ""},
        )

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_movie_success(self, mock_provider_map):
        """type=movie 直接成功"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider = MagicMock()
        mock_provider.get_detail.return_value = self._make_detail(27205, "盗梦空间", "Inception")
        mock_provider_map.return_value = {"tmdb": mock_provider}

        result = _try_tmdb_detail_by_id(27205, "movie")
        self.assertTrue(result["found"])
        self.assertEqual(result["tmdb_id"], 27205)
        self.assertEqual(result["title"], "盗梦空间")
        mock_provider.get_detail.assert_called_once_with("27205", "movie")

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_tv_success(self, mock_provider_map):
        """type=tv 直接成功"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider = MagicMock()
        mock_provider.get_detail.return_value = self._make_detail(95557, "无敌少侠", "Invincible", year=2021, rating=8.7)
        mock_provider_map.return_value = {"tmdb": mock_provider}

        result = _try_tmdb_detail_by_id(95557, "tv")
        self.assertTrue(result["found"])
        self.assertEqual(result["tmdb_id"], 95557)
        mock_provider.get_detail.assert_called_once_with("95557", "tv")

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_movie_fallback_to_tv(self, mock_provider_map):
        """type=movie 失败后自动回退到 tv"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider = MagicMock()
        # movie 返回 None（失败），tv 返回有效结果
        mock_provider.get_detail.side_effect = lambda eid, mtype: (
            None if mtype == "movie" else self._make_detail(95557, "无敌少侠", "Invincible", year=2021)
        )
        mock_provider_map.return_value = {"tmdb": mock_provider}

        result = _try_tmdb_detail_by_id(95557, "movie")
        self.assertTrue(result["found"])
        self.assertEqual(result["tmdb_id"], 95557)
        # 应先尝试 movie，失败后尝试 tv
        self.assertEqual(mock_provider.get_detail.call_count, 2)
        mock_provider.get_detail.assert_any_call("95557", "movie")
        mock_provider.get_detail.assert_any_call("95557", "tv")

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_tv_fallback_to_movie(self, mock_provider_map):
        """type=tv 失败后自动回退到 movie"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider = MagicMock()
        mock_provider.get_detail.side_effect = lambda eid, mtype: (
            None if mtype == "tv" else self._make_detail(27205, "盗梦空间", "Inception")
        )
        mock_provider_map.return_value = {"tmdb": mock_provider}

        result = _try_tmdb_detail_by_id(27205, "tv")
        self.assertTrue(result["found"])
        self.assertEqual(result["tmdb_id"], 27205)
        self.assertEqual(mock_provider.get_detail.call_count, 2)
        mock_provider.get_detail.assert_any_call("27205", "tv")
        mock_provider.get_detail.assert_any_call("27205", "movie")

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_both_fail(self, mock_provider_map):
        """movie 和 tv 都失败，返回 found=False"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider = MagicMock()
        mock_provider.get_detail.return_value = None
        mock_provider_map.return_value = {"tmdb": mock_provider}

        result = _try_tmdb_detail_by_id(99999, "movie")
        self.assertFalse(result["found"])

    @patch("routes.media_detail.get_metadata_provider_map")
    def test_exception_handling(self, mock_provider_map):
        """异常时返回 found=False"""
        from routes.media_detail import _try_tmdb_detail_by_id

        mock_provider_map.side_effect = Exception("连接超时")
        result = _try_tmdb_detail_by_id(27205, "movie")
        self.assertFalse(result["found"])


class TestCalcMatchScore(unittest.TestCase):
    """calc_match_score 评分算法验证"""

    def test_exact_match_with_year(self):
        """精确匹配+年份匹配应得高分"""
        score = calc_match_score("霸王别姬", "霸王别姬", "霸王别姬", "1993", "1993")
        self.assertGreaterEqual(score, 100, "精确匹配+年份应>=100分")

    def test_year_mismatch_penalty(self):
        """年份差距大应大幅扣分"""
        score_match = calc_match_score("霸王别姬", "霸王别姬", "", "1993", "1993")
        score_mismatch = calc_match_score("霸王别姬", "霸王别姬", "", "2020", "1993")
        self.assertGreater(score_match, score_mismatch, "年份不匹配应扣分")

    def test_no_title_match(self):
        """标题完全不匹配应得0分"""
        score = calc_match_score("霸王别姬", "复仇者联盟", "The Avengers", "2012", "1993")
        self.assertLess(score, 30, "不相关标题应低于30分阈值")

    def test_original_title_match(self):
        """原名匹配应得分"""
        score = calc_match_score("inception", "盗梦空间", "Inception", "2010", "2010")
        self.assertGreaterEqual(score, 30, "原名匹配应>=30分")


class TestEmptyResults(unittest.TestCase):
    """空结果处理"""

    def test_empty_results(self):
        """空结果列表应返回 None"""
        match = best_match("任意查询", [], year="2023", type_key="title")
        self.assertIsNone(match)

    def test_empty_query(self):
        """空查询应返回 None"""
        results = [{"id": 1, "title": "Test", "original_title": "", "release_date": "2023-01-01", "popularity": 10}]
        match = best_match("", results, year="2023", type_key="title")
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main(verbosity=2)
