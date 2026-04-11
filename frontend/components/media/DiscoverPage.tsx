// 发现页：多榜单推荐 + 探索筛选 + 搜索（主组件，状态管理+布局编排）
// 核心优化：已加载的 tab 内容保持在 DOM 中（display:none），切 tab 时图片不重新加载
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { normalizeItem, getCachedDetail, setCachedDetail, RECOMMEND_TABS } from "./discoverUtils";
import type { MediaDetail, PrimaryTab } from "./discoverUtils";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import WeeklyCombinedView from "./WeeklyCombinedView";
import DiscoverHeader from "./DiscoverHeader";

interface DiscoverPageProps {
  onSelectMedia: (item: DoubanHotItem) => void;
  visible?: boolean;
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
}

// 每个 tab 的独立状态
interface TabState {
  items: DoubanHotItem[];
  loading: boolean;
  error: boolean;
  hasMore: boolean;
  page: number;
  // 周榜专用
  weeklyChineseItems?: DoubanHotItem[];
  weeklyGlobalItems?: DoubanHotItem[];
}

const EMPTY_TAB: TabState = { items: [], loading: false, error: false, hasMore: true, page: 0 };

export default function DiscoverPage({ onSelectMedia, visible = true, scrollContainerRef }: DiscoverPageProps) {
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>("recommend");
  const [activeTab, setActiveTab] = useState(RECOMMEND_TABS[0].key);
  // 按 tab 存储数据，已加载的 tab 保持在 DOM 中
  const [tabDataMap, setTabDataMap] = useState<Record<string, TabState>>({});
  // 记录哪些 tab 曾经加载过（用于保持 DOM 不销毁）
  const [renderedTabs, setRenderedTabs] = useState<Set<string>>(new Set());

  // 搜索
  const [searchQuery, setSearchQuery] = useState("");
  const [searchItems, setSearchItems] = useState<DoubanHotItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [isSearchMode, setIsSearchMode] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);
  const stickyHeaderRef = useRef<HTMLDivElement>(null);

  // 展开面板
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [expandPos, setExpandPos] = useState<{ afterIndex: number } | null>(null);
  const [detail, setDetail] = useState<MediaDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pendingClickRef = useRef<string>("");

  // 刷新
  const [refreshing, setRefreshing] = useState(false);
  // 加载中（用于骨骼屏）
  const [loadingMore, setLoadingMore] = useState(false);

  // ── 响应式列数 ──
  const [colCount, setColCount] = useState(5);
  const colCountRef = useRef(colCount);
  colCountRef.current = colCount;

  useEffect(() => {
    const calc = () => {
      const w = window.innerWidth;
      if (w >= 1536) setColCount(6);
      else if (w >= 1280) setColCount(5);
      else if (w >= 1024) setColCount(4);
      else if (w >= 640) setColCount(3);
      else setColCount(2);
    };
    calc();
    window.addEventListener("resize", calc);
    return () => window.removeEventListener("resize", calc);
  }, []);

  const scrollToDiscover = useCallback(() => {
    if (!stickyHeaderRef.current || !scrollContainerRef?.current) return;
    const headerTop = stickyHeaderRef.current.offsetTop;
    scrollContainerRef.current.scrollTo({ top: headerTop, behavior: "smooth" });
  }, [scrollContainerRef]);

  const loadIdRef = useRef(0);
  const tabDataMapRef = useRef(tabDataMap);
  tabDataMapRef.current = tabDataMap;

  const closeExpand = useCallback(() => {
    setExpandedIndex(null); setExpandPos(null); setDetail(null); setDetailLoading(false);
    pendingClickRef.current = "";
  }, []);

  // ── 更新单个 tab 的状态 ──
  const updateTab = useCallback((tabKey: string, patch: Partial<TabState>) => {
    setTabDataMap(prev => ({ ...prev, [tabKey]: { ...(prev[tabKey] || EMPTY_TAB), ...patch } }));
  }, []);

  // ── 数据加载 ──
  const loadTab = useCallback(async (tabKey: string, pageNum = 0, append = false, loadId?: number) => {
    const cc = colCountRef.current;
    const reqSize = Math.max(cc * 4, 30);
    const maxShow = cc * 4;
    const isStale = () => loadId !== undefined && loadId !== loadIdRef.current;

    // 标记此 tab 已渲染过
    setRenderedTabs(prev => { if (prev.has(tabKey)) return prev; const n = new Set(prev); n.add(tabKey); return n; });

    if (tabKey === "weekly_combined") {
      const existing = tabDataMapRef.current[tabKey];
      if (existing?.weeklyChineseItems && existing?.weeklyGlobalItems && pageNum === 0 && !append) {
        return;
      }
      updateTab(tabKey, { loading: true, error: false });
      try {
        const [cnData, glData] = await Promise.all([
          api.discoverRecommend("douban_weekly_chinese", 0, 20),
          api.discoverRecommend("douban_weekly_global", 0, 20),
        ]);
        if (isStale()) return;
        const cn = (cnData.items || []).map(normalizeItem);
        const gl = (glData.items || []).map(normalizeItem);
        updateTab(tabKey, { weeklyChineseItems: cn, weeklyGlobalItems: gl, items: [], hasMore: false, loading: false });
      } catch { if (!isStale()) updateTab(tabKey, { error: true, loading: false }); }
      return;
    }

    // 非周榜：检查是否已有数据
    if (pageNum === 0 && !append) {
      const existing = tabDataMapRef.current[tabKey];
      if (existing?.items && existing.items.length > 0) {
        return;
      }
    }

    if (pageNum === 0) { updateTab(tabKey, { loading: true, error: false }); } else setLoadingMore(true);
    try {
      const data = await api.discoverRecommend(tabKey, pageNum * reqSize, reqSize);
      if (isStale()) return;
      const normalized = (data.items || []).map(normalizeItem);
      const trimmed = normalized.slice(0, maxShow);
      if (append) {
        setTabDataMap(prev => {
          const old = prev[tabKey] || EMPTY_TAB;
          const existingIds = new Set(old.items.map((i: DoubanHotItem) => i.douban_id || i.title));
          const unique = trimmed.filter((i: DoubanHotItem) => !existingIds.has(i.douban_id || i.title));
          return { ...prev, [tabKey]: { ...old, items: [...old.items, ...unique], hasMore: normalized.length >= reqSize * 0.5, page: pageNum } };
        });
      } else {
        updateTab(tabKey, { items: trimmed, hasMore: normalized.length >= reqSize * 0.5, loading: false, page: 0 });
      }
    } catch {
      if (!isStale() && !append) updateTab(tabKey, { error: true, items: [], loading: false });
    } finally { if (!isStale()) setLoadingMore(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updateTab]);

  const loadMore = useCallback(() => {
    const cur = tabDataMapRef.current[activeTab] || EMPTY_TAB;
    const p = cur.page + 1;
    loadTab(activeTab, p, true, loadIdRef.current);
  }, [activeTab, loadTab]);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setSearching(true); setIsSearchMode(true); setSearchItems([]); closeExpand();
    try {
      const data = await api.doubanSearch(q);
      setSearchItems((data.candidates || data.items || []).map((c: any) => normalizeItem(c)));
    } catch { setSearchItems([]); } finally { setSearching(false); }
  }, [closeExpand]);

  const exitSearch = () => { setIsSearchMode(false); setSearchQuery(""); setSearchItems([]); closeExpand(); };
  const activeTabConfig = RECOMMEND_TABS.find(t => t.key === activeTab) || RECOMMEND_TABS[0];
  const curTabData = tabDataMap[activeTab] || EMPTY_TAB;
  const displayItems = isSearchMode ? searchItems
    : activeTab === "weekly_combined" ? [...(curTabData.weeklyChineseItems || []), ...(curTabData.weeklyGlobalItems || [])]
    : curTabData.items;

  // ── 首次可见或切 tab 时加载（仅未加载过的 tab 才发请求）──
  useEffect(() => {
    if (!visible) return;
    closeExpand();
    const id = ++loadIdRef.current;
    loadTab(activeTab, 0, false, id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, visible]);

  // colCount 变化时清空所有缓存重新加载
  const prevColCount = useRef(colCount);
  useEffect(() => {
    if (prevColCount.current !== colCount) {
      prevColCount.current = colCount;
      setTabDataMap({}); setRenderedTabs(new Set());
      const id = ++loadIdRef.current;
      loadTab(activeTab, 0, false, id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [colCount]);

  // ── 手动刷新 ──
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (activeTab === "weekly_combined") {
        await Promise.all([api.discoverRefresh("douban_weekly_chinese"), api.discoverRefresh("douban_weekly_global")]);
      } else {
        await api.discoverRefresh(activeTab);
      }
    } catch {}
    // 清除该 tab 的缓存数据，强制重新加载
    setTabDataMap(prev => { const n = { ...prev }; delete n[activeTab]; return n; });
    closeExpand();
    const id = ++loadIdRef.current;
    // 延迟一帧让 state 更新后再加载
    requestAnimationFrame(() => loadTab(activeTab, 0, false, id));
    setRefreshing(false);
  }, [activeTab, loadTab, closeExpand]);

  // ── 展开面板逻辑 ──
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
    setExpandedIndex(index); setExpandPos({ afterIndex: index });
    const item = displayItems[index];
    if (!item) return;
    const cacheKey = `${item.title}_${item.year}_${activeTab}`;
    pendingClickRef.current = cacheKey as any; // 用 cacheKey 做竞态标识
    const cached = getCachedDetail(cacheKey);
    if (cached) { setDetail(cached); setDetailLoading(false); return; }
    setDetail(null); setDetailLoading(true);
    try {
      const tmdbType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
      const detailSource = activeTabConfig.ratingSource || "tmdb";
      const itemId = item.douban_id || "";
      const d = await api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "", detailSource, itemId);
      if (pendingClickRef.current !== cacheKey) return; // 已被新点击覆盖
      if (d.found) setCachedDetail(cacheKey, d);
      setDetail(d);
    } catch {
      if (pendingClickRef.current === cacheKey) setDetail({ found: false });
    } finally {
      if (pendingClickRef.current === cacheKey) setDetailLoading(false);
    }
  }, [expandedIndex, displayItems, activeTab, activeTabConfig, closeExpand]);

  const handleRetry = useCallback(() => {
    if (expandedIndex === null) return;
    const retryItem = displayItems[expandedIndex];
    const cacheKey = `${retryItem.title}_${retryItem.year}_${activeTab}`;
    pendingClickRef.current = cacheKey;
    setDetail(null); setDetailLoading(true);
    const tmdbType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
    const detailSource = activeTabConfig.ratingSource || "tmdb";
    const itemId = retryItem.douban_id || "";
    api.mediaInfo(retryItem.title, retryItem.year, tmdbType as any, retryItem.subtitle || "", detailSource, itemId)
      .then(d => { if (pendingClickRef.current !== cacheKey) return; if (d.found) setCachedDetail(cacheKey, d); setDetail(d); })
      .catch(() => { if (pendingClickRef.current === cacheKey) setDetail({ found: false }); })
      .finally(() => { if (pendingClickRef.current === cacheKey) setDetailLoading(false); });
  }, [expandedIndex, displayItems, activeTab, activeTabConfig]);

  // 全局点击关闭
  useEffect(() => {
    if (expandedIndex === null) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("[data-discover-card]") || t.closest("[data-expand-panel]") ||
          t.closest("button") || t.closest("a") || t.closest("input") || t.closest("textarea")) return;
      closeExpand();
    };
    const timer = setTimeout(() => document.addEventListener("click", handler), 100);
    return () => { clearTimeout(timer); document.removeEventListener("click", handler); };
  }, [expandedIndex, closeExpand]);

  const rowEndIndex = expandPos ? getRowEndIndex(expandPos.afterIndex) : -1;

  // ── 渲染每个 tab 的内容面板（保持 DOM 不销毁）──
  const renderTabContent = (tabKey: string, isActive: boolean) => {
    const data = tabDataMap[tabKey] || EMPTY_TAB;
    const tabConfig = RECOMMEND_TABS.find(t => t.key === tabKey) || RECOMMEND_TABS[0];
    const isWeekly = tabKey === "weekly_combined";
    const tabItems = data.items;

    return (
      <div key={tabKey} style={{ display: isActive && !isSearchMode ? undefined : "none" }}>
        {data.loading && (isWeekly ? !(data.weeklyChineseItems?.length) : tabItems.length === 0) ? (
          <SkeletonGrid colCount={colCount} rows={4} />
        ) : data.error ? (
          <div className="text-center py-12">
            <p className="text-xs text-slate-600 mb-2">加载失败</p>
            <button onClick={() => { const id = ++loadIdRef.current; setTabDataMap(prev => { const n = { ...prev }; delete n[tabKey]; return n; }); loadTab(tabKey, 0, false, id); }}
              className="text-xs text-blue-400 hover:text-blue-300">重试</button>
          </div>
        ) : isWeekly ? (
          <WeeklyCombinedView
            chineseItems={data.weeklyChineseItems || []} globalItems={data.weeklyGlobalItems || []}
            expandedIndex={isActive ? expandedIndex : null} onCardClick={handleCardClick}
            detail={detail} detailLoading={detailLoading}
            onSearch={(item) => onSelectMedia({...item, _tmdb_original_title: detail?.original_title || ""} as any)}
            onCloseExpand={closeExpand} onRetry={handleRetry}
          />
        ) : tabItems.length === 0 ? (
          <p className="text-center py-12 text-xs text-slate-600">暂无数据</p>
        ) : (
          <>
            <div ref={isActive ? gridRef : undefined}
              className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
              {tabItems.map((item, index) => (
                <DiscoverCard key={`card-${tabKey}-${item.douban_id || item.title}-${index}`}
                  item={item} index={index} isActive={isActive && expandedIndex === index}
                  showRank={!!tabConfig.showRank}
                  showMediaType={tabConfig.mediaType === "mixed"}
                  ratingSource={tabConfig.ratingSource || "douban"}
                  onClick={() => handleCardClick(index)}
                  style={isActive ? { order: index <= rowEndIndex || expandedIndex === null ? index : index + 1 } : undefined} />
              ))}
              {isActive && expandedIndex !== null && expandedIndex < tabItems.length && (
                <div key="expand-panel" data-expand-panel
                  className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                  style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                  <ExpandDetail item={tabItems[expandedIndex]} detail={detail} loading={detailLoading}
                    onSearch={() => onSelectMedia({...tabItems[expandedIndex], _tmdb_original_title: detail?.original_title || ""} as any)}
                    onClose={closeExpand} onRetry={handleRetry} />
                </div>
              )}
            </div>
            {isActive && data.hasMore && (
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
    );
  };

  return (
    <div className="mt-8">
      <DiscoverHeader
        primaryTab={primaryTab} setPrimaryTab={setPrimaryTab}
        activeTab={activeTab} setActiveTab={setActiveTab}
        isSearchMode={isSearchMode} searchQuery={searchQuery} setSearchQuery={setSearchQuery}
        onSearch={doSearch} onExitSearch={exitSearch}
        onRefresh={handleRefresh} refreshing={refreshing}
        scrollToDiscover={scrollToDiscover} stickyHeaderRef={stickyHeaderRef}
      />

      <div style={{ minHeight: "80vh" }}>
        {/* 搜索模式 */}
        {isSearchMode && (
          <div>
            {searching ? (
              <SkeletonGrid colCount={colCount} rows={4} />
            ) : searchItems.length === 0 ? (
              <p className="text-center py-12 text-xs text-slate-600">未找到匹配影片</p>
            ) : (
              <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-5">
                {searchItems.map((item, index) => (
                  <DiscoverCard key={`search-${item.douban_id || item.title}-${index}`}
                    item={item} index={index} isActive={expandedIndex === index}
                    showRank={false} showMediaType ratingSource="douban" onClick={() => handleCardClick(index)} />
                ))}
                {expandedIndex !== null && expandedIndex < searchItems.length && (
                  <div key="expand-panel" data-expand-panel
                    className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                    style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                    <ExpandDetail item={searchItems[expandedIndex]} detail={detail} loading={detailLoading}
                      onSearch={() => onSelectMedia({...searchItems[expandedIndex], _tmdb_original_title: detail?.original_title || ""} as any)}
                      onClose={closeExpand} onRetry={handleRetry} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 所有已加载的 tab 内容（保持 DOM，用 display:none 隐藏非当前 tab）*/}
        {Array.from(renderedTabs).map(tabKey => renderTabContent(tabKey, tabKey === activeTab))}
      </div>
    </div>
  );
}
