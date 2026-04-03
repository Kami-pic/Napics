import requests
import re
import os
import json
import unicodedata
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from pydantic import BaseModel
from text_utils import normalize_text

if TYPE_CHECKING:
    from enhanced_scorer import EnhancedScorer, MatchResult
    from search_query_builder import SearchQueryBuilder
    from shadow_name_manager import ShadowNameManager
    from alias_resolver import AliasResolver

def _is_latin(text: str) -> bool:
    """判断字符串是否主要由拉丁字母组成（英文/法文/德文等）"""
    if not text:
        return False
    latin_count = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = sum(1 for ch in text if ch.isalpha())
    return total > 0 and latin_count / total > 0.5

# ── 数据模型 ──

class ScrapeResult(BaseModel):
    tmdb_id: int = 0
    media_type: str = ""  # "movie" | "tv" | "season" | "episode"
    title: str = ""              # 中文名（zh-CN）
    original_title: str = ""     # 原始语言名（日文/韩文/英文等）
    english_title: str = ""      # 英文名（en-US）
    year: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    overview: str = ""
    rating: float = 0.0
    genres: List[str] = []
    director: str = ""
    cast: List[str] = []
    runtime: int = 0
    imdb_id: str = ""
    total_seasons: int = 0
    status: str = ""
    season_number: int = 0
    episode_count: int = 0
    air_date: str = ""
    countries: List[str] = []  # 制片国家
    episode_number: int = 0
    episode_title: str = ""
    still_url: Optional[str] = None
    seasons_info: List[Dict] = []  # [{"season_number": 1, "episode_count": 25}, ...]

CACHE_DIR = os.path.join(os.path.dirname(__file__), "scrape_cache")

# ── 文本标准化 & 匹配算法 ──

