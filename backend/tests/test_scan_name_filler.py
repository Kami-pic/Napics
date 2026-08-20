"""扫描期填名测试。

用户实际反馈：每次清空缓存重新扫描后，大部分检索名和标准名都丢了。
根因是 /scan 只调 clean_from_filename(file_name)，既不看 NFO 也不看文件夹名，
而这两个名字的主要来源就是扫描。这里锁定修复后的取名优先级与优先级保护。
"""

import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from scan_name_filler import fill_names_for_item, fill_search_index_name  # noqa: E402


def _write_movie_nfo(folder, title, english_title="", year="", original_title=""):
    lines = ["<movie>", f"  <title>{title}</title>"]
    if original_title:
        lines.append(f"  <originaltitle>{original_title}</originaltitle>")
    if english_title:
        lines.append(f"  <englishtitle>{english_title}</englishtitle>")
    if year:
        lines.append(f"  <year>{year}</year>")
    lines.append("</movie>")
    with open(os.path.join(folder, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _make_item(folder, file_name):
    path = os.path.join(folder, file_name)
    with open(path, "wb") as f:
        f.write(b"\x00")
    return {"file_path": path, "file_name": file_name}


class TestNfoIsPreferred:
    """有 NFO 时，检索名与标准名都应取 NFO"""

    def test_index_and_standard_name_from_nfo(self, tmp_path):
        folder = tmp_path / "温柔地杀我 Killing Me Softly (2002)"
        folder.mkdir()
        _write_movie_nfo(str(folder), "温柔地杀我", english_title="Killing Me Softly", year="2002")
        item = _make_item(str(folder), "Killing.Me.Softly.2002.1080p.BluRay.x264-BARC0DE.mkv")

        clean_filled, shadow_filled = fill_names_for_item(item)

        assert clean_filled and shadow_filled
        assert item["clean_name_cn"] == "温柔地杀我"
        assert item["clean_name_en"] == "Killing Me Softly"
        assert item["clean_name_source"] == "nfo"
        # 标准名要是规范形态：中文 + 英文 + (年份)
        assert item["shadow_name"] == "温柔地杀我 Killing Me Softly (2002)"
        assert item["shadow_name_source"] == "nfo"

    def test_release_group_not_leaked_into_names(self, tmp_path):
        """曾经的脏值：BARC0DE 残留并被切成 `BARC 0 DE`"""
        folder = tmp_path / "温柔地杀我 Killing Me Softly (2002)"
        folder.mkdir()
        _write_movie_nfo(str(folder), "温柔地杀我", english_title="Killing Me Softly", year="2002")
        item = _make_item(str(folder), "Killing.Me.Softly.2002.1080p.BluRay.x264-BARC0DE.mkv")

        fill_names_for_item(item)

        for field in ("clean_name", "clean_name_en", "shadow_name"):
            assert "BARC" not in item.get(field, "")


class TestFallbackWithoutNfo:
    """没有 NFO 时退回文件夹名，再退回文件名"""

    def test_folder_supplements_english_name(self, tmp_path):
        folder = tmp_path / "爱情与灵药 Love & Other Drugs (2010)"
        folder.mkdir()
        item = _make_item(str(folder), "爱情与灵药 (2010).mp4")

        fill_names_for_item(item)

        assert item["clean_name_cn"] == "爱情与灵药"
        assert "Love" in item["clean_name_en"]

    def test_generic_folder_does_not_pollute(self, tmp_path):
        """视频直接放在 media 这类通用目录下时，目录名不能被当成片名"""
        folder = tmp_path / "media"
        folder.mkdir()
        item = _make_item(str(folder), "Tenet.2020.1080p.BluRay.x264-WiKi.mkv")

        fill_names_for_item(item)

        assert item["clean_name_en"].lower().startswith("tenet")
        assert "media" not in item["clean_name_en"].lower()

    def test_standard_name_falls_back_to_index_name(self, tmp_path):
        folder = tmp_path / "media"
        folder.mkdir()
        item = _make_item(str(folder), "Tenet.2020.1080p.BluRay.x264-WiKi.mkv")

        _, shadow_filled = fill_names_for_item(item)

        assert shadow_filled
        assert item["shadow_name"]
        assert item["shadow_name_source"] == "parsed"


class TestPriorityProtection:
    """扫描不能把用户手填的名字降级"""

    def test_manual_index_name_not_overwritten(self, tmp_path):
        folder = tmp_path / "media"
        folder.mkdir()
        item = _make_item(str(folder), "Tenet.2020.1080p.BluRay.x264-WiKi.mkv")
        item.update({
            "clean_name": "我自己填的名字",
            "clean_name_cn": "我自己填的名字",
            "clean_name_source": "manual",
        })

        filled, _ = fill_search_index_name(item)

        assert filled is False
        assert item["clean_name"] == "我自己填的名字"

    def test_manual_standard_name_not_overwritten(self, tmp_path):
        folder = tmp_path / "温柔地杀我 Killing Me Softly (2002)"
        folder.mkdir()
        _write_movie_nfo(str(folder), "温柔地杀我", english_title="Killing Me Softly", year="2002")
        item = _make_item(str(folder), "Killing.Me.Softly.2002.1080p.BluRay.x264-BARC0DE.mkv")
        item.update({"shadow_name": "手填标准名", "shadow_name_source": "manual"})

        fill_names_for_item(item)

        assert item["shadow_name"] == "手填标准名"


class TestBadInput:
    def test_missing_path_is_noop(self):
        item = {}
        assert fill_names_for_item(item) == (False, False)


class TestRefillOldEntries:
    """扫描时同尺寸文件走"复用"分支、整份沿用旧条目。

    这是用户实际遇到的问题：算法改好后重启重扫，界面上名字纹丝不动——
    因为填名只处理新文件，复用的旧条目被 continue 跳过了。
    靠版本号判断旧条目要不要按当前算法补算一次。
    """

    def test_old_entry_without_version_needs_refill(self):
        from scan_name_filler import needs_refill

        assert needs_refill({"clean_name": "Killing Me Softly BARC 0 DE"}) is True

    def test_entry_with_current_version_skipped(self):
        from scan_name_filler import FILLER_VERSION, needs_refill

        assert needs_refill({"names_filled_v": FILLER_VERSION}) is False

    def test_stale_version_needs_refill(self):
        """取名逻辑改动后 bump 版本号，应触发全库一次性补算"""
        from scan_name_filler import FILLER_VERSION, needs_refill

        assert needs_refill({"names_filled_v": FILLER_VERSION - 1}) is True

    def test_dirty_entry_gets_upgraded(self, tmp_path):
        """修复前落盘的脏值应被 NFO 覆盖"""
        folder = tmp_path / "温柔地杀我 Killing Me Softly (2002)"
        folder.mkdir()
        _write_movie_nfo(str(folder), "温柔地杀我", english_title="Killing Me Softly", year="2002")
        item = _make_item(str(folder), "Killing.Me.Softly.2002.1080p.BluRay.x264-BARC0DE.mkv")
        item.update({
            "clean_name": "Killing Me Softly BARC 0 DE",
            "clean_name_en": "Killing Me Softly BARC 0 DE",
            "clean_name_source": "parsed",
            "shadow_name": "Killing Me Softly BARC 0 DE",
            "shadow_name_source": "parsed",
        })

        fill_names_for_item(item)

        assert item["clean_name_cn"] == "温柔地杀我"
        assert item["shadow_name"] == "温柔地杀我 Killing Me Softly (2002)"
        for field in ("clean_name", "clean_name_cn", "clean_name_en", "shadow_name"):
            assert "BARC" not in item[field]

    def test_filling_marks_version(self, tmp_path):
        """算过就打版本号，避免每次扫描都重复读 NFO"""
        from scan_name_filler import FILLER_VERSION, needs_refill

        folder = tmp_path / "media"
        folder.mkdir()
        item = _make_item(str(folder), "Tenet.2020.1080p.BluRay.x264-WiKi.mkv")

        fill_names_for_item(item)

        assert item["names_filled_v"] == FILLER_VERSION
        assert needs_refill(item) is False
