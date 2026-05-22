"""L4 result-sorting 技能测试 — TDD 驱动"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from result_sorting import multi_level_sort, weighted_sort, SortField


# ── 测试数据 ──

def _make_items():
    return [
        {"title": "A", "match_score": 80, "quality_score": 60, "seeders": 50, "size_gb": 8.5, "is_magnet_only": False, "is_season_pack": False},
        {"title": "B", "match_score": 40, "quality_score": 100, "seeders": 200, "size_gb": 45.0, "is_magnet_only": False, "is_season_pack": False},
        {"title": "C", "match_score": 80, "quality_score": 80, "seeders": 0, "size_gb": 0, "is_magnet_only": True, "is_season_pack": False},
        {"title": "D", "match_score": 90, "quality_score": 70, "seeders": 30, "size_gb": 12.0, "is_magnet_only": False, "is_season_pack": True},
        {"title": "E", "match_score": 80, "quality_score": 60, "seeders": 50, "size_gb": 8.5, "is_magnet_only": False, "is_season_pack": False},  # 和 A 完全相同分数
    ]


# ── multi_level_sort ──

class TestMultiLevelSort:
    def test_match_score_priority(self):
        """match_score 高的排前面，即使 quality_score 低"""
        items = _make_items()
        result = multi_level_sort(items)
        # D(90) 应该排第一，B(40) 应该排最后（正常资源中）
        normal = [i for i in result if not i.get("is_magnet_only")]
        assert normal[0]["title"] == "D"

    def test_magnet_last(self):
        """磁力链接排在正常资源后面"""
        items = _make_items()
        result = multi_level_sort(items)
        magnet_idx = next(i for i, x in enumerate(result) if x["is_magnet_only"])
        normal_indices = [i for i, x in enumerate(result) if not x["is_magnet_only"]]
        assert magnet_idx > max(normal_indices)

    def test_season_pack_first(self):
        """整季包排在同匹配度的单集前面"""
        items = _make_items()
        result = multi_level_sort(items)
        # D 是整季包且 match_score=90，应该排第一
        assert result[0]["title"] == "D"

    def test_stable_sort(self):
        """相同分数的项保持原始顺序"""
        items = _make_items()
        result = multi_level_sort(items)
        # A 和 E 分数完全相同，A 在原始列表中排前面
        a_idx = next(i for i, x in enumerate(result) if x["title"] == "A")
        e_idx = next(i for i, x in enumerate(result) if x["title"] == "E")
        assert a_idx < e_idx

    def test_missing_seeders(self):
        """seeders 缺失按 0 处理，排在有 seeders 的后面"""
        items = [
            {"title": "X", "match_score": 80, "quality_score": 60, "seeders": 50, "size_gb": 8.5, "is_magnet_only": False, "is_season_pack": False},
            {"title": "Y", "match_score": 80, "quality_score": 60, "size_gb": 8.5, "is_magnet_only": False, "is_season_pack": False},  # seeders 缺失
        ]
        result = multi_level_sort(items)
        assert result[0]["title"] == "X"  # 有 seeders 的排前面

    def test_missing_season_pack(self):
        """is_season_pack 缺失按 False 处理"""
        items = [
            {"title": "X", "match_score": 80, "quality_score": 60, "seeders": 50, "size_gb": 8.5, "is_magnet_only": False, "is_season_pack": True},
            {"title": "Y", "match_score": 80, "quality_score": 60, "seeders": 50, "size_gb": 8.5, "is_magnet_only": False},  # is_season_pack 缺失
        ]
        result = multi_level_sort(items)
        assert result[0]["title"] == "X"  # 整季包排前面

    def test_default_sort_order(self):
        """默认排序：is_magnet_only → is_season_pack → match_score → quality_score → seeders → size"""
        items = _make_items()
        result = multi_level_sort(items)
        titles = [i["title"] for i in result]
        # D(整季包,90) > A(80,60,50) = E(80,60,50) > B(40,100,200) > C(磁力链接)
        assert titles.index("D") < titles.index("A")
        assert titles.index("A") < titles.index("B")
        assert titles.index("B") < titles.index("C")


# ── weighted_sort ──

class TestWeightedSort:
    def test_basic_weighted(self):
        items = _make_items()
        fields = [
            SortField("match_score", weight=0.4, max_value=100),
            SortField("quality_score", weight=0.3, max_value=100),
            SortField("seeders", weight=0.2, max_value=1000),
            SortField("size_gb", weight=0.1, max_value=50),
        ]
        result = weighted_sort(items, fields)
        # 应该有结果且不崩溃
        assert len(result) == len(items)

    def test_weighted_respects_weights(self):
        """高 match_score 权重 → match_score 高的排前面"""
        items = [
            {"title": "High Match", "match_score": 100, "quality_score": 10, "seeders": 1, "size_gb": 1, "is_magnet_only": False, "is_season_pack": False},
            {"title": "High Quality", "match_score": 10, "quality_score": 100, "seeders": 1, "size_gb": 1, "is_magnet_only": False, "is_season_pack": False},
        ]
        fields = [
            SortField("match_score", weight=0.6, max_value=100),
            SortField("quality_score", weight=0.4, max_value=100),
        ]
        result = weighted_sort(items, fields)
        assert result[0]["title"] == "High Match"
