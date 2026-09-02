// 发现页：多榜单推荐 + 探索筛选 + 搜索（瘦壳组件，编排两个 hook + 渲染布局）
// 核心优化：已加载的 tab 内容保持在 DOM 中（display:none），切 tab 时图片不重新加载
"use client";
import type { DoubanHotItem } from "@/types";
import DiscoverCard from "./DiscoverCard";
import SkeletonGrid from "./SkeletonGrid";
import ExpandDetail from "./ExpandDetail";
import DiscoverHeader from "./DiscoverHeader";
import ExplorePage from "./ExplorePage";
import RecommendTabContent from "./RecommendTabContent";
import SubscribeInline from "./SubscribeInline";
import SearchModal from "@/components/search/SearchModal";
import SubscribeConfigModal from "./SubscribeConfigModal";
import { useDiscoverState } from "./useDiscoverState";
import { useDiscoverSubscribe } from "./useDiscoverSubscribe";

interface DiscoverPageProps {
  onSelectMedia: (item: DoubanHotItem) => void;
  onNavigateToLocal?: (folderPath: string) => void;
  visible?: boolean;
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
  defaultSavePath?: string;
}

export default function DiscoverPage({ onSelectMedia, onNavigateToLocal, visible = true, scrollContainerRef, defaultSavePath = "" }: DiscoverPageProps) {
  const state = useDiscoverState({ visible, scrollContainerRef });
  const sub = useDiscoverSubscribe({ activeTabConfig: state.activeTabConfig });

  const {
    primaryTab, setPrimaryTab, activeTab, setActiveTab,
    exploreTab, setExploreTab, exploreRefreshTrigger, setExploreRefreshTrigger,
    exploreRefreshing, setExploreRefreshing,
    subscribeView, setSubscribeView, subscribeFilter, setSubscribeFilter,
    tabDataMap, renderedTabs,
    searchQuery, setSearchQuery, searchItems, searching, isSearchMode,
    doSearch, exitSearch,
    expandedIndex, detail, detailLoading,
    closeExpand, handleCardClick, handleRetry, handleRefreshWithSource,
    refreshing, handleRefresh, loadingMore, loadMore,
    colCount, gridRef, stickyHeaderRef,
    activeTabConfig, displayItems, rowEndIndex,
    searchModalOpen, setSearchModalOpen, searchModalItem, setSearchModalItem, searchModalDetail, setSearchModalDetail,
    openSearchModal, scrollToDiscover, handleRetryTab,
  } = state;

  const {
    subscriptions, refreshSubs, justSubscribed, setJustSubscribed, _isSubscribed,
    isSubscribed, handleSubscribe, handleUnsubscribe, handleSubscribeConfirm,
    subConfigOpen, setSubConfigOpen, subConfigItem, setSubConfigItem, subConfigDetail, setSubConfigDetail,
  } = sub;

  /**
   * 用一个纯关键词打开搜索升级弹窗。
   *
   * 豆瓣搜不到不等于片源搜不到 —— 冷门片、纪录片、剧集别名在豆瓣常常匹配不上，
   * 但同一个词去搜种子往往有结果。所以豆瓣搜索这一屏必须留一条通往资源搜索的路，
   * 而不是让用户自己换个地方重新输一遍。
   */
  const openResourceSearch = (keyword: string) => {
    const q = keyword.trim();
    if (!q) return;
    openSearchModal({
      title: q, year: "", rating: 0, cover_url: "", subtitle: "",
      episode: "", douban_id: "",
      // 没有豆瓣条目，清洗名就用原词，避免搜索侧拿到空的中文名
      clean_name_cn: q,
    } as DoubanHotItem, null);
  };

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
              /* 豆瓣搜不到不代表片源搜不到：冷门片、纪录片、剧集别名在豆瓣常常匹配不上，
                 但用同一个词去搜种子往往有结果。所以空态要给一条通往搜索升级的路，
                 而不是让用户自己去别处重新输一遍。 */
              <div className="py-12 flex flex-col items-center gap-2">
                <p className="text-xs text-slate-600">未找到匹配影片</p>
                <button onClick={() => openResourceSearch(searchQuery)}
                  className="text-xs text-blue-400 hover:text-blue-300 underline">
                  直接用「{searchQuery}」搜片源
                </button>
              </div>
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
                      onUnsubscribe={() => handleUnsubscribe(searchItems[expandedIndex])}
                      isSubscribed={isSubscribed(undefined, searchItems[expandedIndex]?.title, searchItems[expandedIndex]?.year)} />
                  </div>
                )}
              </div>
            )}
            {/* 有结果时也给这条路：列表里可能都不是用户要的那一部 */}
            {!searching && searchItems.length > 0 && (
              <p className="pt-5 text-center text-xs text-slate-600">
                都不是想找的？
                <button onClick={() => openResourceSearch(searchQuery)}
                  className="ml-1 text-blue-400 hover:text-blue-300 underline">
                  直接用「{searchQuery}」搜片源
                </button>
              </p>
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
            onUnsubscribe={handleUnsubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)} />
        ))}

        {/* 探索页 */}
        {primaryTab === "explore" && !isSearchMode && (
          <ExplorePage onSelectMedia={(item) => openSearchModal(item, detail)} activeTab={exploreTab} setActiveTab={setExploreTab}
            colCount={colCount} onNavigateToLocal={onNavigateToLocal}
            onSubscribe={handleSubscribe}
            onUnsubscribe={handleUnsubscribe}
            checkSubscribed={(item) => justSubscribed.has(`${item.title}|${item.year || ""}`) || _isSubscribed(undefined, item.title, item.year)}
            refreshTrigger={exploreRefreshTrigger} onRefreshingChange={setExploreRefreshing} />
        )}

        {/* 订阅页 */}
        {primaryTab === "subscribe" && !isSearchMode && (
          <SubscribeInline subscriptions={subscriptions} onRefresh={() => { refreshSubs(); setJustSubscribed(new Set()); }}
            onOpenSearch={(item) => {
              // 从订阅数据构造搜索弹窗参数，传递清洗名
              const aliases = (item as any).aliases || {};
              const cnName = (aliases.cn?.[0]) || item.title;
              const enName = (aliases.en?.[0]) || "";
              const originalName = (aliases.original?.[0]) || "";
              openSearchModal({
                title: item.title, year: item.year || "", rating: 0,
                cover_url: item.poster || "", subtitle: enName,
                episode: "", douban_id: item.douban_id || "",
                media_type: item.type === "tv" ? "tv" : "movie",
                clean_name_en: enName,
                clean_name_original: originalName,
              } as DoubanHotItem, null);
            }}
            onOpenConfig={(item) => {
              // 打开配置弹窗编辑现有订阅（复用 SubscribeConfigModal）
              setSubConfigItem({
                title: item.title, year: item.year || "", rating: 0,
                cover_url: item.poster || "", subtitle: "",
                episode: "", douban_id: item.douban_id || "",
                media_type: item.type === "tv" ? "tv" : "movie",
              } as DoubanHotItem);
              setSubConfigDetail(null);
              setSubConfigOpen(true);
            }}
            view={subscribeView} filter={subscribeFilter} />
        )}
      </div>

      {/* 搜索资源弹窗 */}
      {searchModalOpen && searchModalItem && (
        <SearchModal
          open={searchModalOpen}
          query={searchModalItem.clean_name_cn || searchModalItem.title}
          onClose={() => { setSearchModalOpen(false); setSearchModalItem(null); setSearchModalDetail(null); }}
          defaultSavePath={defaultSavePath}
          cnName={searchModalItem.clean_name_cn || searchModalItem.title}
          enName={searchModalDetail?.english_title || searchModalItem.clean_name_en || (searchModalItem as any)._tmdb_original_title || searchModalDetail?.original_title || searchModalItem.subtitle || ""}
          originalName={searchModalItem.clean_name_original || searchModalDetail?.original_title || ""}
          mediaType={searchModalItem.media_type || activeTabConfig.mediaType || "movie"}
          year={searchModalItem.year || ""}
          seasonNumber={searchModalItem.episode ? parseInt(searchModalItem.episode) || 0 : 0}
        />
      )}

      {/* 订阅配置弹窗 */}
      <SubscribeConfigModal
        open={subConfigOpen}
        onClose={() => { setSubConfigOpen(false); setSubConfigItem(null); setSubConfigDetail(null); }}
        onConfirm={handleSubscribeConfirm}
        title={subConfigItem?.title || ""}
        mediaType={subConfigItem?.media_type || activeTabConfig.mediaType === "tv" ? "tv" : "movie"}
        defaultSavePath={defaultSavePath}
      />
    </div>
  );
}
