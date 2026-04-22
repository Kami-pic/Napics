"""ai_organizer.py 业务层单元测试"""
import pytest
from unittest.mock import patch, MagicMock


# ── 辅助：构造一个 mock AIClient ──

def _make_mock_client(enabled=True, features=None):
    """构造 mock AIClient 实例"""
    client = MagicMock()
    client.enabled = enabled
    _features = features or {}
    client.is_feature_enabled = lambda f: enabled and _features.get(f, False)
    return client


# ══════════════════════════════════════════
# a) ai_extract_episode — 单文件解析
# ══════════════════════════════════════════

class TestAiExtractEpisode:
    """测试 ai_extract_episode 单文件解析"""

    @patch("ai_organizer.get_ai_client")
    def test_normal_json_returns_correct_structure(self, mock_get_client):
        """mock ai_client 返回正常 JSON → 验证返回结构正确，包含 ai_parsed=True"""
        client = _make_mock_client(features={"extract_episode": True})
        client.chat_json.return_value = {
            "clean_title": "进击的巨人",
            "year": "2013",
            "season": 1,
            "episode": 5,
            "absolute_episode": None,
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode
        result = ai_extract_episode("[SubGroup] Shingeki no Kyojin S01E05 [1080p].mkv")

        assert result is not None
        assert result["clean_name"] == "进击的巨人"
        assert result["year"] == "2013"
        assert result["season"] == 1
        assert result["episode"] == 5
        assert result["absolute_episode"] is None
        assert result["ai_parsed"] is True

    @patch("ai_organizer.get_ai_client")
    def test_ai_returns_none(self, mock_get_client):
        """mock ai_client 返回 None → 验证返回 None"""
        client = _make_mock_client(features={"extract_episode": True})
        client.chat_json.return_value = None
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode
        result = ai_extract_episode("garbled_filename.mkv")
        assert result is None

    @patch("ai_organizer.get_ai_client")
    def test_feature_disabled_returns_none(self, mock_get_client):
        """AI 功能关闭时 → 验证返回 None"""
        client = _make_mock_client(features={"extract_episode": False})
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode
        result = ai_extract_episode("test.mkv")
        assert result is None
        # 确认没有调用 chat_json
        client.chat_json.assert_not_called()

    @patch("ai_organizer.get_ai_client")
    def test_clean_title_too_short_returns_none(self, mock_get_client):
        """AI 返回的 clean_title 太短（<2字符）→ 返回 None"""
        client = _make_mock_client(features={"extract_episode": True})
        client.chat_json.return_value = {
            "clean_title": "",
            "year": None,
            "season": None,
            "episode": None,
            "absolute_episode": None,
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode
        result = ai_extract_episode("x.mkv")
        assert result is None


# ══════════════════════════════════════════
# b) ai_extract_episode_batch — 批量解析
# ══════════════════════════════════════════

class TestAiExtractEpisodeBatch:
    """测试 ai_extract_episode_batch 批量解析"""

    @patch("ai_organizer.get_ai_client")
    def test_batch_3_files_all_parsed(self, mock_get_client):
        """传入 3 个文件名，mock 返回批量结果 → 验证 3 个都解析成功"""
        client = _make_mock_client(features={"extract_episode": True})
        client.chat_json.return_value = {
            "results": [
                {"index": 1, "clean_title": "进击的巨人", "year": "2013", "season": 1, "episode": 1, "absolute_episode": None},
                {"index": 2, "clean_title": "鬼灭之刃", "year": "2019", "season": 1, "episode": 2, "absolute_episode": None},
                {"index": 3, "clean_title": "咒术回战", "year": "2020", "season": None, "episode": None, "absolute_episode": 10},
            ]
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode_batch
        filenames = ["[Sub] Shingeki S01E01.mkv", "[Sub] Kimetsu S01E02.mkv", "[Sub] Jujutsu 10.mkv"]
        results = ai_extract_episode_batch(filenames)

        assert len(results) == 3
        assert results[0]["clean_name"] == "进击的巨人"
        assert results[0]["ai_parsed"] is True
        assert results[1]["clean_name"] == "鬼灭之刃"
        assert results[1]["ai_parsed"] is True
        assert results[2]["clean_name"] == "咒术回战"
        assert results[2]["absolute_episode"] == 10

    @patch("ai_organizer.get_ai_client")
    def test_batch_fallback_on_failure(self, mock_get_client):
        """批量失败时 → 验证自动 fallback 到逐个解析"""
        client = _make_mock_client(features={"extract_episode": True})
        # 第一次调用（批量）返回 None，触发 fallback
        # fallback 逐个调用时返回正常结果
        call_count = [0]
        def mock_chat_json(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 批量调用失败
                return None
            # 逐个 fallback 调用
            return {
                "clean_title": f"作品{call_count[0]-1}",
                "year": None,
                "season": None,
                "episode": call_count[0] - 1,
                "absolute_episode": None,
            }
        client.chat_json = mock_chat_json
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode_batch
        filenames = ["file1.mkv", "file2.mkv"]
        results = ai_extract_episode_batch(filenames)

        assert len(results) == 2
        # fallback 应该逐个调用，所以 call_count 应该是 1(批量) + 2(逐个) = 3
        assert call_count[0] == 3
        assert results[0] is not None
        assert results[0]["ai_parsed"] is True
        assert results[1] is not None

    @patch("ai_organizer.get_ai_client")
    def test_batch_feature_disabled(self, mock_get_client):
        """功能关闭时 → 返回全 None 列表"""
        client = _make_mock_client(features={"extract_episode": False})
        mock_get_client.return_value = client

        from ai_organizer import ai_extract_episode_batch
        results = ai_extract_episode_batch(["a.mkv", "b.mkv", "c.mkv"])
        assert results == [None, None, None]


# ══════════════════════════════════════════
# c) ai_select_scrape_candidate — 候选匹配
# ══════════════════════════════════════════

class TestAiSelectScrapeCandidate:
    """测试 ai_select_scrape_candidate 候选匹配"""

    @patch("ai_organizer.get_ai_client")
    def test_select_index_1(self, mock_get_client):
        """传入 3 个候选，mock 返回 index=1 → 验证返回正确"""
        client = _make_mock_client(features={"scrape_candidate": True})
        client.chat_json.return_value = {
            "selected_index": 1,
            "confidence": "high",
            "reason": "标题和年份完全匹配",
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_select_scrape_candidate
        candidates = [
            {"title": "进击的巨人 OVA", "year": "2013"},
            {"title": "进击的巨人", "year": "2013"},
            {"title": "进击的巨人 最终季", "year": "2022"},
        ]
        result = ai_select_scrape_candidate("进击的巨人", ["S01E01.mkv"], candidates)

        assert result is not None
        assert result["selected_index"] == 1
        assert result["confidence"] == "high"
        assert result["ai_selected"] is True

    def test_single_candidate_returns_none(self):
        """只有 1 个候选时 → 验证直接返回 None（不调 AI）"""
        from ai_organizer import ai_select_scrape_candidate
        result = ai_select_scrape_candidate("test", ["file.mkv"], [{"title": "test"}])
        assert result is None

    def test_empty_candidates_returns_none(self):
        """空候选列表 → 返回 None"""
        from ai_organizer import ai_select_scrape_candidate
        result = ai_select_scrape_candidate("test", ["file.mkv"], [])
        assert result is None

    @patch("ai_organizer.get_ai_client")
    def test_index_minus_1_returns_low_confidence(self, mock_get_client):
        """AI 返回 index=-1 → 验证返回 confidence=low"""
        client = _make_mock_client(features={"scrape_candidate": True})
        client.chat_json.return_value = {
            "selected_index": -1,
            "confidence": "low",
            "reason": "所有候选都不匹配",
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_select_scrape_candidate
        candidates = [
            {"title": "完全不相关A", "year": "2000"},
            {"title": "完全不相关B", "year": "2001"},
        ]
        result = ai_select_scrape_candidate("某部电影", ["movie.mkv"], candidates)

        assert result is not None
        assert result["selected_index"] == -1
        assert result["confidence"] == "low"

    @patch("ai_organizer.get_ai_client")
    def test_feature_disabled_returns_none(self, mock_get_client):
        """scrape_candidate 功能关闭 → 返回 None"""
        client = _make_mock_client(features={"scrape_candidate": False})
        mock_get_client.return_value = client

        from ai_organizer import ai_select_scrape_candidate
        candidates = [{"title": "A"}, {"title": "B"}]
        result = ai_select_scrape_candidate("test", ["file.mkv"], candidates)
        assert result is None

    @patch("ai_organizer.get_ai_client")
    def test_index_out_of_range_returns_none(self, mock_get_client):
        """AI 返回越界 index → 返回 None"""
        client = _make_mock_client(features={"scrape_candidate": True})
        client.chat_json.return_value = {
            "selected_index": 99,
            "confidence": "high",
            "reason": "test",
        }
        mock_get_client.return_value = client

        from ai_organizer import ai_select_scrape_candidate
        candidates = [{"title": "A"}, {"title": "B"}]
        result = ai_select_scrape_candidate("test", ["file.mkv"], candidates)
        assert result is None


# ══════════════════════════════════════════
# d) ai_library_diagnosis — 媒体库诊断
# ══════════════════════════════════════════

class TestAiLibraryDiagnosis:
    """测试 ai_library_diagnosis 媒体库诊断"""

    @patch("shared.config_m")
    @patch("ai_organizer.get_ai_client")
    def test_diagnosis_with_library_data(self, mock_get_client, mock_shared_config_m):
        """mock config_m.load_library 返回测试数据 + AI 返回诊断结果 → 验证结构正确"""
        client = _make_mock_client(features={"library_diagnosis": True})
        client.chat_json.return_value = {
            "health_score": 72,
            "priorities": [
                {"category": "missing_nfo", "severity": "high", "count": 10,
                 "suggestion": "批量刮削缺失 NFO 的视频", "action": "batch_scrape"},
            ],
            "summary": "媒体库整体状态良好，但有 10 个视频缺少元数据。",
        }
        mock_get_client.return_value = client

        mock_library = [
            {"file_name": "movie1.mkv", "has_nfo": True, "has_poster": True,
             "height": 1080, "codec": "x265", "quality_score": 80, "is_low_res": False},
            {"file_name": "movie2.mkv", "has_nfo": False, "has_poster": False,
             "height": 720, "codec": "x264", "quality_score": 40, "is_low_res": False},
            {"file_name": "movie3.mkv", "has_nfo": True, "has_poster": True,
             "height": 2160, "codec": "x265", "quality_score": 95, "is_low_res": False},
        ]
        mock_shared_config_m.load_library.return_value = mock_library

        from ai_organizer import ai_library_diagnosis
        result = ai_library_diagnosis()

        assert result is not None
        assert result["health_score"] == 72
        assert isinstance(result["priorities"], list)
        assert len(result["priorities"]) >= 1
        assert result["summary"]

    @patch("shared.config_m")
    @patch("ai_organizer.get_ai_client")
    def test_diagnosis_empty_library(self, mock_get_client, mock_shared_config_m):
        """空媒体库 → 返回默认提示"""
        client = _make_mock_client(features={"library_diagnosis": True})
        mock_get_client.return_value = client
        mock_shared_config_m.load_library.return_value = []

        from ai_organizer import ai_library_diagnosis
        result = ai_library_diagnosis()

        assert result is not None
        assert result["health_score"] == 0
        assert "媒体库为空" in result["summary"]

    @patch("ai_organizer.get_ai_client")
    def test_diagnosis_feature_disabled(self, mock_get_client):
        """library_diagnosis 功能关闭 → 返回 None"""
        client = _make_mock_client(features={"library_diagnosis": False})
        mock_get_client.return_value = client

        from ai_organizer import ai_library_diagnosis
        result = ai_library_diagnosis()
        assert result is None


# ══════════════════════════════════════════
# e) _collect_library_stats — 统计收集
# ══════════════════════════════════════════

class TestCollectLibraryStats:
    """测试 _collect_library_stats 统计收集"""

    def test_stats_collection(self):
        """验证统计收集正确"""
        from ai_organizer import _collect_library_stats
        library = [
            {"has_nfo": True, "has_poster": True, "height": 2160, "codec": "x265"},
            {"has_nfo": False, "has_poster": False, "height": 1080, "codec": "x264"},
            {"has_nfo": True, "has_poster": False, "height": 720, "codec": "x265"},
            {"has_nfo": False, "has_poster": True, "height": 0, "codec": None},
        ]
        stats = _collect_library_stats(library)

        assert stats["total_videos"] == 4
        assert "2/4" in stats["scrape_coverage"]
        assert "2/4" in stats["poster_coverage"]
        assert stats["resolution_distribution"]["4K"] == 1
        assert stats["resolution_distribution"]["1080p"] == 1
        assert stats["resolution_distribution"]["720p"] == 1
        assert stats["resolution_distribution"]["未知"] == 1
        assert "x265" in stats["codec_distribution"]
        assert stats["codec_distribution"]["x265"] == 2


# ══════════════════════════════════════════
# f) _normalize_extract_result — 结果标准化
# ══════════════════════════════════════════

class TestNormalizeExtractResult:
    """测试 _normalize_extract_result 结果标准化"""

    def test_normal_result(self):
        """正常结果标准化"""
        from ai_organizer import _normalize_extract_result
        result = _normalize_extract_result({
            "clean_title": "测试作品",
            "year": 2023,
            "season": "1",
            "episode": "5",
            "absolute_episode": None,
        })
        assert result["clean_name"] == "测试作品"
        assert result["year"] == "2023"
        assert result["season"] == 1
        assert result["episode"] == 5
        assert result["absolute_episode"] is None
        assert result["ai_parsed"] is True

    def test_empty_title_returns_none(self):
        """空标题返回 None"""
        from ai_organizer import _normalize_extract_result
        result = _normalize_extract_result({"clean_title": "", "year": None})
        assert result is None

    def test_invalid_int_fields(self):
        """无法转换为 int 的字段 → None"""
        from ai_organizer import _normalize_extract_result
        result = _normalize_extract_result({
            "clean_title": "测试",
            "year": None,
            "season": "abc",
            "episode": "not_a_number",
            "absolute_episode": [],
        })
        assert result["season"] is None
        assert result["episode"] is None
        assert result["absolute_episode"] is None
