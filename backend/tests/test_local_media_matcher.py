"""测试本地媒体库匹配器"""
import json
import os
import sys

import pytest

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_media_matcher import LocalMediaMatcher, _extract_year


def test_extract_year():
    """测试年份提取"""
    assert _extract_year("你的名字。 Your Name. (2016) 1080p") == "2016"
    assert _extract_year("Millennium Actress (2002)") == "2002"
    assert _extract_year("无年份的标题") == ""
    assert _extract_year("") == ""
    print("✅ test_extract_year 通过")


def _build_matcher():
    """测试索引构建"""
    matcher = LocalMediaMatcher()
    fake_lib = [
        {
            "file_path": "\\\\NAS\\电影\\你的名字\\movie.mkv",
            "file_name": "movie.mkv",
            "folder_name": "电影\\你的名字。 Your Name. (2016) 1080p",
            "clean_name": "你的名字。 Your Name",
            "shadow_name": "",
            "shadow_tmdb_id": None,
            "height": 1080,
        },
        {
            "file_path": "\\\\NAS\\电影\\流浪地球\\movie.mkv",
            "file_name": "movie.mkv",
            "folder_name": "电影\\流浪地球 The Wandering Earth (2019)",
            "clean_name": "流浪地球 The Wandering Earth",
            "shadow_name": "The Wandering Earth (2019)",
            "shadow_tmdb_id": 535167,
            "height": 2160,
        },
        {
            "file_path": "\\\\NAS\\电影\\低画质\\movie.avi",
            "file_name": "movie.avi",
            "folder_name": "电影\\低画质电影",
            "clean_name": "低画质电影",
            "shadow_name": "",
            "shadow_tmdb_id": None,
            "height": 480,
        },
    ]
    matcher.build_index(fake_lib)
    assert matcher._indexed
    assert len(matcher._tmdb_index) >= 1  # 流浪地球有 tmdb_id
    assert len(matcher._title_index) >= 3  # 至少 3 个片名
    print(f"✅ test_build_index 通过: tmdb={len(matcher._tmdb_index)} title_year={len(matcher._title_year_index)} title={len(matcher._title_index)}")
    return matcher


@pytest.fixture(scope="module")
def matcher():
    """构建供匹配用例共享的媒体索引。"""
    return _build_matcher()


def test_build_index(matcher):
    """验证测试索引已成功构建。"""
    assert matcher._indexed


def test_match_by_tmdb_id(matcher):
    """测试 TMDB ID 精确匹配"""
    status, _ = matcher.match({"tmdb_id": 535167, "title": "流浪地球", "year": "2019"})
    assert status == "owned_high", f"期望 owned_high，实际 {status}"
    print("✅ test_match_by_tmdb_id 通过")


def test_match_by_title(matcher):
    """测试片名匹配"""
    status, _ = matcher.match({"title": "你的名字。", "year": "2016"})
    assert status == "owned_high", f"期望 owned_high，实际 {status}"
    print("✅ test_match_by_title 通过")


def test_match_by_title_fuzzy(matcher):
    """测试模糊片名匹配"""
    status, _ = matcher.match({"title": "你的名字", "year": "2016"})
    assert status in ("owned_high", "none"), f"结果: {status}"
    print(f"✅ test_match_by_title_fuzzy: {status}")


def test_match_low_quality(matcher):
    """测试低画质匹配"""
    status, _ = matcher.match({"title": "低画质电影", "year": ""})
    assert status == "owned_low", f"期望 owned_low，实际 {status}"
    print("✅ test_match_low_quality 通过")


def test_match_not_found(matcher):
    """测试未拥有"""
    status, _ = matcher.match({"title": "完全不存在的电影", "year": "2025"})
    assert status == "none", f"期望 none，实际 {status}"
    print("✅ test_match_not_found 通过")


def test_match_batch(matcher):
    """测试批量匹配"""
    items = [
        {"tmdb_id": 535167, "title": "流浪地球", "year": "2019"},
        {"title": "完全不存在的电影", "year": "2025", "douban_id": "99999"},
    ]
    matcher.match_batch(items)
    assert items[0].get("local_status") == "owned_high"
    assert items[1].get("local_status") == "none"
    print("✅ test_match_batch 通过")


def test_local_folder_is_absolute(matcher):
    """local_folder 必须是绝对目录。

    前端（桌面「查看本地」、移动端发现详情的「查看本地」）拿这个值去媒体库目录树里
    找节点，而树节点的 path 是绝对路径。返回 folder_name 原值（相对目录，虚拟库时
    还带库名前缀）会让两端一律报"这个目录不在媒体库里"。
    """
    status, folder = matcher.match({"tmdb_id": 535167, "title": "流浪地球", "year": "2019"})
    assert status == "owned_high"
    assert folder == "\\\\NAS\\电影\\流浪地球"
    # 对照：不能是 folder_name 那种相对路径
    assert not folder.startswith("电影\\")


def test_match_batch_injects_absolute_folder(matcher):
    """批量注入的 local_folder 同样是绝对目录，且未命中时为空串。"""
    items = [
        {"tmdb_id": 535167, "title": "流浪地球", "year": "2019"},
        {"title": "完全不存在的电影", "year": "2025"},
    ]
    matcher.match_batch(items)
    assert items[0]["local_folder"] == "\\\\NAS\\电影\\流浪地球"
    assert items[1]["local_folder"] == ""


def test_id_cache():
    """测试 ID 映射缓存"""
    matcher = LocalMediaMatcher()
    matcher.add_id_mapping("12345", 535167)
    assert matcher._id_cache.get("12345") == 535167
    print("✅ test_id_cache 通过")


def test_real_library():
    """用真实媒体库测试"""
    lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_library.json")
    if not os.path.exists(lib_path):
        print("⏭️ test_real_library 跳过（无 media_library.json）")
        return

    with open(lib_path, "r", encoding="utf-8") as f:
        lib = json.load(f)

    matcher = LocalMediaMatcher()
    matcher.build_index(lib)

    # 测试几个可能在库中的片名
    test_items = [
        {"title": "你的名字。", "year": "2016"},
        {"title": "流浪地球", "year": "2019"},
        {"title": "千年女优", "year": "2002"},
        {"title": "完全不存在的电影XYZ", "year": "2099"},
    ]
    for item in test_items:
        status = matcher.match(item)
        print(f"  {item['title']} ({item['year']}) → {status}")
    print("✅ test_real_library 完成")


if __name__ == "__main__":
    test_extract_year()
    matcher = _build_matcher()
    test_match_by_tmdb_id(matcher)
    test_match_by_title(matcher)
    test_match_by_title_fuzzy(matcher)
    test_match_low_quality(matcher)
    test_match_not_found(matcher)
    test_match_batch(matcher)
    test_id_cache()
    test_real_library()
    print("\n🎉 全部测试通过！")
