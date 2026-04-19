"""L3 数据过滤模块 — 包含/排除、阈值、软过滤、去重

只做过滤（保留/排除/标记），不修改分数（降分逻辑归 L2）。

对应技能文档：.kiro/skills/L3-data-filtering.md
"""
import re
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field


@dataclass
class FilterStats:
    """过滤统计"""
    total: int = 0
    after_dedup: int = 0
    after_exclude: int = 0
    after_threshold: int = 0
    flagged: int = 0
    final: int = 0
    exclude_reasons: Dict[str, int] = field(default_factory=dict)


def include_exclude_filter(
    items: List[Dict],
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    match_fields: Optional[List[str]] = None,
) -> Dict[str, List[Dict]]:
    """包含/排除过滤

    include: 正则列表，所有条件都满足才通过（AND）
    exclude: 正则列表，任一条件命中即排除（OR）
    match_fields: 匹配的字段列表，默认 ["title"]
    """
    if not include and not exclude:
        return {"passed": list(items), "excluded": []}

    fields = match_fields or ["title"]
    passed = []
    excluded = []

    for item in items:
        item_copy = dict(item)
        # 每个字段独立匹配
        field_texts = [str(item.get(f, "")) for f in fields]

        # include 检查（AND：所有条件都满足）
        if include:
            all_match = True
            for pattern in include:
                try:
                    found = any(re.search(pattern, text, re.IGNORECASE) for text in field_texts)
                except re.error:
                    found = False
                if not found:
                    all_match = False
                    break
            if not all_match:
                item_copy["filtered_reason"] = f"include: 不匹配 {pattern}"
                item_copy["filtered_stage"] = "exclude"
                excluded.append(item_copy)
                continue

        # exclude 检查（OR：任一命中即排除）
        if exclude:
            excluded_flag = False
            for pattern in exclude:
                try:
                    found = any(re.search(pattern, text, re.IGNORECASE) for text in field_texts)
                except re.error:
                    found = False
                if found:
                    item_copy["filtered_reason"] = f"exclude: 匹配排除词 {pattern}"
                    item_copy["filtered_stage"] = "exclude"
                    excluded.append(item_copy)
                    excluded_flag = True
                    break
            if excluded_flag:
                continue

        passed.append(item_copy)

    return {"passed": passed, "excluded": excluded}


def threshold_filter(
    items: List[Dict],
    field: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    exempt_condition: Optional[Callable] = None,
) -> Dict[str, List[Dict]]:
    """阈值过滤

    exempt_condition: 豁免条件函数，返回 True 的项不受阈值过滤
    默认豁免：seeders=0 且 size_gb=0 的磁力链接
    """
    if min_val is None and max_val is None:
        return {"passed": list(items), "excluded": []}

    def _default_exempt(item):
        return item.get("seeders", -1) == 0 and item.get("size_gb", -1) == 0

    exempt_fn = exempt_condition or _default_exempt
    passed = []
    excluded = []

    for item in items:
        item_copy = dict(item)
        # 豁免检查
        if exempt_fn(item):
            passed.append(item_copy)
            continue

        val = item.get(field, 0)
        if val is None:
            val = 0

        ok = True
        reason = ""
        if min_val is not None and val < min_val:
            ok = False
            reason = f"threshold: {field} ({val}) < {min_val}"
        if max_val is not None and val > max_val:
            ok = False
            reason = f"threshold: {field} ({val}) > {max_val}"

        if ok:
            passed.append(item_copy)
        else:
            item_copy["filtered_reason"] = reason
            item_copy["filtered_stage"] = "threshold"
            excluded.append(item_copy)

    return {"passed": passed, "excluded": excluded}


