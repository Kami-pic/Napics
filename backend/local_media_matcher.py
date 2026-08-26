"""本地媒体库感知模块 — 三层匹配 + 内存索引 + 异步补全

第一层：启动时构建内存索引（tmdb_id / 片名+年份 / clean_name），推荐/探索接口零延迟匹配
第二层：ID 映射缓存（douban_id → tmdb_id），持久化到 id_mapping_cache.json
第三层：异步补全（后台线程用 TMDB API 搜索补全未命中的豆瓣条目）
"""
import os
import logging
import re
import json
import time
import threading
from typing import Dict, List, Optional, Tuple

from text_processing import normalize
from text_utils import fuzzy_score

logger = logging.getLogger(__name__)
# ── 常量 ──
_FUZZY_THRESHOLD = 0.80  # 片名模糊匹配阈值
_YEAR_TOLERANCE = 1      # 年份允许 ±1 误差
_ASYNC_INTERVAL = 1.5    # 异步补全每条间隔（秒），避免 TMDB 限频
_CACHE_FILE = os.path.join(
    os.environ.get("NAPICS_DATA_DIR") or os.path.dirname(os.path.abspath(__file__)),
    "id_mapping_cache.json"
)
_QUALITY_THRESHOLDS = {"high": 720, "low": 0}  # height >= 720 算高画质


