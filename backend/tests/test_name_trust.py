"""名称可信度机制测试：safe_set_clean_name + auto_fill 分层优先级"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared import safe_set_clean_name, NAME_SOURCE_PRIORITY


class TestSafeSetCleanName:
    """safe_set_clean_name 优先级保护测试"""

    def test_set_on_empty(self):
        """空条目可以设置任何来源"""
        item = {"clean_name": "", "clean_name_source": ""}
        assert safe_set_clean_name(item, "测试名称", "parsed") is True
        assert item["clean_name"] == "测试名称"
        assert item["clean_name_source"] == "parsed"

    def test_set_on_no_source_field(self):
        """没有 clean_name_source 字段的条目（历史数据）可以被任何来源覆盖"""
        item = {"clean_name": "旧名称"}
        assert safe_set_clean_name(item, "新名称", "parsed") is True
        assert item["clean_name"] == "新名称"
        assert item["clean_name_source"] == "parsed"

    def test_scrape_overwrites_parsed(self):
        """scrape(2) 覆盖 parsed(1)"""
        item = {"clean_name": "文件名清洗", "clean_name_source": "parsed"}
        assert safe_set_clean_name(item, "刮削标题", "scrape") is True
        assert item["clean_name"] == "刮削标题"
        assert item["clean_name_source"] == "scrape"

    def test_manual_overwrites_scrape(self):
        """manual(4) 覆盖 scrape(2)"""
        item = {"clean_name": "刮削标题", "clean_name_source": "scrape"}
        assert safe_set_clean_name(item, "手动修改", "manual") is True
        assert item["clean_name"] == "手动修改"
        assert item["clean_name_source"] == "manual"

    def test_scrape_blocked_by_manual(self):
        """scrape(2) 不能覆盖 manual(4)"""
        item = {"clean_name": "手动修改", "clean_name_source": "manual"}
        assert safe_set_clean_name(item, "刮削标题", "scrape") is False
        assert item["clean_name"] == "手动修改"
        assert item["clean_name_source"] == "manual"

    def test_parsed_blocked_by_scrape(self):
        """parsed(1) 不能覆盖 scrape(2)"""
        item = {"clean_name": "刮削标题", "clean_name_source": "scrape"}
        assert safe_set_clean_name(item, "文件名清洗", "parsed") is False
        assert item["clean_name"] == "刮削标题"

    def test_same_priority_allows_overwrite(self):
        """同优先级允许覆盖（新数据替换旧数据）"""
        item = {"clean_name": "旧刮削", "clean_name_source": "scrape"}
        assert safe_set_clean_name(item, "新刮削", "scrape") is True
        assert item["clean_name"] == "新刮削"

    def test_empty_name_rejected(self):
        """空名称被拒绝"""
        item = {"clean_name": "有效名称", "clean_name_source": "parsed"}
        assert safe_set_clean_name(item, "", "manual") is False
        assert item["clean_name"] == "有效名称"

    def test_nfo_overwrites_parsed(self):
        """nfo(3) 覆盖 parsed(1)"""
        item = {"clean_name": "文件名清洗", "clean_name_source": "parsed"}
        assert safe_set_clean_name(item, "NFO标题", "nfo") is True
        assert item["clean_name"] == "NFO标题"

    def test_parsed_blocked_by_nfo(self):
        """parsed(1) 不能覆盖 nfo(3)"""
        item = {"clean_name": "NFO标题", "clean_name_source": "nfo"}
        assert safe_set_clean_name(item, "文件名清洗", "parsed") is False
        assert item["clean_name"] == "NFO标题"


class TestPriorityTable:
    """优先级表完整性测试"""

    def test_manual_is_highest(self):
        assert NAME_SOURCE_PRIORITY["manual"] == 4

    def test_nfo_tmdb_equal(self):
        assert NAME_SOURCE_PRIORITY["nfo"] == NAME_SOURCE_PRIORITY["tmdb"]

    def test_parsed_is_lowest_named(self):
        assert NAME_SOURCE_PRIORITY["parsed"] == 1

    def test_empty_is_zero(self):
        assert NAME_SOURCE_PRIORITY[""] == 0

    def test_all_sources_defined(self):
        """所有已知来源都有优先级定义"""
        expected = {"manual", "nfo", "tmdb", "douban", "bangumi", "scrape", "parsed", ""}
        assert set(NAME_SOURCE_PRIORITY.keys()) == expected
