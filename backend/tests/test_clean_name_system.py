"""清洗名系统测试 — 覆盖所有业务场景"""
import pytest
from clean_name_system import (
    strip_noise, split_names, extract_suffix, compose_display,
    clean_from_filename, clean_from_scrape, clean_for_folder,
    clean_for_season_search, clean_for_episode_search,
    parse_legacy_clean_name, safe_update_clean_name,
    CleanNameResult,
)


# ════════════════════════════════════════
# Level 0：strip_noise 去噪
# ════════════════════════════════════════

class TestStripNoise:
    """去噪：从脏文件名中提取作品名"""

    def test_basic_brackets(self):
        """去方括号标签"""
        result = strip_noise("[字幕组][进击的巨人][01][1080p][x265].mkv")
        assert "进击的巨人" in result
        assert "1080p" not in result

    def test_ad_site(self):
        """去广告站名和 URL"""
        result = strip_noise("电影天堂www.dytt.com.盗梦空间.Inception.2010.BD1080P.中英双字.mkv")
        assert "盗梦空间" in result
        assert "Inception" in result
        assert "2010" in result
        assert "www" not in result
        assert "电影天堂" not in result

    def test_quality_tags(self):
        """去质量标签"""
        result = strip_noise("Inception.2010.BluRay.1080p.x265.DTS-HD.mkv")
        assert "Inception" in result
        assert "2010" in result
        assert "BluRay" not in result
        assert "x265" not in result

    def test_chinese_only(self):
        """纯中文文件名"""
        result = strip_noise("盗梦空间.mkv")
        assert result == "盗梦空间"

    def test_english_only(self):
        """纯英文文件名"""
        result = strip_noise("Inception.2010.mkv")
        assert "Inception" in result

    def test_mixed_cn_en(self):
        """中英混合"""
        result = strip_noise("盗梦空间.Inception.2010.mkv")
        assert "盗梦空间" in result
        assert "Inception" in result

    def test_japanese_with_kana(self):
        """日文文件名（含假名）"""
        result = strip_noise("千と千尋の神隠し.mkv")
        assert "千と千尋の神隠し" in result

    def test_subtitle_group_brackets(self):
        """字幕组方括号全包裹"""
        result = strip_noise("[Lilith-Raws][鬼灭之刃][01][1080p][x265].mkv")
        assert "鬼灭之刃" in result

    def test_preserves_year(self):
        """保留年份"""
        result = strip_noise("Inception.2010.mkv")
        assert "2010" in result

    def test_preserves_episode_number(self):
        """保留集号"""
        result = strip_noise("进击的巨人 S01E03.mkv")
        assert "S01E03" in result or "01" in result

    def test_empty_after_clean(self):
        """全部被清洗后从方括号提取"""
        result = strip_noise("[YIFY][1080p][x265].mkv")
        # 应该有某种 fallback
        assert result  # 不为空


# ════════════════════════════════════════
# Level 1：split_names 语言分离
# ════════════════════════════════════════

class TestSplitNames:
    """语言分离：提取 cn/en/original/year"""

    def test_cn_en_year(self):
        """中英文 + 年份"""
        r = split_names("盗梦空间 Inception 2010")
        assert r["cn"] == "盗梦空间"
        assert r["en"] == "Inception"
        assert r["year"] == "2010"

    def test_cn_only(self):
        """纯中文"""
        r = split_names("进击的巨人")
        assert r["cn"] == "进击的巨人"
        assert r["en"] == ""

    def test_en_only(self):
        """纯英文"""
        r = split_names("Inception")
        assert r["cn"] == ""
        assert r["en"] == "Inception"

    def test_japanese_kana(self):
        """日文（含假名）→ original"""
        r = split_names("千と千尋の神隠し")
        assert r["original"] == "千と千尋の神隠し"

    def test_mixed_jp_cn_en(self):
        """日中英混合"""
        r = split_names("進撃の巨人 进击的巨人 Attack on Titan")
        assert r["original"] == "進撃の巨人"
        assert "进击的巨人" in r["cn"] or "进击" in r["cn"]
        assert "Attack" in r["en"]

    def test_year_in_parens(self):
        """括号年份"""
        r = split_names("盗梦空间 (2010)")
        assert r["cn"] == "盗梦空间"
        assert r["year"] == "2010"

    def test_traditional_chinese(self):
        """繁体中文转简体"""
        r = split_names("進擊的巨人")
        # 繁体应转简体到 cn，原始繁体到 original
        assert "进击" in r["cn"] or "進擊" in r["original"]

    def test_empty(self):
        """空输入"""
        r = split_names("")
        assert r["cn"] == ""
        assert r["en"] == ""
        assert r["original"] == ""
        assert r["year"] == ""


