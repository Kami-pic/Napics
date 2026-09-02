"""标准名（影子名）从 NFO 生成的取值来源测试。

用户实际反馈：`动画番\\军火女王 Jormungand\\Season 01` 下 12 集的标准名分别是
「炎兔」「脉冲星」「奏出音乐的武器第一篇」…—— 全是**分集标题**，不是作品名。

根因：调用方按文件名里有没有 `SxxExx` 判 movie / tv，而 VCB-Studio 这类命名是
`[VCB-Studio] Jormungand [01][...].mkv`，判成了 movie；movie 分支取 NFO 的
`<title>`，在 episodedetails 里那是分集标题，作品名在 `<showtitle>`。

这里锁定：NFO 自称 episodedetails 时不许拿 `<title>` 当作品名；
同时电影（movie.nfo 无 showtitle）的行为不能被这条改动带偏。
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from renamer import generate_shadow_name_from_nfo  # noqa: E402


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _make_episode(folder, file_name, title, showtitle, season=1, episode=1):
    """写一个视频文件 + 同名 episodedetails NFO，返回视频路径"""
    video = os.path.join(folder, file_name)
    with open(video, "wb") as f:
        f.write(b"\x00")
    stem = os.path.splitext(file_name)[0]
    _write(os.path.join(folder, stem + ".nfo"), "\n".join([
        "<episodedetails>",
        f"  <title>{title}</title>",
        f"  <showtitle>{showtitle}</showtitle>",
        f"  <season>{season}</season>",
        f"  <episode>{episode}</episode>",
        "</episodedetails>",
    ]))
    return video


def _make_movie(folder, file_name, title, english_title="", year=""):
    video = os.path.join(folder, file_name)
    with open(video, "wb") as f:
        f.write(b"\x00")
    stem = os.path.splitext(file_name)[0]
    lines = ["<movie>", f"  <title>{title}</title>"]
    if english_title:
        lines.append(f"  <englishtitle>{english_title}</englishtitle>")
    if year:
        lines.append(f"  <year>{year}</year>")
    lines.append("</movie>")
    _write(os.path.join(folder, stem + ".nfo"), "\n".join(lines))
    return video


class TestEpisodeNfoUsesShowtitle:
    """episodedetails 的作品名必须取 showtitle"""

    def test_filename_without_sxxexx_still_uses_showtitle(self, tmp_path):
        """用户实际命名：文件名不带 SxxExx，调用方传 movie"""
        folder = tmp_path / "Season 01"
        folder.mkdir()
        video = _make_episode(
            str(folder), "[VCB-Studio] Jormungand [01][Ma10p_1080p][x265_flac].mkv",
            title="炎兔", showtitle="军火女王", season=1, episode=1)
        assert generate_shadow_name_from_nfo(video, str(folder), "movie") == "军火女王 S01E01"

    def test_episode_title_never_becomes_show_name(self, tmp_path):
        """同一目录多集，分集标题不许出现在标准名里"""
        folder = tmp_path / "Season 01"
        folder.mkdir()
        for idx, ep_title in enumerate(["炎兔", "脉冲星", "奏出音乐的武器 第一篇"], start=1):
            video = _make_episode(
                str(folder), f"[VCB-Studio] Jormungand [{idx:02d}].mkv",
                title=ep_title, showtitle="军火女王", season=1, episode=idx)
            shadow = generate_shadow_name_from_nfo(video, str(folder), "movie")
            assert shadow == f"军火女王 S01E{idx:02d}"
            assert ep_title not in shadow

    def test_tv_folder_type_unchanged(self, tmp_path):
        """显式传 tv 时行为不变"""
        folder = tmp_path / "Season 02"
        folder.mkdir()
        video = _make_episode(
            str(folder), "Jormungand.S02E13.mkv",
            title="奏出音乐的武器", showtitle="军火女王", season=2, episode=13)
        assert generate_shadow_name_from_nfo(video, str(folder), "tv") == "军火女王 S02E13"

    def test_collection_child_also_uses_showtitle(self, tmp_path):
        """聚合容器里的分集同样不许取分集标题"""
        folder = tmp_path / "合集"
        folder.mkdir()
        video = _make_episode(
            str(folder), "[Group] Show [05].mkv",
            title="第五话副标题", showtitle="某作品", season=1, episode=5)
        assert generate_shadow_name_from_nfo(video, str(folder), "collection") == "某作品 S01E05"


class TestMovieUnaffected:
    """movie.nfo 没有 showtitle，电影必须保持原行为"""

    def test_movie_keeps_title_and_year(self, tmp_path):
        folder = tmp_path / "动画电影"
        folder.mkdir()
        video = _make_movie(str(folder), "你的名字。 Your Name. (2016) 1080p.mp4",
                            title="你的名字。", english_title="Your Name.", year="2016")
        assert generate_shadow_name_from_nfo(video, str(folder), "movie") == "你的名字。 Your Name. (2016)"

    def test_no_nfo_returns_none(self, tmp_path):
        """没有 NFO 一律返回 None，不回退文件名清洗"""
        folder = tmp_path / "动画电影"
        folder.mkdir()
        video = os.path.join(str(folder), "无刮削的片子 (2020).mkv")
        with open(video, "wb") as f:
            f.write(b"\x00")
        assert generate_shadow_name_from_nfo(video, str(folder), "movie") is None


# ── 检索名同样不许用分集标题 ──

def _write_tvshow_nfo(folder, title, original="", english=""):
    lines = ["<tvshow>", f"  <title>{title}</title>"]
    if original:
        lines.append(f"  <originaltitle>{original}</originaltitle>")
    if english:
        lines.append(f"  <englishtitle>{english}</englishtitle>")
    lines.append("</tvshow>")
    _write(os.path.join(folder, "tvshow.nfo"), "\n".join(lines))


class TestSearchIndexNameForEpisodes:
    """build_search_index_name 走的是同一批 NFO，坑也一样"""

    def test_index_name_uses_showtitle(self, tmp_path):
        from clean_name_system import build_search_index_name

        work = tmp_path / "军火女王 Jormungand"
        season = work / "Season 01"
        season.mkdir(parents=True)
        name = "[VCB-Studio] Jormungand [01][Ma10p_1080p][x265_flac].mkv"
        _make_episode(str(season), name, title="炎兔", showtitle="军火女王")
        r = build_search_index_name(str(season / name), name)
        assert r is not None
        assert r.cn == "军火女王"
        # NFO 没有英文名，但作品级目录名里有 —— 视频在 Season 01 下，
        # 只看 dirname 只能拿到「Season 01」
        assert r.en == "Jormungand"
        assert "炎兔" not in r.display

    def test_falls_back_to_tvshow_nfo_when_showtitle_empty(self, tmp_path):
        """实测「只有我不在的街道…」的分集 NFO 里 showtitle 是空的"""
        from clean_name_system import build_search_index_name

        work = tmp_path / "只有我不在的街道只有我不在的城市 Boku_Dake_ga_Inai_Machi"
        work.mkdir()
        _write_tvshow_nfo(str(work), "只有我不存在的城市",
                          original="僕だけがいない街", english="ERASED")
        name = "[TSDM][Boku_Dake_ga_Inai_Machi][BDrip][01][GB][1080P].mp4"
        _make_episode(str(work), name, title="第 1 集", showtitle="")
        r = build_search_index_name(str(work / name), name)
        assert r is not None
        assert r.cn == "只有我不存在的城市"
        assert r.en == "ERASED"
        assert "第" not in r.cn

    def test_season_level_tvshow_nfo_not_forced_onto_other_season(self, tmp_path):
        """军火女王根目录的 tvshow.nfo 被第二季刮削覆盖成「军火女王 第二季」，
        showtitle 说的是「军火女王」，就不该把第二季的原名安过来"""
        from clean_name_system import build_search_index_name

        work = tmp_path / "军火女王 Jormungand"
        season = work / "Season 01"
        season.mkdir(parents=True)
        _write_tvshow_nfo(str(work), "军火女王 第二季", original="ヨルムンガンド PERFECT ORDER")
        name = "[VCB-Studio] Jormungand [01].mkv"
        _make_episode(str(season), name, title="炎兔", showtitle="军火女王")
        r = build_search_index_name(str(season / name), name)
        assert r.cn == "军火女王"
        assert "第二季" not in r.display
        assert "PERFECT ORDER" not in (r.original or "")


class TestRegenerateStandardNames:
    """用户点「生成标准名」：已有 nfo 值必须被重算掉，手填的必须留住"""

    def _one_season(self, tmp_path):
        work = tmp_path / "军火女王 Jormungand"
        season = work / "Season 01"
        season.mkdir(parents=True)
        items = []
        for idx, ep_title in enumerate(["炎兔", "脉冲星", "奏出音乐的武器 第一篇"], start=1):
            name = f"[VCB-Studio] Jormungand [{idx:02d}].mkv"
            video = _make_episode(str(season), name, title=ep_title,
                                  showtitle="军火女王", episode=idx)
            items.append({
                "file_path": video, "file_name": name,
                # 库里现存的错值：分集标题被当成作品名，来源标着 nfo
                "shadow_name": ep_title, "shadow_name_source": "nfo",
            })
        return str(work), items

    def test_overwrites_existing_nfo_values(self, tmp_path):
        from scan_name_filler import regenerate_standard_names

        work, library = self._one_season(tmp_path)
        r = regenerate_standard_names(library, work, is_folder=True)
        assert r["matched"] == 3
        assert r["updated"] == 3
        for idx, item in enumerate(library, start=1):
            assert item["shadow_name"] == f"军火女王 S01E{idx:02d}"

    def test_manual_is_kept(self, tmp_path):
        from scan_name_filler import regenerate_standard_names

        work, library = self._one_season(tmp_path)
        library[0]["shadow_name"] = "我自己起的名字"
        library[0]["shadow_name_source"] = "manual"
        r = regenerate_standard_names(library, work, is_folder=True)
        assert r["skipped"] == 1
        assert r["updated"] == 2
        assert library[0]["shadow_name"] == "我自己起的名字"

    def test_unknown_path_reports_zero_matched(self, tmp_path):
        from scan_name_filler import regenerate_standard_names

        _, library = self._one_season(tmp_path)
        r = regenerate_standard_names(library, str(tmp_path / "不存在的目录"), is_folder=True)
        assert r == {"updated": 0, "matched": 0, "skipped": 0, "shadow_name": ""}
