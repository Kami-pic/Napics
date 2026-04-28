from types import SimpleNamespace

from routes import library


def test_get_library_tree_avoids_live_nfo_reads(monkeypatch):
    monkeypatch.setattr(
        library,
        "config_m",
        SimpleNamespace(
            load_library=lambda: [
                {
                    "file_name": "Show.S01E01.mkv",
                    "file_path": r"\\NAS\视频\动画番\军火女王 Jormungand\Season 01\Show.S01E01.mkv",
                    "folder_name": r"动画番\军火女王 Jormungand\Season 01",
                    "clean_name": "军火女王 Jormungand 第1季",
                    "clean_name_cn": "军火女王",
                    "clean_name_en": "Jormungand",
                    "clean_name_original": "",
                }
            ],
            config=SimpleNamespace(
                nas_paths=[r"\\NAS\视频"],
                nas_path="",
                category_tags={r"\\NAS\视频\动画番": "tv"},
            ),
        ),
    )
    monkeypatch.setattr(library.organizer, "_load_folder_type_override", lambda path: None)
    monkeypatch.setattr(library.organizer, "infer_category_tag", lambda name: "tv")

    def fail_read_nfo(_path):
        raise AssertionError("library/tree 不应在首屏链路读取 NFO")

    monkeypatch.setattr(library.scraper, "read_nfo", fail_read_nfo)

    tree = library.get_library_tree()

    anime_root = tree["children"][0]
    show_root = anime_root["children"][0]
    season_node = show_root["children"][0]

    assert anime_root["path"] == r"\\NAS\视频\动画番"
    assert show_root["clean_name_cn"] == "军火女王"
    assert show_root["clean_name_en"] == "Jormungand"
    assert season_node["clean_name_cn"] == "军火女王"
    assert season_node["clean_name_en"] == "Jormungand"
