"""Unit tests for IndexerPriorityManager."""
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from indexer_priority_manager import IndexerConfig, IndexerPriorityManager
from config_manager import AppConfig, ConfigManager


# --- IndexerConfig dataclass ---

def test_indexer_config_defaults():
    """IndexerConfig 默认值"""
    cfg = IndexerConfig(indexer_id=1, name="Test")
    assert cfg.priority == 50
    assert cfg.enabled is True
    assert cfg.preferred_types == []
    assert cfg.supports_chinese is False


def test_indexer_config_custom():
    """IndexerConfig 自定义值"""
    cfg = IndexerConfig(
        indexer_id=5, name="Nyaa", priority=90, enabled=False,
        preferred_types=["anime"], supports_chinese=True,
    )
    assert cfg.indexer_id == 5
    assert cfg.name == "Nyaa"
    assert cfg.priority == 90
    assert cfg.enabled is False
    assert cfg.preferred_types == ["anime"]
    assert cfg.supports_chinese is True


# --- load / save round-trip ---

def test_load_empty_config():
    """配置文件无 indexer_priorities 字段 → 返回空列表"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"prowlarr_url": "http://localhost"}, f)
        path = f.name
    try:
        mgr = IndexerPriorityManager(config_path=path)
        result = mgr.load()
        assert result == []
    finally:
        os.unlink(path)


def test_load_missing_file():
    """配置文件不存在 → 返回空列表"""
    mgr = IndexerPriorityManager(config_path="/tmp/nonexistent_cfg_test.json")
    result = mgr.load()
    assert result == []


def test_save_and_load_roundtrip():
    """save 后 load 应返回相同数据"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        path = f.name
    try:
        mgr = IndexerPriorityManager(config_path=path)
        indexers = [
            IndexerConfig(indexer_id=1, name="YTS", priority=80, enabled=True,
                          preferred_types=["movie"], supports_chinese=False),
            IndexerConfig(indexer_id=2, name="Nyaa", priority=95, enabled=True,
                          preferred_types=["anime"], supports_chinese=True),
        ]
        mgr.save(indexers)

        mgr2 = IndexerPriorityManager(config_path=path)
        loaded = mgr2.load()
        assert len(loaded) == 2
        assert loaded[0].name == "YTS"
        assert loaded[0].priority == 80
        assert loaded[0].preferred_types == ["movie"]
        assert loaded[1].name == "Nyaa"
        assert loaded[1].supports_chinese is True
    finally:
        os.unlink(path)


def test_save_preserves_other_config():
    """save 不应覆盖 config.json 中的其他字段"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"prowlarr_url": "http://test:9696", "tmdb_api_key": "abc"}, f)
        path = f.name
    try:
        mgr = IndexerPriorityManager(config_path=path)
        mgr.save([IndexerConfig(indexer_id=1, name="TPB", priority=60)])

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["prowlarr_url"] == "http://test:9696"
        assert data["tmdb_api_key"] == "abc"
        assert len(data["indexer_priorities"]) == 1
    finally:
        os.unlink(path)


# --- get_prioritized ---

def test_get_prioritized_sorted_descending():
    """返回按 priority 降序排列"""
    mgr = IndexerPriorityManager()
    mgr.indexers = [
        IndexerConfig(indexer_id=1, name="A", priority=30),
        IndexerConfig(indexer_id=2, name="B", priority=90),
        IndexerConfig(indexer_id=3, name="C", priority=60),
    ]
    result = mgr.get_prioritized()
    priorities = [r.priority for r in result]
    assert priorities == [90, 60, 30]


def test_get_prioritized_excludes_disabled():
    """禁用的索引器不返回"""
    mgr = IndexerPriorityManager()
    mgr.indexers = [
        IndexerConfig(indexer_id=1, name="A", priority=80, enabled=True),
        IndexerConfig(indexer_id=2, name="B", priority=90, enabled=False),
    ]
    result = mgr.get_prioritized()
    assert len(result) == 1
    assert result[0].name == "A"


def test_get_prioritized_filter_by_media_type():
    """按媒体类型过滤：preferred_types 包含该类型或为空"""
    mgr = IndexerPriorityManager()
    mgr.indexers = [
        IndexerConfig(indexer_id=1, name="YTS", priority=80,
                      preferred_types=["movie"]),
        IndexerConfig(indexer_id=2, name="Nyaa", priority=90,
                      preferred_types=["anime"]),
        IndexerConfig(indexer_id=3, name="General", priority=70,
                      preferred_types=[]),  # 空 = 支持所有类型
    ]
    result = mgr.get_prioritized(media_type="movie")
    names = [r.name for r in result]
    assert "YTS" in names
    assert "General" in names
    assert "Nyaa" not in names


def test_get_prioritized_no_filter():
    """不指定 media_type → 返回所有启用的索引器"""
    mgr = IndexerPriorityManager()
    mgr.indexers = [
        IndexerConfig(indexer_id=1, name="A", priority=50,
                      preferred_types=["movie"]),
        IndexerConfig(indexer_id=2, name="B", priority=60,
                      preferred_types=["anime"]),
    ]
    result = mgr.get_prioritized()
    assert len(result) == 2


def test_get_prioritized_empty():
    """无索引器 → 返回空列表"""
    mgr = IndexerPriorityManager()
    mgr.indexers = []
    result = mgr.get_prioritized(media_type="movie")
    assert result == []


# --- AppConfig extension ---

def test_appconfig_new_fields_defaults():
    """AppConfig 新增字段有正确默认值"""
    cfg = AppConfig()
    assert cfg.indexer_priorities == []
    assert cfg.search_confidence_threshold == "medium"


def test_appconfig_with_indexer_priorities():
    """AppConfig 可以接受 indexer_priorities 数据"""
    cfg = AppConfig(indexer_priorities=[
        {"indexer_id": 1, "name": "YTS", "priority": 80},
    ])
    assert len(cfg.indexer_priorities) == 1
    assert cfg.indexer_priorities[0].name == "YTS"


def test_config_manager_roundtrip_new_fields():
    """ConfigManager save/load 保留新字段"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        path = f.name
    try:
        cm = ConfigManager(config_path=path)
        cfg = cm.config
        cfg.search_confidence_threshold = "high"
        cfg.indexer_priorities = [
            {"indexer_id": 1, "name": "TPB", "priority": 70,
             "enabled": True, "preferred_types": ["movie"],
             "supports_chinese": False},
        ]
        cm.save(cfg)

        cm2 = ConfigManager(config_path=path)
        loaded = cm2.config
        assert loaded.search_confidence_threshold == "high"
        assert len(loaded.indexer_priorities) == 1
        assert loaded.indexer_priorities[0].name == "TPB"
    finally:
        os.unlink(path)
