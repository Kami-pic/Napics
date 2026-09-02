"""整理重命名：一季多集不许算出同一个文件名。

真机现象（军火女王 `动画番\\军火女王 Jormungand`）：
`rename_videos_in_folder` 的预览里 Season 01 下 12 个视频的 new_name **全是
`Season 01 1080p.mkv`**，执行下去会互相覆盖。三个原因叠在一起：

1. `classify_folder` 把季目录判成 `collection`（合集）—— 因为"每个视频都有同名 NFO"
   被当成多部独立电影的信号，可 Kodi/Emby 风格的番剧刮削本来就是每集一个 NFO；
   合集分支不带集号。
2. 剧名兜底用当前目录名，递归进 `Season 01` 后剧名就成了「Season 01」。
3. 季号只看 NFO，而实测 Season 02 目录里每集写的都是 `season=1`。

这里锁定修复后的行为：唯一文件名、季号来自目录、算不出集号就拒绝改名。
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from organizer import classify_folder  # noqa: E402
from renamer import rename_videos_in_folder  # noqa: E402


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _episode(folder, file_name, title, showtitle, season, episode, tmdb_id=46279):
    video = os.path.join(folder, file_name)
    with open(video, "wb") as f:
        f.write(b"\x00")
    _write(os.path.join(folder, os.path.splitext(file_name)[0] + ".nfo"), "\n".join([
        "<episodedetails>",
        f"  <title>{title}</title>",
        f"  <showtitle>{showtitle}</showtitle>",
        f"  <season>{season}</season>",
        f"  <episode>{episode}</episode>",
        f'  <uniqueid type="tmdb">{tmdb_id}</uniqueid>',
        "</episodedetails>",
    ]))
    return video


def _tvshow(folder, title, original="", tmdb_id=46279):
    lines = ["<tvshow>", f"  <title>{title}</title>"]
    if original:
        lines.append(f"  <originaltitle>{original}</originaltitle>")
    lines.append(f'  <uniqueid type="tmdb">{tmdb_id}</uniqueid>')
    lines.append("</tvshow>")
    _write(os.path.join(folder, "tvshow.nfo"), "\n".join(lines))


def _season_folder(root, season_no, episodes, showtitle="军火女王", nfo_season=None):
    """造一个 `Season 0X` 目录。nfo_season 用来模拟 NFO 里写错的季号"""
    folder = os.path.join(root, f"Season {season_no:02d}")
    os.makedirs(folder, exist_ok=True)
    for ep in episodes:
        _episode(folder, f"[VCB-Studio] Jormungand [{ep:02d}][Ma10p_1080p][x265_flac].mkv",
                 title=f"第{ep}话", showtitle=showtitle,
                 season=nfo_season if nfo_season is not None else season_no, episode=ep)
    return folder


def _videos(results):
    return [r for r in results if not r.get("is_folder")]


class TestNoCollision:
    def test_each_episode_gets_unique_name(self, tmp_path):
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王")
        _season_folder(str(work), 1, range(1, 13))
        results = rename_videos_in_folder(str(work), None, True, [])
        names = [r["new_name"] for r in _videos(results)]
        assert len(names) == 12
        assert len(set(names)) == 12, f"文件名撞了: {names}"
        for ep, name in enumerate(sorted(names), start=1):
            assert f"S01E{ep:02d}" in name

    def test_show_title_not_taken_from_season_dir(self, tmp_path):
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王")
        _season_folder(str(work), 1, [1, 2])
        results = rename_videos_in_folder(str(work), None, True, [])
        for r in _videos(results):
            assert "Season" not in r["new_name"].replace("Season 01", "")
            assert r["new_name"].startswith("军火女王")

    def test_episode_title_not_used_as_show_name(self, tmp_path):
        """分集标题（「第1话」）不许当作品名"""
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王")
        _season_folder(str(work), 1, [1, 2, 3])
        results = rename_videos_in_folder(str(work), None, True, [])
        for r in _videos(results):
            assert "第1话" not in r["new_name"]
            assert "第2话" not in r["new_name"]


class TestSeasonNumberFromDirectory:
    def test_directory_wins_over_nfo(self, tmp_path):
        """Season 02 目录里 NFO 写着 season=1（实测军火女王就是这样）"""
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王")
        _season_folder(str(work), 2, [13, 14, 15], nfo_season=1)
        results = rename_videos_in_folder(str(work), None, True, [])
        # 分辨率后缀取决于媒体库里的 resolution，这里没传 library，所以只比对名字主体
        names = sorted(os.path.splitext(r["new_name"])[0] for r in _videos(results))
        assert names == ["军火女王 S02E13", "军火女王 S02E14", "军火女王 S02E15"], names

    def test_two_seasons_do_not_collide(self, tmp_path):
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王")
        _season_folder(str(work), 1, range(1, 13))
        _season_folder(str(work), 2, range(13, 25), nfo_season=1)
        results = rename_videos_in_folder(str(work), None, True, [])
        names = [r["new_name"] for r in _videos(results)]
        assert len(names) == 24
        assert len(set(names)) == 24


class TestRefuseWhenEpisodeUnknown:
    def test_missing_episode_number_is_skipped(self, tmp_path):
        """连集号都拿不到时不许硬命名 —— 那会让整组撞成一个名字"""
        season = tmp_path / "军火女王 Jormungand" / "Season 01"
        season.mkdir(parents=True)
        for name in ("part_a.mkv", "part_b.mkv"):
            video = season / name
            video.write_bytes(b"\x00")
            _write(str(season / (name[:-4] + ".nfo")), "\n".join([
                "<episodedetails>",
                "  <title>无集号</title>",
                "  <showtitle>军火女王</showtitle>",
                "</episodedetails>",
            ]))
        results = rename_videos_in_folder(str(season), None, True, [])
        vids = _videos(results)
        assert vids, "应当返回条目而不是静默丢弃"
        for r in vids:
            assert r.get("skipped") is True
            assert r.get("skip_reason") == "no_episode_number"
            assert r["new_name"] == r["old_name"]


class TestFolderClassification:
    def test_season_dir_is_not_a_collection(self, tmp_path):
        season = tmp_path / "Season 01"
        season.mkdir()
        for ep in range(1, 6):
            _episode(str(season), f"[VCB-Studio] Jormungand [{ep:02d}].mkv",
                     title=f"第{ep}话", showtitle="军火女王", season=1, episode=ep)
        assert classify_folder(str(season), []).get("type") == "season"

    def test_flat_anime_with_per_episode_nfo_is_tv(self, tmp_path):
        """没有季目录、每集一个 NFO 平铺的番剧也不该判成合集"""
        work = tmp_path / "只有我不在的街道 Boku_Dake_ga_Inai_Machi"
        work.mkdir()
        for ep in range(1, 7):
            _episode(str(work), f"[TSDM][Boku][{ep:02d}][1080P].mp4",
                     title=f"第 {ep} 集", showtitle="只有我不存在的城市", season=1, episode=ep)
        assert classify_folder(str(work), []).get("type") == "tv"


class TestFolderTitleNotTaintedBySeason:
    def test_work_folder_keeps_name_when_tvshow_nfo_says_season_two(self, tmp_path):
        """tvshow.nfo 被第二季刮削覆盖成「军火女王 第二季」时，作品目录名不该跟着变"""
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王 第二季", original="ヨルムンガンド PERFECT ORDER")
        _season_folder(str(work), 1, [1, 2])
        results = rename_videos_in_folder(str(work), None, True, [])
        folder_rows = [r for r in results if r.get("is_folder")]
        for r in folder_rows:
            assert "第二季" not in r["new_name"]
            assert "PERFECT ORDER" not in r["new_name"]

    def test_season_dir_named_after_work_not_after_tainted_nfo(self, tmp_path):
        work = tmp_path / "军火女王 Jormungand"
        work.mkdir()
        _tvshow(str(work), "军火女王 第二季", original="ヨルムンガンド PERFECT ORDER")
        _season_folder(str(work), 1, [1, 2])
        results = rename_videos_in_folder(str(work), None, True, [])
        season_rows = [r for r in results if r.get("old_name") == "Season 01"]
        assert season_rows, "季目录应出现在结果里"
        assert season_rows[0]["new_name"] == "军火女王 Season 01"
