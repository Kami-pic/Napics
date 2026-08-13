from types import SimpleNamespace

import shared


def test_get_category_from_path_reads_known_category_segment_outside_nas_root(monkeypatch):
    fake_config = SimpleNamespace(
        nas_paths=[r"\\NAS\share\视频"],
        category_tags={
            r"\\NAS\share\视频\动画番": "tv",
            r"\\NAS\share\视频\动画电影": "movie",
        },
    )
    monkeypatch.setattr(shared.config_m, "_config", fake_config)

    path = r"C:\testdata\napics\shadow-verify\library\视频\动画番\四月是你的谎言"

    assert shared._get_category_from_path(path) == "tv"


def test_get_category_from_path_returns_empty_for_unknown_non_library_path(monkeypatch):
    fake_config = SimpleNamespace(
        nas_paths=[r"\\NAS\share\视频"],
        category_tags={
            r"\\NAS\share\视频\动画番": "tv",
        },
    )
    monkeypatch.setattr(shared.config_m, "_config", fake_config)

    path = r"C:\testdata\napics\shadow-verify\misc\april-lie"

    assert shared._get_category_from_path(path) == ""
