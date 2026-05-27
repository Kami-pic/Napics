from types import SimpleNamespace

from routes import library_tree as library
from test_support.route_response_snapshot import RouteResponseSnapshot


def test_library_tree_snapshot_keeps_root_shape(monkeypatch):
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
                    "shadow_name": "军火女王",
                    "shadow_tmdb_id": 999,
                    "subtitle_count": 0,
                    "is_low_res": False,
                }
            ],
            config=SimpleNamespace(
                scan_paths=[r"\\NAS\视频"],
                category_tags={r"\\NAS\视频\动画番": "tv"},
                media_libraries=[],
            ),
        ),
    )
    monkeypatch.setattr(library.organizer, "_load_folder_type_override", lambda path: None)
    monkeypatch.setattr(library.organizer, "infer_category_tag", lambda name: "tv")

    tree = library.get_library_tree()
    snapshot = RouteResponseSnapshot.from_body(200, tree)

    assert snapshot.status_code == 200
    assert snapshot.body_type == "dict"
    assert snapshot.field_types["name"] == "str"
    assert snapshot.field_types["path"] == "str"
    assert snapshot.field_types["children"] == "list"
    assert snapshot.field_types["children[].name"] == "str"
    assert snapshot.field_types["children[].path"] == "str"
    assert snapshot.field_types["children[].video_count"] == "int"
    assert snapshot.field_types["children[].children"] == "list"
    assert snapshot.field_types["children[].children[].folder_type"] == "str"
    assert snapshot.field_types["children[].children[].clean_name_cn"] == "str"
    assert snapshot.field_types["children[].children[].clean_name_en"] == "str"
    assert snapshot.list_lengths["children"] == 1
