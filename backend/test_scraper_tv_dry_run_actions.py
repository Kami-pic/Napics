import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

from nfo_handler import write_episode_nfo, write_tvshow_nfo
from scraper import _scrape_tv_v3
from tmdb_client import ScrapeResult


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _with_temp_dir(name, test_fn):
    tmp_dir = Path(os.getcwd()) / f"{name}_{uuid.uuid4().hex[:8]}"
    tmp_dir.mkdir()
    try:
        test_fn(tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class FakeTMDBClient:
    def get_tv_detail(self, tmdb_id):
        return SimpleNamespace(
            tmdb_id=tmdb_id,
            title="四月是你的谎言",
            english_title="Your Lie in April",
            total_seasons=1,
            seasons_info=[{"season_number": 1, "episode_count": 22}],
        )

    def get_episode_detail(self, tmdb_id, season, episode):
        return SimpleNamespace(episode_title=f"Episode {episode}")


def test_scrape_tv_v3_dry_run_skips_move_and_episode_nfo_when_target_already_matches():
    def run(tmp_dir):
        show_dir = tmp_dir / "视频" / "动画番" / "四月是你的谎言"
        video_path = show_dir / "Season 01" / "四月是你的谎言 - S01E01 - Episode 1.mp4"
        _touch(video_path)

        tv_scrape = ScrapeResult(
            tmdb_id=61663,
            media_type="tv",
            title="四月是你的谎言",
            original_title="四月是你的谎言",
            english_title="Your Lie in April",
            season_number=1,
            episode_number=1,
        )
        ep_scrape = ScrapeResult(
            tmdb_id=61663,
            media_type="episode",
            title="Episode 1",
            episode_title="Episode 1",
            season_number=1,
            episode_number=1,
        )
        write_tvshow_nfo(str(show_dir), tv_scrape)
        write_episode_nfo(str(video_path), ep_scrape, showtitle="四月是你的谎言")

        result = _scrape_tv_v3(
            str(show_dir),
            "四月是你的谎言",
            ["Season 01"],
            [],
            FakeTMDBClient(),
            force=True,
            depth=0,
            max_depth=2,
            proxy="",
            results={"self": None, "children": []},
            dry_run=True,
            use_ai=False,
            whitelist=None,
        )

        actionable = [item for item in result["plan"] if item.get("mapped")]
        assert len(actionable) == 1
        assert actionable[0]["actions"] == ["write_shadow"]
        assert result["summary"]["will_process"] == 0
        assert result["summary"]["files_to_move"] == 0
        assert result["summary"]["nfo_to_write"] == 0
        assert result["summary"]["shadows_to_fill"] == 1

    _with_temp_dir("scraper_tv_dry_run_actions", run)