class LocalMediaMatcher:
    """本地媒体库匹配器（单例）"""

    def __init__(self):
        # 内存索引
        self._tmdb_index: Dict[int, dict] = {}          # tmdb_id → {title, max_height, folder}
        self._title_year_index: Dict[str, dict] = {}     # normalized_title|year → {title, max_height, folder}
        self._title_index: Dict[str, dict] = {}           # normalized_title → {title, max_height, folder}
        self._indexed = False

        # ID 映射缓存（douban_id → tmdb_id）
        self._id_cache: Dict[str, int] = {}
        self._load_id_cache()

        # 异步补全队列
        self._pending_queue: List[dict] = []
        self._queue_lock = threading.Lock()
        self._worker_running = False

    # ── 第一层：内存索引 ──

    def build_index(self, library: List[dict]):
        """从 media_library.json 构建内存索引。按文件夹聚合，取最高分辨率。"""
        tmdb_idx: Dict[int, dict] = {}
        title_year_idx: Dict[str, dict] = {}
        title_idx: Dict[str, dict] = {}

        # 按 folder_name 聚合
        folders: Dict[str, dict] = {}
        for v in library:
            fn = v.get("folder_name", "")
            if fn not in folders:
                folders[fn] = {
                    "clean_names": set(),
                    "shadow_names": set(),
                    "tmdb_ids": set(),
                    "max_height": 0,
                    "max_score": 0,
                    "folder": fn,
                    # 绝对目录：folder_name 是相对路径（虚拟库时还带库名前缀），
                    # 前端要用它跳转到媒体库目录树，而树节点的 path 是绝对路径。
                    # 给相对路径的话前端一定匹配不上，只能报"目录不在媒体库里"。
                    "abs_folder": "",
                }
            info = folders[fn]
            if not info["abs_folder"]:
                fp = v.get("file_path", "")
                if fp:
                    info["abs_folder"] = os.path.dirname(fp)
            cn = v.get("clean_name", "").strip()
            if cn:
                info["clean_names"].add(cn)
            sn = v.get("shadow_name", "").strip()
            if sn:
                info["shadow_names"].add(sn)
            tid = v.get("shadow_tmdb_id")
            if tid:
                info["tmdb_ids"].add(int(tid))
            # quality_score
            qs = v.get("quality_score", 0) or 0
            if qs > info["max_score"]:
                info["max_score"] = qs
            h = v.get("height") or 0
            # height=0 时尝试从文件名解析分辨率
            if h == 0:
                fname = v.get("file_name", "")
                if "2160p" in fname or "4K" in fname or "4k" in fname:
                    h = 2160
                elif "1080p" in fname or "1080i" in fname:
                    h = 1080
                elif "720p" in fname:
                    h = 720
            if h > info["max_height"]:
                info["max_height"] = h

        # 构建索引
        for fn, info in folders.items():
            # 质量判断：优先用 quality_score（100 分制），否则回退到 height
            max_score = info.get("max_score", 0)
            if max_score >= 35:  # 大约 1080p WEB-DL 级别
                quality = "high"
            elif info["max_height"] >= _QUALITY_THRESHOLDS["high"]:
                quality = "high"
            else:
                quality = "low"
            entry = {
                # 对外给绝对目录，拿不到时才退回相对（旧条目可能没有 file_path）
                "folder": info.get("abs_folder") or fn,
                "max_height": info["max_height"],
                "quality": quality,
                "quality_score": max_score,
            }

            # tmdb_id 索引
            for tid in info["tmdb_ids"]:
                if tid not in tmdb_idx or info["max_height"] > tmdb_idx[tid]["max_height"]:
                    tmdb_idx[tid] = entry

            # 片名索引（clean_name + shadow_name + folder_name 末段都入索引）
            all_names = info["clean_names"] | info["shadow_names"]
            # 从 folder_name 提取最后一段目录名作为补充片名
            folder_parts = fn.replace("/", "\\").split("\\")
            if folder_parts:
                last_part = folder_parts[-1].strip()
                if last_part and len(last_part) >= 2:
                    all_names.add(last_part)
            for name in all_names:
                # 提取年份
                year = _extract_year(name) or _extract_year(fn)
                norm = normalize(name)
                if not norm:
                    continue

                # title+year 索引
                if year:
                    key = f"{norm}|{year}"
                    if key not in title_year_idx or info["max_height"] > title_year_idx[key]["max_height"]:
                        title_year_idx[key] = entry

                # 纯 title 索引（兜底）
                if norm not in title_idx or info["max_height"] > title_idx[norm]["max_height"]:
                    title_idx[norm] = entry

        self._tmdb_index = tmdb_idx
        self._title_year_index = title_year_idx
        self._title_index = title_idx
        self._indexed = True
        logger.info(f"[LocalMediaMatcher] 索引构建完成: tmdb={len(tmdb_idx)} title_year={len(title_year_idx)} title={len(title_idx)} folders={len(folders)}")

    def match(self, item: dict) -> tuple:
        """匹配单个推荐/探索条目，返回 (local_status, local_folder):
        - status: 'none' / 'owned_low' / 'owned_high'
        - folder: 匹配到的文件夹路径（none 时为空）
        """
        import plugin_guard

        if not plugin_guard.is_feature_allowed("local_match") or not self._indexed:
            return ("none", "")

        # 1. tmdb_id 精确匹配
        tmdb_id = item.get("tmdb_id")
        if tmdb_id:
            entry = self._tmdb_index.get(int(tmdb_id))
            if entry:
                return (f"owned_{entry['quality']}", entry.get("folder", ""))

        # 2. 豆瓣 ID → tmdb_id 缓存映射
        douban_id = str(item.get("douban_id") or "")
        if douban_id:
            cached_tmdb = self._id_cache.get(douban_id)
            if cached_tmdb:
                entry = self._tmdb_index.get(cached_tmdb)
                if entry:
                    return (f"owned_{entry['quality']}", entry.get("folder", ""))

        # 3. 片名 + 年份匹配
        title = item.get("title") or ""
        year = item.get("year") or ""
        orig_title = item.get("original_title") or item.get("subtitle") or ""

        result = self._match_by_title(title, year)
        if result:
            return result

        # 用 original_title 再试一次
        if orig_title and orig_title != title:
            result = self._match_by_title(orig_title, year)
            if result:
                return result

        return ("none", "")

    def _match_by_title(self, title: str, year: str) -> Optional[tuple]:
        """片名匹配内部逻辑，返回 (status, folder) 或 None"""
        norm = normalize(title)
        if not norm:
            return None

        # 精确匹配 title+year
        if year:
            key = f"{norm}|{year}"
            entry = self._title_year_index.get(key)
            if entry:
                return (f"owned_{entry['quality']}", entry.get("folder", ""))
            # 年份 ±1 容错
            for delta in (-1, 1):
                try:
                    alt_year = str(int(year) + delta)
                    entry = self._title_year_index.get(f"{norm}|{alt_year}")
                    if entry:
                        return (f"owned_{entry['quality']}", entry.get("folder", ""))
                except (ValueError, TypeError):
                    pass

        # 精确匹配纯 title
        entry = self._title_index.get(norm)
        if entry:
            return (f"owned_{entry['quality']}", entry.get("folder", ""))

        # 提取中文部分做子串/模糊匹配
        cn_chars = re.sub(r"[^\u4e00-\u9fff]", "", title or "")
        if len(cn_chars) >= 2:
            for idx_title, entry in self._title_index.items():
                idx_cn = re.sub(r"[^\u4e00-\u9fff]", "", idx_title)
                if not idx_cn or len(idx_cn) < 2:
                    continue
                # 匹配规则：完全相等 / 搜索词是索引词前缀 / 索引词是搜索词前缀
                if cn_chars != idx_cn and not idx_cn.startswith(cn_chars) and not cn_chars.startswith(idx_cn):
                    continue
                # 通过子串检查，做年份校验
                if year:
                    for y_delta in range(0, _YEAR_TOLERANCE + 1):
                        for sign in (0, -1, 1):
                            try:
                                check_year = str(int(year) + sign * y_delta)
                                if f"{idx_title}|{check_year}" in self._title_year_index:
                                    return (f"owned_{entry['quality']}", entry.get("folder", ""))
                            except (ValueError, TypeError):
                                pass
                    # 没有年份索引但中文完全匹配，也算命中
                    if cn_chars == idx_cn:
                        return (f"owned_{entry['quality']}", entry.get("folder", ""))
                else:
                    return (f"owned_{entry['quality']}", entry.get("folder", ""))

        # 模糊匹配（遍历 title_index，找最高相似度）
        best_score = 0.0
        best_entry = None
        for idx_title, entry in self._title_index.items():
            score = fuzzy_score(norm, idx_title)
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_score >= _FUZZY_THRESHOLD and best_entry:
            return (f"owned_{best_entry['quality']}", best_entry.get("folder", ""))

        return None

    def match_batch(self, items: List[dict]) -> List[dict]:
        """批量匹配，给每个 item 注入 local_status + local_folder 字段。"""
        import plugin_guard

        if not plugin_guard.is_feature_allowed("local_match"):
            for item in items:
                item["local_status"] = "none"
                item["local_folder"] = ""
            return items

        pending = []
        for item in items:
            status, folder = self.match(item)
            item["local_status"] = status
            item["local_folder"] = folder if status != "none" else ""
            # 收集未匹配的豆瓣条目（有 douban_id 但没 tmdb_id，且不在缓存中）
            if status == "none":
                did = str(item.get("douban_id") or "")
                if did and did not in self._id_cache and not item.get("tmdb_id"):
                    pending.append({
                        "douban_id": did,
                        "title": item.get("title", ""),
                        "year": item.get("year", ""),
                        "original_title": item.get("original_title") or item.get("subtitle") or "",
                        "media_type": item.get("media_type", "movie"),
                    })

        # 丢进异步补全队列
        if pending:
            self._enqueue_async(pending)

        return items

    # ── 第二层：ID 映射缓存 ──

    def _load_id_cache(self):
        """加载持久化的 douban_id → tmdb_id 映射"""
        if os.path.exists(_CACHE_FILE):
            try:
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._id_cache = json.load(f)
                logger.info(f"[LocalMediaMatcher] ID 映射缓存加载: {len(self._id_cache)} 条")
            except Exception as e:
                logger.error(f"[LocalMediaMatcher] ID 映射缓存加载失败: {e}")
                self._id_cache = {}
        else:
            self._id_cache = {}

    def _save_id_cache(self):
        """持久化 ID 映射缓存"""
        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._id_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[LocalMediaMatcher] ID 映射缓存保存失败: {e}")

    def add_id_mapping(self, douban_id: str, tmdb_id: int):
        """添加一条 douban_id → tmdb_id 映射"""
        if douban_id and tmdb_id:
            self._id_cache[str(douban_id)] = tmdb_id

    # ── 第三层：异步补全 ──

    def _enqueue_async(self, items: List[dict]):
        """将未匹配条目加入异步补全队列"""
        import plugin_guard

        if not plugin_guard.is_feature_allowed("local_match") or not plugin_guard.is_metadata_allowed("tmdb"):
            return
        with self._queue_lock:
            # 去重：已在队列中的不重复加
            existing_ids = {i["douban_id"] for i in self._pending_queue}
            for item in items:
                if item["douban_id"] not in existing_ids:
                    self._pending_queue.append(item)
                    existing_ids.add(item["douban_id"])

        # 启动后台 worker（如果没在跑）
        if not self._worker_running:
            t = threading.Thread(target=self._async_worker, daemon=True)
            t.start()

    def _async_worker(self):
        """后台线程：用 TMDB API 搜索补全 douban_id → tmdb_id 映射"""
        self._worker_running = True
        save_counter = 0
        try:
            while True:
                import plugin_guard

                if not plugin_guard.is_feature_allowed("local_match") or not plugin_guard.is_metadata_allowed("tmdb"):
                    with self._queue_lock:
                        self._pending_queue.clear()
                    break
                with self._queue_lock:
                    if not self._pending_queue:
                        break
                    item = self._pending_queue.pop(0)

                douban_id = item["douban_id"]
                if douban_id in self._id_cache:
                    continue

                # 用 TMDB 搜索
                tmdb_id = self._search_tmdb_id(
                    title=item["title"],
                    year=item["year"],
                    original_title=item["original_title"],
                    media_type=item["media_type"],
                )
                if tmdb_id:
                    self._id_cache[douban_id] = tmdb_id
                    save_counter += 1
                    # 每 5 条保存一次
                    if save_counter % 5 == 0:
                        self._save_id_cache()
                else:
                    # 标记为搜索过但没找到（用 0 表示），避免重复搜索
                    self._id_cache[douban_id] = 0
                    save_counter += 1

                time.sleep(_ASYNC_INTERVAL)

        except Exception as e:
            logger.info(f"[LocalMediaMatcher] 异步补全异常: {e}")
        finally:
            # 最终保存
            if save_counter > 0:
                self._save_id_cache()
                logger.info(f"[LocalMediaMatcher] 异步补全完成，新增 {save_counter} 条映射")
            self._worker_running = False

    def _search_tmdb_id(self, title: str, year: str, original_title: str, media_type: str) -> Optional[int]:
        """用 TMDB API 搜索获取 tmdb_id"""
        try:
            import plugin_guard

            if not plugin_guard.is_feature_allowed("local_match") or not plugin_guard.is_metadata_allowed("tmdb"):
                return None
            from shared import get_clients

            tmdb = get_clients()["tmdb"]
            if not tmdb:
                return None

            # 优先用 original_title 搜索（英文/原始名匹配率更高）
            search_titles = []
            if original_title:
                search_titles.append(original_title)
            if title and title != original_title:
                search_titles.append(title)

            search_fn = tmdb.search_tv if media_type == "tv" else tmdb.search_movie
            for st in search_titles:
                results = search_fn(st)
                if not results:
                    continue
                # 有年份时优先匹配年份
                if year:
                    for r in results:
                        r_year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
                        if r_year == year:
                            tid = r.get("id")
                            if tid:
                                return int(tid)
                # 取第一个结果
                tid = results[0].get("id")
                if tid:
                    return int(tid)
        except Exception as e:
            logger.error(f"[LocalMediaMatcher] TMDB 搜索失败 ({title}): {e}")
        return None


# ── 工具函数 ──

def _extract_year(text: str) -> str:
    """从文本中提取四位年份"""
    m = re.search(r"\b(19|20)\d{2}\b", text or "")
    return m.group(0) if m else ""
