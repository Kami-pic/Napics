// 发现页状态管理 hook：Tab 数据管理 + 搜索 + 展开面板 + 响应式列数 + 刷新
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { normalizeItem, getCachedDetail, setCachedDetail, deleteCachedDetail, RECOMMEND_TABS, EXPLORE_TABS } from "./discoverUtils";
import type { MediaDetail, PrimaryTab } from "./discoverUtils";

// 每个 tab 的独立状态
export interface TabState {
  items: DoubanHotItem[];
  loading: boolean;
  error: boolean;
  hasMore: boolean;
  page: number;
  // 周榜专用
  weeklyChineseItems?: DoubanHotItem[];
  weeklyGlobalItems?: DoubanHotItem[];
}

export const EMPTY_TAB: TabState = { items: [], loading: false, error: false, hasMore: true, page: 0 };

export interface UseDiscoverStateParams {
  visible: boolean;
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
}

export function useDiscoverState({ visible, scrollContainerRef }: UseDiscoverStateParams) {
  const [primaryTab, setPrimaryTab] = useState<PrimaryTab>("recommend");
  const [activeTab, setActiveTab] = useState(RECOMMEND_TABS[0].key);
  const [exploreTab, setExploreTab] = useState(EXPLORE_TABS[0].key);
  // 探索刷新
  const [exploreRefreshTrigger, setExploreRefreshTrigger] = useState(0);
  const [exploreRefreshing, setExploreRefreshing] = useState(false);
  const [subscribeView, setSubscribeView] = useState("list");
  const [subscribeFilter, setSubscribeFilter] = useState("all");
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

  // ── 搜索资源弹窗（SearchModal）──
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [searchModalItem, setSearchModalItem] = useState<DoubanHotItem | null>(null);
  const [searchModalDetail, setSearchModalDetail] = useState<MediaDetail | null>(null);

  const openSearchModal = useCallback((item: DoubanHotItem, d: MediaDetail | null) => {
    setSearchModalItem(item);
    setSearchModalDetail(d);
    setSearchModalOpen(true);
  }, []);

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

  const scrollToDiscover = useCallback((instant?: boolean) => {
    if (!stickyHeaderRef.current || !scrollContainerRef?.current) return;
    const headerTop = stickyHeaderRef.current.offsetTop;
    scrollContainerRef.current.scrollTo({ top: headerTop, behavior: instant ? "instant" as ScrollBehavior : "smooth" });
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
      const cc = colCountRef.current;
      const trimmed = normalized.slice(0, Math.floor(Math.min(normalized.length, maxShow) / cc) * cc);
      if (append) {
        setTabDataMap(prev => {
          const old = prev[tabKey] || EMPTY_TAB;
          const existingIds = new Set(old.items.map((i: DoubanHotItem) => i.douban_id || i.title));
          const unique = trimmed.filter((i: DoubanHotItem) => !existingIds.has(i.douban_id || i.title));
          const merged = [...old.items, ...unique];
          // 截断到整行
          const rowAligned = merged.slice(0, Math.floor(merged.length / cc) * cc);
          const more = unique.length > 0 && normalized.length >= reqSize * 0.5;
          return { ...prev, [tabKey]: { ...old, items: rowAligned, hasMore: more, page: pageNum } };
        });
      } else {
        const more = normalized.length >= reqSize * 0.5;
        updateTab(tabKey, { items: trimmed, hasMore: more, loading: false, page: 0 });
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
    scrollToDiscover();
    setExpandedIndex(index); setExpandPos({ afterIndex: index });
    const item = displayItems[index];
    if (!item) return;
    const detailSource = activeTabConfig.ratingSource || "tmdb";
    const cacheKey = `${item.title}_${item.year}_${detailSource}`;
    pendingClickRef.current = cacheKey as any;
    const cached = getCachedDetail(cacheKey);
    if (cached) { setDetail(cached); setDetailLoading(false); return; }
    setDetail(null); setDetailLoading(true);
    try {
      const tmdbType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
      const itemId = item.douban_id || "";
      const d = await api.mediaInfo(item.title, item.year, tmdbType, item.subtitle || "", detailSource, itemId);
      if (pendingClickRef.current !== cacheKey) return;
      if (d.found) setCachedDetail(cacheKey, d);
      setDetail(d);
    } catch {
      if (pendingClickRef.current === cacheKey) setDetail({ found: false });
    } finally {
      if (pendingClickRef.current === cacheKey) setDetailLoading(false);
    }
  }, [expandedIndex, displayItems, activeTab, activeTabConfig, closeExpand, scrollToDiscover]);

  const handleRetry = useCallback(() => {
    if (expandedIndex === null) return;
    const retryItem = displayItems[expandedIndex];
    const detailSource = activeTabConfig.ratingSource || "tmdb";
    const cacheKey = `${retryItem.title}_${retryItem.year}_${detailSource}`;
    pendingClickRef.current = cacheKey;
    setDetail(null); setDetailLoading(true);
    const tmdbType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
    const itemId = retryItem.douban_id || "";
    api.mediaInfo(retryItem.title, retryItem.year, tmdbType as any, retryItem.subtitle || "", detailSource, itemId)
      .then(d => { if (pendingClickRef.current !== cacheKey) return; if (d.found) setCachedDetail(cacheKey, d); setDetail(d); })
      .catch(() => { if (pendingClickRef.current === cacheKey) setDetail({ found: false }); })
      .finally(() => { if (pendingClickRef.current === cacheKey) setDetailLoading(false); });
  }, [expandedIndex, displayItems, activeTab, activeTabConfig]);

  // 切换数据源刷新（清缓存 + 用指定源重新请求）
  const handleRefreshWithSource = useCallback((source: string) => {
    if (expandedIndex === null) return;
    const item = displayItems[expandedIndex];
    if (!item) return;
    // 清除所有源的缓存
    for (const src of ["douban", "tmdb", "bangumi"]) {
      deleteCachedDetail(`${item.title}_${item.year}_${src}`);
    }
    const cacheKey = `${item.title}_${item.year}_${source}`;
    pendingClickRef.current = cacheKey;
    setDetail(null); setDetailLoading(true);
    const tmdbType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
    const itemId = item.douban_id || "";
    api.mediaInfo(item.title, item.year, tmdbType as any, item.subtitle || "", source, itemId)
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

  // 重试 tab 加载
  const handleRetryTab = useCallback((tabKey: string) => {
    const id = ++loadIdRef.current;
    setTabDataMap(prev => { const n = { ...prev }; delete n[tabKey]; return n; });
    loadTab(tabKey, 0, false, id);
  }, [loadTab]);

  return {
    // Tab 状态
    primaryTab, setPrimaryTab,
    activeTab, setActiveTab,
    exploreTab, setExploreTab,
    exploreRefreshTrigger, setExploreRefreshTrigger,
    exploreRefreshing, setExploreRefreshing,
    subscribeView, setSubscribeView,
    subscribeFilter, setSubscribeFilter,
    tabDataMap, renderedTabs,
    // 搜索
    searchQuery, setSearchQuery, searchItems, searching, isSearchMode,
    doSearch, exitSearch,
    // 展开面板
    expandedIndex, detail, detailLoading,
    closeExpand, handleCardClick, handleRetry, handleRefreshWithSource,
    // 刷新
    refreshing, handleRefresh,
    loadingMore, loadMore,
    // 响应式列数
    colCount,
    // Refs
    gridRef, stickyHeaderRef,
    // 派生
    activeTabConfig, curTabData, displayItems, rowEndIndex,
    // 搜索资源弹窗
    searchModalOpen, setSearchModalOpen, searchModalItem, setSearchModalItem, searchModalDetail, setSearchModalDetail,
    openSearchModal,
    // 其他
    scrollToDiscover, handleRetryTab,
  };
}
