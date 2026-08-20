"""字幕结果相关性匹配 —— 复用项目既有的 L2 匹配链，不另写一套算法。

直接调用：
- `match_scoring.match_chain`：0-100 分匹配链（ID/精确/别名/子串/token/fuzzy 六档）
- `search_helpers.extract_bt_title_for_match`：从 release 风格标题里剥掉技术标签
- `text_processing.split_by_language`：中英分离

与 BT 搜索的差异（不能照搬 compute_junk_flags 的原因）：
- 字幕没有 seeders/size_gb，死种规则不适用
- 字幕站的 native_name 常是斜杠分隔的多别名
  （如 `刺客教條/刺客信条/Assassin's Creed (2016)`），必须拆开分别参与匹配，
  否则整串永远匹配不上
"""

import logging
import re
from typing import Dict, List, Sequence

from match_scoring import match_chain
from search_helpers import extract_bt_title_for_match
from text_processing import normalize, split_by_language, tokenize

logger = logging.getLogger(__name__)

# 匹配度低于此分数视为不相关（与 BT 搜索同口径）
MATCH_SCORE_THRESHOLD = 30
# 搜索词在目标标题中的占比下限，低于此值说明只是"关键词被覆盖"
TITLE_RATIO_THRESHOLD = 0.3
# 需要做占比复核的分数区间（非精确匹配段）
RATIO_CHECK_RANGE = (40, 70)
# 中文侧最长连续公共子串占比下限，低于此值说明只是零散字符重合
CN_OVERLAP_THRESHOLD = 0.6

# native_name 里的别名分隔符
_ALIAS_SEP_RE = re.compile(r"[/｜|]")
# 结尾的年份括号，如 "Assassin's Creed (2016)"
_TRAILING_YEAR_RE = re.compile(r"[（(]\s*(?:19|20)\d{2}\s*[)）]\s*$")

# CJK 字符
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# 同一作品的合法尾缀修饰（季/部/篇/剧场版/特别篇/年份等）。
# 用于区分 "进击的巨人｜最终季"（同作品）和 "刺客｜信条"（不同作品）。
_MODIFIER_SUFFIX_RE = re.compile(
    r"^(?:"
    r"[\s\-·:：]*"
    r"(?:"
    r"第[0-9一二三四五六七八九十]+[季部篇章集话話]|"
    r"[0-9]+|"
    r"最终季|终季|完结篇|前篇|后篇|上篇|下篇|前传|后传|续集|"
    r"剧场版|电影版|特别篇|番外篇|新篇|外传|"
    r"加长版|导演剪辑版|导剪版|重制版|修复版|公映版|国配|未删减版|完整版|"
    r"ova|oad|sp|special|movie|film|"
    # 同一部片的不同版本（IMAX / 加长 / 未分级 等），不是另一部作品
    r"imax|extended|unrated|uncut|remastered|theatrical|director'?s?\s*cut|"
    r"proper|repack|3d|hdr|dv|v[0-9]+|"
    r"season\s*[0-9]*|s[0-9]+|part\s*[0-9ivx]*|chapter\s*[0-9]*|final(?:\s*season)?|"
    r"(?:19|20)[0-9]{2}"
    r")"
    r"[\s\-·:：]*"
    r")+$",
    re.IGNORECASE,
)


