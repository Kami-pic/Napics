import re


def normalize_text(s: str) -> str:
    """全角→半角，去标点空格，小写"""
    if not s:
        return ""
    # 全角→半角
    out = []
    for ch in s:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
        else:
            out.append(ch)
    s = "".join(out)
    # 去标点、空格、常见干扰符
    s = re.sub(
        r'[\s\-·・、，。.,:;：；！!？?（）()「」『』【】\[\]\/\\～~＝="\'\"&＆_]',
        '',
        s,
    )
    return s.lower()


def fuzzy_score(s1: str, s2: str) -> float:
    """基于 Levenshtein 编辑距离的模糊匹配，返回 0.0-1.0 的相似度。

    规则:
    - 任一字符串为空 → 0.0
    - 完全相同 → 1.0
    - 长度差异超过较长字符串 50% → 0.0
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    max_len = max(len1, len2)

    # 长度差异过大直接返回 0.0
    if abs(len1 - len2) > max_len * 0.5:
        return 0.0

    # 动态规划计算 Levenshtein 编辑距离（空间优化为一维）
    dp = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len2 + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    distance = dp[len2]
    return 1.0 - (distance / max_len)