# ════════════════════════════════════════
# Level 2：extract_suffix 附加信息
# ════════════════════════════════════════

class TestExtractSuffix:
    """提取季集号和特殊标记"""

    def test_season_episode(self):
        """标准季集号"""
        r = extract_suffix("进击的巨人 S01E03.mkv")
        assert r["suffix"] == "S01E03"
        assert r["season"] == 1
        assert r["episode"] == 3

    def test_absolute_episode(self):
        """绝对集号"""
        r = extract_suffix("进击的巨人 - 25.mkv")
        # parse_filename 应该能识别
        assert r["episode"] is not None or r["suffix"]

    def test_special_ova(self):
        """OVA 标记"""
        r = extract_suffix("进击的巨人 OVA.mkv")
        assert r["special"] == "OVA"

    def test_special_movie(self):
        """剧场版标记"""
        r = extract_suffix("进击的巨人 剧场版.mkv")
        assert r["special"] == "剧场版"

    def test_override(self):
        """手动覆盖季集号"""
        r = extract_suffix("random.mkv", season_override=2, episode_override=5)
        assert r["suffix"] == "S02E05"
        assert r["season"] == 2
        assert r["episode"] == 5


# ════════════════════════════════════════
# Level 3：compose_display 组装展示名
# ════════════════════════════════════════

class TestComposeDisplay:
    """组装 UI 展示名"""

    def test_cn_only(self):
        assert compose_display("进击的巨人") == "进击的巨人"

    def test_cn_with_suffix(self):
        assert compose_display("进击的巨人", suffix="S01E03") == "进击的巨人 S01E03"

    def test_cn_en(self):
        assert compose_display("进击的巨人", "Attack on Titan", include_en=True) == "进击的巨人 Attack on Titan"

    def test_cn_en_same(self):
        """cn 和 en 相同时不重复"""
        assert compose_display("Inception", "Inception", include_en=True) == "Inception"

    def test_fallback_to_en(self):
        """cn 为空时用 en"""
        assert compose_display("", "Inception") == "Inception"

    def test_empty(self):
        assert compose_display("") == ""

    def test_season_suffix(self):
        assert compose_display("进击的巨人", suffix="第3季") == "进击的巨人 第3季"


# ════════════════════════════════════════
# 统一入口测试
# ════════════════════════════════════════

class TestCleanFromFilename:
    """从文件名解析清洗名"""

    def test_basic_movie(self):
        """电影文件名"""
        r = clean_from_filename("盗梦空间.Inception.2010.BluRay.1080p.x265.mkv")
        assert r.cn == "盗梦空间"
        assert r.en == "Inception"
        assert r.year == "2010"
        assert r.source == "parsed"

    def test_tv_episode(self):
        """剧集文件名"""
        r = clean_from_filename("进击的巨人 S01E03.mkv")
        assert "进击的巨人" in r.cn
        assert r.suffix == "S01E03"
        assert "S01E03" in r.display

    def test_with_parent_names(self):
        """继承父文件夹名称"""
        r = clean_from_filename(
            "[SubGroup] 01.mkv",
            parent_cn="进击的巨人",
            parent_en="Attack on Titan",
        )
        assert r.cn == "进击的巨人"
        assert r.en == "Attack on Titan"

    def test_japanese_anime(self):
        """日文动画"""
        r = clean_from_filename("千と千尋の神隠し.mkv")
        assert r.original  # 应该有日文原名


