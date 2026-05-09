"""测试自动命名 + 标准结构 + 一键整理（dry_run 预览）"""
import pytest
import requests


BASE = "http://localhost:8000"

TEST_CASES = [
    ("自由的她们 (动画season)", r"\\DS218play\share\视频\动画番\测试动画合集\自由的她们"),
    ("爱乐之城 (电影)", r"\\DS218play\share\视频\电影\测试文件夹\爱乐之城 La La Land (2016)"),
    ("白2023 (电影)", r"\\DS218play\share\视频\电影\测试文件夹\白2023"),
    ("测试动画合集 (tv容器)", r"\\DS218play\share\视频\动画番\测试动画合集"),
    ("测试文件夹 (collection)", r"\\DS218play\share\视频\电影\测试文件夹"),
]


def api_get(url, params=None, timeout=20):
    response = requests.get(f"{BASE}{url}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


@pytest.mark.parametrize("label,path", TEST_CASES)
def test_auto_rename_preview(label, path):
    data = api_get("/rename", {"path": path, "dry_run": "true"})
    assert "_error" not in data, f"{label}: {data.get('_error')}"
    assert isinstance(data.get("items", []), list)


@pytest.mark.parametrize("label,path", TEST_CASES)
def test_structure_preview(label, path):
    data = api_get("/organize/structure", {"path": path, "dry_run": "true"})
    assert "_error" not in data, f"{label}: {data.get('_error')}"
    assert isinstance(data.get("ops", []), list)


@pytest.mark.parametrize("label,path", TEST_CASES)
def test_full_organize_preview(label, path):
    data = api_get("/organize/full", {"path": path, "dry_run": "true"}, timeout=60)
    assert "_error" not in data, f"{label}: {data.get('_error')}"
    assert isinstance(data.get("summary", {}), dict)
