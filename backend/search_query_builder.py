"""
智能搜索词构造器：根据影片信息和别名，构造多个搜索词变体，提高搜索命中率。

TMDB 搜索策略（按成功概率降序）：
1. 原始中文标题
2. 豆瓣 subtitle（外文名）— en_names 第一个
3. Bangumi original_title（日文名）— jp_names 第一个
4. 去除副标题的简化版本
5. 英文名变体（en_names 其余项）

BT 搜索策略（按成功概率降序）：
1. 英文名 + 年份（BT 站英文为主）
2. 原始标题（中文站可能支持）
3. 日文名（动画资源）
4. 简化英文名（去除副标题）
"""
import re
from typing import List, Optional

from alias_resolver import AliasSet


class SearchQueryBuilder:

    def build_tmdb_queries(self, title: str, aliases: Optional[AliasSet] = None,
                           year: str = "") -> List[str]:
        """构造 TMDB 搜索词列表（按优先级排序）

        前置条件: title 非空
        后置条件:
          - 返回列表非空（至少包含原始 title）
          - 列表按搜索成功概率降序排列
          - 列表长度 <= 6
          - 列表中无重复项
        """
        if not title:
            return []

        queries: List[str] = []
        seen: set = set()

        def _add(q: str) -> None:
            q = q.strip()
            if q and q not in seen and len(queries) < 6:
                seen.add(q)
                queries.append(q)

        # 1. 原始中文标题（最高优先级）
        _add(title)

        if aliases:
            # 2. 豆瓣 subtitle（外文名）— en_names 第一个
            if aliases.en_names:
                _add(aliases.en_names[0])

            # 3. Bangumi original_title（日文名）— jp_names 第一个
            if aliases.jp_names:
                _add(aliases.jp_names[0])

        # 4. 去除副标题的简化版本
        simplified = self._simplify_title(title)
        if simplified != title:
            _add(simplified)

        if aliases:
            # 5. 英文名变体（en_names 其余项）
            for en_name in aliases.en_names[1:]:
                _add(en_name)

            # 额外：其他中文名变体（cn_names 中非原始标题的）
            for cn_name in aliases.cn_names:
                if cn_name != title:
                    _add(cn_name)

        return queries

    def build_bt_queries(self, title: str, aliases: Optional[AliasSet] = None,
                         year: str = "",
                         media_type: str = "") -> List[str]:
        """构造 BT 搜索词列表（英文名+年份优先）

        前置条件: title 非空
        后置条件:
          - 返回列表非空（至少包含原始 title）
          - 英文名+年份排在最前
          - 列表中无重复项
        """
        if not title:
            return []

        queries: List[str] = []
        seen: set = set()

        def _add(q: str) -> None:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                queries.append(q)

        if aliases and aliases.en_names:
            # 1. 英文名 + 年份（BT 站英文为主，最高命中率）
            en_primary = aliases.en_names[0]
            if year:
                _add(f"{en_primary} {year}")
            else:
                _add(en_primary)

        # 2. 原始标题（中文站可能支持）
        _add(title)

        if aliases:
            # 3. 日文名（动画资源）
            if aliases.jp_names:
                _add(aliases.jp_names[0])

            # 4. 简化英文名（去除副标题）
            if aliases.en_names:
                simplified_en = self._simplify_title(aliases.en_names[0])
                if simplified_en != aliases.en_names[0]:
                    _add(simplified_en)

        return queries

    def _simplify_title(self, title: str) -> str:
        """简化标题：去除副标题（冒号/中文冒号/破折号后的内容）

        处理的分隔符：
        - 英文冒号 ':'
        - 中文冒号 '：'
        - 破折号 ' - '（两侧有空格的短横线）

        返回冒号/分隔符前的部分，去除首尾空格。
        如果没有分隔符，返回原始标题。
        """
        if not title:
            return title

        # 按优先级尝试分割：中文冒号、英文冒号、破折号（两侧有空格）
        for sep in ['：', ':', ' - ']:
            if sep in title:
                parts = title.split(sep, 1)
                main_part = parts[0].strip()
                if main_part:
                    return main_part

        return title
