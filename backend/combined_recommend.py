"""综合推荐算法 — 三源融合排序（豆瓣+TMDB+Bangumi）

数据获取（并发，timeout=5s）→ 多维去重 → 评分归一化 → 加权排序 → 产出 40 条
复用 text_utils.normalize_text / fuzzy_score 做标题匹配去重。
"""
import re
import time
import concurrent.futures
from typing import List, Dict, Optional, Tuple

from text_processing import normalize as normalize_text
from text_utils import fuzzy_score
import douban_api_v2
import bangumi_client


# ── 去重阈值 ──
_FUZZY_THRESHOLD = 0.85  # 模糊匹配阈值
_YEAR_TOLERANCE = 1      # 年份允许 ±1 误差
_TARGET_COUNT = 60       # 目标产出条数（前端按 colCount*4 分页取）
_ANIME_MIN_RATIO = 0.30  # 动漫保底比例


def _extract_chinese(text: str) -> set:
    """提取中文字符集合"""
    return set(re.findall(r'[\u4e00-\u9fff]', text or ""))


def _is_same_media(a: Dict, b: Dict) -> bool:
    """判断两个条目是否指向同一部作品。
    优先级：ID 关联 > original_title 精确 > 中文标题+年份模糊匹配。
    """
    # 1. tmdb_id 关联
    a_tmdb = a.get("tmdb_id") or 0
    b_tmdb = b.get("tmdb_id") or 0
    if a_tmdb and b_tmdb and a_tmdb == b_tmdb:
        return True

    # 2. douban_id 关联
    a_db = a.get("douban_id") or ""
    b_db = b.get("douban_id") or ""
    if a_db and b_db and a_db == b_db:
        return True

    # 3. original_title 精确匹配（normalize 后）
    a_orig = normalize_text(a.get("original_title") or a.get("subtitle") or "")
    b_orig = normalize_text(b.get("original_title") or b.get("subtitle") or "")
    if a_orig and b_orig and a_orig == b_orig:
        return True

    # 4. 中文标题 + 年份匹配
    a_title = normalize_text(a.get("title") or "")
    b_title = normalize_text(b.get("title") or "")
    if not a_title or not b_title:
        return False

    # 标题相似度
    if fuzzy_score(a_title, b_title) < _FUZZY_THRESHOLD:
        # 中文字重叠兜底（短标题场景）
        a_chars = _extract_chinese(a.get("title") or "")
        b_chars = _extract_chinese(b.get("title") or "")
        if not a_chars or not b_chars:
            return False
        overlap = len(a_chars & b_chars)
        min_len = min(len(a_chars), len(b_chars))
        max_len = max(len(a_chars), len(b_chars))
        # 短标题（<= 3 字）要求完全包含（overlap == min_len 且长度差 <= 1）
        if min_len <= 3:
            if overlap < min_len or max_len - min_len > 1:
                return False
        else:
            # 长标题要求重叠比例 >= 70%
            if overlap < max(2, int(min_len * 0.7)):
                return False

    # 年份校验
    a_year = a.get("year") or ""
    b_year = b.get("year") or ""
    if a_year and b_year:
        try:
            if abs(int(a_year) - int(b_year)) > _YEAR_TOLERANCE:
                return False
        except (ValueError, TypeError):
            pass

    return True


def _is_anime(item: Dict) -> bool:
    """判断是否为动画类资源"""
    genres = item.get("genres") or []
    genre_str = " ".join(g.lower() for g in genres)
    return any(kw in genre_str for kw in ("动画", "animation", "anime"))


def _normalize_score(rating: float, source: str) -> float:
    """评分归一化到 10 分制基准"""
    if not rating or rating <= 0:
        return 0.0
    if source == "douban":
        return rating * 1.0
    elif source == "tmdb":
        return (rating + 0.5) * 0.9  # 补偿 TMDB 评分偏低
    elif source == "bangumi":
        return rating + 0.2  # 补偿动漫评分严苛
    return rating


