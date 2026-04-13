// 发现页工具函数：代理 URL、数据标准化、详情缓存
import type { DoubanHotItem } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** 图片代理 URL 转换 */
export function proxyUrl(url: string): string {
  if (!url) return "";
  if (url.startsWith("/proxy/")) return `${BASE_URL}/proxy${url.replace("/proxy/", "/")}`;
  if (url.includes("doubanio.com")) return `${BASE_URL}/proxy/image?url=${encodeURIComponent(url)}`;
  return url;
}

/** 标准化推荐数据为 DoubanHotItem 格式 */
export function normalizeItem(item: any): DoubanHotItem {
  return {
    douban_id: item.douban_id || item.tmdb_id?.toString() || "",
    title: item.title || "",
    year: item.year || "",
    rating: item.rating || 0,
    cover_url: item.poster_url || item.cover_url || "",
    subtitle: item.original_title || item.subtitle || "",
    episode: item.episode || (item.episode_count ? `${item.episode_count}集` : ""),
    genres: item.genres || [],
    overview: item.overview || item.intro || "",
    directors: item.directors || [],
    actors: item.actors || [],
    countries: item.countries || [],
    media_type: item.media_type || "",
    episodes_info: item.episodes_info || "",
    local_status: item.local_status || undefined,
    local_folder: item.local_folder || undefined,
  };
}

// ── 详情缓存 ──
export interface MediaDetail {
  found: boolean;
  tmdb_id?: number; title?: string; original_title?: string; year?: string;
  poster_url?: string; backdrop_url?: string; overview?: string; rating?: number;
  genres?: string[]; director?: string; cast?: string[]; runtime?: number;
  imdb_id?: string; total_seasons?: number; episode_count?: number; status?: string;
  countries?: string[];
  source?: "tmdb" | "douban" | "bangumi";
  ratings?: { douban?: number; tmdb?: number; bangumi?: number };
  external_ids?: { tmdb_id?: number; imdb_id?: string };
}

const DETAIL_CACHE_KEY = "discover_detail_cache";
const DETAIL_CACHE_MAX = 60;

function loadDetailCache(): Map<string, MediaDetail> {
  try {
    const raw = localStorage.getItem(DETAIL_CACHE_KEY);
    if (raw) return new Map(JSON.parse(raw) as [string, MediaDetail][]);
  } catch {}
  return new Map();
}

function saveDetailCache(cache: Map<string, MediaDetail>) {
  try { localStorage.setItem(DETAIL_CACHE_KEY, JSON.stringify(Array.from(cache.entries()))); } catch {}
}

const detailCache = loadDetailCache();

export function getCachedDetail(key: string): MediaDetail | undefined {
  return detailCache.get(key);
}

export function setCachedDetail(key: string, val: MediaDetail) {
  if (detailCache.size >= DETAIL_CACHE_MAX) {
    const first = detailCache.keys().next().value;
    if (first) detailCache.delete(first);
  }
  detailCache.set(key, val);
  saveDetailCache(detailCache);
}

export function deleteCachedDetail(key: string) {
  detailCache.delete(key);
  saveDetailCache(detailCache);
}

// ── 推荐源配置 ──
export type RecommendSource = {
  key: string;
  label: string;
  mediaType: "movie" | "tv" | "mixed";
  showRank?: boolean;
  ratingSource?: "douban" | "tmdb" | "bangumi";
};

export const RECOMMEND_TABS: RecommendSource[] = [
  { key: "combined", label: "综合推荐", mediaType: "mixed", ratingSource: "douban" },
  { key: "douban_movie_hot", label: "热门电影", mediaType: "movie", ratingSource: "douban" },
  { key: "douban_tv_hot", label: "热门剧集", mediaType: "tv", ratingSource: "douban" },
  { key: "douban_animation", label: "热门动画", mediaType: "tv", ratingSource: "douban" },
  { key: "douban_showing", label: "正在热映", mediaType: "movie", ratingSource: "douban" },
  { key: "weekly_combined", label: "剧集周榜", mediaType: "tv", showRank: true, ratingSource: "douban" },
  { key: "tmdb_trending", label: "TMDB放送", mediaType: "mixed", ratingSource: "tmdb" },
  { key: "bangumi_calendar", label: "Bangumi放送", mediaType: "tv", ratingSource: "bangumi" },
];

// ── 一级 tab 配置 ──
export type PrimaryTab = "recommend" | "explore" | "subscribe";
export const PRIMARY_TABS: { key: PrimaryTab; label: string }[] = [
  { key: "recommend", label: "推荐" },
  { key: "explore", label: "探索" },
  { key: "subscribe", label: "订阅" },
];

// ── 探索源配置 ──
export type ExploreSource = {
  key: string;
  label: string;
  provider: string;
  type: string;
  defaultSort: string;
};

export const EXPLORE_TABS: ExploreSource[] = [
  { key: "douban_movie", label: "豆瓣电影", provider: "douban", type: "movie", defaultSort: "T" },
  { key: "douban_tv", label: "豆瓣剧集", provider: "douban", type: "tv", defaultSort: "T" },
  { key: "tmdb_movie", label: "TMDB电影", provider: "tmdb", type: "movie", defaultSort: "popularity.desc" },
  { key: "tmdb_tv", label: "TMDB剧集", provider: "tmdb", type: "tv", defaultSort: "popularity.desc" },
  { key: "bangumi", label: "Bangumi", provider: "bangumi", type: "2", defaultSort: "rank" },
];