def soft_filter(
    items: List[Dict],
    patterns: Optional[List[str]] = None,
    condition: Optional[Callable] = None,
    mark_field: str = "is_junk",
) -> List[Dict]:
    """软过滤：标记但不排除

    patterns: 正则列表，标题匹配任一即标记
    condition: 自定义条件函数
    """
    result = []
    for item in items:
        item_copy = dict(item)
        marked = False

        if patterns:
            title = str(item.get("title", ""))
            for pattern in patterns:
                try:
                    if re.search(pattern, title, re.IGNORECASE):
                        marked = True
                        item_copy["filtered_reason"] = f"softFilter: 匹配 {pattern}"
                        break
                except re.error:
                    pass

        if condition and not marked:
            if condition(item):
                marked = True
                item_copy["filtered_reason"] = f"softFilter: 条件匹配"

        if marked:
            item_copy[mark_field] = True
            item_copy["filtered_stage"] = "softFilter"
        else:
            item_copy[mark_field] = False

        result.append(item_copy)

    return result


def deduplicate(
    items: List[Dict],
    key_field: str = "infohash",
    prefer_field: Optional[str] = None,
) -> Dict[str, Any]:
    """去重：按 key_field 去重，保留 prefer_field 最大的那条"""
    seen: Dict[str, Dict] = {}
    removed_count = 0

    for item in items:
        key = item.get(key_field, "")
        if not key:
            # 无 key 的项保留
            if key not in seen:
                seen[id(item)] = item
            continue

        if key in seen:
            # 已存在，比较 prefer_field
            if prefer_field:
                existing_val = seen[key].get(prefer_field, 0) or 0
                new_val = item.get(prefer_field, 0) or 0
                if new_val > existing_val:
                    seen[key] = item
            removed_count += 1
        else:
            seen[key] = item

    return {
        "passed": list(seen.values()),
        "removed_count": removed_count,
    }


def filter_pipeline(
    items: List[Dict],
    dedup_key: Optional[str] = None,
    dedup_prefer: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    threshold_rules: Optional[List[Dict]] = None,
    soft_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """完整过滤流水线：去重 → include/exclude → threshold → softFilter"""

    stats = FilterStats(total=len(items))
    all_excluded: List[Dict] = []

    # 1. 去重（必须第一步）
    if dedup_key:
        dedup_result = deduplicate(items, key_field=dedup_key, prefer_field=dedup_prefer)
        current = dedup_result["passed"]
    else:
        current = list(items)
    stats.after_dedup = len(current)

    # 2. include/exclude
    if include or exclude:
        ie_result = include_exclude_filter(current, include=include, exclude=exclude)
        current = ie_result["passed"]
        all_excluded.extend(ie_result["excluded"])
        for item in ie_result["excluded"]:
            reason = item.get("filtered_reason", "unknown")
            stats.exclude_reasons[reason] = stats.exclude_reasons.get(reason, 0) + 1
    stats.after_exclude = len(current)

    # 3. threshold
    if threshold_rules:
        for rule in threshold_rules:
            t_result = threshold_filter(
                current,
                field=rule.get("field", ""),
                min_val=rule.get("min"),
                max_val=rule.get("max"),
            )
            current = t_result["passed"]
            all_excluded.extend(t_result["excluded"])
            for item in t_result["excluded"]:
                reason = item.get("filtered_reason", "unknown")
                stats.exclude_reasons[reason] = stats.exclude_reasons.get(reason, 0) + 1
    stats.after_threshold = len(current)

    # 4. softFilter（标记，不排除）
    if soft_patterns:
        current = soft_filter(current, patterns=soft_patterns)
        stats.flagged = sum(1 for i in current if i.get("is_junk"))

    stats.final = len(current)

    return {
        "items": current,
        "excluded": all_excluded,
        "stats": {
            "total": stats.total,
            "after_dedup": stats.after_dedup,
            "after_exclude": stats.after_exclude,
            "after_threshold": stats.after_threshold,
            "flagged": stats.flagged,
            "final": stats.final,
            "exclude_reasons": stats.exclude_reasons,
        },
    }