def _calc_final_score(item: Dict, source_count: int) -> float:
    """加权计算 final_score"""
    base = item.get("_normalized_score", 0.0)

    # 豆瓣来源加成
    if item.get("_source") == "douban":
        base += 0.5

    # 动漫爱好者加成
    if _is_anime(item):
        base += 0.8

    # 当季新番加成（Bangumi 来源 + 首播 180 天内）
    if item.get("_source") == "bangumi" and item.get("year"):
        try:
            import datetime
            air_year = int(item["year"])
            now_year = datetime.datetime.now().year
            if now_year - air_year <= 0:
                base += 0.8
                item["is_new_anime"] = True
        except (ValueError, TypeError):
            pass

    # 多源共振
    if source_count >= 3:
        base += 2.0
    elif source_count >= 2:
        base += 1.0

    # 冷门降权：单源且评价人数极少
    if source_count <= 1:
        vote_count = item.get("vote_count") or item.get("rating_count") or 0
        if isinstance(vote_count, (int, float)) and vote_count < 100:
            base *= 0.8

    return round(base, 2)


def _dedup_and_merge(all_items: List[Tuple[Dict, str]]) -> List[Dict]:
    """多维去重 + 合并多源信息。
    all_items: [(item_dict, source_name), ...]
    返回去重后的列表，每个 item 带 _source_count 和 _sources 字段。
    """
    merged: List[Dict] = []

    for item, source in all_items:
        item["_source"] = source
        found = False
        for existing in merged:
            if _is_same_media(existing, item):
                # 合并：记录多源命中
                existing["_source_count"] = existing.get("_source_count", 1) + 1
                existing.setdefault("_sources", [existing.get("_source", "unknown")])
                if source not in existing["_sources"]:
                    existing["_sources"].append(source)
                # 取更高评分
                new_score = _normalize_score(item.get("rating", 0), source)
                if new_score > existing.get("_normalized_score", 0):
                    existing["_normalized_score"] = new_score
                # 更新封面（仅 ID 精确匹配时才覆盖，避免模糊匹配导致封面错误）
                has_id_match = (
                    (existing.get("tmdb_id") and item.get("tmdb_id") and existing["tmdb_id"] == item["tmdb_id"]) or
                    (existing.get("douban_id") and item.get("douban_id") and existing["douban_id"] == item["douban_id"])
                )
                if has_id_match and source == "tmdb" and item.get("poster_url"):
                    existing["poster_url"] = item["poster_url"]
                    existing["cover_url"] = item.get("cover_url") or item.get("poster_url")
                found = True
                break

        if not found:
            item["_source_count"] = 1
            item["_sources"] = [source]
            item["_normalized_score"] = _normalize_score(item.get("rating", 0), source)
            merged.append(item)

    return merged


def _assign_reason(item: Dict) -> str:
    """生成推荐理由"""
    sc = item.get("_source_count", 1)
    if sc >= 3:
        return "全网热门"
    if item.get("is_new_anime"):
        return "当季新番"
    if _is_anime(item) and item.get("rating", 0) >= 7.5:
        return "高分番剧"
    if item.get("_source") == "douban":
        return "豆瓣热榜"
    if item.get("_source") == "tmdb":
        return "全球热门"
    if item.get("_source") == "bangumi":
        return "Bangumi 热门"
    return "综合推荐"


