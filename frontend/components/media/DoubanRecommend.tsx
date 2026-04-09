// 豆瓣热门推荐 + 展开详情面板（复用媒体库的交互模式）
"use client";
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";

type HotTab = "movie" | "tv" | "anime";
const TAB_CONFIG: { key: HotTab; label: string; type: "movie" | "tv"; tag: string }[] = [
  { key: "movie", label: "电影", type: "movie", tag: "热门" },
  { key: "tv", label: "剧集", type: "tv", tag: "热门" },
  { key: "anime", label: "动画", type: "movie", tag: "动画" },
];

interface MediaDetail {
  found: boolean;
  tmdb_id?: number; title?: string; original_title?: string; year?: string;
  poster_url?: string; backdrop_url?: string; overview?: string; rating?: number;
  genres?: string[]; director?: string; cast?: string[]; runtime?: number;
  imdb_id?: string; total_seasons?: number; episode_count?: number; status?: string;
  countries?: string[];
}

interface DoubanRecommendProps {
  onSelectMedia: (item: DoubanHotItem) => void;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** 豆瓣代理 URL 需要拼上后端地址 */
function proxyUrl(url: string): string {
  if (!url) return "";
  if (url.startsWith("/proxy/")) return `${BASE_URL}/proxy${url.replace("/proxy/", "/")}`;
  if (url.includes("doubanio.com")) return `${BASE_URL}/proxy/image?url=${encodeURIComponent(url)}`;
  return url;
}

// LRU 缓存：最多 60 条详情，持久化到 localStorage
const DETAIL_CACHE_KEY = "discover_detail_cache";
const DETAIL_CACHE_MAX = 60;

function loadDetailCache(): Map<string, MediaDetail> {
  try {
    const raw = localStorage.getItem(DETAIL_CACHE_KEY);
    if (raw) {
      const entries: [string, MediaDetail][] = JSON.parse(raw);
      return new Map(entries);
    }
  } catch {}
  return new Map();
}

function saveDetailCache(cache: Map<string, MediaDetail>) {
  try {
    const entries = Array.from(cache.entries());
    localStorage.setItem(DETAIL_CACHE_KEY, JSON.stringify(entries));
  } catch {}
}

const detailCache = loadDetailCache();

function getCachedDetail(key: string): MediaDetail | undefined { return detailCache.get(key); }
function setCachedDetail(key: string, val: MediaDetail) {
  if (detailCache.size >= DETAIL_CACHE_MAX) {
    const first = detailCache.keys().next().value;
    if (first) detailCache.delete(first);
  }
  detailCache.set(key, val);
  saveDetailCache(detailCache);
}

export default function DoubanRecommend({ onSelectMedia }: DoubanRecommendProps) {
  const [tab, setTab] = useState<HotTab>("movie");
  const [items, setItems] = useState<DoubanHotItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchItems, setSearchItems] = useState<DoubanHotItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [isSearchMode, setIsSearchMode] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  // 展开面板
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [expandPos, setExpandPos] = useState<{ afterIndex: number } | null>(null);
  const [detail, setDetail] = useState<MediaDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ── 数据加载 ──
  const loadHot = useCallback(async (tabKey: HotTab, pageStart = 0, append = false) => {
    const cfg = TAB_CONFIG.find(t => t.key === tabKey) || TAB_CONFIG[0];
    if (pageStart === 0 && !append) {
      const cached = sessionStorage.getItem(`douban_hot_v4_${tabKey}`);
      if (cached) {
        try {
          const p = JSON.parse(cached);
          if (p.length <= 12) { setItems(p); setHasMore(true); return; }
          sessionStorage.removeItem(`douban_hot_v4_${tabKey}`);
        } catch { sessionStorage.removeItem(`douban_hot_v4_${tabKey}`); }
      }
    }
    if (pageStart === 0) { setLoading(true); setError(false); } else setLoadingMore(true);
    try {
      const data = await api.doubanHot(cfg.type, pageStart, cfg.tag);
      const n: DoubanHotItem[] = data.items || [];
      if (append) {
        setItems(prev => {
          const existingIds = new Set(prev.map(i => i.douban_id));
          const unique = n.filter(i => i.douban_id && !existingIds.has(i.douban_id));
          return [...prev, ...unique].slice(0, 60);
        });
      } else {
        setItems(n);
        try { sessionStorage.setItem(`douban_hot_v4_${tabKey}`, JSON.stringify(n)); } catch {}
      }
      setHasMore(n.length >= 12);
    } catch { if (!append) { setError(true); setItems([]); } }
    finally { setLoading(false); setLoadingMore(false); }
  }, []);

