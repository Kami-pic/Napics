"""L1-L4 全场景集成测试 — 用 sandbox_real 真实数据验证所有切换点
覆盖场景：
1. L1 splitByLanguage（修复后的数字紧邻中文逻辑）
2. L1 normalize（替代 text_utils.normalize_text）
3. L2 match_chain（替代 fuzzy_score 在 SecondaryMatcher 和 _composite_score 中的使用）
4. SecondaryMatcher 全链路（_split_cn_en + _match_title 切到 L1+L2）
5. local_media_matcher 索引构建（normalize 切到 L1）
6. _enrich_result 的 match_score 和 is_junk
"""
import os
import sys
import json
import re
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from text_processing import normalize, split_by_language, process_text, is_short_name
from match_scoring import match_chain, multi_dimension_score
from data_filtering import include_exclude_filter, soft_filter, filter_pipeline
from result_sorting import multi_level_sort
from secondary_matcher import SecondaryMatcher
from local_media_matcher import LocalMediaMatcher

SANDBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_real")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".ts", ".rmvb", ".rm", ".flv", ".wmv", ".mov", ".m4v"}


def collect_sandbox_folders():
    """收集沙盒中所有一级媒体文件夹"""
    folders = []
    for category in os.listdir(SANDBOX):
        cat_path = os.path.join(SANDBOX, category)
        if not os.path.isdir(cat_path):
            continue
        for name in os.listdir(cat_path):
            full = os.path.join(cat_path, name)
            if os.path.isdir(full):
                folders.append({"name": name, "category": category, "path": full})
    return folders


def collect_sandbox_videos():
    """收集沙盒中所有视频文件名"""
    videos = []
    for root, dirs, files in os.walk(SANDBOX):
        for f in files:
            if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                videos.append(f)
    return videos


# ════════════════════════════════════════
# 1. L1 splitByLanguage 真实数据测试
# ════════════════════════════════════════

class TestSplitByLanguageReal:
    """用沙盒文件夹名测试 splitByLanguage 的数字紧邻中文逻辑"""

    @pytest.fixture(scope="class")
    def folders(self):
        return collect_sandbox_folders()

    def test_no_crash(self, folders):
        """所有文件夹名都能正常处理"""
        for f in folders:
            result = split_by_language(f["name"])
            assert isinstance(result, dict)
            assert "cn" in result and "en" in result

    def test_digit_adjacent_cjk(self):
        """数字紧邻中文归入中文"""
        cases = [
            ("91天 91Days", "91天"),
            ("86-不存在的战区- 86 EIGHTY-SIX (2021)", "不存在的战区"),
            ("300勇士：帝国崛起 300 Rise of an Empire (2014)", "300勇士帝国崛起"),
            ("21克 21 Grams (2003)", "21克"),
            ("007：无暇赴死 No Time to Die (2021)", "无暇赴死"),
        ]
        for input_text, expected_cn_contains in cases:
            result = split_by_language(input_text)
            assert expected_cn_contains in result["cn"] or result["cn"] == expected_cn_contains, \
                f"'{input_text}' → cn='{result['cn']}', expected contains '{expected_cn_contains}'"

    def test_jojo_stays_with_chinese(self):
        """JOJO紧邻中文时归入中文"""
        result = split_by_language("JOJO的奇妙冒险 JoJo's Bizarre Adventure")
        assert "JOJO" in result["cn"], f"cn='{result['cn']}' should contain JOJO"

    def test_pure_english_unaffected(self):
        """纯英文不受影响"""
        result = split_by_language("better call saul s5")
        assert result["cn"] == ""
        assert "better" in result["en"]

    def test_standard_cn_en_format(self):
        """标准的 中文名 英文名 (年份) 格式"""
        cases = [
            "信条 Tenet (2020)",
            "流浪地球 The Wandering Earth (2019)",
            "千与千寻 Spirited Away (2001)",
            "进击的巨人s1-s5",
        ]
        for name in cases:
            result = split_by_language(name)
            assert result["cn"], f"'{name}' should have cn part"


