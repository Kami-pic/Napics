"""全局质量过滤器：基于用户配置的必须包含/严格排除关键词过滤搜索结果。

核心设计：
- 使用正则 \\b 词边界匹配，防止子串误杀（如排除 CAM 不会误杀 Camelot）
- 大小写不敏感
- 配置为空时使用默认排除列表兜底
"""

import re
from typing import List, Optional


# 默认排除的垃圾版本标签
DEFAULT_EXCLUDES: List[str] = ["TS", "CAM", "HDTC", "TC", "TELECINE", "HDTS"]


class GlobalFilter:
    """全局质量过滤规则。

    参数:
        must_include: 必须包含的关键词列表（任一命中即通过）
        must_exclude: 严格排除的关键词列表（任一命中即丢弃）
    """

    def __init__(
        self,
        must_include: Optional[List[str]] = None,
        must_exclude: Optional[List[str]] = None,
    ):
        self.must_include = must_include or []
        # 配置为空时使用默认排除列表兜底
        self.must_exclude = must_exclude if must_exclude is not None else DEFAULT_EXCLUDES

        # 预编译正则，提升批量过滤性能
        self._exclude_patterns = self._compile_patterns(self.must_exclude)
        self._include_patterns = self._compile_patterns(self.must_include)

    @staticmethod
    def _compile_patterns(keywords: List[str]) -> List[re.Pattern]:
        """将关键词列表编译为词边界正则。

        使用 \\b 词边界确保精确匹配：
        - "CAM" 匹配 "xxx.CAM.xxx" 但不匹配 "Camelot"
        - "TS" 匹配 "xxx.TS.xxx" 但不匹配 "HDTS"（HDTS 需要单独配置）
        - "HDTS" 匹配 "xxx.HDTS.xxx"

        对于包含特殊正则字符的关键词，先做 re.escape 转义。
        """
        patterns = []
        for kw in keywords:
            if not kw or not kw.strip():
                continue
            escaped = re.escape(kw.strip())
            try:
                pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
                patterns.append(pattern)
            except re.error:
                # 关键词编译失败时跳过，不影响其他规则
                continue
        return patterns

    def apply(self, titles: List[str]) -> List[int]:
        """对标题列表执行过滤，返回通过过滤的索引列表。

        过滤逻辑（按顺序执行）：
        1. 排除检查：标题命中任一排除词 → 丢弃
        2. 包含检查：配置了包含词时，标题未命中任一包含词 → 丢弃

        参数:
            titles: BT 资源标题列表

        返回:
            通过过滤的索引列表
        """
        passed = []
        for i, title in enumerate(titles):
            if not title:
                continue
            if self._is_excluded(title):
                continue
            if self._include_patterns and not self._is_included(title):
                continue
            passed.append(i)
        return passed

    def check_single(self, title: str) -> bool:
        """检查单条标题是否通过过滤。

        返回 True 表示通过（保留），False 表示被过滤（丢弃）。
        """
        if not title:
            return False
        if self._is_excluded(title):
            return False
        if self._include_patterns and not self._is_included(title):
            return False
        return True

    def _is_excluded(self, title: str) -> bool:
        """检查标题是否命中任一排除词。"""
        for pattern in self._exclude_patterns:
            if pattern.search(title):
                return True
        return False

    def _is_included(self, title: str) -> bool:
        """检查标题是否命中任一包含词。"""
        for pattern in self._include_patterns:
            if pattern.search(title):
                return True
        return False

    @classmethod
    def from_config(cls, config: dict) -> "GlobalFilter":
        """从配置字典创建 GlobalFilter 实例。

        config 格式:
            {
                "must_include": ["HEVC", "x265"],
                "must_exclude": ["TS", "CAM", "HDTC"]
            }
        """
        search_filter = config.get("search_filter", {})
        return cls(
            must_include=search_filter.get("must_include", []),
            must_exclude=search_filter.get("must_exclude"),
        )