def _fallback_fill(current: List[Dict], target: int) -> List[Dict]:
    """去重后不足 target 条时，从 top250 和 weekly 补位"""
    need = target - len(current)
    if need <= 0:
        return current

    existing_titles = {normalize_text(i.get("title") or "") for i in current}
    existing_ids = set()
    for i in current:
        if i.get("douban_id"):
            existing_ids.add(str(i["douban_id"]))
        if i.get("tmdb_id"):
            existing_ids.add(f"tmdb_{i['tmdb_id']}")

    def _is_dup(item: Dict) -> bool:
        did = str(item.get("douban_id") or "")
        if did and did in existing_ids:
            return True
        tid = item.get("tmdb_id")
        if tid and f"tmdb_{tid}" in existing_ids:
            return True
        t = normalize_text(item.get("title") or "")
        return t and t in existing_titles

    fill_items = []
    # 优先从 top250 补位
    try:
        top = douban_api_v2.movie_top250(0, need * 2)
        for item in (top or []):
            if not _is_dup(item):
                item["media_type"] = item.get("media_type") or "movie"
                item["_source"] = "douban"
                item["_source_count"] = 1
                item["_sources"] = ["douban"]
                item["_normalized_score"] = _normalize_score(item.get("rating", 0), "douban")
                item["_final_score"] = _calc_final_score(item, 1)
                fill_items.append(item)
                existing_titles.add(normalize_text(item.get("title") or ""))
                if len(fill_items) >= need:
                    break
    except Exception as e:
        print(f"[CombinedRecommend] top250 补位失败: {e}")

    # 仍不足则从 weekly 补位
    if len(fill_items) < need:
        try:
            weekly = douban_api_v2.tv_weekly_chinese(0, 20)
            weekly = (weekly or []) + (douban_api_v2.tv_weekly_global(0, 20) or [])
            for item in weekly:
                if not _is_dup(item):
                    item["media_type"] = item.get("media_type") or "tv"
                    item["_source"] = "douban"
                    item["_source_count"] = 1
                    item["_sources"] = ["douban"]
                    item["_normalized_score"] = _normalize_score(item.get("rating", 0), "douban")
                    item["_final_score"] = _calc_final_score(item, 1)
                    fill_items.append(item)
                    existing_titles.add(normalize_text(item.get("title") or ""))
                    if len(fill_items) >= need:
                        break
        except Exception as e:
            print(f"[CombinedRecommend] weekly 补位失败: {e}")

    return current + fill_items[:need]


def _interleave(items: List[Dict]) -> List[Dict]:
    """影剧交叉排列：每 3 条中至少 1 条电影 + 1 条剧集/番剧"""
    movies = [i for i in items if i.get("media_type") == "movie"]
    others = [i for i in items if i.get("media_type") != "movie"]

    if not movies or not others:
        return items

    result = []
    mi, oi = 0, 0
    while mi < len(movies) or oi < len(others):
        # 每 3 条：2 条 others + 1 条 movie
        for _ in range(2):
            if oi < len(others):
                result.append(others[oi]); oi += 1
        if mi < len(movies):
            result.append(movies[mi]); mi += 1

    return result