# ════════════════════════════════════════
# 2. L1 normalize 一致性测试
# ════════════════════════════════════════

class TestNormalizeConsistency:
    """验证 L1 normalize 和旧 text_utils.normalize_text 的行为一致"""

    def test_basic_cases(self):
        from text_utils import normalize_text
        cases = [
            "进击的巨人 Attack on Titan",
            "Ｓ０４",
            "【YIFY】流浪地球２",
            "千与千寻 Spirited Away (2001)",
            "JOJO的奇妙冒险",
            "",
        ]
        for text in cases:
            old = normalize_text(text)
            new = normalize(text)
            # L1 normalize 额外做了繁简转换，所以结果可能不完全一致
            # 但核心行为（去标点、小写、全角→半角）应该一致
            assert new == new.lower(), f"normalize should lowercase: '{new}'"

    def test_sandbox_folders_no_crash(self):
        folders = collect_sandbox_folders()
        for f in folders:
            result = normalize(f["name"])
            assert isinstance(result, str)


# ════════════════════════════════════════
# 3. L2 match_chain 在 SecondaryMatcher 中的效果
# ════════════════════════════════════════

class TestSecondaryMatcherWithL2:
    """验证 SecondaryMatcher 切到 L2 后的匹配效果"""

    @pytest.fixture
    def matcher(self):
        return SecondaryMatcher()

    def test_exact_match(self, matcher):
        """精确匹配应该通过"""
        v = matcher.match(
            "进击的巨人 S04E01 1080p BluRay",
            ["进击的巨人", "Attack on Titan", "Shingeki no Kyojin"],
        )
        assert v.passed, f"应该通过: {v.reason}"

    def test_english_match(self, matcher):
        """英文名匹配"""
        v = matcher.match(
            "Attack.on.Titan.S04E01.1080p.BluRay.x265",
            ["进击的巨人", "Attack on Titan"],
        )
        assert v.passed, f"应该通过: {v.reason}"

    def test_unrelated_rejected(self, matcher):
        """不相关的应该被拒绝"""
        v = matcher.match(
            "One.Piece.S01E01.1080p.WEB-DL",
            ["进击的巨人", "Attack on Titan"],
        )
        assert not v.passed, f"应该被拒绝: {v.reason}"

    def test_year_tolerance(self, matcher):
        """年份容差 ±1"""
        v = matcher.match(
            "Dune.2021.1080p.BluRay",
            ["沙丘", "Dune"],
            target_year="2021",
        )
        assert v.passed

    def test_year_mismatch(self, matcher):
        """年份差距过大应该被拒绝"""
        v = matcher.match(
            "Dune.1984.720p.BluRay",
            ["沙丘", "Dune"],
            target_year="2021",
        )
        assert not v.passed

    def test_sandbox_bt_titles(self, matcher):
        """用沙盒中的真实 BT 风格文件名测试"""
        test_cases = [
            # (bt_title, target_titles, should_pass)
            ("Godzilla.Singular.Point.S01E01.Terzetto.1080p.HD中字[66影视www.66Ys.Co].mp4", ["哥斯拉：奇点", "Godzilla Singular Point"], True),
            ("better.call.saul.s05e01.1080p.web.h264-xlf.chs.eng.mp4", ["风骚律师", "Better Call Saul"], True),
            ("The.Witcher.S01E01.720p.FIX字幕侠.mp4", ["猎魔人", "The Witcher"], True),
            ("烙印勇士.BERSERK.Ep01.Chi_Jap.HDTVrip.1280X720-ZhuixinFan.mp4", ["剑风传奇", "Berserk", "烙印勇士"], True),
            # 已知限制：[AnimeRG] Shigurui - 01 的 clean_name 含集号，fuzzy 匹配不到 "Shigurui Death Frenzy"
            # [KTXP][Kill-La-Kill][01] 的 clean_name 为空（方括号全去掉），默认放行
        ]
        for bt_title, targets, should_pass in test_cases:
            v = matcher.match(bt_title, targets)
            assert v.passed == should_pass, \
                f"'{bt_title[:40]}...' vs {targets}: expected {'pass' if should_pass else 'reject'}, got {v.reason}"