  const loadMore = () => { const p = page + 1; setPage(p); loadHot(tab, p * 12, true); };

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setSearching(true); setIsSearchMode(true); setSearchItems([]); closeExpand();
    try {
      const data = await api.doubanSearch(q);
      setSearchItems((data.candidates || data.items || []).map((c: any) => ({
        douban_id: c.douban_id || c.id || "", title: c.title || "", year: c.year || "",
        rating: c.rating || 0, cover_url: c.cover_url || c.poster_url || "",
        subtitle: c.subtitle || "", episode: c.episode || "",
      })));
    } catch { setSearchItems([]); } finally { setSearching(false); }
  }, []);

  useEffect(() => { setPage(0); setHasMore(true); closeExpand(); loadHot(tab); }, [tab]);
  const exitSearch = () => { setIsSearchMode(false); setSearchQuery(""); setSearchItems([]); closeExpand(); };
  const displayItems = isSearchMode ? searchItems : items;

  // ── 展开面板逻辑（复用 CardGrid 的 getRowEndIndex 模式）──
  const closeExpand = () => { setExpandedIndex(null); setExpandPos(null); setDetail(null); };

  const getRowEndIndex = useCallback((clickIndex: number): number => {
    if (!gridRef.current) return clickIndex;
    const cards = gridRef.current.querySelectorAll<HTMLElement>('[data-discover-card]');
    if (!cards[clickIndex]) return clickIndex;
    const clickTop = cards[clickIndex].offsetTop;
    let lastInRow = clickIndex;
    for (let i = clickIndex + 1; i < cards.length; i++) {
      if (cards[i].offsetTop === clickTop) lastInRow = i; else break;
    }
    return lastInRow;
  }, []);

  const handleCardClick = useCallback(async (index: number) => {
    if (expandedIndex === index) { closeExpand(); return; }
    setExpandedIndex(index);
    setExpandPos({ afterIndex: index });
    const item = displayItems[index];
    const cacheKey = `${item.title}_${item.year}_${tab}`;
    const cached = getCachedDetail(cacheKey);
    if (cached) { setDetail(cached); setDetailLoading(false); return; }
    setDetail(null); setDetailLoading(true);
    try {
      const tmdbType = (TAB_CONFIG.find(t => t.key === tab)?.type || "movie") as "movie" | "tv";
      const d = await api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "");
      // 只缓存成功的结果
      if (d.found) setCachedDetail(cacheKey, d);
      setDetail(d);
    } catch { setDetail({ found: false }); }
    finally { setDetailLoading(false); }
  }, [expandedIndex, displayItems, tab]);

  // 全局点击关闭（复用 CardGrid 的模式）
  useEffect(() => {
    if (expandedIndex === null) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest('[data-discover-card]') || t.closest('[data-expand-panel]') ||
          t.closest('button') || t.closest('a') || t.closest('input') || t.closest('textarea')) return;
      closeExpand();
    };
    const timer = setTimeout(() => document.addEventListener('click', handler), 100);
    return () => { clearTimeout(timer); document.removeEventListener('click', handler); };
  }, [expandedIndex]);

  const rowEndIndex = expandPos ? getRowEndIndex(expandPos.afterIndex) : -1;

  // 构建渲染列表（卡片 + 展开面板插入）
  const renderList = useMemo(() => {
    const list: ({ type: "card"; item: DoubanHotItem; index: number } | { type: "expand" })[] = [];
    displayItems.forEach((item, i) => {
      list.push({ type: "card", item, index: i });
      if (i === rowEndIndex && expandedIndex !== null) list.push({ type: "expand" });
    });
    if (expandedIndex !== null && rowEndIndex >= displayItems.length) list.push({ type: "expand" });
    return list;
  }, [displayItems, rowEndIndex, expandedIndex]);

  return (
    <div className="mt-8">
      {/* 标题栏 — sticky 吸顶（相对于滚动容器） */}
      <div className="sticky top-0 z-20 bg-[#0f0f0f] py-3 -mx-6 px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-bold text-white tracking-tight">发现新影片</h1>
          <div className="flex gap-1">
            {TAB_CONFIG.map((t) => (
              <button key={t.key} onClick={() => { exitSearch(); if (t.key !== tab) setTab(t.key); }}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  tab === t.key && !isSearchMode ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
                }`}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-2 w-[240px] justify-end">
            {isSearchMode && (
              <button onClick={exitSearch} className="text-xs text-slate-500 hover:text-slate-300 flex-shrink-0 whitespace-nowrap">← 热榜</button>
            )}
            <div className="relative flex-shrink-0">
              <svg className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
              </svg>
              <input ref={inputRef} value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doSearch(searchQuery)}
                placeholder="搜索影片..."
                className="bg-white/[0.04] border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white outline-none focus:border-blue-500/50 w-44 placeholder:text-slate-600" />
            </div>
          </div>
        </div>
      </div>

      {/* 内容区 */}
      <div>
        {(loading || searching) ? (
          <div className="flex items-center gap-2 py-16 justify-center">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500" />
            <span className="text-xs text-slate-500">加载中...</span>
          </div>
        ) : error && !isSearchMode ? (
          <div className="text-center py-12">
            <p className="text-xs text-slate-600 mb-2">豆瓣热榜加载失败</p>
            <button onClick={() => loadHot(tab)} className="text-xs text-blue-400 hover:text-blue-300">重试</button>
          </div>
        ) : displayItems.length === 0 ? (
          <p className="text-center py-12 text-xs text-slate-600">{isSearchMode ? "未找到匹配影片" : "暂无数据"}</p>
        ) : (
          <>
            {/* 网格：和媒体库完全一致的响应式列数 */}
            <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
              {renderList.map((entry, ri) => {
                if (entry.type === "expand" && expandedIndex !== null) {
                  const expandItem = displayItems[expandedIndex];
                  return (
                    <div key="expand-panel" data-expand-panel className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200">
                      <ExpandDetail item={expandItem} detail={detail} loading={detailLoading}
                        onSearch={() => onSelectMedia({...expandItem, _tmdb_original_title: detail?.original_title || ""})}
                        onClose={closeExpand}
                        onRetry={() => {
                          if (expandedIndex === null) return;
                          const item = displayItems[expandedIndex];
                          setDetail(null); setDetailLoading(true);
                          const tmdbType = (TAB_CONFIG.find(t => t.key === tab)?.type || "movie") as "movie" | "tv";
                          api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "")
                            .then(d => { if (d.found) setCachedDetail(`${item.title}_${item.year}_${tab}`, d); setDetail(d); })
                            .catch(() => setDetail({ found: false }))
                            .finally(() => setDetailLoading(false));
                        }} />
                    </div>
                  );
                }
                if (entry.type !== "card") return null;
                const { item, index } = entry;
                const isActive = expandedIndex === index;
                return (
                  <div key={`${item.douban_id || index}`} data-discover-card
                    className={`group rounded-xl overflow-hidden bg-[#1a1a1a] border cursor-pointer transition-all ${
                      isActive ? "border-blue-500/50 ring-1 ring-blue-500/20" : "border-white/[0.06] hover:border-slate-500"
                    }`}
                    onClick={() => handleCardClick(index)}>
                    <div className="relative aspect-[2/3] bg-[#111]">
                      {item.cover_url ? (
                        <img src={proxyUrl(item.cover_url)} alt={item.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                      ) : null}
                      <div className="absolute inset-0 flex items-center justify-center text-slate-700 text-xs pointer-events-none select-none">
                        {!item.cover_url && "暂无封面"}
                      </div>
                      <div className="absolute inset-0 bg-gradient-to-t from-[#1a1a1a] via-transparent to-transparent" />
                      {item.rating > 0 && (
                        <span className="absolute top-3 right-3 bg-black/80 text-yellow-400 text-sm font-bold px-2 py-0.5 rounded-lg">
                          {item.rating}
                        </span>
                      )}
                      <div className="absolute bottom-0 left-0 right-0 p-4">
                        <p className="text-[15px] font-semibold text-white truncate">{item.title}</p>
                        <p className="text-xs text-slate-400 mt-1">
                          {item.year || "—"}{item.episode ? ` · ${item.episode}` : ""}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {!isSearchMode && hasMore && (
              <div className="flex justify-center mt-6 pb-8">
                <button onClick={loadMore} disabled={loadingMore}
                  className="px-5 py-2 text-xs text-slate-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] rounded-lg transition-all disabled:opacity-50">
                  {loadingMore ? "加载中..." : "查看更多"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── 展开详情面板 ──
function ExpandDetail({ item, detail, loading, onSearch, onClose, onRetry }: {
  item: DoubanHotItem; detail: MediaDetail | null; loading: boolean;
  onSearch: () => void; onClose: () => void; onRetry: () => void;
}) {
  const d = detail?.found ? detail : null;
  const posterSrc = d?.poster_url || (item.cover_url ? proxyUrl(item.cover_url) : "");

  return (
    <div className="flex gap-5">
      <div className="w-[140px] flex-shrink-0">
        <div className="aspect-[2/3] bg-[#1a1a1a] rounded-lg overflow-hidden">
          {posterSrc ? (
            <img src={posterSrc} alt={item.title}
              className="w-full h-full object-cover"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-700 text-xs">暂无封面</div>
          )}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white">{d?.title || item.title}</h3>
            {(d?.original_title && d.original_title !== d.title) && (
              <p className="text-xs text-slate-500 mt-0.5">{d.original_title}</p>
            )}
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all flex-shrink-0">✕</button>
        </div>
        {loading ? (
          <div className="flex items-center gap-2 py-8">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500" />
            <span className="text-xs text-slate-500">加载详情...</span>
          </div>
        ) : !d ? (
          /* TMDB 搜不到 — 显示豆瓣基础信息 */
          <div className="mt-3">
            <div className="flex items-center gap-2 flex-wrap">
              {item.year && <span className="text-xs text-slate-400 bg-white/[0.06] px-2 py-0.5 rounded">{item.year}</span>}
              {item.rating > 0 && <span className="text-xs text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded font-bold">⭐ {item.rating}</span>}
              {item.episode && <span className="text-xs text-slate-500">{item.episode}</span>}
            </div>
            <p className="text-xs text-slate-500 mt-4">暂无相关数据 <button onClick={onRetry} className="text-blue-400 hover:text-blue-300 ml-2">重试</button></p>
            <div className="flex gap-2 mt-4">
              <button onClick={onSearch}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium text-white transition-colors">搜索资源</button>
              {item.douban_id && (
                <a href={`https://movie.douban.com/subject/${item.douban_id}/`} target="_blank" rel="noopener noreferrer"
                  className="px-4 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">豆瓣</a>
              )}
            </div>
          </div>
        ) : (
          /* TMDB 数据完整展示 */
          <>
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span className="text-xs text-slate-400 bg-white/[0.06] px-2 py-0.5 rounded">{d.year || item.year || "—"}</span>
              {(d.rating || item.rating) > 0 && (
                <span className="text-xs text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded font-bold">⭐ {d.rating || item.rating}</span>
              )}
              {d.runtime ? <span className="text-xs text-slate-500">{d.runtime} 分钟</span> : null}
              {d.total_seasons ? <span className="text-xs text-slate-500">{d.total_seasons} 季</span> : null}
              {d.episode_count ? <span className="text-xs text-slate-500">{d.episode_count} 集</span> : null}
              {d.countries && d.countries.length > 0 && (
                <span className="text-xs text-slate-500">{d.countries.join(" / ")}</span>
              )}
            </div>
            {d.genres && d.genres.length > 0 && (
              <div className="flex gap-1.5 mt-2 flex-wrap">
                {d.genres.map(g => (
                  <span key={g} className="text-[10px] text-slate-400 border border-white/[0.08] px-1.5 py-0.5 rounded">{g}</span>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-400 mt-3 leading-relaxed line-clamp-3">{d.overview || "暂无简介"}</p>
            <div className="mt-3 space-y-1">
              {d.director && <p className="text-xs text-slate-500">导演：<span className="text-slate-300">{d.director}</span></p>}
              {d.cast && d.cast.length > 0 && (
                <p className="text-xs text-slate-500">主演：<span className="text-slate-300">{d.cast.join(" / ")}</span></p>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={onSearch}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-medium text-white transition-colors">搜索资源</button>
              {item.douban_id && (
                <a href={`https://movie.douban.com/subject/${item.douban_id}/`} target="_blank" rel="noopener noreferrer"
                  className="px-4 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">豆瓣</a>
              )}
              {d.imdb_id && (
                <a href={`https://www.imdb.com/title/${d.imdb_id}`} target="_blank" rel="noopener noreferrer"
                  className="px-4 py-2 bg-white/[0.06] hover:bg-white/10 rounded-lg text-xs text-slate-300 transition-colors">IMDB</a>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