def get_combined_recommend() -> List[Dict]:
    """综合推荐主入口。并发拉取三源数据 → 去重 → 评分 → 排序 → 产出。
    单源超时/失败不影响其他源。
    """
    from shared import get_clients

    all_items: List[Tuple[Dict, str]] = []

    def _fetch_douban():
        """豆瓣：热门电影 20 条 + 热门剧集 20 条 + 热门动画 10 条"""
        results = []
        try:
            movies = douban_api_v2.movie_hot(0, 20)
            for m in (movies or []):
                m["media_type"] = m.get("media_type") or "movie"
            results.extend(movies or [])
        except Exception as e:
            print(f"[CombinedRecommend] 豆瓣电影失败: {e}")
        try:
            tvs = douban_api_v2.tv_hot(0, 20)
            for t in (tvs or []):
                t["media_type"] = t.get("media_type") or "tv"
            results.extend(tvs or [])
        except Exception as e:
            print(f"[CombinedRecommend] 豆瓣剧集失败: {e}")
        try:
            animes = douban_api_v2.tv_animation(0, 10)
            for a in (animes or []):
                a["media_type"] = a.get("media_type") or "tv"
            results.extend(animes or [])
        except Exception as e:
            print(f"[CombinedRecommend] 豆瓣动画失败: {e}")
        return [(_normalize_douban(r), "douban") for r in results]

    def _fetch_tmdb():
        """TMDB：trending/week 40 条（2 页）"""
        try:
            tmdb = get_clients()["tmdb"]
            items = []
            for pg in (1, 2):
                page_items = tmdb.trending(page=pg)
                items.extend(page_items or [])
            return [(_normalize_tmdb(r), "tmdb") for r in items]
        except Exception as e:
            print(f"[CombinedRecommend] TMDB 失败: {e}")
            return []

    def _fetch_bangumi():
        """Bangumi：calendar 热门 20 条"""
        try:
            items = bangumi_client.get_hot_anime(0, 20)
            return [(_normalize_bangumi(r), "bangumi") for r in (items or [])]
        except Exception as e:
            print(f"[CombinedRecommend] Bangumi 失败: {e}")
            return []

    # 并发拉取，timeout=5s
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_fetch_douban): "douban",
            pool.submit(_fetch_tmdb): "tmdb",
            pool.submit(_fetch_bangumi): "bangumi",
        }
        for future in concurrent.futures.as_completed(futures, timeout=8):
            try:
                result = future.result(timeout=5)
                all_items.extend(result)
            except Exception as e:
                src = futures[future]
                print(f"[CombinedRecommend] {src} 超时或异常: {e}")

    if not all_items:
        return []

    # 去重 + 合并
    merged = _dedup_and_merge(all_items)

    # 计算 final_score
    for item in merged:
        item["_final_score"] = _calc_final_score(item, item.get("_source_count", 1))

    # 按 final_score 降序排序
    merged.sort(key=lambda x: x.get("_final_score", 0), reverse=True)

    # 动漫保底：至少 30% 动画类
    anime_items = [i for i in merged if _is_anime(i)]
    non_anime = [i for i in merged if not _is_anime(i)]
    min_anime = max(int(_TARGET_COUNT * _ANIME_MIN_RATIO), 1)

    if len(anime_items) < min_anime:
        # 动漫不足，全部保留
        final = anime_items + non_anime[:_TARGET_COUNT - len(anime_items)]
    else:
        # 按 score 排序后取 top N，保证动漫占比
        final = merged[:_TARGET_COUNT]
        anime_in_final = sum(1 for i in final if _is_anime(i))
        if anime_in_final < min_anime:
            # 从 anime_items 补位
            extra_needed = min_anime - anime_in_final
            existing_ids = {i.get("title") for i in final}
            for a in anime_items:
                if extra_needed <= 0:
                    break
                if a.get("title") not in existing_ids:
                    final.append(a)
                    extra_needed -= 1
            final = final[:_TARGET_COUNT]

    # Fallback 补位：去重后不足目标数时，从 top250 和 weekly 补位
    if len(final) < _TARGET_COUNT:
        final = _fallback_fill(final, _TARGET_COUNT)

    # 影剧交叉排列
    final = _interleave(final)

    # 生成推荐理由 + 清理内部字段
    output = []
    for item in final[:_TARGET_COUNT]:
        item["reason"] = _assign_reason(item)
        item["is_new_anime"] = item.get("is_new_anime", False)
        # 清理内部字段
        for key in ("_source", "_source_count", "_sources", "_normalized_score", "_final_score"):
            item.pop(key, None)
        output.append(item)

    return output


# ── 数据标准化（统一为 DoubanHotItem 兼容格式）──

def _normalize_douban(item: Dict) -> Dict:
    """豆瓣数据已经是标准格式，补充 cover_url"""
    item["cover_url"] = item.get("poster_url") or item.get("cover_url") or ""
    return item


def _normalize_tmdb(item: Dict) -> Dict:
    """TMDB trending 数据标准化"""
    item["cover_url"] = item.get("poster_url") or item.get("cover_url") or ""
    item["original_title"] = item.get("original_title") or ""
    item["douban_id"] = ""
    return item


def _normalize_bangumi(item: Dict) -> Dict:
    """Bangumi calendar 数据标准化"""
    item["cover_url"] = item.get("cover_url") or ""
    item["original_title"] = item.get("subtitle") or ""
    item["media_type"] = "tv"
    return item
