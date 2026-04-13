// 探索页主组件（筛选+无限滚动+卡片网格，复用 DiscoverCard + ExpandDetail）
// 展示逻辑和推荐完全一致：colCount * 4 行，响应式列数
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { normalizeItem, getCachedDetail, setCachedDetail, deleteCachedDetail, EXPLORE_TABS } from "./discoverUtils";
import type { MediaDetail } from "./discoverUtils";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import ExploreFilterBar, { DEFAULT_FILTERS } from "./ExploreFilterBar";
import type { ExploreFilters } from "./ExploreFilterBar";

interface ExplorePageProps {
  onSelectMedia: (item: DoubanHotItem) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  colCount: number;
  onNavigateToLocal?: (folderPath: string) => void;
  onSubscribe?: (item: DoubanHotItem, detail: MediaDetail | null) => void;
  checkSubscribed?: (item: DoubanHotItem) => boolean;
}

export default function ExplorePage({ onSelectMedia, activeTab, setActiveTab, colCount, onNavigateToLocal, onSubscribe, checkSubscribed }: ExplorePageProps) {
  const tabConfig = EXPLORE_TABS.find(t => t.key === activeTab) || EXPLORE_TABS[0];
  const [filters, setFilters] = useState<Record<string, ExploreFilters>>({});
  const [items, setItems] = useState<DoubanHotItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const gridRef = useRef<HTMLDivElement>(null);
  const loadIdRef = useRef(0);
  // 内存缓存：tab+筛选 → 已加载数据（切 tab 瞬间切换）
  const dataCacheRef = useRef<Record<string, { items: DoubanHotItem[]; page: number; hasMore: boolean }>>({});

  // 展开面板
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [detail, setDetail] = useState<MediaDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pendingClickRef = useRef<string>("");

  // 滚动自动加载
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [autoLoadPending, setAutoLoadPending] = useState(false);
  const AUTO_LOAD_BATCHES = 4;
  const MAX_ITEMS = 200;
  const isAutoMode = page < AUTO_LOAD_BATCHES;
  const reachedMax = items.length >= MAX_ITEMS;

  // 和推荐一致：每次加载精确 colCount * 4 条
  const reqSize = Math.max(colCount * 4, 20);

  const currentFilters = filters[activeTab] || { ...DEFAULT_FILTERS, sort: tabConfig.defaultSort };

  const closeExpand = useCallback(() => {
    setExpandedIndex(null); setDetail(null); setDetailLoading(false);
    pendingClickRef.current = "";
  }, []);

  // 缓存 key = tab + 筛选参数
  const getCacheKey = useCallback(() => {
    const f = filters[activeTab] || { ...DEFAULT_FILTERS, sort: tabConfig.defaultSort };
    return `${activeTab}_${f.sort}_${f.tags}_${f.language}_${f.year}_${f.voteAverage}_${f.voteMax}_${f.area}_${f.bangumiType}`;
  }, [activeTab, filters, tabConfig]);

  // 加载数据
  const loadData = useCallback(async (pageNum: number, append: boolean, loadId: number) => {
    const f = filters[activeTab] || { ...DEFAULT_FILTERS, sort: tabConfig.defaultSort };
    const cacheKey = getCacheKey();

    // 首页且有缓存 → 直接用缓存
    if (pageNum === 0 && !append && dataCacheRef.current[cacheKey]) {
      const cached = dataCacheRef.current[cacheKey];
      setItems(cached.items); setPage(cached.page); setHasMore(cached.hasMore);
      setLoading(false); setLoadingMore(false);
      return;
    }

    if (pageNum === 0) { setLoading(true); setItems([]); } else { setLoadingMore(true); }
    try {
      const data = await api.discoverExplore(
        tabConfig.provider, tabConfig.type,
        f.sort || tabConfig.defaultSort,
        f.tags, pageNum, reqSize, f.language, f.year, f.voteAverage, f.area,
        tabConfig.provider === "bangumi" ? (f.bangumiType || "") : "",
        f.voteMax,
      );
      if (loadId !== loadIdRef.current) return;
      const normalized = (data.items || []).map(normalizeItem);
      const newHasMore = normalized.length >= reqSize * 0.5;
      if (append) {
        setItems(prev => {
          const ids = new Set(prev.map(i => i.douban_id || i.title));
          const merged = [...prev, ...normalized.filter((i: DoubanHotItem) => !ids.has(i.douban_id || i.title))];
          // 截断到 colCount 整数倍，避免最后一行不满
          const cc = colCount;
          const trimmed = merged.slice(0, Math.floor(merged.length / cc) * cc);
          dataCacheRef.current[cacheKey] = { items: trimmed, page: pageNum, hasMore: newHasMore };
          return trimmed;
        });
      } else {
        // 首次加载也截断到整行
        const cc = colCount;
        const trimmed = normalized.slice(0, Math.floor(normalized.length / cc) * cc);
        setItems(trimmed);
        dataCacheRef.current[cacheKey] = { items: trimmed, page: pageNum, hasMore: newHasMore };
      }
      setHasMore(newHasMore);
      setPage(pageNum);
    } catch {
      if (!append) setItems([]);
    } finally {
      if (loadId === loadIdRef.current) { setLoading(false); setLoadingMore(false); }
    }
  }, [activeTab, filters, tabConfig, reqSize, getCacheKey]);

  // tab 切换或筛选变化时重新加载
  useEffect(() => {
    closeExpand();
    const id = ++loadIdRef.current;
    loadData(0, false, id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, filters[activeTab]]);

  const loadMore = useCallback(() => {
    if (reachedMax) return;
    loadData(page + 1, true, loadIdRef.current);
  }, [page, loadData, reachedMax]);

  // 同步 loading 状态到 ref（避免 observer 闭包问题）
  const loadingRef = useRef(false);
  loadingRef.current = loadingMore || autoLoadPending;

  // IntersectionObserver 自动加载（前 4 批自动，之后手动）
  useEffect(() => {
    if (!isAutoMode || !hasMore || loadingMore || loading || reachedMax) return;
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !loadingRef.current) {
        loadingRef.current = true;
        setAutoLoadPending(true);
        setTimeout(() => {
          loadData(page + 1, true, loadIdRef.current);
          setAutoLoadPending(false);
        }, 400);
      }
    }, { threshold: 0.1 });
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [isAutoMode, hasMore, loadingMore, loading, reachedMax, page, loadData]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    closeExpand();
    // 清除当前 tab+筛选的缓存
    const cacheKey = getCacheKey();
    delete dataCacheRef.current[cacheKey];
    const id = ++loadIdRef.current;
    await loadData(0, false, id);
    setRefreshing(false);
  }, [loadData, closeExpand, getCacheKey]);

  const handleFilterChange = useCallback((newFilters: ExploreFilters) => {
    setFilters(prev => ({ ...prev, [activeTab]: newFilters }));
  }, [activeTab]);

  // 展开面板逻辑
  const getRowEndIndex = useCallback((clickIndex: number): number => {
    if (!gridRef.current) return clickIndex;
    const cards = gridRef.current.querySelectorAll<HTMLElement>("[data-discover-card]");
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
    const item = items[index];
    if (!item) return;
    const cacheKey = `explore_${item.title}_${item.year}_${activeTab}`;
    pendingClickRef.current = cacheKey;
    const cached = getCachedDetail(cacheKey);
    if (cached) { setDetail(cached); setDetailLoading(false); return; }
    setDetail(null); setDetailLoading(true);
    try {
      const tmdbType = tabConfig.type === "tv" || tabConfig.provider === "bangumi" ? "tv" : "movie";
      const source = tabConfig.provider === "bangumi" ? "bangumi" : tabConfig.provider === "tmdb" ? "tmdb" : "douban";
      const d = await api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "", source, item.douban_id || "");
      if (pendingClickRef.current !== cacheKey) return;
      if (d.found) setCachedDetail(cacheKey, d);
      setDetail(d);
    } catch {
      if (pendingClickRef.current === cacheKey) setDetail({ found: false });
    } finally {
      if (pendingClickRef.current === cacheKey) setDetailLoading(false);
    }
  }, [expandedIndex, items, activeTab, tabConfig, closeExpand]);

  const handleRefreshWithSource = useCallback((source: string) => {
    if (expandedIndex === null) return;
    const item = items[expandedIndex];
    if (!item) return;
    const cacheKey = `explore_${item.title}_${item.year}_${activeTab}`;
    deleteCachedDetail(cacheKey);
    pendingClickRef.current = cacheKey;
    setDetail(null); setDetailLoading(true);
    const tmdbType = tabConfig.type === "tv" || tabConfig.provider === "bangumi" ? "tv" : "movie";
    api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "", source, item.douban_id || "")
      .then(d => { if (pendingClickRef.current !== cacheKey) return; if (d.found) setCachedDetail(cacheKey, d); setDetail(d); })
      .catch(() => { if (pendingClickRef.current === cacheKey) setDetail({ found: false }); })
      .finally(() => { if (pendingClickRef.current === cacheKey) setDetailLoading(false); });
  }, [expandedIndex, items, activeTab, tabConfig]);

  const rowEndIndex = expandedIndex !== null ? getRowEndIndex(expandedIndex) : -1;
  const ratingSource = tabConfig.provider === "bangumi" ? "bangumi" as const : tabConfig.provider === "tmdb" ? "tmdb" as const : "douban" as const;

  return (
    <div>
      {/* 二级 tab（sticky 吸附在一级 header 下方） */}
      <div className="sticky top-[52px] z-10 bg-[#0f0f0f] -mx-6 px-6">
        <div className="flex gap-2 overflow-x-auto no-scrollbar py-3 border-b border-white/[0.04]">
          {EXPLORE_TABS.map(t => {
            const isActive = activeTab === t.key;
            // 电影蓝/剧集绿色彩规范
            const coloredLabel = t.label.replace(/(电影)/g, "##MOVIE##").replace(/(剧集)/g, "##TV##");
            const parts = coloredLabel.split(/(##MOVIE##|##TV##)/);
            return (
            <button key={t.key} onClick={() => { if (t.key !== activeTab) setActiveTab(t.key); }}
              className={`px-4 py-1.5 rounded-lg text-[13px] font-medium transition-colors whitespace-nowrap flex-shrink-0 flex items-center gap-1 ${
                isActive ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
              }`}>
              <span>{parts.map((p, i) =>
                p === "##MOVIE##" ? <span key={i} className="text-blue-400">电影</span> :
                p === "##TV##" ? <span key={i} className="text-green-400">剧集</span> :
                <span key={i}>{p}</span>
              )}</span>
              {isActive && (
                <span onClick={(e) => { e.stopPropagation(); handleRefresh(); }}
                  className={`inline-flex items-center justify-center w-4 h-4 rounded hover:bg-white/10 transition-all cursor-pointer ${refreshing ? "animate-spin" : ""}`}
                  title="刷新">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </span>
              )}
            </button>
            );
          })}
        </div>
      </div>

      {/* 筛选栏（不吸附，跟随滚动） */}
      <ExploreFilterBar provider={tabConfig.provider} type={tabConfig.type}
        filters={currentFilters} onChange={handleFilterChange} />

      {/* 卡片网格 */}
      {loading ? (
        <SkeletonGrid colCount={colCount} rows={4} />
      ) : items.length === 0 ? (
        <p className="text-center py-12 text-xs text-slate-600">暂无数据</p>
      ) : (
        <>
          <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
            {items.map((item, index) => (
              <DiscoverCard key={`explore-${item.douban_id || item.title}-${index}`}
                item={item} index={index} isActive={expandedIndex === index}
                showRank={currentFilters.sort === "TOP250"} showMediaType={tabConfig.provider === "tmdb"}
                ratingSource={ratingSource} onClick={() => handleCardClick(index)}
                style={{ order: index <= rowEndIndex || expandedIndex === null ? index : index + 1 }}
                isSubscribed={checkSubscribed?.(item)} />
            ))}
            {expandedIndex !== null && expandedIndex < items.length && (
              <div key="expand-panel" data-expand-panel
                className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                <ExpandDetail item={items[expandedIndex]} detail={detail} loading={detailLoading}
                  onSearch={() => onSelectMedia({...items[expandedIndex], _tmdb_original_title: detail?.original_title || ""} as any)}
                  onClose={closeExpand} onRetry={() => handleRefreshWithSource(ratingSource)}
                  defaultSource={ratingSource}
                  showBangumiRating={tabConfig.provider === "bangumi"}
                  onRefreshWithSource={handleRefreshWithSource}
                  onNavigateToLocal={onNavigateToLocal}
                  onSubscribe={onSubscribe ? () => onSubscribe(items[expandedIndex], detail) : undefined}
                  isSubscribed={checkSubscribed?.(items[expandedIndex])} />
              </div>
            )}
          </div>
          {hasMore && !reachedMax && (
            <>
              {isAutoMode ? (
                <div ref={sentinelRef} className="mt-5">
                  {(loadingMore || autoLoadPending) && <SkeletonGrid colCount={colCount} rows={1} />}
                </div>
              ) : (
                <div className="flex justify-center mt-6 pb-8">
                  <button onClick={loadMore} disabled={loadingMore}
                    className="px-5 py-2 text-xs text-slate-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] rounded-lg transition-all disabled:opacity-50">
                    {loadingMore ? "加载中..." : "查看更多"}
                  </button>
                </div>
              )}
            </>
          )}
          {(reachedMax || (!hasMore && items.length > 0)) && (
            <p className="text-center py-6 text-xs text-slate-600">已加载全部</p>
          )}
        </>
      )}
    </div>
  );
}
