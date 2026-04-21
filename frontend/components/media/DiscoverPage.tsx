// 发现页：多榜单推荐 + 探索筛选 + 搜索（主组件，状态管理+布局编排）
// 核心优化：已加载的 tab 内容保持在 DOM 中（display:none），切 tab 时图片不重新加载
"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import type { DoubanHotItem } from "@/types";
import { api } from "@/lib/api";
import { normalizeItem, getCachedDetail, setCachedDetail, deleteCachedDetail, RECOMMEND_TABS, EXPLORE_TABS } from "./discoverUtils";
import type { MediaDetail, PrimaryTab } from "./discoverUtils";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import DiscoverHeader from "./DiscoverHeader";
import ExplorePage from "./ExplorePage";
import RecommendTabContent from "./RecommendTabContent";
import SubscribeInline from "./SubscribeInline";
import { useSubscriptions } from "@/hooks/useSubscriptions";
import SearchModal from "@/components/search/SearchModal";
import SubscribeConfigModal from "./SubscribeConfigModal";
import type { SubscribeConfig } from "./SubscribeConfigModal";

interface DiscoverPageProps {
  onSelectMedia: (item: DoubanHotItem) => void;
  onNavigateToLocal?: (folderPath: string) => void;
  visible?: boolean;
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
  defaultSavePath?: string;
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

export default function DiscoverPage({ onSelectMedia, onNavigateToLocal, visible = true, scrollContainerRef, defaultSavePath = "" }: DiscoverPageProps) {
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

  // ── 订阅配置弹窗 ──
  const [subConfigOpen, setSubConfigOpen] = useState(false);
  const [subConfigItem, setSubConfigItem] = useState<DoubanHotItem | null>(null);
  const [subConfigDetail, setSubConfigDetail] = useState<MediaDetail | null>(null);

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

  // ── 订阅状态 ──
  const { isSubscribed: _isSubscribed, subscribe: doSubscribe, subscriptions, refresh: refreshSubs } = useSubscriptions();
  const [subscribing, setSubscribing] = useState(false);
  const [justSubscribed, setJustSubscribed] = useState<Set<string>>(new Set());

  // 包装 isSubscribed：加入"刚订阅"的临时标记
  const isSubscribed = useCallback((tmdbId?: number, title?: string, year?: string, season?: number): boolean => {
    if (title && justSubscribed.has(`${title}|${year || ""}`)) return true;
    return _isSubscribed(tmdbId, title, year, season);
  }, [_isSubscribed, justSubscribed]);

  const handleSubscribe = useCallback(async (item: DoubanHotItem, d: MediaDetail | null) => {
    // 打开配置弹窗而非直接订阅
    setSubConfigItem(item);
    setSubConfigDetail(d);
    setSubConfigOpen(true);
  }, []);

  const handleSubscribeConfirm = useCallback(async (config: SubscribeConfig) => {
    if (!subConfigItem) return;
    setSubscribing(true);
    setSubConfigOpen(false);
    const item = subConfigItem;
    const d = subConfigDetail;
    try {
      const mediaType = activeTabConfig.mediaType === "tv" ? "tv" : "movie";
      const result = await doSubscribe({
        title: item.title,
        year: item.year || d?.year || "",
        type: mediaType,
        tmdb_id: d?.tmdb_id || d?.external_ids?.tmdb_id || undefined,
        douban_id: item.douban_id || undefined,
        poster: item.cover_url || d?.poster_url || "",
        quality: config.quality,
        include: config.include,
        exclude: config.exclude,
        mode: config.mode,
        best_version: config.best_version,
        save_path: config.save_path,
        search_keyword: config.search_keyword,
        sources: config.sources,
      });
      if (result.status === "ok") {
        setJustSubscribed(prev => new Set(prev).add(`${item.title}|${item.year || d?.year || ""}`));
      }
    } catch (e) {
      console.error("[Subscribe] 异常:", e);
    } finally {
      setSubscribing(false);
      setSubConfigItem(null);
      setSubConfigDetail(null);
    }
  }, [doSubscribe, activeTabConfig, subConfigItem, subConfigDetail]);

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
  }, [expandedIndex, displayItems, activeTab, activeTabConfig, closeExpand, scrollToDiscover]);

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

  // 切换数据源刷新（清缓存 + 用指定源重新请求）
  const handleRefreshWithSource = useCallback((source: string) => {
    if (expandedIndex === null) return;
    const item = displayItems[expandedIndex];
    if (!item) return;
    // 清除旧缓存（所有源的缓存都清）
    for (const suffix of ["", "_douban", "_tmdb", "_bangumi"]) {
      deleteCachedDetail(`${item.title}_${item.year}_${activeTab}${suffix}`);
    }
    // 也清除默认 key
    deleteCachedDetail(`${item.title}_${item.year}_${activeTab}`);
    const cacheKey = `${item.title}_${item.year}_${activeTab}`;
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

  return (
    <div className="mt-8" style={{ minHeight: "100vh" }}>
      <DiscoverHeader
        primaryTab={primaryTab} setPrimaryTab={(tab) => { setPrimaryTab(tab); closeExpand(); setTimeout(() => scrollToDiscover(true), 50); }}
        activeTab={activeTab} setActiveTab={setActiveTab}
        exploreTab={exploreTab} setExploreTab={setExploreTab}
        isSearchMode={isSearchMode} searchQuery={searchQuery} setSearchQuery={setSearchQuery}
        onSearch={doSearch} onExitSearch={exitSearch}
        onRefresh={handleRefresh} refreshing={refreshing}
        scrollToDiscover={scrollToDiscover} stickyHeaderRef={stickyHeaderRef}
        subscribeView={subscribeView} onSetSubscribeView={setSubscribeView}
        subscribeFilter={subscribeFilter} onSetSubscribeFilter={setSubscribeFilter}
        subscribeFilterTabs={[
          { key: "all", label: `全部 (${subscriptions.length})` },
          { key: "active", label: "活跃" },
          { key: "paused", label: "已暂停" },
          { key: "completed", label: "已完成" },
        ]}
        onExploreRefresh={() => setExploreRefreshTrigger(n => n + 1)}
        exploreRefreshing={exploreRefreshing}
      />

      <div style={{ minHeight: "100vh" }}>
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
                    showRank={false} showMediaType ratingSource="douban" onClick={() => handleCardClick(index)}
                    style={{ order: index <= rowEndIndex || expandedIndex === null ? index : index + 1 }}
                    isSubscribed={justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)} />
                ))}
                {expandedIndex !== null && expandedIndex < searchItems.length && (
                  <div key="expand-panel" data-expand-panel
                    className="col-span-full bg-[#141414] border border-white/[0.06] rounded-xl p-5 animate-in fade-in duration-200"
                    style={{ order: rowEndIndex >= 0 ? rowEndIndex + 1 : 9999 }}>
                    <ExpandDetail item={searchItems[expandedIndex]} detail={detail} loading={detailLoading}
                      onSearch={() => openSearchModal(searchItems[expandedIndex], detail)}
                      onClose={closeExpand} onRetry={handleRetry}
                      defaultSource="douban"
                      onRefreshWithSource={handleRefreshWithSource}
                      onNavigateToLocal={onNavigateToLocal}
                      onSubscribe={() => handleSubscribe(searchItems[expandedIndex], detail)}
                      isSubscribed={isSubscribed(undefined, searchItems[expandedIndex]?.title, searchItems[expandedIndex]?.year)} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 所有已加载的推荐 tab 内容（保持 DOM，用 display:none 隐藏非当前 tab）*/}
        {primaryTab === "recommend" && Array.from(renderedTabs).map(tabKey => (
          <RecommendTabContent key={tabKey} tabKey={tabKey} isActive={tabKey === activeTab}
            isSearchMode={isSearchMode} data={tabDataMap[tabKey] || { items: [], loading: false, error: false, hasMore: true, page: 0 }}
            colCount={colCount} expandedIndex={expandedIndex} detail={detail} detailLoading={detailLoading}
            loadingMore={loadingMore} rowEndIndex={rowEndIndex} gridRef={gridRef}
            onCardClick={handleCardClick} onSelectMedia={(item) => openSearchModal(item, detail)} onCloseExpand={closeExpand}
            onRetry={handleRetry} onRefreshWithSource={handleRefreshWithSource}
            onLoadMore={loadMore} onRetryTab={handleRetryTab}
            onNavigateToLocal={onNavigateToLocal}
            onSubscribe={handleSubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)} />
        ))}

        {/* 探索页 */}
        {primaryTab === "explore" && !isSearchMode && (
          <ExplorePage onSelectMedia={(item) => openSearchModal(item, detail)} activeTab={exploreTab} setActiveTab={setExploreTab}
            colCount={colCount} onNavigateToLocal={onNavigateToLocal}
            onSubscribe={handleSubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)}
            refreshTrigger={exploreRefreshTrigger} onRefreshingChange={setExploreRefreshing} />
        )}

        {/* 订阅页 */}
        {primaryTab === "subscribe" && !isSearchMode && (
          <SubscribeInline subscriptions={subscriptions} onRefresh={refreshSubs}
            onOpenSearch={(item) => openSearchModal({ title: item.title, year: item.year || "", rating: 0, cover_url: item.poster || "", subtitle: "", episode: "", douban_id: item.douban_id || "", media_type: item.type === "tv" ? "tv" : "movie" } as DoubanHotItem, null)}
            view={subscribeView} filter={subscribeFilter} />
        )}
      </div>

      {/* 搜索资源弹窗 */}
      {searchModalOpen && searchModalItem && (
        <SearchModal
          open={searchModalOpen}
          query={searchModalItem.title}
          onClose={() => { setSearchModalOpen(false); setSearchModalItem(null); setSearchModalDetail(null); }}
          defaultSavePath={defaultSavePath}
          cnName={searchModalItem.title}
          enName={searchModalDetail?.english_title || searchModalItem.clean_name_en || (searchModalItem as any)._tmdb_original_title || searchModalDetail?.original_title || searchModalItem.subtitle || ""}
          originalName={searchModalDetail?.original_title || ""}
          mediaType={searchModalItem.media_type || activeTabConfig.mediaType || "movie"}
        />
      )}

      {/* 订阅配置弹窗 */}
      <SubscribeConfigModal
        open={subConfigOpen}
        onClose={() => { setSubConfigOpen(false); setSubConfigItem(null); setSubConfigDetail(null); }}
        onConfirm={handleSubscribeConfirm}
        title={subConfigItem?.title || ""}
        mediaType={activeTabConfig.mediaType === "tv" ? "tv" : "movie"}
      />
    </div>
  );
}