class TestCleanFromScrape:
    """从刮削结果构建清洗名"""

    def test_tmdb_movie(self):
        """TMDB 电影刮削"""
        r = clean_from_scrape(
            title="盗梦空间",
            english_title="Inception",
            year="2010",
            source="tmdb",
        )
        assert r.cn == "盗梦空间"
        assert r.en == "Inception"
        assert r.year == "2010"
        assert r.source == "tmdb"
        assert r.confidence == "high"

    def test_tmdb_tv_episode(self):
        """TMDB 剧集刮削"""
        r = clean_from_scrape(
            title="进击的巨人",
            english_title="Attack on Titan",
            filename="进击的巨人 S01E03.mkv",
            source="tmdb",
        )
        assert r.cn == "进击的巨人"
        assert r.en == "Attack on Titan"
        assert r.suffix == "S01E03"

    def test_japanese_title(self):
        """日文标题"""
        r = clean_from_scrape(
            title="千と千尋の神隠し",
            english_title="Spirited Away",
            source="tmdb",
        )
        assert r.original == "千と千尋の神隠し"
        assert r.en == "Spirited Away"

    def test_english_only_title(self):
        """纯英文标题"""
        r = clean_from_scrape(
            title="Inception",
            original_title="Inception",
            source="tmdb",
        )
        assert r.en == "Inception"


class TestCleanForFolder:
    """文件夹级清洗名"""

    def test_movie_folder_with_shadow(self):
        """有 shadow_name 的电影文件夹"""
        r = clean_for_folder(
            folder_name="盗梦空间.Inception.2010.BluRay",
            shadow_name="盗梦空间 Inception (2010)",
            folder_type="movie",
        )
        assert r.cn == "盗梦空间"
        assert "Inception" in r.en
        assert r.year == "2010"

    def test_tv_folder_no_shadow(self):
        """无 shadow_name 的 TV 文件夹"""
        r = clean_for_folder(
            folder_name="进击的巨人.Attack.on.Titan",
            folder_type="tv",
        )
        assert "进击的巨人" in r.cn or "进击" in r.cn

    def test_season_folder(self):
        """季文件夹"""
        r = clean_for_folder(
            folder_name="Season 3",
            folder_type="season",
            parent_cn="进击的巨人",
            parent_en="Attack on Titan",
            season_num=3,
        )
        assert r.cn == "进击的巨人"
        assert r.suffix == "第3季"
        assert "进击的巨人 第3季" in r.display


class TestSearchQueries:
    """搜索词构造"""

    def test_season_search(self):
        """季搜索词"""
        r = clean_for_season_search("进击的巨人", "Attack on Titan", season=3)
        assert r["cn_query"] == "进击的巨人 第3季"
        assert r["en_query"] == "Attack on Titan S03"

    def test_episode_search(self):
        """单集搜索词"""
        r = clean_for_episode_search("进击的巨人", "Attack on Titan", season=1, episode=3)
        assert r["cn_query"] == "进击的巨人 S01E03"
        assert r["en_query"] == "Attack on Titan S01E03"


class TestLegacyCompat:
    """旧数据兼容"""

    def test_parse_old_format(self):
        """旧格式 clean_name 反向解析"""
        item = {"clean_name": "进击的巨人 S01E03", "clean_name_source": "scrape"}
        r = parse_legacy_clean_name(item)
        assert "进击的巨人" in r.cn
        assert r.suffix == "S01E03"
        assert r.source == "scrape"

    def test_parse_new_format(self):
        """新格式直接读取"""
        item = {
            "clean_name": "进击的巨人 S01E03",
            "clean_name_source": "tmdb",
            "clean_name_cn": "进击的巨人",
            "clean_name_en": "Attack on Titan",
            "clean_name_original": "進撃の巨人",
        }
        r = parse_legacy_clean_name(item)
        assert r.cn == "进击的巨人"
        assert r.en == "Attack on Titan"
        assert r.original == "進撃の巨人"


