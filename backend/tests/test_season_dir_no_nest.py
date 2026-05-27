"""测试：当 save_path 本身是季目录时，不应嵌套 Season XX。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))


def test_scrape_tv_v3_detects_season_folder():
    """当 folder_path 名称包含季号（如"第三季"），target_path 不应嵌套 Season。"""
    from unittest.mock import MagicMock, patch
    from scraper import _scrape_tv_v3

    with tempfile.TemporaryDirectory() as tmp:
        # 模拟"爱、死亡与机器人第三季"目录
        season_dir = os.path.join(tmp, "爱、死亡与机器人第三季")
        os.makedirs(season_dir)

        # 创建视频文件
        for i in range(1, 4):
            with open(os.path.join(season_dir, f"Love.Death.and.Robots.S03E{i:02d}.mkv"), "w") as f:
                f.write("")

        # Mock TMDB 客户端
        mock_tmdb = MagicMock()
        mock_detail = MagicMock()
        mock_detail.tmdb_id = 86831
        mock_detail.title = "爱，死亡和机器人"
        mock_detail.english_title = "Love, Death & Robots"
        mock_detail.total_seasons = 4
        mock_detail.poster_url = ""
        mock_detail.backdrop_url = ""
        mock_detail.seasons_info = [
            {"season_number": 1, "episode_count": 18},
            {"season_number": 2, "episode_count": 8},
            {"season_number": 3, "episode_count": 9},
            {"season_number": 4, "episode_count": 9},
        ]
        mock_tmdb.get_tv_detail.return_value = mock_detail
        mock_tmdb.proxy = ""

        # Mock read_nfo 返回有效的 tvshow.nfo
        with patch("scraper.read_nfo", return_value={"title": "爱，死亡和机器人", "tmdb_id": 86831}):
            with patch("scraper.write_tvshow_nfo"):
                with patch("scraper.write_episode_nfo"):
                    with patch("scraper.download_poster"):
                        results = _scrape_tv_v3(
                            folder_path=season_dir,
                            folder_name="爱、死亡与机器人第三季",
                            subdirs=[],
                            video_files=[f"Love.Death.and.Robots.S03E{i:02d}.mkv" for i in range(1, 4)],
                            tmdb_client_instance=mock_tmdb,
                            force=False, depth=0, max_depth=2, proxy="",
                            results={"self": None, "children": []},
                            dry_run=True, use_ai=False, whitelist=None,
                        )

        plan = results.get("plan", [])
        assert len(plan) == 3, f"应有 3 个 plan item，实际 {len(plan)}"

        for item in plan:
            tp = item.get("target_path", "")
            print(f"  {item['original_filename']} -> {os.path.relpath(tp, tmp)}")

            # target_path 不应包含 "Season 03" 子目录
            assert "Season 03" not in tp, \
                f"target_path 不应嵌套 Season 03: {tp}"

            # target_path 应直接在 season_dir 下
            assert os.path.dirname(tp) == season_dir, \
                f"target_path 应在 {season_dir} 下，实际在 {os.path.dirname(tp)}"

            # target_season_dir 应为 None（不需要新建季目录）
            assert item.get("target_season_dir") is None, \
                f"target_season_dir 应为 None，实际 {item.get('target_season_dir')}"


def test_scrape_tv_v3_normal_folder_still_nests():
    """当 folder_path 是普通剧集目录时，target_path 应正常嵌套 Season。"""
    from unittest.mock import MagicMock, patch
    from scraper import _scrape_tv_v3

    with tempfile.TemporaryDirectory() as tmp:
        # 模拟普通剧集目录
        show_dir = os.path.join(tmp, "爱，死亡和机器人")
        os.makedirs(show_dir)

        for i in range(1, 3):
            with open(os.path.join(show_dir, f"Love.Death.and.Robots.S03E{i:02d}.mkv"), "w") as f:
                f.write("")

        mock_tmdb = MagicMock()
        mock_detail = MagicMock()
        mock_detail.tmdb_id = 86831
        mock_detail.title = "爱，死亡和机器人"
        mock_detail.english_title = "Love, Death & Robots"
        mock_detail.total_seasons = 4
        mock_detail.poster_url = ""
        mock_detail.backdrop_url = ""
        mock_detail.seasons_info = [
            {"season_number": 1, "episode_count": 18},
            {"season_number": 2, "episode_count": 8},
            {"season_number": 3, "episode_count": 9},
        ]
        mock_tmdb.get_tv_detail.return_value = mock_detail
        mock_tmdb.proxy = ""

        with patch("scraper.read_nfo", return_value={"title": "爱，死亡和机器人", "tmdb_id": 86831}):
            results = _scrape_tv_v3(
                folder_path=show_dir,
                folder_name="爱，死亡和机器人",
                subdirs=[],
                video_files=[f"Love.Death.and.Robots.S03E{i:02d}.mkv" for i in range(1, 3)],
                tmdb_client_instance=mock_tmdb,
                force=False, depth=0, max_depth=2, proxy="",
                results={"self": None, "children": []},
                dry_run=True, use_ai=False, whitelist=None,
            )

        plan = results.get("plan", [])
        assert len(plan) == 2

        for item in plan:
            tp = item.get("target_path", "")
            # 普通目录应嵌套 Season 03
            assert "Season 03" in tp, \
                f"普通目录的 target_path 应包含 Season 03: {tp}"
            assert item.get("target_season_dir") == "Season 03"
