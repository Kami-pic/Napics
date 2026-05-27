"""L3 data-filtering 技能测试 — TDD 驱动"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from data_filtering import (
    include_exclude_filter, threshold_filter, soft_filter,
    deduplicate, filter_pipeline, FilterStats,
)


# ── 测试数据 ──

def _make_items():
    """构造模拟搜索结果"""
    return [
        {"title": "进击的巨人 S04 1080p BluRay x265", "seeders": 50, "size_gb": 8.5, "infohash": "AAA", "indexer": "prowlarr"},
        {"title": "进击的巨人 S04 CAM 720p", "seeders": 3, "size_gb": 1.2, "infohash": "BBB", "indexer": "prowlarr"},
        {"title": "进击的巨人 S04 2160p Remux", "seeders": 20, "size_gb": 45.0, "infohash": "CCC", "indexer": "nyaa"},
        {"title": "美国派 1080p WEB-DL", "seeders": 100, "size_gb": 4.0, "infohash": "DDD", "indexer": "bitsearch"},
        {"title": "进击的巨人 TS 480p", "seeders": 1, "size_gb": 0.8, "infohash": "EEE", "indexer": "xl720"},
        {"title": "进击的巨人 S04 磁力链接", "seeders": 0, "size_gb": 0, "infohash": "FFF", "indexer": "cilixiong"},
        {"title": "进击的巨人 S04 1080p BluRay x265", "seeders": 30, "size_gb": 8.5, "infohash": "AAA", "indexer": "nyaa"},  # 重复 infohash
    ]


# ── include/exclude ──

class TestIncludeExclude:
    def test_exclude_cam(self):
        items = _make_items()
        result = include_exclude_filter(items, exclude=["CAM|TS"])
        titles = [r["title"] for r in result["passed"]]
        assert not any("CAM" in t for t in titles)
        assert not any(" TS " in t for t in titles)

    def test_exclude_with_reason(self):
        items = _make_items()
        result = include_exclude_filter(items, exclude=["CAM"])
        # 被排除的项应有 filtered_reason
        assert len(result["excluded"]) > 0
        for item in result["excluded"]:
            assert "filtered_reason" in item
            assert "filtered_stage" in item
            assert item["filtered_stage"] == "exclude"

    def test_include_1080p(self):
        items = _make_items()
        result = include_exclude_filter(items, include=["1080p"])
        for item in result["passed"]:
            assert "1080p" in item["title"]

    def test_empty_filters(self):
        """空过滤器 = 不过滤"""
        items = _make_items()
        result = include_exclude_filter(items)
        assert len(result["passed"]) == len(items)

    def test_include_and_exclude(self):
        """同时有 include 和 exclude"""
        items = _make_items()
        result = include_exclude_filter(items, include=["进击的巨人"], exclude=["CAM|TS"])
        for item in result["passed"]:
            assert "进击的巨人" in item["title"]
            assert "CAM" not in item["title"]


# ── threshold ──

class TestThreshold:
    def test_min_seeders(self):
        items = _make_items()
        result = threshold_filter(items, field="seeders", min_val=5)
        for item in result["passed"]:
            # 磁力链接豁免
            if item["seeders"] == 0 and item["size_gb"] == 0:
                continue
            assert item["seeders"] >= 5

    def test_magnet_exempt(self):
        """磁力链接（seeders=0 且 size=0）不受阈值过滤"""
        items = _make_items()
        result = threshold_filter(items, field="seeders", min_val=5)
        magnet = [i for i in result["passed"] if i["seeders"] == 0 and i["size_gb"] == 0]
        assert len(magnet) > 0  # 磁力链接应该保留

    def test_size_range(self):
        items = _make_items()
        result = threshold_filter(items, field="size_gb", min_val=1.0, max_val=10.0)
        for item in result["passed"]:
            if item["seeders"] == 0 and item["size_gb"] == 0:
                continue
            assert 1.0 <= item["size_gb"] <= 10.0

    def test_excluded_with_reason(self):
        items = _make_items()
        result = threshold_filter(items, field="seeders", min_val=50)
        for item in result["excluded"]:
            assert "filtered_reason" in item
            assert "threshold" in item["filtered_stage"]


# ── soft_filter ──

class TestSoftFilter:
    def test_mark_junk(self):
        items = _make_items()
        result = soft_filter(items, patterns=["CAM|TS|HDTC"], mark_field="is_junk")
        marked = [i for i in result if i.get("is_junk")]
        assert len(marked) > 0
        # 标记但不排除
        assert len(result) == len(items)

    def test_mark_with_reason(self):
        items = _make_items()
        result = soft_filter(items, patterns=["CAM"], mark_field="is_junk")
        for item in result:
            if item.get("is_junk"):
                assert "filtered_reason" in item
                assert item["filtered_stage"] == "softFilter"

    def test_mark_magnet_only(self):
        items = _make_items()
        result = soft_filter(
            items,
            condition=lambda i: i["seeders"] == 0 and i["size_gb"] == 0,
            mark_field="is_magnet_only",
        )
        magnets = [i for i in result if i.get("is_magnet_only")]
        assert len(magnets) > 0


# ── deduplicate ──

class TestDeduplicate:
    def test_infohash_dedup(self):
        items = _make_items()
        result = deduplicate(items, key_field="infohash")
        hashes = [i["infohash"] for i in result["passed"]]
        assert len(hashes) == len(set(hashes))

    def test_keep_best(self):
        """去重时保留 seeders 更高的那条"""
        items = _make_items()
        result = deduplicate(items, key_field="infohash", prefer_field="seeders")
        aaa = [i for i in result["passed"] if i["infohash"] == "AAA"]
        assert len(aaa) == 1
        assert aaa[0]["seeders"] == 50  # 保留 seeders=50 的，不是 30 的

    def test_dedup_stats(self):
        items = _make_items()
        result = deduplicate(items, key_field="infohash")
        assert result["removed_count"] > 0


# ── filter_pipeline（完整流水线）──

class TestFilterPipeline:
    def test_full_pipeline(self):
        items = _make_items()
        result = filter_pipeline(
            items,
            dedup_key="infohash",
            dedup_prefer="seeders",
            exclude=["CAM|TS"],
            threshold_rules=[{"field": "seeders", "min": 5}],
            soft_patterns=["HDTC"],
        )
        assert isinstance(result["stats"], dict)
        assert result["stats"]["total"] == len(items)
        assert result["stats"]["after_dedup"] <= len(items)
        assert result["stats"]["final"] <= result["stats"]["after_dedup"]

    def test_pipeline_order(self):
        """去重 → exclude → threshold → soft"""
        items = _make_items()
        result = filter_pipeline(
            items,
            dedup_key="infohash",
            exclude=["CAM|TS"],
            threshold_rules=[{"field": "seeders", "min": 5}],
        )
        stats = result["stats"]
        # 去重后数量 <= 原始
        assert stats["after_dedup"] <= stats["total"]
        # exclude 后 <= 去重后
        assert stats["after_exclude"] <= stats["after_dedup"]
        # threshold 后 <= exclude 后
        assert stats["after_threshold"] <= stats["after_exclude"]

    def test_pipeline_stats_has_reasons(self):
        items = _make_items()
        result = filter_pipeline(
            items,
            dedup_key="infohash",
            exclude=["CAM|TS"],
        )
        assert "exclude_reasons" in result["stats"]

    def test_empty_result_returns_all(self):
        """过滤后为空时返回全量 + 提示"""
        items = [{"title": "CAM only", "seeders": 0, "size_gb": 0, "infohash": "X", "indexer": "x"}]
        result = filter_pipeline(items, exclude=["CAM"])
        assert result["stats"]["final"] == 0