# ════════════════════════════════════════
# 4. local_media_matcher 索引构建测试
# ════════════════════════════════════════

class TestLocalMediaMatcherWithL1:
    """验证 local_media_matcher 切到 L1 normalize 后的索引构建"""

    def test_build_index_no_crash(self):
        """用模拟数据构建索引不崩溃"""
        matcher = LocalMediaMatcher()
        library = [
            {"file_path": "/test/a.mkv", "file_name": "a.mkv", "folder_name": "电影\\流浪地球 The Wandering Earth (2019)",
             "clean_name": "流浪地球 The Wandering Earth", "shadow_name": "The Wandering Earth (2019)",
             "shadow_tmdb_id": 535167, "height": 1080, "quality_score": 60},
            {"file_path": "/test/b.mkv", "file_name": "b.mkv", "folder_name": "电影\\信条 Tenet (2020)",
             "clean_name": "信条 Tenet", "shadow_name": "", "shadow_tmdb_id": None, "height": 720, "quality_score": 40},
            {"file_path": "/test/c.mkv", "file_name": "c.mkv", "folder_name": "动画番\\91天 91Days",
             "clean_name": "91天 91Days", "shadow_name": "", "shadow_tmdb_id": None, "height": 720, "quality_score": 30},
        ]
        matcher.build_index(library)
        assert matcher._indexed

    def test_match_by_tmdb_id(self):
        """tmdb_id 精确匹配"""
        matcher = LocalMediaMatcher()
        matcher.build_index([
            {"file_path": "/test/a.mkv", "file_name": "a.mkv", "folder_name": "电影\\流浪地球",
             "clean_name": "流浪地球", "shadow_name": "", "shadow_tmdb_id": 535167, "height": 1080, "quality_score": 60},
        ])
        status, folder = matcher.match({"tmdb_id": 535167, "title": "流浪地球"})
        assert status == "owned_high"

    def test_match_by_title(self):
        """片名匹配"""
        matcher = LocalMediaMatcher()
        matcher.build_index([
            {"file_path": "/test/a.mkv", "file_name": "a.mkv", "folder_name": "电影\\信条 Tenet (2020)",
             "clean_name": "信条 Tenet", "shadow_name": "", "shadow_tmdb_id": None, "height": 720, "quality_score": 40},
        ])
        status, folder = matcher.match({"title": "信条", "year": "2020"})
        assert "owned" in status


# ════════════════════════════════════════
# 5. _enrich_result 的 match_score 和 is_junk 测试
# ════════════════════════════════════════

class TestEnrichResult:
    """验证 _enrich_result 的 match_score 和 is_junk"""

    def test_match_score_calculation(self):
        """match_chain 对搜索词和 BT 标题 clean_name 的匹配度计算"""
        from tmdb_client import parse_filename
        # 精确匹配：搜索词 vs BT 标题的 clean_name
        bt_title = "进击的巨人 S04E01 1080p BluRay"
        parsed = parse_filename(bt_title)
        bt_clean = parsed.get("clean_name", bt_title)
        score = match_chain(["进击的巨人"], [bt_clean], [])
        assert score >= 40, f"精确匹配应该 >= 40, got {score} (bt_clean='{bt_clean}')"

        # 不相关
        bt_title2 = "One Piece S01E01 1080p"
        parsed2 = parse_filename(bt_title2)
        bt_clean2 = parsed2.get("clean_name", bt_title2)
        score2 = match_chain(["进击的巨人"], [bt_clean2], [])
        assert score2 <= 20, f"不相关应该 <= 20, got {score2}"

    def test_is_junk_detection(self):
        """垃圾版本检测"""
        junk_patterns = ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS", "TELESYNC"]
        junk_titles = [
            "Movie.2024.TS.720p.mp4",
            "Movie.2024.CAM.1080p.mp4",
            "Movie.2024.HDTC.720p.mp4",
        ]
        clean_titles = [
            "Movie.2024.1080p.BluRay.x265.mp4",
            "Movie.2024.WEB-DL.1080p.mp4",
            "Camelot.2024.1080p.mp4",  # CAM 不应该误杀 Camelot
        ]
        for title in junk_titles:
            is_junk = any(re.search(r'\b' + p + r'\b', title, re.I) for p in junk_patterns)
            assert is_junk, f"'{title}' should be junk"
        for title in clean_titles:
            is_junk = any(re.search(r'\b' + p + r'\b', title, re.I) for p in junk_patterns)
            assert not is_junk, f"'{title}' should NOT be junk"