def build_match_candidates(
    *,
    cn_name: str = "",
    en_name: str = "",
    original_name: str = "",
    query: str = "",
) -> List[str]:
    """构造匹配候选名（搜索侧）。

    只用基础片名，不含季集号变体：季集号是"哪一集"的约束，
    拼进来反而会在子串档产生误匹配。
    """
    candidates: List[str] = []

    def _add(value: str):
        value = (value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    for name in (cn_name, en_name, original_name, query):
        _add(name)
        if name:
            parts = split_by_language(name)
            _add(parts["cn"])
            _add(parts["en"])

    return candidates


def build_match_targets(native_name: str = "", videoname: str = "") -> List[str]:
    """构造匹配目标（结果侧）。

    native_name 走别名拆分（斜杠分隔的多语言片名），
    videoname 是 release 风格，先剥技术标签再拆中英。
    """
    targets: List[str] = []

    def _add(value: str):
        value = (value or "").strip()
        if value and value not in targets:
            targets.append(value)

    # native_name：按别名分隔符拆开，逐个去尾部年份后参与匹配
    for alias in _ALIAS_SEP_RE.split(native_name or ""):
        alias = _TRAILING_YEAR_RE.sub("", alias).strip()
        if not alias:
            continue
        _add(alias)
        parts = split_by_language(alias)
        _add(parts["cn"])
        _add(parts["en"])
        # SubDL 的 native_name 直接就是 release 名（Tenet.2020.IMAX.1080p...），
        # 也要剥一遍技术标签，否则只能靠子串档匹配、还会被误判成另一部作品
        cleaned_alias = extract_bt_title_for_match(alias)
        if cleaned_alias != alias:
            _add(cleaned_alias)
            cleaned_parts = split_by_language(cleaned_alias)
            _add(cleaned_parts["cn"])
            _add(cleaned_parts["en"])

    # videoname：release 风格，剥技术标签
    if videoname:
        cleaned = extract_bt_title_for_match(videoname)
        _add(cleaned)
        parts = split_by_language(cleaned)
        _add(parts["cn"])
        _add(parts["en"])

    return targets


def compute_match_score(candidates: Sequence[str], targets: Sequence[str]) -> int:
    """调用既有匹配链算分（0-100）"""
    if not candidates or not targets:
        return 0
    try:
        return match_chain(list(candidates), list(targets), [])
    except Exception as e:
        logger.debug(f"[subtitle] 匹配打分失败: {e}")
        return 0


def compute_junk_flags(
    *,
    match_score: int,
    candidates: Sequence[str],
    targets: Sequence[str],
) -> Dict:
    """字幕版垃圾标记。

    只保留通用规则，去掉 BT 特有的死种/枪版判断：
    1. low_match  — 有分但低于阈值
    2. unmatched  — 完全不匹配（且搜索词有效）
    3. low_title_ratio — 中间分段但搜索词只占目标标题一小部分
    """
    reasons: List[str] = []

    if 0 < match_score < MATCH_SCORE_THRESHOLD:
        reasons.append(f"low_match:{match_score}")

    has_valid_query = any(len(name) >= 2 for name in candidates)
    if match_score == 0 and has_valid_query:
        reasons.append("unmatched")

    low, high = RATIO_CHECK_RANGE
    if low <= match_score <= high and not any(r.startswith("low_match") for r in reasons):
        ratio = _best_title_ratio(candidates, targets)
        if ratio < TITLE_RATIO_THRESHOLD:
            reasons.append(f"low_title_ratio:{ratio:.2f}")
        elif _is_different_work(candidates, targets):
            # 中文逐字分词会让 "信条" 在 "刺客信条" 里 100% 命中而拿到 60 分，
            # 占比 0.5 也高于阈值，只能靠"多出来的字是不是修饰词"来区分
            reasons.append("different_work")
        elif _has_weak_cn_overlap(candidates, targets):
            # 无包含关系但零散字符重合也能拿 60 分
            # （"进击的巨人" vs "巨人族的花嫁" 共有 巨/人/的）
            reasons.append("weak_overlap")

    return {"is_junk": bool(reasons), "junk_reasons": reasons}


def _is_different_work(candidates: Sequence[str], targets: Sequence[str]) -> bool:
    """搜索名是目标名的一部分，但多出的内容不是季/版本之类的修饰词 → 判为不同作品。

    `刺客信条` vs `信条`：多出的 `刺客` 在前缀且非修饰词 → 不同作品
    `进击的巨人最终季` vs `进击的巨人`：多出的 `最终季` 是修饰词 → 同一作品

    判定是"任一对证据显示同作品就保留"，不能碰到一个像不同作品的目标就下结论：
    同一条结果会派生出多个目标（原始 release 名 + 剥完技术标签的短名），
    原始 release 名 normalize 后必然"多出一堆内容"，若提前短路会把正确结果全误杀。
    """
    saw_containment = False

    for target in targets:
        target_parts = split_by_language(target)
        for name in candidates:
            name_parts = split_by_language(name)
            for key in ("cn", "en"):
                name_side = normalize(name_parts[key]) if name_parts[key] else ""
                target_side = normalize(target_parts[key]) if target_parts[key] else ""
                if not name_side or not target_side:
                    continue
                if name_side == target_side:
                    return False  # 完全相同，同一作品
                if name_side not in target_side:
                    continue

                saw_containment = True
                index = target_side.find(name_side)
                prefix = target_side[:index]
                suffix = target_side[index + len(name_side):]

                prefix_has_content = bool(_CJK_RE.search(prefix) or re.search(r"[a-z]{2,}", prefix))
                suffix_is_modifier = (
                    not suffix.strip() or bool(_MODIFIER_SUFFIX_RE.match(suffix))
                )
                if not prefix_has_content and suffix_is_modifier:
                    return False  # 只多了修饰词，同一作品

    # 出现过包含关系，但没有任何一对像同一作品
    return saw_containment


def _has_weak_cn_overlap(candidates: Sequence[str], targets: Sequence[str]) -> bool:
    """中文侧没有包含关系、且最长连续公共子串占比过低 → 弱匹配。

    存在包含关系时交给 `_is_different_work` 判断，这里只处理零散重合。
    """
    best = 0.0
    compared = False

    for target in targets:
        target_cn = normalize(split_by_language(target)["cn"])
        if not target_cn:
            continue
        for name in candidates:
            name_cn = normalize(split_by_language(name)["cn"])
            if not name_cn:
                continue
            if name_cn in target_cn or target_cn in name_cn:
                return False
            compared = True
            common = _longest_common_substring_len(name_cn, target_cn)
            best = max(best, common / min(len(name_cn), len(target_cn)))

    return compared and best < CN_OVERLAP_THRESHOLD


def _longest_common_substring_len(a: str, b: str) -> int:
    """最长连续公共子串长度（标题都很短，直接 DP）"""
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        current = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best


def _best_title_ratio(candidates: Sequence[str], targets: Sequence[str]) -> float:
    """搜索词在目标标题中的最大占比（子串占比或 token 交集占比）"""
    best = 0.0
    for target in targets:
        target_parts = split_by_language(target)
        target_tokens = set(tokenize(target))
        for name in candidates:
            name_parts = split_by_language(name)

            for key in ("cn", "en"):
                name_side = normalize(name_parts[key]) if name_parts[key] else ""
                target_side = normalize(target_parts[key]) if target_parts[key] else ""
                if not name_side or not target_side:
                    continue
                if name_side in target_side or target_side in name_side:
                    shorter = min(len(name_side), len(target_side))
                    best = max(best, shorter / max(len(target_side), 1))

            if best < TITLE_RATIO_THRESHOLD and target_tokens:
                overlap = len(set(tokenize(name)) & target_tokens)
                best = max(best, overlap / len(target_tokens))

    return best


def enrich_items(items: List, candidates: Sequence[str]) -> None:
    """就地给字幕结果补 match_score / is_junk / junk_reasons"""
    for item in items:
        targets = build_match_targets(
            native_name=item.native_name,
            videoname=item.videoname,
        )
        item.match_score = compute_match_score(candidates, targets)
        flags = compute_junk_flags(
            match_score=item.match_score,
            candidates=candidates,
            targets=targets,
        )
        item.is_junk = flags["is_junk"]
        item.junk_reasons = flags["junk_reasons"]
