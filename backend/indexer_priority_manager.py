"""索引器优先级管理器 — 管理 Prowlarr 索引器的优先级配置。"""
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IndexerConfig:
    """索引器配置"""
    indexer_id: int
    name: str
    priority: int = 50           # 0-100，越高越优先
    enabled: bool = True
    preferred_types: List[str] = field(default_factory=list)  # ["anime", "movie", "tv"]
    supports_chinese: bool = False


class IndexerPriorityManager:
    """管理 Prowlarr 索引器的优先级配置，支持按内容类型调整搜索策略。"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.indexers: List[IndexerConfig] = []

    def load(self) -> List[IndexerConfig]:
        """从配置文件加载索引器优先级"""
        if not os.path.exists(self.config_path):
            self.indexers = []
            return self.indexers

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_list = data.get("indexer_priorities", [])
        self.indexers = []
        for item in raw_list:
            self.indexers.append(IndexerConfig(
                indexer_id=item.get("indexer_id", 0),
                name=item.get("name", ""),
                priority=item.get("priority", 50),
                enabled=item.get("enabled", True),
                preferred_types=item.get("preferred_types", []),
                supports_chinese=item.get("supports_chinese", False),
            ))
        return self.indexers

    def save(self, indexers: List[IndexerConfig]):
        """保存索引器优先级配置到 config.json"""
        # 读取现有配置
        data = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        # 序列化索引器列表
        data["indexer_priorities"] = [
            {
                "indexer_id": idx.indexer_id,
                "name": idx.name,
                "priority": idx.priority,
                "enabled": idx.enabled,
                "preferred_types": idx.preferred_types,
                "supports_chinese": idx.supports_chinese,
            }
            for idx in indexers
        ]

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.indexers = list(indexers)

    def get_prioritized(self, media_type: str = "") -> List[IndexerConfig]:
        """按优先级降序返回启用的索引器列表，可按媒体类型过滤。

        当 media_type 非空时，只返回 preferred_types 包含该类型
        或 preferred_types 为空（表示支持所有类型）的索引器。
        """
        result = [idx for idx in self.indexers if idx.enabled]

        if media_type:
            result = [
                idx for idx in result
                if not idx.preferred_types or media_type in idx.preferred_types
            ]

        result.sort(key=lambda x: x.priority, reverse=True)
        return result