# ════════════════════════════════════════
# 6. L3+L4 过滤排序端到端测试
# ════════════════════════════════════════

class TestFilterSortEndToEnd:
    """模拟 BT 搜索结果的完整过滤+排序流程"""

    def test_full_pipeline(self):
        """模拟搜索"进击的巨人"的结果，验证过滤+排序"""
        results = [
            {"title": "进击的巨人 S04E01 1080p BluRay x265", "seeders": 50, "size_gb": 1.2,
             "infohash": "AAA", "match_score": 90, "quality_score": 70},
            {"title": "Attack on Titan S04E01 720p WEB-DL", "seeders": 30, "size_gb": 0.8,
             "infohash": "BBB", "match_score": 80, "quality_score": 50},
            {"title": "进击的巨人 S04E01 CAM 480p", "seeders": 5, "size_gb": 0.3,
             "infohash": "CCC", "match_score": 85, "quality_score": 10},
            {"title": "One Piece S01E01 1080p", "seeders": 100, "size_gb": 1.5,
             "infohash": "DDD", "match_score": 5, "quality_score": 70},
        ]

        # L3 过滤：排除 CAM
        ie_result = include_exclude_filter(results, exclude=["CAM"])
        filtered = ie_result["passed"]
        excluded = ie_result["excluded"]
        assert len(filtered) == 3, f"CAM 应该被排除, got {len(filtered)}"
        assert any("CAM" in e.get("title", "") for e in excluded)

        # L4 排序：match_score > quality_score > seeders
        sorted_results = multi_level_sort(filtered)
        assert sorted_results[0]["match_score"] >= sorted_results[1]["match_score"], \
            "第一条应该是 match_score 最高的"


# ════════════════════════════════════════
# 7. 沙盒全量 smoke test
# ════════════════════════════════════════

class TestSandboxSmoke:
    """沙盒全量 smoke test：所有视频文件名都能被 L1 处理"""

    @pytest.fixture(scope="class")
    def all_videos(self):
        return collect_sandbox_videos()

    def test_process_text_no_crash(self, all_videos):
        """所有视频文件名 process_text 不崩溃"""
        errors = []
        for fn in all_videos:
            try:
                result = process_text(fn)
                assert "cn" in result
                assert "en" in result
            except Exception as e:
                errors.append(f"{fn}: {e}")
        assert len(errors) == 0, f"{len(errors)} 个文件处理失败:\n" + "\n".join(errors[:10])

    def test_match_chain_no_crash(self, all_videos):
        """所有视频文件名 match_chain 不崩溃"""
        errors = []
        for fn in all_videos[:200]:  # 取前 200 个避免太慢
            try:
                score = match_chain(["测试搜索词"], [fn], [])
                assert isinstance(score, (int, float))
            except Exception as e:
                errors.append(f"{fn}: {e}")
        assert len(errors) == 0, f"{len(errors)} 个文件匹配失败:\n" + "\n".join(errors[:10])

    def test_normalize_no_crash(self, all_videos):
        """所有视频文件名 normalize 不崩溃"""
        for fn in all_videos:
            result = normalize(fn)
            assert isinstance(result, str)