def parse_filename(filename: str) -> dict:
    """解析文件名，提取作品名、季、集、年份，清洗标签"""
    name = os.path.splitext(filename)[0]
    # 只去掉视频扩展名，不去掉 .Paprika 这种
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in video_exts:
        name = filename
    
    result = {"clean_name": "", "season": None, "episode": None, "absolute_episode": None, "year": None, "raw": name}
    
    # 预处理：+ 替换为空格（字幕组常用 + 代替空格）
    name = re.sub(r'\+', ' ', name)
    
    # 先从原始文件名提取集号（在清洗之前，因为 [02] 会被清掉）
    # 匹配 S01E01
    ep_match = re.search(r'S(\d+)\s*E(\d+)', name, re.I)
    if ep_match:
        result["season"] = int(ep_match.group(1))
        result["episode"] = int(ep_match.group(2))
    
    # 匹配中文/日文 第X季第X集/第X話
    if result["episode"] is None:
        cn_ep = re.search(r'第(\d+)[集话話]', name)
        cn_season = re.search(r'第(\d+)季', name)
        if cn_ep:
            result["episode"] = int(cn_ep.group(1))
            result["season"] = int(cn_season.group(1)) if cn_season else 1
    
    # 匹配方括号内的纯数字集号 [02] [12] [END]
    if result["episode"] is None:
        bracket_ep = re.search(r'\[(\d{1,3})\]', name)
        if bracket_ep:
            result["episode"] = int(bracket_ep.group(1))
            result["season"] = 1
    
    # 匹配方括号内数字+版本号 [13v2] [02v2]
    if result["episode"] is None:
        bracket_v_ep = re.search(r'\[(\d{1,3})v\d\]', name, re.I)
        if bracket_v_ep:
            result["episode"] = int(bracket_v_ep.group(1))
            result["season"] = 1
    
    # 匹配圆括号内的纯数字集号 (02) (12)（如 "加速世界 (10).mp4"）
    if result["episode"] is None:
        paren_ep = re.search(r'\((\d{1,3})\)', name)
        if paren_ep:
            ep_num = int(paren_ep.group(1))
            if 1 <= ep_num <= 999 and ep_num not in (720, 1080, 480, 2160):
                result["episode"] = ep_num
                result["season"] = 1
    
    # 匹配连字符分隔的集号：- 01 后面可以跟空格/括号/方括号
    if result["episode"] is None:
        dash_ep = re.search(r'(?:^|[^\d])\s*-\s*(\d{1,3})\s*(?:[-\[\(]|$)', name)
        if dash_ep:
            ep_num = int(dash_ep.group(1))
            if 1 <= ep_num <= 999:
                result["episode"] = ep_num
                result["season"] = 1
    
    # 匹配 S1 01 格式（S+季号+空格+集号，非标准 S01E01）
    if result["episode"] is None:
        s_space_ep = re.search(r'S(\d+)\s+(\d{1,3})\b', name, re.I)
        if s_space_ep:
            result["season"] = int(s_space_ep.group(1))
            result["episode"] = int(s_space_ep.group(2))
    
    # 匹配中文数字集号：第一集、第二集
    if result["episode"] is None:
        cn_num_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
                      '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,'十六':16,'十七':17,'十八':18,'十九':19,'二十':20}
        cn_ep2 = re.search(r'第([一二三四五六七八九十]+)[集话話]', name)
        if cn_ep2:
            cn_text = cn_ep2.group(1)
            if cn_text in cn_num_map:
                result["episode"] = cn_num_map[cn_text]
                result["season"] = 1
    
    # 匹配文件名开头的纯数字（如 "02.2160p.HD..." 或 "01 xxx"）
    if result["episode"] is None:
        head_ep = re.match(r'^(\d{1,3})(?:\.|[ \t])', name)
        if head_ep:
            ep_num = int(head_ep.group(1))
            if 1 <= ep_num <= 999 and ep_num not in (720, 1080, 480, 2160, 1920, 1280):
                result["episode"] = ep_num
                result["season"] = 1
    
    # 匹配 SP01/SP02（特别篇，归入 Season 0）
    if result["episode"] is None:
        sp_match = re.search(r'\bSP\s*(\d{1,3})\b', name, re.I)
        if sp_match:
            result["episode"] = int(sp_match.group(1))
            result["season"] = 0  # 特别篇 = Season 0
    
    # 匹配 EP01 或 E01（不在 S01E01 里的）
    if result["episode"] is None:
        ep2 = re.search(r'(?<![SE])EP?(\d{1,3})\b', name, re.I)
        if ep2:
            result["episode"] = int(ep2.group(1))
            result["season"] = 1
    
    # 匹配标题后空格+数字+空格/括号（如 "Baccano! 01 (" 或 "Title 03 ["）
    if result["episode"] is None:
        title_ep = re.search(r'[a-zA-Z!?）\u4e00-\u9fff]\s+(\d{1,3})\s*[\[\(（]', name)
        if title_ep:
            ep_num = int(title_ep.group(1))
            if 1 <= ep_num <= 999 and ep_num not in (720, 1080, 480, 2160):
                result["episode"] = ep_num
                result["season"] = 1
    
    # 匹配尾部纯数字集号（如 "权力的游戏第一季1024高清02.rmvb" 里的 02）
    if result["episode"] is None:
        # 先去掉尾部的分辨率标签再提取
        import re as _re_tail
        tail_name = name
        tail_name = _re_tail.sub(r'\s*\d{3,4}[pPiI]?\s*$', '', tail_name)  # 去尾部 720p 等
        tail_name = _re_tail.sub(r'\s*(?:720|1080|480|2160|1024|1280)\s*$', '', tail_name)  # 去尾部纯分辨率数字
        tail_ep = _re_tail.search(r'(?:^|[^\d])(\d{1,2})$', tail_name)
        if tail_ep:
            ep_num = int(tail_ep.group(1))
            if 1 <= ep_num <= 99:  # 合理的集号范围
                result["episode"] = ep_num
                # 尝试从文件名提取季号
                cn_s = re.search(r'第([一二三四五六七八九十\d]+)季', name)
                if cn_s:
                    s_text = cn_s.group(1)
                    cn_num_map = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
                    result["season"] = cn_num_map.get(s_text, int(s_text) if s_text.isdigit() else 1)
                else:
                    result["season"] = 1
    
    # 匹配纯数字文件名（如 "060" "100" — 去掉扩展名后整个就是数字）
    if result["episode"] is None:
        pure_num = re.match(r'^0*(\d+)$', name.strip())
        if pure_num:
            ep_num = int(pure_num.group(1))
            if 1 <= ep_num <= 9999 and ep_num not in (720, 1080, 480, 2160, 1920, 1280):
                result["episode"] = ep_num
                result["season"] = 1
    
    # 清洗文件名
    clean = re.sub(r'[\[\(【（].*?[\]\)】）]', ' ', name)
    clean = re.sub(r'(?i)\b(2160p|1080p|720p|480p|BluRay|Blu-Ray|WEB-?DL|WEBRip|HDTV|DVDRip|BDRip|x264|x265|H\.?264|H\.?265|HEVC|AVC|AAC|DTS|DTS-HD|FLAC|Atmos|TrueHD|Remux|PROPER|REPACK|10bit|HDR|DV|DoVi)\b', '', clean)
    # BD/HD/SD 紧跟中文或在词边界都要去掉
    clean = re.sub(r'(?<![a-zA-Z])(BD|HD|SD)(?![a-zA-Z])', '', clean, flags=re.I)
    clean = re.sub(r'(?i)\b(CMCT|CHD|Wiki|FLTth|HDChina|MTeam|TTG|FRDS|RARBG|YTS|YIFY)\b', '', clean)
    # 中文语言/字幕标签（更全面）
    clean = re.sub(r'(中英双字|中英字幕|中文字幕|双语字幕|简繁字幕|简体|繁体|中字|英字|字幕组|影视)', '', clean)
    clean = re.sub(r'(国粤日三语|国日双语|国英双语|国粤双语|日语中字|中英双语|国语|粤语|日语|韩语|英语|法语|德语)', '', clean)
    clean = re.sub(r'\b\w+\.(com|co|net|org|cc|tv|me)\b', '', clean, flags=re.I)
    clean = re.sub(r'www\.\S+', '', clean, flags=re.I)
    clean = re.sub(r'[._]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.strip(' -·')
    
    # 如果有 S01E01，截取作品名
    if ep_match:
        pos = name.upper().find(ep_match.group(0).upper())
        if pos > 0:
            pre = name[:pos]
            pre = re.sub(r'[\[\(【（].*?[\]\)】）]', ' ', pre)
            pre = re.sub(r'[._\-]', ' ', pre).strip()
            if pre:
                clean = pre
    
    # 提取年份（开头或末尾都处理）
    year_match = re.search(r'((?:19|20)\d{2})', clean)
    if year_match:
        result["year"] = year_match.group(1)
        # 去掉年份（不管在哪个位置）
        clean = clean[:year_match.start()] + clean[year_match.end():]
        clean = clean.strip(' -·')
    
    # 最终清理：去掉残留的分辨率标签（可能紧跟中文没有边界）
    clean = re.sub(r'(?i)(2160|1080|1024|720|480)[piPIkK]?', '', clean)
    # 去掉中文标点
    clean = re.sub(r'[：；，。！？、]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.strip(' -·')
    
    result["clean_name"] = clean
    
    # ── 绝对集数判定 ──
    # 如果 season 被默认设为 1 且没有明确的季号特征，
    # 同时 episode 数值 > 50（保守阈值），则判定为绝对集数
    if result["episode"] is not None and result["season"] == 1:
        has_explicit_season = bool(re.search(
            r'S\d+|第\d+季|Season\s*\d+|[①②③④⑤⑥⑦⑧⑨⑩]', filename, re.I
        ))
        if not has_explicit_season and result["episode"] > 50:
            result["absolute_episode"] = result["episode"]
            result["season"] = None
            result["episode"] = None
    
    return result


def build_absolute_episode_map(seasons_info: List[Dict]) -> Dict[int, tuple]:
    """构建绝对集数 → (season_number, episode_number) 的映射表。
    关键：跳过 Season 0（特别篇），只累加正式季。
    
    参数: seasons_info — 来自 ScrapeResult.seasons_info
          [{"season_number": 0, "episode_count": 5}, {"season_number": 1, "episode_count": 25}, ...]
    返回: {1: (1,1), 2: (1,2), ..., 26: (2,1), ..., 60: (3,10)}
    """
    mapping: Dict[int, tuple] = {}
    absolute_counter = 1
    
    for s in sorted(seasons_info, key=lambda x: x.get("season_number", 0)):
        sn = s.get("season_number", 0)
        if sn == 0:  # 跳过特别篇
            continue
        ep_count = s.get("episode_count", 0)
        for ep in range(1, ep_count + 1):
            mapping[absolute_counter] = (sn, ep)
            absolute_counter += 1
    
    return mapping


def calc_match_score(query_norm: str, candidate_title: str, candidate_original: str, candidate_year: str, target_year: Optional[str]) -> int:
    """计算匹配评分，借鉴多维度评分算法"""
    score = 0
    
    title_norm = normalize_text(candidate_title)
    orig_norm = normalize_text(candidate_original)
    
    if not query_norm:
        return 0
    
    short_query = len(query_norm) <= 2
    
    # 中文名匹配（最高 100 分）
    if title_norm:
        if title_norm == query_norm:
            score = max(score, 100)
        elif not short_query and len(title_norm) > 2:
            if title_norm.startswith(query_norm) or query_norm.startswith(title_norm):
                score = max(score, 70)
            elif title_norm in query_norm or query_norm in title_norm:
                score = max(score, 50)
    
    # 原名匹配（最高 80 分）
    orig_score = 0
    if orig_norm and orig_norm != title_norm:
        if orig_norm == query_norm:
            orig_score = 80
        elif not short_query and len(orig_norm) > 2:
            if orig_norm.startswith(query_norm) or query_norm.startswith(orig_norm):
                orig_score = 60
            elif orig_norm in query_norm or query_norm in orig_norm:
                orig_score = 40
    
    # 交叉验证：中文名和原名都有匹配 +15
    if score >= 50 and orig_score >= 40:
        score += 15
    score = max(score, orig_score)
    
    # 年份匹配：有年份时是决定性因素
    if target_year and candidate_year:
        try:
            diff = abs(int(target_year) - int(candidate_year))
            if diff == 0:
                score += 40  # 精确匹配
            elif diff <= 1:
                score += 20  # 相差1年（可能是发行年 vs 首播年）
            else:
                score -= 50  # 年份差距大，大幅扣分
        except ValueError:
            pass
    
    return score

def best_match(query: str, results: List[dict], year: Optional[str] = None, type_key: str = "title") -> Optional[dict]:
    """从搜索结果中选最佳匹配"""
    if not results:
        return None
    
    query_norm = normalize_text(query)
    best = None
    best_score = 0
    
    for item in results:
        title = item.get(type_key, "") or item.get("name", "")
        original = item.get(f"original_{type_key}", "") or item.get("original_name", "")
        item_year = (item.get("release_date", "") or item.get("first_air_date", ""))[:4]
        
        s = calc_match_score(query_norm, title, original, item_year, year)
        
        # 热度加分：没有年份信息时热度更重要（最高 +20）
        popularity = item.get("popularity", 0)
        if year:
            s += min(int(popularity / 10), 10)
        else:
            s += min(int(popularity / 5), 20)
        
        if s > best_score:
            best_score = s
            best = item
    
    # 最低阈值：至少 30 分才算匹配上
    return best if best_score >= 30 else None

# ── TMDB 客户端 ──

class TMDBClient:
    def __init__(self, api_key: str, proxy: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.proxy = proxy
        os.makedirs(CACHE_DIR, exist_ok=True)

        # 增强刮削组件（延迟初始化）
        self._shadow_manager: Optional[ShadowNameManager] = None
        self._alias_resolver: Optional[AliasResolver] = None
        self._scorer: Optional[EnhancedScorer] = None
        self._query_builder: Optional[SearchQueryBuilder] = None

    @property
    def shadow_manager(self) -> "ShadowNameManager":
        if self._shadow_manager is None:
            from shadow_name_manager import ShadowNameManager
            self._shadow_manager = ShadowNameManager()
        return self._shadow_manager

    @property
    def alias_resolver(self) -> "AliasResolver":
        if self._alias_resolver is None:
            import douban_client
            import bangumi_client
            from alias_resolver import AliasResolver
            self._alias_resolver = AliasResolver(douban_client, bangumi_client)
        return self._alias_resolver

    @property
    def scorer(self) -> "EnhancedScorer":
        if self._scorer is None:
            from enhanced_scorer import EnhancedScorer
            self._scorer = EnhancedScorer()
        return self._scorer

    @property
    def query_builder(self) -> "SearchQueryBuilder":
        if self._query_builder is None:
            from search_query_builder import SearchQueryBuilder
            self._query_builder = SearchQueryBuilder()
        return self._query_builder

    def _get(self, path: str, params: dict = {}) -> dict:
        params["api_key"] = self.api_key
        params.setdefault("language", "zh-CN")
        proxies = None
        if self.proxy:
            proxies = {"http": self.proxy, "https": self.proxy}
        resp = requests.get(f"{self.base_url}{path}", params=params, timeout=8, proxies=proxies)
        resp.raise_for_status()
        return resp.json()

    def _poster(self, path: Optional[str], size="w500") -> Optional[str]:
        return f"https://image.tmdb.org/t/p/{size}{path}" if path else None

    def _get_english_title(self, media_type: str, tmdb_id: int, original_title: str = "") -> str:
        """获取 TMDB 英文标题。如果 original_title 已经是英文则直接返回。
        结果缓存到文件避免重复请求。"""
        if original_title and _is_latin(original_title):
            return original_title
        # 检查缓存
        cache_key = f"en_{media_type}_{tmdb_id}"
        cp = os.path.join(CACHE_DIR, f"{cache_key}.json")
        cached = self._load_cache(cp)
        if cached and cached.get("en_title"):
            return cached["en_title"]
        try:
            endpoint = f"/{media_type}/{tmdb_id}"
            d = self._get(endpoint, {"language": "en-US"})
            if media_type == "movie":
                en = d.get("title", "") or d.get("original_title", "")
            else:
                en = d.get("name", "") or d.get("original_name", "")
            if en:
                self._save_cache(cp, {"en_title": en})
            return en
        except Exception:
            return ""

    def _cache_path(self, prefix: str, id: int) -> str:
        return os.path.join(CACHE_DIR, f"{prefix}_{id}.json")

    def _search_cache_path(self, prefix: str, query: str) -> str:
        # 用 query 的 hash 作为文件名
        import hashlib
        h = hashlib.md5(query.encode()).hexdigest()[:12]
        return os.path.join(CACHE_DIR, f"search_{prefix}_{h}.json")

    def _load_cache(self, path: str, max_age_hours: int = 0) -> Optional[dict]:
        if os.path.exists(path):
            try:
                # 检查过期时间
                if max_age_hours > 0:
                    import time
                    mtime = os.path.getmtime(path)
                    if time.time() - mtime > max_age_hours * 3600:
                        return None
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return None

    def _save_cache(self, path: str, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def search_movie(self, query: str) -> List[dict]:
        cp = self._search_cache_path("movie", query)
        cached = self._load_cache(cp, max_age_hours=24)
        if cached is not None:
            return cached.get("results", [])[:10]
        try:
            results = self._get("/search/movie", {"query": query}).get("results", [])[:10]
            self._save_cache(cp, {"results": results})
            return results
        except: return []

    def search_tv(self, query: str) -> List[dict]:
        cp = self._search_cache_path("tv", query)
        cached = self._load_cache(cp, max_age_hours=24)
        if cached is not None:
            return cached.get("results", [])[:10]
        try:
            results = self._get("/search/tv", {"query": query}).get("results", [])[:10]
            self._save_cache(cp, {"results": results})
            return results
        except: return []

    # ── 详情 ──

    def get_movie_detail(self, tmdb_id: int) -> ScrapeResult:
        cp = self._cache_path("movie", tmdb_id)
        cached = self._load_cache(cp)
        if cached:
            result = ScrapeResult(**cached)
            # 旧缓存没有 english_title，补充获取
            if not result.english_title:
                en = self._get_english_title("movie", tmdb_id, result.original_title)
                if en:
                    result.english_title = en
                    self._save_cache(cp, result.dict())
            return result
        try:
            d = self._get(f"/movie/{tmdb_id}", {"append_to_response": "credits"})
            credits = d.get("credits", {})
            directors = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
            cast = [c["name"] for c in credits.get("cast", [])[:6]]
            
            orig = d.get("original_title", "")
            # 获取英文名（如果 original_title 已经是英文就直接用）
            en_title = ""
            if _is_latin(orig):
                en_title = orig
            else:
                en_title = self._get_english_title("movie", tmdb_id, orig)
            
            r = ScrapeResult(
                tmdb_id=tmdb_id, media_type="movie",
                title=d.get("title", ""),
                original_title=orig,
                english_title=en_title,
                year=d.get("release_date", "")[:4],
                poster_url=self._poster(d.get("poster_path")),
                backdrop_url=self._poster(d.get("backdrop_path"), "w1280"),
                overview=d.get("overview", ""), rating=round(d.get("vote_average", 0), 1),
                genres=[g["name"] for g in d.get("genres", [])],
                director=directors[0] if directors else "", cast=cast,
                runtime=d.get("runtime", 0), imdb_id=d.get("imdb_id") or "",
                countries=[c["name"] for c in d.get("production_countries", [])],
            )
            self._save_cache(cp, r.dict())
            return r
        except Exception as e:
            print(f"TMDB movie detail error: {e}")
            return ScrapeResult()

    def get_tv_detail(self, tmdb_id: int) -> ScrapeResult:
        cp = self._cache_path("tv", tmdb_id)
        cached = self._load_cache(cp)
        if cached:
            result = ScrapeResult(**cached)
            if not result.english_title:
                en = self._get_english_title("tv", tmdb_id, result.original_title)
                if en:
                    result.english_title = en
                    self._save_cache(cp, result.dict())
            return result
        try:
            d = self._get(f"/tv/{tmdb_id}")
            
            orig = d.get("original_name", "")
            en_title = ""
            if _is_latin(orig):
                en_title = orig
            else:
                en_title = self._get_english_title("tv", tmdb_id, orig)
            
            r = ScrapeResult(
                tmdb_id=tmdb_id, media_type="tv",
                title=d.get("name", ""),
                original_title=orig,
                english_title=en_title,
                year=d.get("first_air_date", "")[:4],
                poster_url=self._poster(d.get("poster_path")),
                backdrop_url=self._poster(d.get("backdrop_path"), "w1280"),
                overview=d.get("overview", ""), rating=round(d.get("vote_average", 0), 1),
                genres=[g["name"] for g in d.get("genres", [])],
                total_seasons=d.get("number_of_seasons", 0), status=d.get("status", ""),
                countries=[c.get("name", c) if isinstance(c, dict) else c for c in d.get("production_countries", d.get("origin_country", []))],
                seasons_info=[
                    {"season_number": s["season_number"], "episode_count": s["episode_count"]}
                    for s in d.get("seasons", [])
                    if isinstance(s, dict) and "season_number" in s and "episode_count" in s
                ],
            )
            self._save_cache(cp, r.dict())
            return r
        except Exception as e:
            print(f"TMDB tv detail error: {e}")
            return ScrapeResult()

    def get_season_detail(self, tv_id: int, season_num: int) -> ScrapeResult:
        cp = self._cache_path(f"tv{tv_id}_s", season_num)
        cached = self._load_cache(cp)
        if cached: return ScrapeResult(**cached)
        try:
            d = self._get(f"/tv/{tv_id}/season/{season_num}")
            r = ScrapeResult(
                tmdb_id=tv_id, media_type="season", title=d.get("name", ""),
                season_number=season_num, poster_url=self._poster(d.get("poster_path")),
                overview=d.get("overview", ""), episode_count=len(d.get("episodes", [])),
                air_date=d.get("air_date", ""),
            )
            self._save_cache(cp, r.dict())
            return r
        except Exception as e:
            print(f"TMDB season detail error: {e}")
            return ScrapeResult()

    def get_episode_detail(self, tv_id: int, season_num: int, ep_num: int) -> ScrapeResult:
        cp = self._cache_path(f"tv{tv_id}_s{season_num}_e", ep_num)
        cached = self._load_cache(cp)
        if cached: return ScrapeResult(**cached)
        try:
            d = self._get(f"/tv/{tv_id}/season/{season_num}/episode/{ep_num}")
            r = ScrapeResult(
                tmdb_id=tv_id, media_type="episode",
                episode_number=ep_num, season_number=season_num,
                episode_title=d.get("name", ""), overview=d.get("overview", ""),
                rating=round(d.get("vote_average", 0), 1),
                still_url=self._poster(d.get("still_path"), "w400"),
                air_date=d.get("air_date", ""),
            )
            self._save_cache(cp, r.dict())
            return r
        except Exception as e:
            print(f"TMDB episode detail error: {e}")
            return ScrapeResult()

    # ── 智能刮削：解析文件名 + 评分匹配 ──

    def scrape_by_filename(self, filename: str) -> ScrapeResult:
        parsed = parse_filename(filename)
        query = parsed["clean_name"]
        if not query:
            return ScrapeResult()
        
        # 清理搜索词中的连字符（TMDB 搜索对连字符敏感）
        search_query = re.sub(r'[-–—]', ' ', query).strip()
        search_query = re.sub(r'\s+', ' ', search_query)

        season = parsed.get("season")
        episode = parsed.get("episode")
        year = parsed.get("year")

        # 有集号 → 剧集
        if episode is not None:
            results = self.search_tv(search_query)
            match = best_match(query, results, year, type_key="name")
            if match:
                tv_id = match["id"]
                tv_detail = self.get_tv_detail(tv_id)
                s_num = season or 1
                ep_detail = self.get_episode_detail(tv_id, s_num, episode)
                return ScrapeResult(
                    tmdb_id=tv_id, media_type="episode",
                    title=tv_detail.title, original_title=tv_detail.original_title,
                    year=tv_detail.year, poster_url=tv_detail.poster_url,
                    overview=ep_detail.overview or tv_detail.overview,
                    rating=ep_detail.rating or tv_detail.rating,
                    genres=tv_detail.genres,
                    season_number=s_num, episode_number=episode,
                    episode_title=ep_detail.episode_title,
                    still_url=ep_detail.still_url,
                    total_seasons=tv_detail.total_seasons, status=tv_detail.status,
                )

        # 无集号 → 先搜电影，再搜剧集，取最高分
        movie_results = self.search_movie(search_query)
        tv_results = self.search_tv(search_query)

        movie_match = best_match(query, movie_results, year, type_key="title")
        tv_match = best_match(query, tv_results, year, type_key="name")

        # 比较两者评分
        query_norm = normalize_text(query)
        movie_score = 0
        tv_score = 0

        if movie_match:
            movie_score = calc_match_score(
                query_norm,
                movie_match.get("title", ""),
                movie_match.get("original_title", ""),
                movie_match.get("release_date", "")[:4],
                year
            )
        if tv_match:
            tv_score = calc_match_score(
                query_norm,
                tv_match.get("name", ""),
                tv_match.get("original_name", ""),
                tv_match.get("first_air_date", "")[:4],
                year
            )

        if movie_score >= tv_score and movie_match:
            return self.get_movie_detail(movie_match["id"])
        elif tv_match:
            return self.get_tv_detail(tv_match["id"])

        return ScrapeResult()

    # ── 增强刮削：影子名 + 别名 + 增强评分 ──

    def enhanced_scrape_by_filename(self, filename: str,
                                    file_path: str = "") -> "MatchResult":
        """增强版文件名刮削 — 使用影子名、别名解析、增强评分

        前置条件: filename 非空
        后置条件: 返回 MatchResult，confidence 反映匹配质量
                 刮削成功且置信度 high/medium 时自动回填影子名
        """
        from enhanced_scorer import MatchResult

        # Step 0: 优先使用影子名
        parsed = parse_filename(filename)
        year = parsed.get("year")
        season = parsed.get("season")
        episode = parsed.get("episode")

        if file_path:
            search_name = self.shadow_manager.get_search_name(file_path)
        else:
            search_name = ""

        if search_name and search_name != filename:
            # 有影子名，用影子名作为搜索词
            title = search_name
        else:
            title = parsed["clean_name"]

        if not title:
            return MatchResult(item={}, score=0, confidence="low",
                               match_details={})

        # Step 1: 收集别名
        aliases = self.alias_resolver.resolve(title, year or "")

        # Step 2: 构造搜索词列表
        queries = self.query_builder.build_tmdb_queries(
            title, aliases, year or ""
        )

        # Step 3: 对每个搜索词执行搜索，收集所有候选，按 TMDB ID 去重
        all_candidates: List[dict] = []
        seen_ids: set = set()

        for query in queries:
            if episode is not None:
                results = self.search_tv(query)
            else:
                results = self.search_movie(query) + self.search_tv(query)

            for r in results:
                rid = r.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_candidates.append(r)

        # Step 4: 增强评分，选出最佳匹配
        best = self.scorer.best_match(
            title, all_candidates, aliases, year
        )

        if not best or best.confidence == "low":
            return best or MatchResult(
                item={}, score=0, confidence="low",
                match_details={}
            )

        # Step 5: 获取详情
        if best.media_type == "movie":
            detail = self.get_movie_detail(best.tmdb_id)
        else:
            detail = self.get_tv_detail(best.tmdb_id)

        # 将详情信息更新到 best.item 中（方便调用方使用）
        if detail and detail.tmdb_id:
            best.item = detail.dict()

        # Step 6: 自动回填影子名（刮削成功且置信度 high/medium 时，优先英文名）
        if file_path and best.confidence in ("high", "medium"):
            en_title = (detail.english_title if detail and detail.english_title else "")
            orig_title = (detail.original_title if detail and detail.original_title else "")
            # 优先英文名，fallback 到原始语言名
            shadow_title = en_title or orig_title
            detail_year = (detail.year if detail else "")
            if shadow_title:
                shadow = (f"{shadow_title} ({detail_year})"
                          if detail_year else shadow_title)
                self.shadow_manager.auto_fill(
                    file_path, shadow, source="tmdb",
                    tmdb_id=best.tmdb_id
                )

        return best

    # ── 生成规范文件名（用于重命名功能） ──

    @staticmethod
    def generate_clean_filename(scrape: ScrapeResult, original_filename: str, video_info: dict = None) -> str:
        """根据刮削结果生成规范文件名"""
        ext = os.path.splitext(original_filename)[1]
        parts = []

        if scrape.media_type == "movie":
            parts.append(scrape.title or scrape.original_title)
            if scrape.year:
                parts.append(f"({scrape.year})")
        elif scrape.media_type in ("tv", "episode"):
            parts.append(scrape.title or scrape.original_title)
            if scrape.season_number:
                parts.append(f"S{str(scrape.season_number).zfill(2)}")
            if scrape.episode_number:
                parts.append(f"E{str(scrape.episode_number).zfill(2)}")

        # 附加音频信息
        if video_info:
            codec = video_info.get("audio_codec", "")
            channels = video_info.get("audio_channels", 0)
            if codec:
                parts.append(codec.upper())
            resolution = video_info.get("resolution", "")
            if resolution:
                h = video_info.get("height", 0)
                if h >= 2160: parts.append("2160p")
                elif h >= 1080: parts.append("1080p")
                elif h >= 720: parts.append("720p")

        name = " ".join(parts) if parts else os.path.splitext(original_filename)[0]
        # 清理文件名中不允许的字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        return name + ext