class TestSafeUpdate:
    """优先级保护写入"""

    def test_higher_priority_overwrites(self):
        """高优先级覆盖低优先级"""
        item = {"clean_name": "旧名", "clean_name_source": "parsed"}
        new = CleanNameResult(cn="新名", en="New", display="新名", source="tmdb")
        assert safe_update_clean_name(item, new) is True
        assert item["clean_name"] == "新名"
        assert item["clean_name_cn"] == "新名"

    def test_lower_priority_rejected(self):
        """低优先级不覆盖高优先级"""
        item = {"clean_name": "手动名", "clean_name_source": "manual"}
        new = CleanNameResult(cn="自动名", display="自动名", source="parsed")
        assert safe_update_clean_name(item, new) is False
        assert item["clean_name"] == "手动名"

    def test_same_priority_overwrites(self):
        """同优先级覆盖"""
        item = {"clean_name": "旧刮削", "clean_name_source": "scrape"}
        new = CleanNameResult(cn="新刮削", display="新刮削", source="scrape")
        assert safe_update_clean_name(item, new) is True
        assert item["clean_name"] == "新刮削"


# ════════════════════════════════════════
# 发布组尾缀与搜索索引名（曾出问题的点）
# ════════════════════════════════════════

class TestUnknownReleaseGroupStripped:
    """_KNOWN_GROUPS 是白名单，覆盖不到的发布组会残留并被切成垃圾尾缀。

    实际案例：`Killing.Me.Softly.2002...x264-BARC0DE.mkv`
    清洗成 `Killing Me Softly BARC 0 DE`，清洗名和标准名同时被污染。
    """

    def test_unknown_group_with_digit_removed(self):
        from clean_name_system import strip_noise

        result = strip_noise("Killing.Me.Softly.2002.1080p.BluRay.DTS-HD.x264-BARC0DE.mkv")
        assert "BARC" not in result
        assert "Killing Me Softly" in result

    def test_hyphenated_title_preserved(self):
        """片名本身带连字符的不能被当成发布组剥掉"""
        from clean_name_system import strip_noise

        for filename in ("X-MEN.mkv", "Spider-Man.mkv", "WALL-E.2008.1080p.BluRay.x264.mkv"):
            result = strip_noise(filename)
            assert result.strip(), f"{filename} 被清空了"
            # 首个单词必须还在
            head = filename.split(".")[0].split("-")[0]
            assert head.lower() in result.lower(), f"{filename} -> {result}"

    def test_organized_name_untouched(self):
        from clean_name_system import strip_noise

        result = strip_noise("珍珠港 Pearl Harbor (2001).mkv")
        assert "珍珠港" in result
        assert "Pearl Harbor" in result


class TestBuildSearchIndexName:
    """搜索索引名取名优先级：NFO → 文件夹名补齐 → 文件名。

    实际案例：`爱情与灵药 (2010).mp4` 文件名里没有英文名，
    但目录 `爱情与灵药 Love & Other Drugs (2010)` 里有；只看文件名会漏掉英文名。
    """

    def test_folder_supplements_missing_english(self, tmp_path):
        from clean_name_system import build_search_index_name

        folder = tmp_path / "爱情与灵药 Love & Other Drugs (2010)"
        folder.mkdir()
        video = folder / "爱情与灵药 (2010).mp4"
        video.write_bytes(b"\x00")

        result = build_search_index_name(str(video))
        assert result is not None
        assert result.cn == "爱情与灵药"
        assert "Love" in result.en

    def test_generic_folder_not_used_as_title(self, tmp_path):
        """视频直接放在 media 这类通用目录下，目录名不能被当成片名"""
        from clean_name_system import build_search_index_name

        folder = tmp_path / "media"
        folder.mkdir()
        video = folder / "Tenet.2020.1080p.BluRay.x264-WiKi.mkv"
        video.write_bytes(b"\x00")

        result = build_search_index_name(str(video))
        assert result is not None
        assert result.en.lower().startswith("tenet")
        assert "media" not in result.en.lower()
