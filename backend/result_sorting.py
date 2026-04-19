"""L4 结果排序模块 — 多级排序、加权排序、特殊项处理

负责将 L2 匹配分和业务质量分合并为最终排序分。

对应技能文档：.kiro/skills/L4-result-sorting.md
"""
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class SortField:
    """加权排序的字段配置"""
    field: str
    weight: float = 1.0
    max_value: float = 100.0
    ascending: bool = False  # 默认降序


# ── 默认排序字段顺序 ──
_DEFAULT_SORT_FIELDS = [
    # 特殊优先级（不混进普通权重）
    ("is_magnet_only", True),    # ASC: 0=正常优先, 1=磁力链接排后
    ("is_season_pack", False),   # DESC: 1=整季包优先
    # 普通排序维度
    ("match_score", False),      # DESC
    ("quality_score", False),    # DESC
    ("seeders", False),          # DESC
    ("size_gb", False),          # DESC
]


def _get_val(item: Dict, field: str, default=0):
    """安全获取字段值，缺失按默认值处理"""
    val = item.get(field)
    if val is None:
        return default
    return val


def multi_level_sort(
    items: List[Dict],
    sort_fields: Optional[List[tuple]] = None,
) -> List[Dict]:
    """多级排序：逐级比较，第一级相同时比第二级

    sort_fields: [(field_name, ascending), ...]
    默认排序：is_magnet_only ASC → is_season_pack DESC → match_score DESC → quality_score DESC → seeders DESC → size_gb DESC
    """
    if not items:
        return []

    fields = sort_fields or _DEFAULT_SORT_FIELDS

    # 给每个 item 加原始索引（保证稳定排序）
    indexed = [(i, item) for i, item in enumerate(items)]

    def _sort_key(pair):
        idx, item = pair
        key = []
        for field, ascending in fields:
            # 缺失值兜底
            if field in ("is_magnet_only", "is_season_pack"):
                val = 1 if _get_val(item, field, False) else 0
            else:
                val = _get_val(item, field, 0)

            if ascending:
                key.append(val)
            else:
                key.append(-val if isinstance(val, (int, float)) else val)

        # 最后加原始索引保证稳定排序
        key.append(idx)
        return tuple(key)

    indexed.sort(key=_sort_key)
    return [item for _, item in indexed]


def weighted_sort(
    items: List[Dict],
    fields: List[SortField],
) -> List[Dict]:
    """加权排序：多字段加权计算综合分，按分数排序"""
    if not items:
        return []

    def _calc_score(item: Dict) -> float:
        score = 0.0
        for f in fields:
            val = _get_val(item, f.field, 0)
            # 归一化到 0-1
            normalized = min(val / f.max_value, 1.0) if f.max_value > 0 else 0.0
            score += normalized * f.weight
        return score

    # 加原始索引保证稳定排序
    indexed = [(i, item) for i, item in enumerate(items)]
    indexed.sort(key=lambda pair: (-_calc_score(pair[1]), pair[0]))
    return [item for _, item in indexed]
