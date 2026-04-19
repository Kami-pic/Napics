"""二次匹配器：对 Prowlarr 搜索结果执行标题+年份精确比对，剔除误匹配。

核心原则：
- 复用 tmdb_client.parse_filename 作为唯一解析引擎，不手写 BT 标题正则
- 复用 L1 text_processing 做文本标准化和中英文分离
- 复用 L2 match_scoring 做匹配评分
"""

import re
from typing import List, Optional
from pydantic import BaseModel

from tmdb_client import parse_filename
from text_processing import normalize, split_by_language
from match_scoring import match_chain


class BTTitleInfo(BaseModel):
    """从 BT 标题中解析出的结构化信息"""
    cn_name: str = ""
    en_name: str = ""
    year: str = ""
    season: Optional[int] = None
    episodes: List[int] = []


class MatchVerdict(BaseModel):
    """匹配判定结果"""
    passed: bool
    reason: str = ""


class SecondaryMatcher:
    """二次匹配器：从 BT 标题中解析信息，与目标媒体精确比对。

    使用场景：Prowlarr 返回的原始搜索结果可能包含同名不同片、年份不符等
    误匹配资源，本模块在评分排序之前先做硬性过滤。
    """

    def match(
        self,
        bt_title: str,
        target_titles: List[str],
        target_year: str = "",
        media_type: str = "movie",
        season_years: Optional[dict] = None,
    ) -> MatchVerdict:
        """对单条 BT 搜索结果执行二次匹配。

        参数:
            bt_title: BT 资源的原始标题
            target_titles: 目标媒体的所有标题变体（中文名、英文名、别名、译名）
            target_year: 目标媒体的年份（如 "2024"）
            media_type: "movie" 或 "tv"
            season_years: 剧集各季年份映射 {season_number: "year"}，仅 tv 类型使用

        返回:
            MatchVerdict(passed=True/False, reason=匹配/不匹配原因)
        """
        if not bt_title or not target_titles:
            return MatchVerdict(passed=False, reason="输入为空")

        # 用 parse_filename 解析 BT 标题
        info = self._parse_bt_title(bt_title)

        # 第一关：标题比对
        title_passed, title_reason = self._match_title(info, target_titles)
        if not title_passed:
            return MatchVerdict(passed=False, reason=title_reason)

        # 第二关：年份比对
        if target_year and info.year:
            year_passed, year_reason = self._match_year(
                info.year, target_year, media_type, season_years
            )
            if not year_passed:
                return MatchVerdict(passed=False, reason=year_reason)

        return MatchVerdict(passed=True, reason=title_reason)

    def batch_filter(
        self,
        bt_titles: List[str],
        target_titles: List[str],
        target_year: str = "",
        media_type: str = "movie",
        season_years: Optional[dict] = None,
    ) -> List[int]:
        """批量过滤，返回通过匹配的索引列表。"""
        passed_indices = []
        for i, bt_title in enumerate(bt_titles):
            verdict = self.match(
                bt_title, target_titles, target_year, media_type, season_years
            )
            if verdict.passed:
                passed_indices.append(i)
        return passed_indices

    def _parse_bt_title(self, title: str) -> BTTitleInfo:
        """复用 tmdb_client.parse_filename 解析 BT 标题。

        parse_filename 返回 dict:
            clean_name, season, episode, absolute_episode, year, raw

        clean_name 已经过清洗（去方括号标签、去质量标签、去网站域名等），
        包含中英文混合的作品名。本方法将其拆分为 cn_name 和 en_name。
        """
        parsed = parse_filename(title)
        clean = parsed.get("clean_name", "")
        year = parsed.get("year", "") or ""

        # 从 clean_name 中拆分中文名和英文名
        cn_name, en_name = self._split_cn_en(clean)

        # 集数
        episodes = []
        ep = parsed.get("episode")
        if ep is not None:
            episodes = [ep]

        return BTTitleInfo(
            cn_name=cn_name,
            en_name=en_name,
            year=str(year) if year else "",
            season=parsed.get("season"),
            episodes=episodes,
        )

    def _split_cn_en(self, name: str) -> tuple:
        """将混合名拆分为中文部分和英文部分（复用 L1 split_by_language）。"""
        if not name:
            return "", ""
        parts = split_by_language(name)
        return parts["cn"], parts["en"]

    def _match_title(
        self, info: BTTitleInfo, target_titles: List[str]
    ) -> tuple:
        """标题比对：用 L2 match_chain 评分，阈值 40 分通过。

        返回 (passed: bool, reason: str)
        """
        if not target_titles:
            return False, "目标标题列表为空"

        # 收集 BT 标题中的候选名
        candidates = []
        if info.cn_name:
            candidates.append(("cn", info.cn_name))
        if info.en_name:
            candidates.append(("en", info.en_name))

        if not candidates:
            return True, "BT标题无法解析名称，默认放行"

        # 用 L2 match_chain 逐一比对
        best_score = 0
        best_match = ""
        for ctype, cname in candidates:
            score = match_chain([cname], target_titles, [])
            if score > best_score:
                best_score = score
                best_match = f"{ctype}:{cname} ({score})"

        if best_score >= 40:
            return True, f"标题匹配: {best_match}"
        else:
            return False, f"标题不匹配(最高{best_score}<40)"

    def _match_year(
        self,
        bt_year: str,
        target_year: str,
        media_type: str,
        season_years: Optional[dict] = None,
    ) -> tuple:
        """年份比对。

        规则:
        - 电影：±1 年容差
        - 剧集：与任一季的年份匹配即通过（±1 年容差）
        - 无法解析年份时默认放行

        返回 (passed: bool, reason: str)
        """
        try:
            bt_y = int(bt_year)
        except (ValueError, TypeError):
            return True, "BT年份无法解析，默认放行"

        if media_type == "tv" and season_years:
            # 剧集：与任一季年份匹配即通过
            for season_num, sy in season_years.items():
                try:
                    sy_int = int(sy)
                    if abs(bt_y - sy_int) <= 1:
                        return True, f"年份匹配季{season_num}: {bt_year}≈{sy}"
                except (ValueError, TypeError):
                    continue
            # 也与主年份比对
            try:
                target_y = int(target_year)
                if abs(bt_y - target_y) <= 1:
                    return True, f"年份匹配: {bt_year}≈{target_year}"
            except (ValueError, TypeError):
                pass
            return False, f"年份不匹配: BT={bt_year}, 目标季年份={season_years}"
        else:
            # 电影：±1 年容差
            try:
                target_y = int(target_year)
                if abs(bt_y - target_y) <= 1:
                    return True, f"年份匹配: {bt_year}≈{target_year}"
                else:
                    return False, f"年份不匹配: {bt_year} vs {target_year}(差{abs(bt_y-target_y)}年)"
            except (ValueError, TypeError):
                return True, "目标年份无法解析，默认放行"
